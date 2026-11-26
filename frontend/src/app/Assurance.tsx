import { motion, useReducedMotion } from "framer-motion";
import { Link } from "react-router-dom";
import { PageHead, Panel, SourceTag, StateBlock, StatusBadge } from "../components/ui";
import { api } from "../lib/api";
import { humanReason, num, pct } from "../lib/format";
import type { ReleaseView } from "../lib/types";
import { useWorkspace } from "../lib/workspace";
import { useFileName } from "./Overview";

type State = "ok" | "warn" | "bad" | "idle";
interface Check { title: string; detail: string; state: State; value?: string }

function checks(r: ReleaseView): Check[] {
  const a = r.assurance!;
  const cd = r.source === "practice" ? r.evidence?.check_dev : undefined;
  const released = a.files.filter((f) => f.status === "sanitized");
  const gateQ = a.files.filter((f) => f.reason === "release_verifier_failed").length;
  const out: Check[] = [
    { title: "Engine run", state: r.pipeline?.exit_code === 0 ? "ok" : "bad",
      detail: r.pipeline ? `main.py exit ${r.pipeline.exit_code} · ${r.pipeline.message}` : "no run recorded" },
    { title: "Output contract", state: !a.contract.evaluated ? "idle" : a.contract.ok ? "ok" : "bad",
      detail: a.contract.evaluated ? `organiser's validate_output.py: ${a.contract.ok ? "CONTRACT OK" : `${a.contract.errors} error(s)`}` : "Not evaluated: organiser validator not found" },
    { title: "PII verification", state: a.residual.total ? "warn" : "ok", value: num(a.residual.total),
      detail: `independent re-scan of ${released.length} released files: ${a.residual.total ? `${a.residual.total} span(s) to review (${Object.keys(a.residual.by_category).join(", ")})` : "no residual PII found"}` },
  ];
  if (cd?.pii) out.push({ title: "PII against the answer key", state: cd.pii.visible ? "warn" : "ok", value: `${cd.pii.visible}/${cd.pii.total}`,
    detail: `organiser's check_dev.py: ${cd.pii.visible} of ${num(cd.pii.total)} pieces visible · ${cd.canaries?.found ?? "–"} of ${cd.canaries?.total ?? "–"} canaries` });
  out.push(
    { title: "Clinical preservation", state: a.clinical.kept < a.clinical.before ? "warn" : a.clinical.before ? "ok" : "idle",
      value: a.clinical.before ? pct(a.clinical.kept, a.clinical.before) : undefined,
      detail: a.clinical.before ? `${num(a.clinical.kept)} of ${num(a.clinical.before)} clinical values unchanged` : "no clinical values found to compare" },
    { title: "Identity consistency", state: "ok",
      detail: `${num(a.identity.linked_records)} of ${num(a.identity.records)} records carry one keyed pseudonym; ${num(a.identity.patients)} patients${cd?.linking ? ` · F0.5 ${cd.linking.f05.toFixed(2)} vs answer key` : ""}` },
    { title: "Structural validation", state: a.structure.total ? "bad" : "ok",
      detail: a.structure.total ? Object.keys(a.structure.codes).join(", ") : "every released file is valid UTF-8; JSON parses; FHIR references resolve" },
    { title: "File-level gate", state: "ok",
      detail: `every released file passed the in-pipeline release gate${gateQ ? `; ${gateQ} file(s) failed it and were quarantined` : ""}` },
    { title: "Release-wide verification", state: !a.release_wide.evaluated ? "idle" : a.release_wide.passed ? "ok" : "bad",
      detail: a.release_wide.evaluated ? (a.release_wide.passed ? "all inputs accounted for; report and manifest match the exported tree; secret and known values absent from report and manifest" : a.release_wide.codes.join(", ")) : "Not evaluated" },
  );
  return out;
}

