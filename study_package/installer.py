from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import shutil
import tarfile
import uuid

import chromadb
import duckdb

from db_rag.local_knowledge import LocalPublicationKnowledge
from db_rag.study_design import LocalStudyDesign

from .manifest import (
    StudyPackageManifest,
    load_installed_manifest,
    resolve_package_path,
)
from .registry import StudyRegistryFile, load_registry, package_root, write_registry


@dataclass(frozen=True)
class StagedStudy:
    archive_path: Path
    extracted_root: Path
    archive_sha256: str
    manifest: StudyPackageManifest
    stage_root: Path


@dataclass(frozen=True)
class InstalledStudy:
    study_id: str
    package_version: str
    package_root: Path
    archive_sha256: str
    manifest: StudyPackageManifest


def _copy_archive(source: Path, destination: Path) -> str:
    digest = sha256()
    with source.open("rb") as source_file, destination.open("xb") as destination_file:
        while chunk := source_file.read(1024 * 1024):
            digest.update(chunk)
            destination_file.write(chunk)
    return digest.hexdigest()


def _validate_member(member: tarfile.TarInfo, seen: set[str]) -> None:
    name = member.name
    parts = name.split("/")
    if (
        not name
        or name.startswith("/")
        or "\\" in name
        or any(part in {"", ".", ".."} for part in parts)
        or name in seen
        or member.issym()
        or member.islnk()
        or not (member.isfile() or member.isdir())
    ):
        raise ValueError(f"unsafe archive member: {name!r}")
    seen.add(name)


def _extract_archive(archive_path: Path, extracted_root: Path) -> None:
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            members = archive.getmembers()
            seen: set[str] = set()
            for member in members:
                _validate_member(member, seen)
            archive.extractall(extracted_root, members=members, filter="data")
    except (OSError, tarfile.TarError) as error:
        raise ValueError(f"Cannot read study archive: {archive_path}") from error


def _validate_duckdb(path: Path) -> None:
    try:
        with duckdb.connect(str(path), read_only=True) as connection:
            tables = connection.execute("SHOW TABLES").fetchall()
    except duckdb.Error as error:
        raise ValueError(f"database.duckdb is not a readable DuckDB database: {path}") from error
    if not tables:
        raise ValueError("database.duckdb contains no tables")


def _validate_catalog(path: Path) -> None:
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"database.catalog is not valid JSON: {path}") from error
    if not isinstance(catalog, dict) or catalog.get("catalog_version") != 1:
        raise ValueError("database.catalog must use catalog_version 1")
    if not isinstance(catalog.get("tables"), list) or not catalog["tables"]:
        raise ValueError("database.catalog contains no tables")
    if not isinstance(catalog.get("columns"), list) or not catalog["columns"]:
        raise ValueError("database.catalog contains no columns")


def _validate_index(path: Path) -> None:
    try:
        client = chromadb.PersistentClient(path=str(path))
        for collection_name in ("table_summaries", "column_chunks"):
            collection = client.get_collection(collection_name)
            if collection.count() < 1:
                raise ValueError(f"database.index collection is empty: {collection_name}")
    except ValueError:
        raise
    except Exception as error:
        raise ValueError(f"database.index is not a readable Chroma store: {path}") from error


def _validate_knowledge(path: Path) -> None:
    try:
        LocalPublicationKnowledge.from_root(path)
    except ValueError as error:
        raise ValueError(f"knowledge.root is not valid publication knowledge: {path}") from error


def _validate_study_design(
    path: Path,
    manifest: StudyPackageManifest,
) -> None:
    try:
        design = LocalStudyDesign.from_path(path)
    except ValueError as error:
        raise ValueError(f"study_design.document is not a valid study design: {path}") from error
    if (
        design.study_id != manifest.study_id
        or design.label != manifest.label
    ):
        raise ValueError(
            "study_design.document identity does not match the study package manifest"
        )


def validate_staged_package(
    package_root: Path,
    manifest: StudyPackageManifest,
) -> None:
    declared = manifest.declared_paths()
    resolved: dict[str, Path] = {}
    for field, (relative, kind) in declared.items():
        path = resolve_package_path(package_root, relative, field)
        if not path.exists() or path.is_symlink():
            raise ValueError(f"{field} is missing from study package")
        if kind == "file" and not path.is_file():
            raise ValueError(f"{field} must be a file")
        if kind == "directory" and not path.is_dir():
            raise ValueError(f"{field} must be a directory")
        resolved[field] = path

    _validate_duckdb(resolved["database.duckdb"])
    _validate_catalog(resolved["database.catalog"])
    _validate_index(resolved["database.index"])
    if manifest.knowledge is not None:
        _validate_knowledge(resolved["knowledge.root"])
    if manifest.study_design is not None:
        _validate_study_design(resolved["study_design.document"], manifest)


