import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { lazy, Suspense, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ReviewDialog, StatusDot } from "../components/ops";
import { Metric, PageHead, Panel, StateBlock } from "../components/ui";
import { basename, num } from "../lib/format";
import { useRelease } from "../lib/workspace";
import { prettySource } from "../state/model";
import SceneCanvas from "../three/SceneCanvas";
import { sourceColor } from "../three/palette";
import { scriptLabel } from "./Intake";

const IdentityResolutionScene = lazy(() => import("../three/scenes/IdentityResolutionScene"));
const loc = (l: string) => (l === "doc" ? "document" : l.startsWith("row:") ? `row ${l.slice(4)}` : l.replace(/^\//, "").replace(/\//g, " › "));

export default function IdentityPage() {
  const { model, actions, decisions, review } = useRelease();
  const [params, setParams] = useSearchParams();
  const reduce = useReducedMotion();
  const [src, setSrc] = useState("all");
  const [lang, setLang] = useState("all");
  const status = params.get("status") ?? "all";
  const [sel, setSel] = useState<string | null>(null);
  const [selRec, setSelRec] = useState<string | null>(null);
  const [reviewing, setReviewing] = useState(false);
  const id = model.identity;
  const sourceIndex = useMemo(() => Object.fromEntries(model.sources.map((s, i) => [s.key, i])), [model.sources]);
  const langOf = useMemo(() => Object.fromEntries(model.files.filter((f) => f.output).map((f) => [f.output!, scriptLabel(f.inspection)])), [model.files]);
  const langs = [...new Set(Object.values(langOf))].filter((x) => x !== "–");
  const keep = (r: { sourceKey: string; file: string }) => (src === "all" || r.sourceKey === src) && (lang === "all" || langOf[r.file] === lang);
  const clusters = status === "unlinked" ? [] : id.clusters.map((c) => ({ ...c, records: c.records.filter(keep) })).filter((c) => c.records.length);
  const unlinked = status === "linked" ? [] : id.unlinked.filter(keep);
  const cluster = id.clusters.find((c) => c.pseudonym === sel) ?? null;
  const rec = id.unlinked.find((r) => `${r.file}#${r.loc}` === selRec) ?? null;
  const exception = actions.find((a) => a.id === "identity-exceptions") ?? null;
  const setStatus = (s: string) => setParams(s === "all" ? {} : { status: s }, { replace: true });

  return (
    <>
      <PageHead eyebrow="Identity resolution" title="One patient across hospitals, without the person">
        The engine links records of the same patient across files, scripts and formats under one keyed pseudonym.
        Only pseudonyms, released file names and record positions are shown here.
      </PageHead>
      <section className="panel">
        <div className="metric-row" style={{ borderTop: 0 }}>
          <Metric value={num(id.patients)} label="pseudonymous patients" />
          <Metric value={num(id.linked)} unit={`of ${num(id.records)}`} label="records linked to a patient" />
          <Metric value={num(id.multiSource)} label="patients linked across more than one source" />
          <Metric value={num(id.unlinkedTotal)} label="records released unlinked (engine abstained)" />
          <Metric value={id.linking ? id.linking.f05.toFixed(2) : "–"} label={id.linking ? `linking F0.5 vs answer key · ${id.linking.wrongMerges} wrong merge(s)` : "linking accuracy: not measurable without an answer key"} />
        </div>
      </section>

      <div className="ws-grid">
        <section className="panel scene-panel">
          <header className="panel-head"><h2>Patient relationships</h2>
            <span className="muted" style={{ fontSize: 12.5 }}>{clusters.length > 48 ? "48 largest shown" : `${clusters.length} patients`} · {unlinked.length} unlinked</span></header>
          <div className="filters">
            <label>Source <select className="filter" value={src} onChange={(e) => setSrc(e.target.value)}>
              <option value="all">All sources</option>{model.sources.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}</select></label>
            <label>Language <select className="filter" value={lang} onChange={(e) => setLang(e.target.value)}>
              <option value="all">All</option>{langs.map((l) => <option key={l} value={l}>{l}</option>)}</select></label>
            <div className="chip-row" role="group" aria-label="Link status">
              {["all", "linked", "unlinked"].map((s) => (
                <button type="button" key={s} className={`chip ${status === s ? "on" : ""}`} onClick={() => setStatus(s)}>{s === "all" ? "All" : s === "linked" ? "Linked" : "Unlinked"}</button>
              ))}
            </div>
          </div>
          <SceneCanvas label="Linked patients as hubs with their records; unlinked records in a separate field" camera={[0.5, 3.1, 4.6]} target={[0.4, -0.35, 0]} fov={42} minHeight={420}
            fallback={<p className="muted">3D view unavailable; the lists show the same relationships.</p>}>
            <Suspense fallback={null}>
              <IdentityResolutionScene clusters={clusters} unlinked={unlinked} sourceIndex={sourceIndex} selected={sel} selectedRecord={selRec}
                onCluster={(p) => { setSelRec(null); setSel(p === sel ? null : p); }} onRecord={(k) => { setSel(null); setSelRec(k === selRec ? null : k); }} />
            </Suspense>
          </SceneCanvas>
          <div className="scene-legend">
            <span><i style={{ background: "var(--forest)" }} />linked patient (pseudonym)</span>
            {model.sources.slice(0, 6).map((s, i) => <span key={s.key}><i style={{ background: sourceColor(i), borderRadius: 2 }} />{s.label}</span>)}
            <span><i style={{ background: "#C3CBC4", borderRadius: 2 }} />unlinked record</span>
          </div>
        </section>

        <div className="ws-side">
          <AnimatePresence mode="wait">
            <motion.div key={sel ?? selRec ?? "none"} initial={reduce ? false : { opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}>
              {cluster ? (
                <Panel title="Linked patient" aside={<span className="psn">{cluster.pseudonym}</span>}>
                  <p className="muted" style={{ fontSize: 13, marginBottom: 12 }}>{cluster.records.length} records from {cluster.sources.length} source{cluster.sources.length > 1 ? "s" : ""}.</p>
                  <ul className="detail-list">
                    {cluster.records.map((r) => (
                      <li key={`${r.file}#${r.loc}`}>
                        <i style={{ width: 10, height: 10, borderRadius: 2, background: sourceColor(sourceIndex[r.sourceKey] ?? 0), flex: "none" }} />
                        <span><strong style={{ fontWeight: 600 }}>{prettySource(r.sourceKey)}</strong> · <span className="mono">{basename(r.file)}</span> · {loc(r.loc)}
                          <span className="muted"> · {langOf[r.file] ?? "–"}</span></span>
                      </li>
                    ))}
                  </ul>
                  <p className="muted" style={{ fontSize: 12.5, marginTop: 14 }}>
                    Evidence: the engine links only on a strong identifier, or an exact name plus a supporting clue, and checks for conflicts before
                    every merge. It does not export per-link evidence or a confidence score.
                  </p>
                </Panel>
              ) : rec ? (
                <Panel title="Unlinked record" aside={<StatusDot status="attention" label="engine abstained" />}>
                  <dl className="kv small">
                    <dt>Source</dt><dd>{prettySource(rec.sourceKey)}</dd>
                    <dt>File</dt><dd className="mono">{basename(rec.file)}</dd>
                    <dt>Position</dt><dd>{loc(rec.loc)}</dd>
                    <dt>Released as</dt><dd className="mono">patient: null</dd>
                  </dl>
                  <p className="muted" style={{ fontSize: 13, marginTop: 12 }}>
                    The evidence for this record was not enough to link it safely, so Anaam released it without a patient link rather than risk
                    merging two people. Anaam never merges records from this interface.
                  </p>
                </Panel>
              ) : (
                <Panel title="Select a patient or record">
                  <p className="muted">Select a hub to see the records linked to that patient, or an unlinked record to see why it stands alone.</p>
                </Panel>
              )}
            </motion.div>
          </AnimatePresence>
          {exception && (
            <Panel title="Identity exceptions" aside={decisions.reviewed[exception.id] ? <span className="badge ok">Reviewed</span> : <span className="badge warn">To review</span>}>
              <p style={{ fontSize: 13.5 }}>{exception.title}.</p>
              <p className="muted" style={{ fontSize: 13, marginTop: 6 }}>{exception.affected.join(" · ")}</p>
              <div style={{ display: "flex", gap: 10, marginTop: 12, flexWrap: "wrap" }}>
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => setStatus("unlinked")}>Show unlinked records</button>
                {!decisions.reviewed[exception.id] && <button type="button" className="btn btn-primary btn-sm" onClick={() => setReviewing(true)}>Mark reviewed</button>}
              </div>
            </Panel>
          )}
        </div>
      </div>

      <Panel title={status === "unlinked" ? `Unlinked records (${unlinked.length})` : `Patients (${clusters.length})`} bodyClass="">
        {status === "unlinked" ? (
          unlinked.length === 0 ? <StateBlock title="No unlinked records" /> : (
            <div className="table-wrap" style={{ maxHeight: 420 }}>
              <table className="data">
                <thead><tr><th>Source</th><th>Released file</th><th>Position</th><th>Language</th></tr></thead>
                <tbody>{unlinked.map((r) => (
                  <tr key={`${r.file}#${r.loc}`} className="clickable" tabIndex={0} aria-selected={selRec === `${r.file}#${r.loc}`}
                    onClick={() => { setSel(null); setSelRec(`${r.file}#${r.loc}`); }} onKeyDown={(e) => e.key === "Enter" && setSelRec(`${r.file}#${r.loc}`)}>
                    <td>{prettySource(r.sourceKey)}</td><td className="mono">{basename(r.file)}</td><td>{loc(r.loc)}</td><td>{langOf[r.file] ?? "–"}</td>
                  </tr>))}</tbody>
              </table>
            </div>)
        ) : clusters.length === 0 ? <StateBlock title="No linked patients">No record carries a pseudonym under the current filters.</StateBlock> : (
          <div className="table-wrap" style={{ maxHeight: 420 }}>
            <table className="data">
              <thead><tr><th>Pseudonym</th><th className="r">Records</th><th>Sources</th></tr></thead>
              <tbody>{clusters.map((c) => (
                <tr key={c.pseudonym} className="clickable" tabIndex={0} aria-selected={sel === c.pseudonym}
                  onClick={() => { setSelRec(null); setSel(c.pseudonym); }} onKeyDown={(e) => e.key === "Enter" && setSel(c.pseudonym)}>
                  <td><span className="psn">{c.pseudonym}</span></td><td className="r">{c.records.length}</td>
                  <td>{[...new Set(c.records.map((r) => prettySource(r.sourceKey)))].join(", ")}</td>
                </tr>))}</tbody>
            </table>
          </div>
        )}
      </Panel>
      <ReviewDialog action={exception} open={reviewing} onClose={() => setReviewing(false)}
        onConfirm={(note) => { if (exception) review(exception.id, note); setReviewing(false); }} />
    </>
  );
}