export default function Assurance() {
  const { current } = useWorkspace();
  const reduce = useReducedMotion();
  const name = useFileName(current);
  if (current.status !== "complete") {
    return (
      <>
        <PageHead eyebrow="Release assurance" title="Verification in progress" />
        <Panel title="Status" aside={<StatusBadge status={current.status} />}>
          <Progress stage={current.stage} status={current.status} />
          {current.status === "failed" && <div className="notice bad" style={{ marginTop: 16 }}>The release failed and was not published. Safe reason: {current.error ?? current.pipeline?.message ?? "unknown"}</div>}
        </Panel>
      </>
    );
  }
  const a = current.assurance;
  if (!a) return <Panel><StateBlock title="Not evaluated">This release has no verification results, so it is not verified.</StateBlock></Panel>;
  const list = checks(current);
  const verdict = a.status;
  const tone = verdict === "VERIFIED" ? "ok" : verdict === "BLOCKED" ? "bad" : "warn";
  const quarantined = a.files.filter((f) => f.status !== "sanitized");

  return (
    <>
      <PageHead eyebrow="Release assurance" title="The final gate" aside={<SourceTag source={current.source} />}>
        A release is shown as verified only when every check below ran and passed.
      </PageHead>
      <motion.div className={`verdict ${tone}`} initial={reduce ? false : { opacity: 0, scale: 0.985 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.5 }}>
        <Seal tone={tone} />
        <div>
          <div className="title">{verdict}</div>
          <p style={{ marginTop: 8, opacity: 0.85 }}>
            {verdict === "VERIFIED" && "Every check ran and passed. This release can leave the hospital."}
            {verdict === "VERIFICATION REQUIRED" && "The release was produced, but at least one check needs a person to review it before it leaves."}
            {verdict === "BLOCKED" && "A blocking check failed. Do not release this output."}
          </p>
        </div>
        <span className="mono" style={{ opacity: 0.75 }}>{list.filter((c) => c.state === "ok").length}/{list.length} checks passed</span>
      </motion.div>

      <div className="grid-2">
        <Panel title="Checks" bodyClass="">
          {list.map((c, i) => (
            <motion.div key={c.title} className="check" initial={reduce ? false : { opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 + i * 0.06 }}>
              <span className={`mark ${c.state}`} aria-label={c.state}>{c.state === "ok" ? "✓" : c.state === "bad" ? "✕" : c.state === "warn" ? "!" : "–"}</span>
              <div><h3>{c.title}</h3><p>{c.detail}</p></div>
              <span className="mono muted">{c.value ?? (c.state === "idle" ? "not evaluated" : "")}</span>
            </motion.div>
          ))}
        </Panel>
        <div style={{ display: "grid", gap: 22 }}>
          <Panel title={`Quarantined (${quarantined.length})`}>
            {quarantined.length === 0 ? <p className="muted">No file was quarantined.</p> : (
              <ul style={{ margin: 0, paddingLeft: 0, listStyle: "none", display: "grid", gap: 10 }}>
                {quarantined.map((f) => (
                  <li key={f.input_sha256} style={{ display: "grid", gap: 2 }}>
                    <span className="mono" style={{ wordBreak: "break-all" }}>{name(f.input_sha256, f.output)}</span>
                    <span className="muted" style={{ fontSize: 13 }}>{humanReason(f.reason)}</span>
                  </li>
                ))}
              </ul>
            )}
            <p className="muted" style={{ fontSize: 12.5, marginTop: 12 }}>Quarantined files are never copied into the release.</p>
          </Panel>
          <Panel title="Release files">
            {current.source === "live" ? (
              <div style={{ display: "grid", gap: 10 }}>
                <a className="btn btn-ghost btn-sm" href={api.fileUrl(current.id, "report.json", true)}>Download report.json</a>
                <a className="btn btn-ghost btn-sm" href={api.fileUrl(current.id, "records.jsonl", true)}>Download records.jsonl</a>
                <Link to="/studio/inventory" className="btn btn-quiet btn-sm">Browse released files</Link>
                <p className="muted" style={{ fontSize: 12.5 }}>Only released output is served. Uploaded inputs were deleted after the run.</p>
              </div>
            ) : (
              <p className="muted" style={{ fontSize: 13 }}>Downloads are available for releases run in this Studio. This {current.source === "demo" ? "recorded synthetic demo" : "practice evaluation"} keeps summaries only.</p>
            )}
          </Panel>
        </div>
      </div>
    </>
  );
}

function Progress({ stage, status }: { stage?: string; status: string }) {
  const steps = [["queued", "Files received"], ["pipeline", "Engine running (main.py)"], ["verification", "Independent checks"], ["done", "Complete"]];
  const at = Math.max(0, steps.findIndex((s) => s[0] === stage));
  return (
    <ol className="timeline">
      {steps.map(([k, label], i) => (
        <li key={k}>
          <span className={`dot ${i < at || status === "complete" ? "ok" : i === at && status !== "failed" ? "warn" : status === "failed" && i === at ? "bad" : ""}`} />
          <span>{label}</span>
          <span className="mono muted">{i === at && status !== "failed" && status !== "complete" ? "in progress" : i < at ? "done" : ""}</span>
        </li>
      ))}
    </ol>
  );
}

function Seal({ tone }: { tone: string }) {
  const c = tone === "ok" ? "#F2F0E8" : tone === "bad" ? "#A94F45" : "#BD8D43";
  return (
    <svg className="seal" viewBox="0 0 64 64" aria-hidden="true">
      <circle cx="32" cy="32" r="29" fill="none" stroke={c} strokeWidth="1.5" strokeDasharray="3 3" />
      <circle cx="32" cy="32" r="22" fill="none" stroke={c} strokeWidth="2" />
      {tone === "ok" ? <path d="M22 33l7 7 13-15" fill="none" stroke={c} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
        : tone === "bad" ? <path d="M24 24l16 16M40 24 24 40" stroke={c} strokeWidth="3" strokeLinecap="round" />
        : <path d="M32 21v14M32 42v1" stroke={c} strokeWidth="3.4" strokeLinecap="round" />}
    </svg>
  );
}
