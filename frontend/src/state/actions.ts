// Deterministic next-best-action engine. Rules read the unified ReleaseModel only (no ML, no
// network) and produce prioritised, explained action items. Consequential decisions (accepting a
// finding, authorising a release) are never taken here: they are recorded human decisions.
import type { ReleaseModel, StageId } from "./model";
import { prettySource } from "./model";

export type Severity = "critical" | "warning" | "attention" | "info" | "ready";
export interface ActionItem {
  id: string;
  severity: Severity;
  stage: StageId;
  title: string;          // what happened
  why: string;            // why it matters
  affected: string[];     // files / records / sources, PII-free labels
  impact: string;         // effect on the release
  recommendation: string; // the action, imperative
  after: string;          // what happens after the action
  route: string;          // where the evidence is, with selection in the query
  blocking: boolean;      // blocks authorisation until resolved (cannot be marked reviewed)
  reviewable: boolean;    // a person may record that they reviewed it
}

export interface Decisions { reviewed: Record<string, { at: string; note: string }>; authorisedAt: string | null }
export interface Readiness {
  state: "in_progress" | "failed" | "blocked" | "review" | "ready" | "authorised" | "not_evaluated";
  label: string; detail: string; blockers: number; toReview: number;
}

const RANK: Record<Severity, number> = { critical: 0, warning: 1, attention: 2, info: 3, ready: 4 };
const files = (xs: { name: string }[], n = 4) =>
  xs.slice(0, n).map((x) => x.name).concat(xs.length > n ? [`+${xs.length - n} more`] : []);

