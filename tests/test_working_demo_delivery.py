from pathlib import Path

from scripts.verify_working_demo_delivery import (
    collect_delivery_violations,
    ignored_required_paths,
    tracked_paths,
    unignored_local_paths,
)


ROOT = Path(__file__).parents[1]


def test_working_demo_delivery_contract_is_consistent() -> None:
    paths = tracked_paths(ROOT)
    assert collect_delivery_violations(ROOT, paths) == []
    assert ignored_required_paths(ROOT) == []
    assert unignored_local_paths(ROOT) == []
