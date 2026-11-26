import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { lazy, Suspense, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Dialog, ReadinessBadge, StatusDot } from "../components/ops";
import { PageHead, Panel } from "../components/ui";
import { api } from "../lib/api";
import { humanReason } from "../lib/format";
import { useRelease } from "../lib/workspace";
import SceneCanvas from "../three/SceneCanvas";

const ReleaseAssuranceScene = lazy(() => import("../three/scenes/ReleaseAssuranceScene"));

export default function AssurancePage() {
  const { model, view, actions, decisions, readiness, authorise, revokeAuthorisation } = useRelease();
  const [params, setParams] = useSearchParams();
  const nav = useNavigate();
  const reduce = useReducedMotion();
  const [confirming, setConfirming] = useState(false);
  const [ack, setAck] = useState(false);
  const layers = model.layers;
  const selectedId = params.get("layer");
  const selected = layers.find((l) => l.id === selectedId) ?? null;
  const select = (id: string) => {
    const next = new URLSearchParams(params);
    if (id === selectedId) next.delete("layer"); else next.set("layer", id);
    setParams(next, { replace: true });
  };
  const passed = layers.filter((l) => l.status === "passed").length;
  const quarantined = model.files.filter((f) => f.status !== "sanitized");
  const layerActions = selected ? actions.filter((a) => a.route.includes(`layer=${selected.id}`) || a.route.startsWith(selected.route)) : [];
  const open = actions.filter((a) => a.blocking || (a.reviewable && !decisions.reviewed[a.id] && a.severity !== "info"));
  const canAuthorise = readiness.state === "ready";
  const authorised = readiness.state === "authorised";
  const live = view.source === "live" && view.status === "complete";

  return (
    <>
      <PageHead eyebrow="Release assurance" title="Seven checks, then a person decides">
        Every layer below is computed from the engine's own verification output. The stack closes only when all seven pass;
        the release is authorised only when an authorised person confirms it.
      </PageHead>

      <div className="ws-grid">
        <section className="panel scene-panel">
          <header className="panel-head">
            <h2>Verification stack</h2>
            <span className="muted" style={{ fontSize: 12.5 }}>{passed} of {layers.length} layers passed · select a layer</span>
          </header>
          <SceneCanvas label={`Seven verification layers; ${passed} of ${layers.length} passed`} camera={[0, 2.3, 5.0]} target={[0, 0, 0]} fov={36} minHeight={400}
            fallback={<p className="muted">3D view unavailable; the layer list shows the same results.</p>}>
            <Suspense fallback={null}>
              <ReleaseAssuranceScene layers={layers} selected={selectedId} onSelect={select} authorised={authorised} />
            </Suspense>
          </SceneCanvas>
          <ol className="stage-strip layer-strip" aria-label="Verification layers">
            {layers.map((l, i) => (
              <li key={l.id}>
                <button type="button" aria-pressed={selectedId === l.id} onClick={() => select(l.id)}>
                  <span className="mono muted">{String(i + 1).padStart(2, "0")}</span>
                  <span className="name">{l.label}</span>
                  <StatusDot status={l.status} />
                </button>
              </li>
            ))}
          </ol>
        </section>

        <div className="ws-side">
          <AnimatePresence mode="wait">
            <motion.div key={selected?.id ?? "summary"} initial={reduce ? false : { opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0 }} transition={{ duration: 0.2 }}>
              {selected ? (
                <Panel title={selected.label} aside={<StatusDot status={selected.status} />}>
                  <p>{selected.detail}</p>
                  {layerActions.length > 0 && (
                    <ul className="plain-list" style={{ marginTop: 14 }}>
                      {layerActions.map((a) => (
                        <li key={a.id}><strong>{a.title}.</strong> <span className="muted">{a.impact}</span></li>
                      ))}
                    </ul>
                  )}
                  <div style={{ display: "flex", gap: 10, marginTop: 16, flexWrap: "wrap" }}>
                    {selected.route !== "/assurance" && (
                      <button type="button" className="btn btn-primary btn-sm" onClick={() => nav(selected.route)}>Open the evidence <span className="arrow">→</span></button>
                    )}
                    <button type="button" className="btn btn-quiet btn-sm" onClick={() => select(selected.id)}>Back to summary</button>
                  </div>
                </Panel>
              ) : (
                <Panel title="Release readiness" aside={<ReadinessBadge r={readiness} />}>
                  <p>{readiness.detail}.</p>
                  {open.length > 0 ? (
                    <>
                      <p className="muted" style={{ marginTop: 12, fontSize: 13 }}>Open before authorisation:</p>
                      <ul className="plain-list">
                        {open.map((a) => (
                          <li key={a.id}>
                            <Link to={a.route}>{a.title}</Link>
                            {a.blocking && <span className="badge bad" style={{ marginLeft: 8 }}>Blocks release</span>}
                          </li>
                        ))}
                      </ul>
                    </>
                  ) : (
                    <p className="muted" style={{ marginTop: 12, fontSize: 13 }}>No open findings.</p>
                  )}
                </Panel>
              )}
            </motion.div>
          </AnimatePresence>

          <Panel title="Human authorisation">
            {authorised ? (
              <>
                <p><strong>Authorised</strong> in this session at {new Date(decisions.authorisedAt!).toLocaleTimeString("en-GB")}.</p>
                <p className="muted" style={{ fontSize: 12.5, margin: "8px 0 14px" }}>
                  The decision is kept in this browser tab only and is lost on reload. Anaam never authorises a release by itself.
                </p>
                <button type="button" className="btn btn-ghost btn-sm" onClick={revokeAuthorisation}>Revoke authorisation</button>
              </>
            ) : (
              <>
                <p className="muted" style={{ fontSize: 13.5 }}>
                  {canAuthorise ? "Every layer passed and every finding has a recorded review."
                    : readiness.state === "blocked" ? "A blocking issue must be fixed and the release re-run first."
                    : readiness.state === "in_progress" ? "Available when processing and verification finish."
                    : "Review the open findings first; authorisation unlocks when nothing is left open."}
                </p>
                <button type="button" className="btn btn-primary btn-sm" style={{ marginTop: 14 }} disabled={!canAuthorise}
                  onClick={() => { setAck(false); setConfirming(true); }}>
                  Authorise release
                </button>
              </>
            )}
          </Panel>

          <Panel title={`Quarantined (${quarantined.length})`}>
            {quarantined.length === 0 ? <p className="muted">No file was quarantined.</p> : (
              <ul className="plain-list">
                {quarantined.map((f) => (
                  <li key={f.input_sha256}>
                    <Link to={`/intake?file=${encodeURIComponent(f.input_sha256)}`} className="mono" style={{ wordBreak: "break-all" }}>{f.name}</Link>
                    <div className="muted" style={{ fontSize: 13 }}>{humanReason(f.reason)}</div>
                  </li>
                ))}
              </ul>
            )}
            <p className="muted" style={{ fontSize: 12.5, marginTop: 12 }}>Quarantined files are never copied into the release.</p>
          </Panel>

          <Panel title="Release files">
            {live ? (
              <div style={{ display: "grid", gap: 10 }}>
                <a className="btn btn-ghost btn-sm" href={api.fileUrl(view.id, "report.json", true)}>Download report.json</a>
                <a className="btn btn-ghost btn-sm" href={api.fileUrl(view.id, "records.jsonl", true)}>Download records.jsonl</a>
                <Link to="/intake" className="btn btn-quiet btn-sm">Open released files by source</Link>
                <p className="muted" style={{ fontSize: 12.5 }}>Only released output is served. Uploaded inputs were deleted after the run.</p>
              </div>
            ) : (
              <p className="muted" style={{ fontSize: 13 }}>
                Downloads are available for releases run on this machine. This {view.source === "demo" ? "recorded synthetic demo" : "practice evaluation"} keeps summaries only.
              </p>
            )}
          </Panel>
        </div>
      </div>

      <Dialog open={confirming} title="Authorise this release" onClose={() => setConfirming(false)}>
        <form onSubmit={(e) => { e.preventDefault(); if (ack && canAuthorise) { authorise(); setConfirming(false); } }}>
          <p className="muted" style={{ marginBottom: 12 }}>
            <strong style={{ color: "var(--ink)" }}>{view.label}.</strong> {model.counts.released} of {model.counts.files} files,
            {" "}{model.counts.records} records; {passed} of {layers.length} verification layers passed;
            {" "}{Object.keys(decisions.reviewed).length} finding review{Object.keys(decisions.reviewed).length === 1 ? "" : "s"} recorded.
          </p>
          <label className="check-row">
            <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} />
            <span>I am authorised to release this dataset, I have reviewed the findings, and I accept the remaining privacy risk shown on the Privacy Risk screen.</span>
          </label>
          <p className="muted" style={{ fontSize: 12.5, margin: "10px 0 16px" }}>Recorded in this browser tab only; lost on reload.</p>
          <div className="dialog-actions">
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setConfirming(false)}>Cancel</button>
            <button type="submit" className="btn btn-primary btn-sm" disabled={!ack || !canAuthorise}>Authorise release</button>
          </div>
        </form>
      </Dialog>
    </>
  );
}