export function deriveActions(m: ReleaseModel): ActionItem[] {
  const out: ActionItem[] = [];
  const v = m.view;
  const a = m.assurance;
  if (v.status === "failed" || (v.pipeline && v.pipeline.exit_code !== 0)) {
    out.push({ id: "run-failed", severity: "critical", stage: "intake", title: "The engine run failed",
      why: "Nothing from this run was published; the release does not exist yet.",
      affected: [v.error ?? v.pipeline?.message ?? "unknown reason"], impact: "No release to verify or authorise.",
      recommendation: "Inspect the failure and start a new release", after: "A new run replaces this one; inputs are never modified.",
      route: "/intake", blocking: true, reviewable: false });
    return out;
  }
  if (["queued", "running", "verifying"].includes(v.status)) {
    out.push({ id: "running", severity: "info", stage: v.status === "verifying" ? "verification" : "intake",
      title: v.status === "verifying" ? "Independent checks are running" : "The engine is processing the files",
      why: "Results appear as soon as the run and its checks finish.", affected: [`${v.label}`],
      impact: "Readiness is not known until verification completes.", recommendation: "Wait for processing to finish",
      after: "The operations queue fills in from the real results.", route: "/workspace", blocking: false, reviewable: false });
    return out;
  }
  if (!a) return out;

  // structural or release-wide failures: blocking
  const failedLayers = m.layers.filter((l) => l.status === "failed");
  for (const l of failedLayers) {
    out.push({ id: `layer-${l.id}`, severity: "critical", stage: "verification", title: `${l.label} failed`,
      why: "A failed verification layer means the output cannot be trusted as released.", affected: [l.detail],
      impact: "Release is blocked.", recommendation: "Investigate the failed verification layer",
      after: "Fix the cause and run the release again; Anaam re-verifies every file.", route: `/assurance?layer=${l.id}`,
      blocking: true, reviewable: false });
  }

  // quarantined files, grouped by reason
  const q = m.files.filter((f) => f.status !== "sanitized");
  const byReason = new Map<string, typeof q>();
  for (const f of q) byReason.set(f.reason ?? "unknown", [...(byReason.get(f.reason ?? "unknown") ?? []), f]);
  for (const [reason, fs] of byReason) {
    out.push({ id: `quarantine-${reason}`, severity: "warning", stage: "intake",
      title: `${fs.length} file${fs.length > 1 ? "s" : ""} quarantined: ${reasonText(reason)}`,
      why: "Anaam never copies a file it cannot process safely, so its records are missing from the research dataset.",
      affected: files(fs), impact: `${fs.length} source file${fs.length > 1 ? "s are" : " is"} not in the release.`,
      recommendation: "Review quarantined files", after: "Replace or repair the source file and run a new release; or accept the gap.",
      route: `/intake?file=${encodeURIComponent(fs[0].input_sha256)}`, blocking: false, reviewable: true });
  }

  // legacy encodings (informational: handled by the engine)
  const legacy = m.files.filter((f) => f.inspection?.issues.includes("legacy_encoding"));
  if (legacy.length) {
    const encs = [...new Set(legacy.map((f) => f.inspection!.encoding))].join(", ");
    out.push({ id: "legacy-encoding", severity: "attention", stage: "intake",
      title: `Legacy encoding detected (${encs}) in ${legacy.length} file${legacy.length > 1 ? "s" : ""}`,
      why: "Older hospital exports use other text encodings. Anaam decoded them and released UTF-8; a mis-decoded file would garble names and values.",
      affected: files(legacy), impact: "No data was lost if the decoded text looks right; worth one human check.",
      recommendation: "Review legacy encoding", after: "Mark it reviewed once the released file reads correctly.",
      route: `/intake?file=${encodeURIComponent(legacy[0].input_sha256)}`, blocking: false, reviewable: true });
  }

  // residual PII
  const resid = m.files.filter((f) => f.residual > 0);
  if (resid.length) {
    out.push({ id: "residual-pii", severity: "warning", stage: "protection",
      title: `Possible residual PII in ${resid.length} released file${resid.length > 1 ? "s" : ""}`,
      why: "An independent re-scan of the released files found spans that look like personal data.",
      affected: files(resid), impact: "The release needs review before it can be authorised.",
      recommendation: "Investigate possible residual PII", after: "If it is personal data, report it and re-run; if not, record the review.",
      route: `/protection?file=${encodeURIComponent(resid[0].input_sha256)}`, blocking: false, reviewable: true });
  }

  // clinical loss
  const loss = m.files.filter((f) => f.clinical_kept < f.clinical_before);
  if (loss.length) {
    out.push({ id: "clinical-loss", severity: "warning", stage: "clinical",
      title: `Clinical values changed in ${loss.length} file${loss.length > 1 ? "s" : ""}`,
      why: "A changed dose, lab value or diagnosis reduces the research value of the record.",
      affected: files(loss), impact: "Clinical preservation is incomplete.", recommendation: "Complete clinical validation",
      after: "Confirm whether the change was a permitted transformation.", route: "/clinical-integrity", blocking: false, reviewable: true });
  }

  // identity exceptions: records released without a patient link
  if (m.identity.unlinkedTotal > 0) {
    const bySource = new Map<string, number>();
    for (const r of m.identity.unlinked) bySource.set(r.sourceKey, (bySource.get(r.sourceKey) ?? 0) + 1);
    out.push({ id: "identity-exceptions", severity: "attention", stage: "identity",
      title: `${m.identity.unlinkedTotal} record${m.identity.unlinkedTotal > 1 ? "s" : ""} released without a patient link`,
      why: "Anaam links records only on a strong identifier, or an exact name plus a supporting clue. Where the evidence is insufficient it abstains and releases the record with patient: null, so different people are never merged.",
      affected: [...bySource.entries()].map(([k, n]) => `${prettySource(k)}: ${n}`),
      impact: "Those records cannot be followed across hospitals in the research dataset.",
      recommendation: "Review identity exceptions",
      after: "Anaam never merges records from the interface. A confirmed gap (e.g. an unrecognised identity column) is fixed in the engine and the release re-run.",
      route: "/identity?status=unlinked", blocking: false, reviewable: true });
  }

  // privacy risk (attack lab, practice data only)
  const ev = m.evidence;
  if (ev) {
    const p = ev.attacks.protected, b = ev.attacks.unprotected_baseline;
    if (p.A4.rate > 0.3) {
      out.push({ id: "risk-a4", severity: "warning", stage: "risk",
        title: `Profile re-identification at ${(100 * p.A4.rate).toFixed(1)}%`,
        why: "Removing names is not enough: combined age band, place, visit dates and diagnoses can still single out a person in a voter list.",
        affected: [`${p.A4.reidentified} of ${p.A4.total} assessed profiles`, `unprotected copy: ${(100 * b.A4.rate).toFixed(1)}%`],
        impact: "The largest remaining privacy risk in this release.", recommendation: "Investigate privacy risk",
        after: "Coarser generalisation of rare diagnoses and visit dates is the planned engine fix.", route: "/risk?scenario=A4",
        blocking: false, reviewable: true });
    }
    if (p.A5.rate > b.A5.rate) {
      out.push({ id: "risk-a5", severity: "warning", stage: "risk",
        title: "Known-fact attack finds more on the protected release",
        why: "Linked pseudonyms let an attacker pool known facts across one patient's records.",
        affected: [`${p.A5.found} of ${p.A5.total} facts (unprotected copy: ${b.A5.found})`],
        impact: "Linking improves research value but increases this risk.", recommendation: "Investigate privacy risk",
        after: "Record the review; the fix belongs in the privacy layer.", route: "/risk?scenario=A5", blocking: false, reviewable: true });
    }
  } else {
    out.push({ id: "risk-not-evaluated", severity: "info", stage: "risk", title: "Privacy attacks not evaluated for this release",
      why: "Attack replay needs the organiser's attacker knowledge, which exists only for the practice data.",
      affected: [m.view.label], impact: "Re-identification risk is unknown for this release.",
      recommendation: "Review the practice attack evaluation", after: "Use it as an indication of the engine's behaviour, not as this release's score.",
      route: "/risk", blocking: false, reviewable: true });
  }

  if (!a.contract.evaluated) {
    out.push({ id: "contract-not-evaluated", severity: "attention", stage: "verification",
      title: "Organiser's output validator not run", why: "The output contract was not checked by the organiser's own validator.",
      affected: ["validate_output.py not found"], impact: "Verification is incomplete.", recommendation: "Run the organiser's validator",
      after: "Start the Studio server with the Team Kit next to the repository.", route: "/assurance?layer=structure",
      blocking: true, reviewable: false });
  }
  return out.sort((x, y) => RANK[x.severity] - RANK[y.severity]);
}

