import { motion, useReducedMotion } from "framer-motion";
import { Link } from "react-router-dom";
import { Metric, PageHead, Panel, SourceTag, StateBlock, StatusBadge, VerdictBadge } from "../components/ui";
import { humanReason, num, pct, when } from "../lib/format";
import type { ReleaseView } from "../lib/types";
import { useWorkspace } from "../lib/workspace";

export function useFileName(r: ReleaseView) {
  return (sha: string, output: string | null) => r.names[sha] ?? output?.replace(/^sanitized\//, "") ?? `input ${sha.slice(0, 10)}…`;
}

export default function Overview() {
  const { current, releases, select, health } = useWorkspace();
  const a = current.assurance;
  const reduce = useReducedMotion();
  const quarantined = a?.files.filter((f) => f.status !== "sanitized") ?? [];
  const piiLabel = current.source === "practice" && current.evidence?.check_dev.pii
    ? { value: num(current.evidence.check_dev.pii.visible), unit: `of ${num(current.evidence.check_dev.pii.total)}`, label: "PII pieces visible (organiser's check_dev, vs answer key)" }
    : { value: a ? num(a.residual.total) : "–", unit: undefined, label: "possible residual PII (independent re-scan of released files)" };

  const events = timeline(current);
  return (
    <>
      <PageHead eyebrow="Firewall overview" title={current.source === "demo" ? "Synthetic demo workspace" : current.label}
        aside={<Link to="/studio/new" className="btn btn-primary">New release <span className="arrow">→</span></Link>}>
        {current.source === "demo" && "Three fictional hospitals and five invented patients, processed by the real engine. Recorded output; nothing here is a real person."}
        {current.source === "practice" && "The organiser's practice data, processed by main.py and measured with the organiser's checkers on this machine."}
        {current.source === "live" && "A release you ran in this Studio. Uploaded files were processed locally and then deleted; only the released output remains."}
      </PageHead>

      {current.status !== "complete" ? (
        <Panel title="Release in progress" aside={<StatusBadge status={current.status} />}>
          <StateBlock title={current.status === "failed" ? "This release failed" : "Processing on this machine"}>
            {current.status === "failed" ? `Safe reason: ${current.error ?? current.pipeline?.message ?? "unknown"}` : `Stage: ${current.stage ?? "queued"}`}
          </StateBlock>
        </Panel>
      ) : !a ? (
        <Panel><StateBlock title="Not evaluated">This release has no verification results.</StateBlock></Panel>
      ) : (
        <section className="panel">
          <header className="panel-head">
            <h2>Release summary</h2>
            <span style={{ display: "flex", gap: 10, alignItems: "center" }}><SourceTag source={current.source} /><VerdictBadge verdict={a.status} /></span>
          </header>
          <div className="metric-row">
            <Metric value={num(a.counts.files_total)} label={`files · ${num(a.counts.files_sanitized)} released, ${num(a.counts.files_quarantined)} quarantined`} />
            <Metric value={num(a.counts.records_processed)} label="records processed" />
            <Metric value={piiLabel.value} unit={piiLabel.unit} label={piiLabel.label} />
            <Metric value={a.clinical.before ? pct(a.clinical.kept, a.clinical.before) : "–"} label={`clinical values kept (${num(a.clinical.kept)} of ${num(a.clinical.before)})`} />
            <Metric value={num(a.identity.patients)} label={`pseudonymous patients · ${num(a.identity.linked_records)} of ${num(a.identity.records)} records linked`} />
          </div>
        </section>
      )}

      <div className="grid-2">
        <Panel title="Activity" aside={<span className="muted" style={{ fontSize: 12.5 }}>from this release's own records</span>}>
          {events.length === 0 ? <StateBlock title="No activity yet" /> : (
            <ol className="timeline">
              {events.map((e, i) => (
                <motion.li key={i} initial={reduce ? false : { opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }}>
                  <span className={`dot ${e.tone}`} />
                  <div><strong style={{ fontWeight: 600 }}>{e.title}</strong><p className="muted" style={{ fontSize: 13 }}>{e.detail}</p></div>
                  <span className="mono muted">{e.time}</span>
                </motion.li>
              ))}
            </ol>
          )}
          {quarantined.length > 0 && (
            <p className="muted" style={{ fontSize: 13, marginTop: 12 }}>
              Quarantined: {quarantined.map((f) => humanReason(f.reason)).join(", ")}. <Link to="/studio/inventory" className="btn-quiet">Inspect</Link>
            </p>
          )}
        </Panel>

        <Panel title="Releases" aside={<span className="muted" style={{ fontSize: 12.5 }}>{health ? "local engine connected" : "engine offline: demo only"}</span>} bodyClass="">
          <div className="table-wrap">
            <table className="data">
              <thead><tr><th>Release</th><th>Source</th><th>Verdict</th></tr></thead>
              <tbody>
                {releases.map((r) => (
                  <tr key={r.id} className="clickable" aria-selected={r.id === current.id} tabIndex={0}
                    onClick={() => select(r.id)} onKeyDown={(e) => e.key === "Enter" && select(r.id)}>
                    <td><div style={{ fontWeight: 500 }}>{r.label}</div><div className="mono muted">{when(r.createdAt)}</div></td>
                    <td><SourceTag source={r.source} /></td>
                    <td>{r.status === "complete" ? <VerdictBadge verdict={r.assurance?.status} /> : <StatusBadge status={r.status} />}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>
    </>
  );
}

function timeline(r: ReleaseView) {
  const out: { title: string; detail: string; time: string; tone: string }[] = [];
  out.push({ title: r.source === "live" ? "Files received" : "Release created", detail: r.source === "practice" ? "Organiser practice data" : `${r.source === "demo" ? `${r.assurance?.counts.files_total ?? "–"} synthetic files` : "uploaded from this browser"}`, time: when(r.createdAt), tone: "" });
  if (r.pipeline) {
    out.push({ title: r.pipeline.exit_code === 0 ? "Engine run completed" : "Engine run failed", detail: `${r.pipeline.message} · ${r.pipeline.seconds}s`, time: "main.py", tone: r.pipeline.exit_code === 0 ? "ok" : "bad" });
  }
  const a = r.assurance;
  if (a?.files) {
    const q = a.files.filter((f) => f.status !== "sanitized").length;
    if (q) out.push({ title: `${q} file${q > 1 ? "s" : ""} quarantined`, detail: "never copied to the release", time: "ingest / gate", tone: "warn" });
    out.push({ title: "Independent re-scan", detail: `${a.residual.total} possible residual PII spans in released files`, time: "verify", tone: a.residual.total ? "warn" : "ok" });
    out.push({ title: "Release-wide check", detail: a.release_wide.passed ? "inputs accounted for; report and manifest consistent; secret absent" : a.release_wide.codes.join(", "), time: "verify", tone: a.release_wide.passed ? "ok" : "bad" });
    out.push({ title: `Verdict: ${a.status}`, detail: a.contract.evaluated ? `output contract ${a.contract.ok ? "OK" : "failed"} (organiser validator)` : "organiser validator not available", time: "assurance", tone: a.status === "VERIFIED" ? "ok" : a.status === "BLOCKED" ? "bad" : "warn" });
  }
  return out;
}
