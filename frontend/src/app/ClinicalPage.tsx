import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { lazy, Suspense, useState } from "react";
import { ReviewDialog, StatusDot } from "../components/ops";
import { Metric, PageHead, Panel, StateBlock } from "../components/ui";
import { num, pct } from "../lib/format";
import { useRelease } from "../lib/workspace";
import SceneCanvas from "../three/SceneCanvas";

const ClinicalPreservationScene = lazy(() => import("../three/scenes/ClinicalPreservationScene"));
export const CAT_LABEL: Record<string, string> = {
  MEDICATION: "Medication", DOSE: "Dose", FREQUENCY: "Schedule (1-0-1)", VITAL: "Vitals (incl. blood pressure)", LAB: "Laboratory values",
  DIAGNOSIS: "Diagnoses", DIAGNOSIS_CODE: "ICD codes", PROCEDURE: "Procedures", COMPLAINT: "Complaints",
  HISTORY: "History", EPONYM: "Eponyms", DOCTOR: "Treating doctor",
};

/** A synthetic before/after line pair from the recorded demo output, for the linked example. */
function examplePair(examples: { before: string; after: string }[] | undefined, re: RegExp) {
  for (const e of examples ?? []) {
    const b = e.before.split("\n"), a = e.after.split("\n");
    const i = b.findIndex((l) => re.test(l));
    if (i >= 0) {
      const j = a.findIndex((l) => l.includes(b[i].match(/BP [\d/]+ mmHg/)?.[0] ?? "\u0000"));
      return { before: b[i], after: j >= 0 ? a[j] : "" };
    }
  }
  return null;
}