def stage_study_archive(archive: Path, studies_root: Path) -> StagedStudy:
    source = Path(archive)
    if (
        source.is_symlink()
        or not source.is_file()
        or source.suffixes[-2:] != [".tar", ".gz"]
    ):
        raise ValueError(f"Study archive must be a local .tar.gz file: {source}")

    staging_root = Path(studies_root) / ".staging"
    staging_root.mkdir(parents=True, exist_ok=True)
    stage_root = staging_root / uuid.uuid4().hex
    stage_root.mkdir()
    copied_archive = stage_root / "study.tar.gz"
    extracted_root = stage_root / "package"
    extracted_root.mkdir()
    try:
        archive_sha256 = _copy_archive(source, copied_archive)
        _extract_archive(copied_archive, extracted_root)
        manifest = load_installed_manifest(extracted_root)
        validate_staged_package(extracted_root, manifest)
        return StagedStudy(
            archive_path=copied_archive,
            extracted_root=extracted_root,
            archive_sha256=archive_sha256,
            manifest=manifest,
            stage_root=stage_root,
        )
    except Exception:
        shutil.rmtree(stage_root, ignore_errors=True)
        raise


def _installed_record_path(package_root: Path) -> Path:
    return Path(package_root) / ".installed.json"


def _write_installed_record(staged: StagedStudy) -> None:
    _installed_record_path(staged.extracted_root).write_text(
        json.dumps(
            {
                "archive_sha256": staged.archive_sha256,
                "study_id": staged.manifest.study_id,
                "package_version": staged.manifest.package_version,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def load_installed_study(package_root_path: Path) -> InstalledStudy:
    package_root_path = Path(package_root_path)
    manifest = load_installed_manifest(package_root_path)
    validate_staged_package(package_root_path, manifest)
    try:
        record = json.loads(_installed_record_path(package_root_path).read_text(encoding="utf-8"))
        archive_sha256 = str(record["archive_sha256"])
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid installed study record: {package_root_path}") from error
    if (
        record.get("study_id") != manifest.study_id
        or record.get("package_version") != manifest.package_version
        or len(archive_sha256) != 64
    ):
        raise ValueError(f"Installed study record does not match manifest: {package_root_path}")
    return InstalledStudy(
        study_id=manifest.study_id,
        package_version=manifest.package_version,
        package_root=package_root_path,
        archive_sha256=archive_sha256,
        manifest=manifest,
    )


def _cleanup_staged(staged: StagedStudy) -> None:
    shutil.rmtree(staged.stage_root, ignore_errors=True)


def install_study_archives(
    archives: Sequence[Path],
    studies_root: Path,
) -> tuple[InstalledStudy, ...]:
    if not archives:
        raise ValueError("At least one study archive is required")

    staged_studies: list[StagedStudy] = []
    try:
        for archive in archives:
            staged_studies.append(stage_study_archive(archive, studies_root))

        seen_study_ids: set[str] = set()
        for staged in staged_studies:
            study_id = staged.manifest.study_id
            if study_id in seen_study_ids:
                raise ValueError(f"Batch contains duplicate study_id: {study_id}")
            seen_study_ids.add(study_id)

        current_registry = load_registry(studies_root)
        active = dict(current_registry.active)
        installed: list[InstalledStudy | None] = [None] * len(staged_studies)
        promotions: list[tuple[int, StagedStudy, Path]] = []
        for index, staged in enumerate(staged_studies):
            manifest = staged.manifest
            destination = package_root(
                studies_root,
                manifest.study_id,
                manifest.package_version,
            )
            if destination.exists():
                existing = load_installed_study(destination)
                if existing.archive_sha256 != staged.archive_sha256:
                    raise ValueError(
                        "Published study package versions are immutable: "
                        f"{manifest.study_id}@{manifest.package_version}"
                    )
                installed[index] = existing
            else:
                promotions.append((index, staged, destination))
            active[manifest.study_id] = manifest.package_version

        for _index, staged, _destination in promotions:
            _write_installed_record(staged)
        promoted_destinations: list[Path] = []
        try:
            for index, staged, destination in promotions:
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.exists():
                    raise ValueError(f"Study package destination already exists: {destination}")
                promoted_destinations.append(destination)
                shutil.move(str(staged.extracted_root), str(destination))
                installed[index] = InstalledStudy(
                    study_id=staged.manifest.study_id,
                    package_version=staged.manifest.package_version,
                    package_root=destination,
                    archive_sha256=staged.archive_sha256,
                    manifest=staged.manifest,
                )

            write_registry(
                studies_root,
                StudyRegistryFile(active=active),
            )
        except Exception:
            for destination in reversed(promoted_destinations):
                shutil.rmtree(destination, ignore_errors=True)
            raise
        return tuple(item for item in installed if item is not None)
    finally:
        for staged in staged_studies:
            _cleanup_staged(staged)


def activate_study_version(
    study_id: str,
    package_version: str,
    studies_root: Path,
) -> InstalledStudy:
    installed = load_installed_study(package_root(studies_root, study_id, package_version))
    registry = load_registry(studies_root)
    active = dict(registry.active)
    active[study_id] = package_version
    write_registry(studies_root, StudyRegistryFile(active=active))
    return installed
