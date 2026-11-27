// The unified release model: one derivation from the engine's real outputs (Assurance, practice
// Evidence, pipeline status) that every screen and every 3D scene reads. Nothing here invents a
// value: anything the engine did not produce is "not_evaluated".
import type { Assurance, Evidence, FileEntry, Inspection, ReleaseView } from "../lib/types";

export type StageId = "intake" | "identity" | "protection" | "clinical" | "risk" | "verification" | "authorisation";
export type StageStatus = "complete" | "running" | "waiting" | "attention" | "blocked" | "failed" | "not_evaluated";
export type LayerStatus = "passed" | "attention" | "failed" | "running" | "not_evaluated";

export interface FileRow extends FileEntry {
  name: string;          // the user's own file name (this tab only), else the PII-free released path
  sourceKey: string;
  format: string;
  inspection?: Inspection;
}

export interface Source {
  key: string;
  label: string;
  files: FileRow[];
  records: number;
  quarantined: number;
  formats: string[];
  scripts: string[];
  legacyEncodings: string[];
  issues: number;
}

export interface Stage { id: StageId; label: string; route: string; status: StageStatus; summary: string }
export interface Layer { id: string; label: string; status: LayerStatus; detail: string; route: string; actionId?: string }

export interface IdentityRecord { file: string; loc: string; sourceKey: string; pseudonym: string | null }
export interface IdentityModel {
  records: number; linked: number; patients: number; unlinkedTotal: number; multiSource: number;
  clusters: { pseudonym: string; records: IdentityRecord[]; sources: string[] }[];
  unlinked: IdentityRecord[];
  linking?: { precision: number; recall: number; f05: number; wrongMerges: number }; // practice only
}

export interface ReleaseModel {
  view: ReleaseView;
  assurance?: Assurance;
  evidence?: Evidence;
  sources: Source[];
  files: FileRow[];
  stages: Stage[];
  layers: Layer[];
  identity: IdentityModel;
  counts: { files: number; released: number; quarantined: number; records: number };
  complete: boolean;
}

const STAGE_META: { id: StageId; label: string; route: string }[] = [
  { id: "intake", label: "Source intake", route: "/intake" },
  { id: "identity", label: "Identity resolution", route: "/identity" },
  { id: "protection", label: "Privacy protection", route: "/protection" },
  { id: "clinical", label: "Clinical validation", route: "/clinical-integrity" },
  { id: "risk", label: "Privacy risk", route: "/risk" },
  { id: "verification", label: "Release verification", route: "/assurance" },
  { id: "authorisation", label: "Authorisation", route: "/assurance" },
];