export default function ClinicalPage() {
  const { model, actions, decisions, review } = useRelease();
  const reduce = useReducedMotion();
  const [sel, setSel] = useState<string | null>(null);
  const [reviewing, setReviewing] = useState(false);
  const a = model.assurance;
  if (!a) return <Panel><StateBlock title="Not evaluated">This release has no clinical comparison yet.</StateBlock></Panel>;
  const cats = a.clinical.by_category;
  const cat = cats.find((c) => c.category === sel) ?? null;
  const kit = model.evidence?.check_dev.medical;
  const pair = examplePair(model.view.examples, /sahab ka BP/);
  const lossFiles = model.files.filter((f) => f.clinical_kept < f.clinical_before);
  const lossAction = actions.find((x) => x.id === "clinical-loss") ?? null;
  const resultOf = (c: { before: number; kept: number }) => (c.before === 0 ? "not_evaluated" : c.kept < c.before ? "failed" : "passed");

  return (
    <>
      <PageHead eyebrow="Clinical integrity" title="The identity is protected. The blood pressure stays.">
        Every clinical value the engine detects in an input file is compared with the released file. Exact preservation is shown
        separately from the transformations the privacy layer is permitted to make.
      </PageHead>
      {pair && (
        <section className="panel pair">
          <div><span className="eyebrow plain">Before · synthetic nursing note</span><p className="mono">{pair.before.split("Arif sahab")[0]}<mark className="hl-id">Arif sahab</mark>{pair.before.split("Arif sahab").slice(1).join("Arif sahab")}</p></div>
          <div className="pair-arrow" aria-hidden="true">→</div>
          <div><span className="eyebrow plain">After · released by the engine</span><p className="mono">{pair.after.split(/(\[PATIENT\]|BP [\d/]+ mmHg)/).map((t, i) =>
            t === "[PATIENT]" ? <span key={i} className="ph">{t}</span> : /^BP /.test(t) ? <mark key={i} className="hl-clin">{t}</mark> : t)}</p></div>
          <p className="muted pair-note">The patient's identity is protected; the blood pressure is preserved exactly. Recorded engine output on invented data.</p>
        </section>
      )}
      <section className="panel">
        <div className="metric-row" style={{ borderTop: 0 }}>
          <Metric value={a.clinical.before ? pct(a.clinical.kept, a.clinical.before) : "–"} label={`kept exactly (${num(a.clinical.kept)} of ${num(a.clinical.before)}, engine's clinical detector)`} />
          {kit ? <Metric value={pct(kit.kept, kit.total)} label={`organiser's medical probes kept (${num(kit.kept)} of ${num(kit.total)})`} /> : <Metric value="–" label="organiser's medical probes: not evaluated for this release" />}
          <Metric value={num(lossFiles.length)} label="files with a changed clinical value" />
          <Metric value={num(a.counts.records_generalized)} label="records with permitted generalisation" />
        </div>
      </section>
      <div className="ws-grid">
        <section className="panel scene-panel">
          <header className="panel-head"><h2>Clinical preservation</h2><span className="muted" style={{ fontSize: 12.5 }}>one column per category · select one</span></header>
          <SceneCanvas label="Columns for each clinical category: values found and values kept" camera={[0, 2.2, 6.6]} target={[0, 0, 0]} fov={40} minHeight={360}
            fallback={<p className="muted">3D view unavailable; the table shows the same results.</p>}>
            <Suspense fallback={null}><ClinicalPreservationScene cats={cats} selected={sel} onSelect={(c) => setSel(c === sel ? null : c)} /></Suspense>
          </SceneCanvas>
          <div className="scene-legend">
            <span><i style={{ background: "#E3ECE6", border: "1px solid var(--sage)", borderRadius: 2 }} />found in inputs (log scale)</span>
            <span><i style={{ background: "var(--forest)", borderRadius: 2 }} />unchanged in the release</span>
            <span><i style={{ background: "var(--terracotta)", borderRadius: 2 }} />changed or lost</span>
          </div>
        </section>
        <div className="ws-side">
          <AnimatePresence mode="wait">
            <motion.div key={sel ?? "none"} initial={reduce ? false : { opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}>
              <Panel title={cat ? CAT_LABEL[cat.category] ?? cat.category : "Permitted transformations"}>
                {cat ? (
                  <dl className="kv small">
                    <dt>Found in inputs</dt><dd>{num(cat.before)}</dd>
                    <dt>Unchanged</dt><dd>{num(cat.kept)}</dd>
                    <dt>Result</dt><dd><StatusDot status={resultOf(cat)} label={resultOf(cat) === "passed" ? "exact preservation" : resultOf(cat) === "failed" ? "failed validation" : "not evaluated"} /></dd>
                  </dl>
                ) : (
                  <dl className="kv small">
                    <dt><StatusDot status="complete" label="Exact" /></dt><dd>Medicines, doses, schedules, vitals, labs, diagnoses, ICD codes, procedures</dd>
                    <dt><StatusDot status="attention" label="Shifted" /></dt><dd>Dates move by one secret per-patient offset; intervals and stays stay exact</dd>
                    <dt><StatusDot status="attention" label="Banded" /></dt><dd>Ages become 5-year bands containing the true age</dd>
                    <dt><StatusDot status="attention" label="Generalised" /></dt><dd>Rare villages lift to tehsil or district, or are suppressed</dd>
                  </dl>
                )}
              </Panel>
            </motion.div>
          </AnimatePresence>
          {lossAction && (
            <Panel title="Clinical validation" aside={decisions.reviewed[lossAction.id] ? <span className="badge ok">Reviewed</span> : <span className="badge warn">To review</span>}>
              <p style={{ fontSize: 13.5 }}>{lossAction.title}.</p>
              {!decisions.reviewed[lossAction.id] && <button type="button" className="btn btn-primary btn-sm" style={{ marginTop: 12 }} onClick={() => setReviewing(true)}>Mark reviewed</button>}
            </Panel>
          )}
        </div>
      </div>
      <Panel title="By category" bodyClass="">
        <div className="table-wrap">
          <table className="data">
            <thead><tr><th>Category</th><th className="r">Found</th><th className="r">Unchanged</th><th>Result</th></tr></thead>
            <tbody>{cats.map((c) => (
              <tr key={c.category} className="clickable" tabIndex={0} aria-selected={sel === c.category} onClick={() => setSel(c.category)} onKeyDown={(e) => e.key === "Enter" && setSel(c.category)}>
                <td>{CAT_LABEL[c.category] ?? c.category}</td><td className="r">{num(c.before)}</td><td className="r">{num(c.kept)}</td>
                <td><StatusDot status={resultOf(c)} label={resultOf(c) === "passed" ? "exact preservation" : resultOf(c) === "failed" ? "failed validation" : "not evaluated"} /></td>
              </tr>))}</tbody>
          </table>
        </div>
      </Panel>
      <ReviewDialog action={lossAction} open={reviewing} onClose={() => setReviewing(false)}
        onConfirm={(note) => { if (lossAction) review(lossAction.id, note); setReviewing(false); }} />
    </>
  );
}
