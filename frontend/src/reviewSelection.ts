import type { ReviewGroup } from "./types";

export function initialSelectedKeys(groups: ReviewGroup[]): Set<string> {
  const selected = new Set<string>();
  for (const group of groups) {
    for (const column of group.columns) {
      if (
        column.roles.length === 1 &&
        column.roles[0] === "requested" &&
        column.selected !== false &&
        column.key
      ) {
        selected.add(column.key);
      }
    }
  }
  return selected;
}

export function nextConceptIndex(
  currentIndex: number,
  groupCount: number,
): number {
  return Math.min(currentIndex + 1, Math.max(0, groupCount - 1));
}

export function selectedKeysForApproval(selected: Set<string>): string[] {
  return Array.from(selected).sort();
}
