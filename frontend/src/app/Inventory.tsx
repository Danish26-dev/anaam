import { motion, useReducedMotion } from "framer-motion";
import { useState } from "react";
import { PageHead, Panel, StateBlock, StatusBadge } from "../components/ui";
import { api } from "../lib/api";
import { ext, humanReason, num } from "../lib/format";
import { useWorkspace } from "../lib/workspace";
import { useFileName } from "./Overview";

export default function Inventory() {
  const { current } = useWorkspace();
  const a = current.assurance;
  const name = useFileName(current);
  const [sel, setSel] = useState<string | null>(null);
  const reduce = useReducedMotion();
  if (!a) return <Panel><StateBlock title="Not evaluated">This release has no file results yet.</StateBlock></Panel>;
  const files = [...a.files].sort((x, y) => (x.status === y.status ? 0 : x.status === "sanitized" ? 1 : -1));
  const f = files.find((x) => x.input_sha256 === sel) ?? null;
  const example = current.examples?.find((e) => e.output === f?.output);

  return (
    <>
      <PageHead eyebrow="Data inventory" title="What came in, and what was released">
        Every input file is accounted for by its SHA-256. Released files carry new, PII-free names; quarantined files are
        never copied out. {current.source === "live" && "Original file names are shown only in this browser tab."}
      </PageHead>
      <div className="grid-2">
        <Panel title={`${num(a.counts.files_total)} files`} bodyClass=""
          aside={<span className="muted" style={{ fontSize: 12.5 }}>{num(a.counts.files_sanitized)} released · {num(a.counts.files_quarantined)} quarantined</span>}>
          <div className="table-wrap">
            <table className="data">
              <thead><tr><th>File</th><th>Format</th><th className="r">Records</th><th>Status</th><th className="r">Re-scan</th></tr></thead>
              <tbody>
                {files.map((x, i) => (
                  <motion.tr key={x.input_sha256} className="clickable" tabIndex={0} aria-selected={x.input_sha256 === sel}
                    onClick={() => setSel(x.input_sha256)} onKeyDown={(e) => e.key === "Enter" && setSel(x.input_sha256)}
                    initial={reduce ? false : { opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(i, 20) * 0.02 }}>
                    <td style={{ maxWidth: 360 }}>
                      <div className="mono" style={{ wordBreak: "break-all" }}>{name(x.input_sha256, x.output)}</div>
                      {x.reason && <div className="muted" style={{ fontSize: 12.5 }}>{humanReason(x.reason)}</div>}
                    </td>
                    <td>{ext(x.output ?? current.names[x.input_sha256] ?? "").slice(1) || "–"}</td>
                    <td className="r">{x.status === "sanitized" ? num(x.records) : "–"}</td>
                    <td><StatusBadge status={x.status} /></td>
                    <td className="r">{x.status === "sanitized" ? (x.residual ? <span className="badge warn">{x.residual}</span> : <span className="badge ok">clean</span>) : "–"}</td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>

        <Panel title="File summary" aside={f && <StatusBadge status={f.status} />}>
          {!f ? (
            <StateBlock title="Select a file">Its processing summary appears here. Raw input content is never shown.</StateBlock>
          ) : (
            <div style={{ display: "grid", gap: 18 }}>
              <dl className="kv">
                <dt>Input</dt><dd className="mono" style={{ wordBreak: "break-all" }}>{current.names[f.input_sha256] ?? "name not known to this browser"}</dd>
                <dt>SHA-256</dt><dd className="mono">{f.input_sha256.slice(0, 24)}…</dd>
                <dt>Released as</dt><dd className="mono" style={{ wordBreak: "break-all" }}>{f.output ?? "not released"}</dd>
                {f.reason && <><dt>Reason</dt><dd>{humanReason(f.reason)} <span className="mono muted">({f.reason})</span></dd></>}
                {f.status === "sanitized" && <>
                  <dt>Records</dt><dd className="num">{num(f.records)}</dd>
                  <dt>Clinical values</dt><dd className="num">{num(f.clinical_kept)} of {num(f.clinical_before)} kept</dd>
                  <dt>Re-scan</dt><dd>{f.residual ? `${f.residual} span(s) to review` : "no residual PII found"}</dd>
                  <dt>Structure</dt><dd>{f.structure.length ? f.structure.join(", ") : "valid"}</dd>
                </>}
              </dl>
              {f.status === "sanitized" && f.output && current.source === "live" && (
                <a className="btn btn-ghost btn-sm" href={api.fileUrl(current.id, f.output)} target="_blank" rel="noreferrer">Open released file</a>
              )}
              {example && (
                <pre className="mono" style={{ margin: 0, padding: 14, background: "var(--limestone)", borderRadius: 6, maxHeight: 320, overflow: "auto", fontSize: 12, whiteSpace: "pre-wrap" }}>
                  {example.after}
                </pre>
              )}
              {f.status === "sanitized" && current.source !== "live" && !example && (
                <p className="muted" style={{ fontSize: 13 }}>Released content is viewable for local releases; this {current.source === "demo" ? "recorded demo" : "practice"} view keeps counts only.</p>
              )}
            </div>
          )}
        </Panel>
      </div>
    </>
  );
}
