// One colour system for the DOM and every Three.js scene.
export const C = {
  background: "#F3F5F2",
  surface: "#FFFFFF",
  forest: "#204B42",
  forestLight: "#2F6B5E",
  ink: "#202A27",
  slate: "#68756E",
  copper: "#B87552",
  sage: "#AAB8A9",
  line: "#DCE2DC",
  amber: "#BD8D43",
  terracotta: "#A94F45",
  ivory: "#FBFAF6",
} as const;

import type { LayerStatus, StageStatus } from "../state/model";

/** Status -> colour, identical in DOM badges and 3D materials. */
export function statusColor(s: StageStatus | LayerStatus): string {
  switch (s) {
    case "complete": case "passed": return C.forest;
    case "running": return C.copper;
    case "attention": return C.amber;
    case "blocked": case "failed": return C.terracotta;
    case "waiting": return C.sage;
    default: return "#C9D0C9"; // not evaluated
  }
}

export const STATUS_LABEL: Record<string, string> = {
  complete: "Complete", passed: "Passed", running: "Running", waiting: "Waiting", attention: "Requires attention",
  blocked: "Blocked", failed: "Failed", not_evaluated: "Not evaluated",
};

/** A small fixed palette for sources (hospitals), derived from the brand colours. */
const SOURCE = [C.forest, C.copper, "#5E7F73", "#8A6A4F", "#3E6A7A", "#7A5E86", "#6B7F3E", "#9A5A4A"];
export const sourceColor = (i: number) => SOURCE[i % SOURCE.length];
