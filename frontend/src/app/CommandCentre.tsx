import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { lazy, Suspense, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ActionCard, ReadinessBadge, ReviewDialog, SeverityBadge, StageStrip, StatusDot } from "../components/ops";
import { Metric, SourceTag } from "../components/ui";
import { num, when } from "../lib/format";
import { useRelease } from "../lib/workspace";
import type { ActionItem } from "../state/actions";
import type { StageId } from "../state/model";
import SceneCanvas from "../three/SceneCanvas";

const ReleaseOverviewScene = lazy(() => import("../three/scenes/ReleaseOverviewScene"));

export default function CommandCentre() {
  const r = useRelease();
  const { model, actions, decisions, readiness, next, view } = r;
  const nav = useNavigate();
  const reduce = useReducedMotion();
  const [stage, setStage] = useState<StageId | null>(null);
  const [source, setSource] = useState<string | null>(null);
  const [reviewing, setReviewing] = useState<ActionItem | null>(null);
  const selStage = model.stages.find((s) => s.id === stage) ?? null;
  const selSource = model.sources.find((s) => s.key === source) ?? null;
  const current = model.stages.find((s) => s.status === "running") ?? model.stages.find((s) => s.status === "attention" || s.status === "blocked" || s.status === "failed")
    ?? model.stages.find((s) => s.status === "waiting") ?? model.stages[model.stages.length - 1];
  const stageActions = (id: StageId) => actions.filter((a) => a.stage === id);
  const open = actions.filter((a) => a.blocking || !decisions.reviewed[a.id]);
  const done = actions.filter((a) => !a.blocking && decisions.reviewed[a.id]);

  return (
    <>
      {/* A. release overview */}
      <header className="cc-head">
        <div>
          <span className="eyebrow">Research release command centre</span>
          <h1>{view.source === "demo" ? "Synthetic demo release" : view.source === "practice" ? "Practice evaluation release" : view.label}</h1>
          <p className="muted">
            {view.source === "demo" && "Four fictional hospitals, five invented patients, processed by the real engine. Recorded output; nothing here is a real person."}
            {view.source === "practice" && "The organiser's practice data, processed by main.py on this machine and measured with the organiser's checkers."}
            {view.source === "live" && "A release run on this machine. Uploaded inputs were deleted after the run; only the released output is kept."}
          </p>
        </div>
        <div className="cc-head-aside">
          <SourceTag source={view.source} />
          <ReadinessBadge r={readiness} />
        </div>
      </header>
      <section className="panel">
        <div className="metric-row" style={{ borderTop: 0 }}>
          <Metric value={num(model.sources.filter((s) => s.key !== "_unassigned").length) || "–"} label="participating sources" />
          <Metric value={num(model.counts.files)} label={`input files · ${num(model.counts.quarantined)} quarantined`} />
          <Metric value={num(model.counts.records)} label="records processed" />
          <Metric value={<span style={{ fontSize: 22 }}>{current?.label ?? "–"}</span>} label={current ? <StatusDot status={current.status} /> : "stage"} />
          <Metric value={<span style={{ fontSize: 22 }}>{readiness.label}</span>} label={readiness.detail} />
          <Metric value={<span style={{ fontSize: 22 }}>{when(view.createdAt)}</span>} label={`release ${view.id.slice(0, 14)}`} />
        </div>
      </section>

      <div className="cc-grid">
        {/* C. 3D release overview */}
        <section className="panel scene-panel">
          <header className="panel-head">
            <h2>Release lifecycle</h2>
            <span className="muted" style={{ fontSize: 12.5 }}>Select a source or a stage</span>
          </header>
          <SceneCanvas label="Three-dimensional view of the release: hospital sources, record streams and seven stage gates coloured by status"
            camera={[0.3, 3.0, 7.4]} target={[0.2, -0.25, 0]} fov={38} minHeight={400}
            fallback={<p className="muted">3D view unavailable in this browser; the stage list below shows the same states.</p>}>
            <Suspense fallback={null}>
              <ReleaseOverviewScene model={model} selectedStage={stage} selectedSource={source} highlight={next?.stage ?? null}
                onStage={(id) => { setSource(null); setStage(id === stage ? null : id); }}
                onSource={(k) => { setStage(null); setSource(k === source ? null : k); }} />
            </Suspense>
          </SceneCanvas>
          <StageStrip stages={model.stages} selected={stage} highlight={next?.stage ?? null}
            onSelect={(id) => { setSource(null); setStage(id === stage ? null : id); }} />
          <AnimatePresence mode="wait">
            {(selStage || selSource) && (
              <motion.div key={selStage?.id ?? selSource?.key} className="detail" initial={reduce ? false : { opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}>
                {selStage && (
                  <>
                    <div className="detail-head"><h3>{selStage.label}</h3><StatusDot status={selStage.status} /></div>
                    <p>{selStage.summary}</p>
                    {stageActions(selStage.id).length > 0 && (
                      <ul className="detail-list">
                        {stageActions(selStage.id).map((a) => <li key={a.id}><SeverityBadge s={a.severity} /> {a.title}</li>)}
                      </ul>
                    )}
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => nav(selStage.route)}>Open {selStage.label.toLowerCase()} <span className="arrow">→</span></button>
                  </>
                )}
                {selSource && (
                  <>
                    <div className="detail-head"><h3>{selSource.label}</h3><span className="mono muted">{selSource.files.length} files</span></div>
                    <dl className="kv small">
                      <dt>Records released</dt><dd>{num(selSource.records)}</dd>
                      <dt>Formats</dt><dd>{selSource.formats.join(", ") || "–"}</dd>
                      <dt>Scripts</dt><dd>{selSource.scripts.join(", ") || "–"}</dd>
                      <dt>Quarantined</dt><dd>{selSource.quarantined}</dd>
                      {selSource.legacyEncodings.length > 0 && <><dt>Legacy encoding</dt><dd>{selSource.legacyEncodings.join(", ")}</dd></>}
                    </dl>
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => nav(`/intake?source=${encodeURIComponent(selSource.key)}`)}>Open intake for this source <span className="arrow">→</span></button>
                  </>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </section>

        {/* B. next best action */}
        <div className="cc-side">
          <AnimatePresence mode="wait">
            {next ? (
              <motion.section key={next.id} className={`nba nba-${next.severity}`} initial={reduce ? false : { opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.3 }} aria-live="polite">
                <span className="eyebrow plain">Anaam recommends</span>
                <h2>{next.recommendation}</h2>
                <p className="lead">{next.title}.</p>
                <p>{next.why}</p>
                <dl className="kv small">
                  <dt>Affected</dt><dd>{next.affected.join(" · ")}</dd>
                  <dt>Impact</dt><dd>{next.impact}</dd>
                  <dt>Afterwards</dt><dd>{next.after}</dd>
                </dl>
                <div className="nba-actions">
                  <button type="button" className="btn btn-primary" onClick={() => nav(next.route)}>{next.recommendation} <span className="arrow">→</span></button>
                  {next.reviewable && !decisions.reviewed[next.id] && (
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => setReviewing(next)}>Mark reviewed</button>
                  )}
                </div>
              </motion.section>
            ) : (
              <section className="nba"><span className="eyebrow plain">Anaam recommends</span><h2>No action needed</h2></section>
            )}
          </AnimatePresence>
          <section className="panel">
            <header className="panel-head"><h2>Release readiness</h2><ReadinessBadge r={readiness} /></header>
            <div className="panel-body">
              <ul className="readiness-list">
                <li><span>Blocking issues</span><strong className={readiness.blockers ? "bad" : ""}>{readiness.blockers}</strong></li>
                <li><span>Findings to review</span><strong className={readiness.toReview ? "warn" : ""}>{readiness.toReview}</strong></li>
                <li><span>Verification</span><strong>{model.assurance?.status ?? "Not evaluated"}</strong></li>
                <li><span>Authorisation</span><strong>{decisions.authorisedAt ? "Authorised" : "Not authorised"}</strong></li>
              </ul>
              <Link to="/assurance" className="btn btn-quiet btn-sm">Open release assurance</Link>
            </div>
          </section>
        </div>
      </div>

      {/* D. operations queue */}
      <section className="panel">
        <header className="panel-head">
          <h2>Operations queue</h2>
          <span className="muted" style={{ fontSize: 12.5 }}>{open.length} open · {done.length} reviewed · derived from this release's own results</span>
        </header>
        <div className="queue">
          <AnimatePresence initial={false}>
            {open.length === 0 && <p className="muted" style={{ padding: 22 }}>Nothing open. Every finding has a recorded review.</p>}
            {open.map((a, i) => (
              <ActionCard key={a.id} a={a} index={i} onReview={() => setReviewing(a)} />
            ))}
            {done.map((a, i) => (
              <ActionCard key={a.id} a={a} index={i} compact reviewed={decisions.reviewed[a.id]} onUnreview={() => r.unreview(a.id)} />
            ))}
          </AnimatePresence>
        </div>
      </section>
      <ReviewDialog action={reviewing} open={!!reviewing} onClose={() => setReviewing(null)}
        onConfirm={(note) => { if (reviewing) r.review(reviewing.id, note); setReviewing(null); }} />
    </>
  );
}
