import { describe, expect, it } from "vitest";
import {
  initialSelectedKeys,
  nextConceptIndex,
  selectedKeysForApproval,
} from "./reviewSelection";
import type { ReviewGroup } from "./types";

const reviewGroups: ReviewGroup[] = [
  {
    concept_id: "project",
    concept_label: "Project",
    columns: [
      {
        key: "projects.project_id",
        table: "projects",
        column: "project_id",
        selected: true,
        roles: ["requested"],
      },
      {
        key: "projects.abstract",
        table: "projects",
        column: "abstract",
        roles: ["requested"],
      },
      {
        key: "projects.internal_score",
        table: "projects",
        column: "internal_score",
        selected: false,
        roles: ["requested"],
      },
    ],
  },
  {
    concept_id: "organization",
    concept_label: "Organization",
    columns: [
      {
        key: "organizations.name",
        table: "organizations",
        column: "name",
        roles: ["requested"],
      },
    ],
  },
];

describe("reviewSelection", () => {
  it("derives initially selected user-facing column keys", () => {
    expect(Array.from(initialSelectedKeys(reviewGroups)).sort()).toEqual([
      "organizations.name",
      "projects.abstract",
      "projects.project_id",
    ]);
  });

  it("advances to the next concept without exceeding the final concept", () => {
    expect(nextConceptIndex(0, 3)).toBe(1);
    expect(nextConceptIndex(2, 3)).toBe(2);
  });

  it("returns 0 when there are no groups", () => {
    expect(nextConceptIndex(0, 0)).toBe(0);
  });

  it("returns sorted selected keys for approval", () => {
    expect(
      selectedKeysForApproval(
        new Set(["projects.abstract", "organizations.name"]),
      ),
    ).toEqual(["organizations.name", "projects.abstract"]);
  });
});