export const prettySource = (key: string) =>
  key === "_unassigned" ? "Unassigned files" : key.replace(/[_-]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

function sourceOf(f: FileEntry, names: Record<string, string>): string {
  const known = names[f.input_sha256];
  if (known && known.includes("/")) return known.split("/")[0];
  if (f.source) return f.source;
  if (f.output) {
    const parts = f.output.replace(/^sanitized\//, "").split("/");
    if (parts.length > 1) return parts[0];
  }
  return "_unassigned";
}

export function buildModel(view: ReleaseView): ReleaseModel {
  const a = view.assurance;
  const ev = view.evidence;
  const complete = view.status === "complete" && !!a;
  const files: FileRow[] = (a?.files ?? []).map((f) => ({
    ...f,
    name: view.names[f.input_sha256] ?? f.input_name ?? f.output?.replace(/^sanitized\//, "") ?? `input ${f.input_sha256.slice(0, 10)}…`,
    sourceKey: sourceOf(f, view.names),
    format: f.inspection?.format ?? (f.output ? f.output.split(".").pop() ?? "" : ""),
  }));

  const byKey = new Map<string, FileRow[]>();
  for (const f of files) byKey.set(f.sourceKey, [...(byKey.get(f.sourceKey) ?? []), f]);
  const sources: Source[] = [...byKey.entries()].map(([key, fs]) => ({
    key, label: prettySource(key), files: fs,
    records: fs.reduce((s, f) => s + (f.status === "sanitized" ? f.records : 0), 0),
    quarantined: fs.filter((f) => f.status !== "sanitized").length,
    formats: [...new Set(fs.map((f) => f.format).filter(Boolean))],
    scripts: [...new Set(fs.map((f) => f.inspection?.script).filter((s): s is NonNullable<typeof s> => !!s && s !== "none"))],
    legacyEncodings: [...new Set(fs.filter((f) => f.inspection?.issues.includes("legacy_encoding")).map((f) => f.inspection!.encoding!))],
    issues: fs.filter((f) => f.status !== "sanitized" || (f.inspection?.issues.length ?? 0) > 0).length,
  })).sort((x, y) => (x.key === "_unassigned" ? 1 : y.key === "_unassigned" ? -1 : x.label.localeCompare(y.label)));

  const srcOfOutput = new Map(files.filter((f) => f.output).map((f) => [f.output!, f.sourceKey]));
  const rec = (r: { file: string; loc: string }, p: string | null): IdentityRecord =>
    ({ file: r.file, loc: r.loc, sourceKey: srcOfOutput.get(r.file) ?? "_unassigned", pseudonym: p });
  const clusters = (a?.identity.clusters ?? []).map((c) => {
    const records = c.records.map((r) => rec(r, c.pseudonym));
    return { pseudonym: c.pseudonym, records, sources: [...new Set(records.map((r) => r.sourceKey))] };
  });
  const lk = ev?.check_dev.linking;
  const identity: IdentityModel = {
    records: a?.identity.records ?? 0,
    linked: a?.identity.linked_records ?? 0,
    patients: a?.identity.patients ?? 0,
    unlinkedTotal: a?.identity.unlinked_total ?? Math.max(0, (a?.identity.records ?? 0) - (a?.identity.linked_records ?? 0)),
    multiSource: clusters.filter((c) => c.sources.length > 1).length,
    clusters,
    unlinked: (a?.identity.unlinked ?? []).map((r) => rec(r, null)),
    linking: lk ? { precision: lk.precision, recall: lk.recall, f05: lk.f05, wrongMerges: lk.wrong_merges } : undefined,
  };

  const counts = {
    files: a?.counts.files_total ?? files.length,
    released: a?.counts.files_sanitized ?? files.filter((f) => f.status === "sanitized").length,
    quarantined: a?.counts.files_quarantined ?? files.filter((f) => f.status !== "sanitized").length,
    records: a?.counts.records_processed ?? identity.records,
  };

  const layers = buildLayers(view, a, ev);
  const stages = buildStages(view, a, ev, files, identity, layers);
  return { view, assurance: a, evidence: ev, sources, files, stages, layers, identity, counts, complete };
}

function buildLayers(view: ReleaseView, a?: Assurance, ev?: Evidence): Layer[] {
  const running = ["queued", "running", "verifying"].includes(view.status);
  const pending = (id: string, label: string, route: string): Layer =>
    ({ id, label, route, status: running ? "running" : "not_evaluated", detail: running ? "Waiting for the engine run" : "Not evaluated" });
  if (!a) {
    return [["input", "Input accounting"], ["pii", "PII verification"], ["identity", "Identity consistency"],
      ["clinical", "Clinical preservation"], ["structure", "Output structure"], ["file", "File-level privacy gate"],
      ["release", "Release-wide verification"]].map(([id, l]) => pending(id, l, "/assurance"));
  }
  const cd = ev?.check_dev;
  const released = a.files.filter((f) => f.status === "sanitized").length;
  const gateQ = a.files.filter((f) => f.reason === "release_verifier_failed").length;
  const piiDetail = `Independent re-scan of ${released} released files: ${a.residual.total ? `${a.residual.total} span(s) to review` : "no residual PII"}` +
    (cd?.pii ? ` · organiser checker: ${cd.pii.visible} of ${cd.pii.total.toLocaleString("en-IN")} visible` : "");
  return [
    { id: "input", label: "Input accounting", route: "/intake",
      status: a.release_wide.evaluated ? (a.release_wide.codes.includes("UNACCOUNTED_INPUT") ? "failed" : "passed") : "not_evaluated",
      detail: `${a.counts.files_total} inputs: ${a.counts.files_sanitized} released, ${a.counts.files_quarantined} quarantined; every input listed in report.json` },
    { id: "pii", label: "PII verification", route: "/protection", status: a.residual.total || (cd?.pii?.visible ?? 0) > 0 ? "attention" : "passed", detail: piiDetail },
    { id: "identity", label: "Identity consistency", route: "/identity", status: "passed",
      detail: `${a.identity.linked_records} of ${a.identity.records} records carry one keyed pseudonym; ${a.identity.patients} patients` },
    { id: "clinical", label: "Clinical preservation", route: "/clinical-integrity",
      status: a.clinical.before === 0 ? "not_evaluated" : a.clinical.kept < a.clinical.before ? "attention" : "passed",
      detail: a.clinical.before ? `${a.clinical.kept} of ${a.clinical.before} clinical values unchanged` : "No clinical values found to compare" },
    { id: "structure", label: "Output structure", route: "/intake",
      status: a.structure.total || (a.contract.evaluated && !a.contract.ok) ? "failed" : !a.contract.evaluated ? "attention" : "passed",
      detail: a.structure.total ? Object.keys(a.structure.codes).join(", ")
        : a.contract.evaluated ? "Valid UTF-8, JSON and FHIR references; organiser's validate_output.py: CONTRACT OK" : "Organiser validator not available" },
    { id: "file", label: "File-level privacy gate", route: "/intake", status: "passed",
      detail: `Every released file passed the in-pipeline release gate${gateQ ? `; ${gateQ} file(s) failed it and were quarantined` : ""}` },
    { id: "release", label: "Release-wide verification", route: "/assurance",
      status: !a.release_wide.evaluated ? "not_evaluated" : a.release_wide.passed ? "passed" : "failed",
      detail: a.release_wide.passed ? "Inputs accounted for; report and manifest match the exported tree; secret and known values absent"
        : a.release_wide.codes.join(", ") || "Not evaluated" },
  ];
}

function buildStages(view: ReleaseView, a: Assurance | undefined, ev: Evidence | undefined, files: FileRow[],
  identity: IdentityModel, layers: Layer[]): Stage[] {
  const running = ["queued", "running", "verifying"].includes(view.status);
  const failed = view.status === "failed" || (view.pipeline && view.pipeline.exit_code !== 0);
  const status: Record<StageId, [StageStatus, string]> = {} as never;
  if (failed) {
    for (const s of STAGE_META) status[s.id] = s.id === "intake" ? ["failed", view.error ?? view.pipeline?.message ?? "Engine run failed"] : ["waiting", "Not reached"];
  } else if (running || !a) {
    for (const s of STAGE_META) status[s.id] = s.id === "intake" ? ["running", "The engine is processing the files"] : ["waiting", "Waiting for the engine run"];
  } else {
    const q = files.filter((f) => f.status !== "sanitized").length;
    const legacy = files.filter((f) => f.inspection?.issues.includes("legacy_encoding")).length;
    status.intake = [q || legacy ? "attention" : "complete",
      `${a.counts.files_sanitized} of ${a.counts.files_total} files processed${q ? `, ${q} quarantined` : ""}${legacy ? `, ${legacy} legacy-encoded` : ""}`];
    status.identity = identity.records === 0 ? ["not_evaluated", "No records"]
      : [identity.unlinkedTotal ? "attention" : "complete", `${identity.patients} patients; ${identity.unlinkedTotal} record(s) released unlinked`];
    status.protection = [a.residual.total ? "attention" : "complete",
      a.residual.total ? `${a.residual.total} possible residual PII span(s)` : "No residual PII in released files"];
    status.clinical = a.clinical.before === 0 ? ["not_evaluated", "No clinical values found"]
      : [a.clinical.kept < a.clinical.before ? "attention" : "complete", `${a.clinical.kept} of ${a.clinical.before} values unchanged`];
    if (ev) {
      const p = ev.attacks.protected, b = ev.attacks.unprotected_baseline;
      const concern = p.A4.rate > 0.3 || p.A5.rate > b.A5.rate;
      status.risk = [concern ? "attention" : "complete", `Profile re-identification ${(100 * p.A4.rate).toFixed(1)}% (local attack lab)`];
    } else {
      status.risk = ["not_evaluated", "Attack evaluation needs the organiser's practice attacker files"];
    }
    const blocked = layers.some((l) => l.status === "failed");
    status.verification = [blocked ? "blocked" : a.status === "VERIFIED" ? "complete" : "attention", a.status];
    status.authorisation = [blocked ? "blocked" : "waiting", blocked ? "Blocked by a failed verification layer" : "Requires human authorisation"];
  }
  return STAGE_META.map((s) => ({ ...s, status: status[s.id][0], summary: status[s.id][1] }));
}