export function readiness(m: ReleaseModel, actions: ActionItem[], d: Decisions): Readiness {
  const v = m.view;
  if (["queued", "running", "verifying"].includes(v.status)) return { state: "in_progress", label: "Processing", detail: "The engine and its checks are running", blockers: 0, toReview: 0 };
  if (v.status === "failed") return { state: "failed", label: "Failed", detail: "The engine run failed; nothing was released", blockers: 1, toReview: 0 };
  if (!m.assurance) return { state: "not_evaluated", label: "Not evaluated", detail: "No verification results", blockers: 0, toReview: 0 };
  const blockers = actions.filter((x) => x.blocking).length;
  const toReview = actions.filter((x) => x.reviewable && !d.reviewed[x.id] && x.severity !== "info").length;
  if (d.authorisedAt && blockers === 0) return { state: "authorised", label: "Authorised", detail: `Authorised in this session at ${new Date(d.authorisedAt).toLocaleTimeString("en-GB")}`, blockers, toReview };
  if (blockers) return { state: "blocked", label: "Blocked", detail: `${blockers} blocking issue${blockers > 1 ? "s" : ""}`, blockers, toReview };
  if (m.assurance.status !== "VERIFIED") return { state: "review", label: "Verification required", detail: "At least one check needs human review", blockers, toReview };
  if (toReview) return { state: "review", label: "Review required", detail: `${toReview} finding${toReview > 1 ? "s" : ""} to review before authorisation`, blockers, toReview };
  return { state: "ready", label: "Ready for authorisation", detail: "Every required check passed and every finding has been reviewed", blockers, toReview };
}

/** The single next recommended action, given decisions already taken. */
export function nextAction(m: ReleaseModel, actions: ActionItem[], d: Decisions, r: Readiness): ActionItem | null {
  const open = actions.filter((x) => x.blocking || (x.reviewable && !d.reviewed[x.id]) || (!x.reviewable && !x.blocking));
  const first = open.find((x) => x.severity !== "info") ?? null;
  if (first) return first;
  if (r.state === "ready") {
    return { id: "authorise", severity: "ready", stage: "authorisation", title: "All required checks passed",
      why: "Every verification layer passed and every finding has a recorded review.", affected: [m.view.label],
      impact: "The release can be authorised for research use.", recommendation: "Review release for authorisation",
      after: "An authorised person confirms the release; the decision is recorded in this session.", route: "/assurance",
      blocking: false, reviewable: false };
  }
  return open[0] ?? null;
}

function reasonText(r: string): string {
  return ({
    unsupported: "format not recognised", unsupported_format: "unsupported file type", undecodable_text: "text could not be decoded",
    empty_file: "empty file", json_nesting_too_deep: "JSON nested too deeply", release_verifier_failed: "failed the release gate",
    detection_failed: "detection failed", fhir_patient_count_unsupported: "FHIR bundle without exactly one patient",
  } as Record<string, string>)[r] ?? r.replace(/_/g, " ");
}
