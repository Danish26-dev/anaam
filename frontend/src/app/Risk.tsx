import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { lazy, Suspense, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ReviewDialog } from "../components/ops";
import { Bar, PageHead, Panel, StateBlock } from "../components/ui";
import { num, rate } from "../lib/format";
import type { Evidence } from "../lib/types";
import { useRelease } from "../lib/workspace";
import SceneCanvas from "../three/SceneCanvas";

const RiskLandscapeScene = lazy(() => import("../three/scenes/RiskLandscapeScene"));

interface Scenario {
  code: string; name: string; unit: string; objective: string; contributed: string[]; investigate: string;
  get: (e: Evidence) => { total: number; base?: number; prot: number; baseText?: string; protText: string; note?: string };
}
const SCENARIOS: Scenario[] = [
  { code: "A1", name: "Direct exposure", unit: "registry people",
    objective: "Search every released file and file name for any registry person's full name, phone number or Aadhaar last four digits.",
    contributed: ["Multilingual name and identifier detection", "Hidden channels: file names, headers, keys, base64", "Typed placeholders and keyed pseudonyms"],
    investigate: "Confirm that remaining hits are coincidental 4-digit matches, not identifiers.",
    get: (e) => ({ total: e.attacks.protected.A1.total, base: e.attacks.unprotected_baseline.A1.exposed, prot: e.attacks.protected.A1.exposed,
      baseText: `${e.attacks.unprotected_baseline.A1.exposed} of ${e.attacks.unprotected_baseline.A1.total}`, protText: `${e.attacks.protected.A1.exposed} of ${e.attacks.protected.A1.total}`,
      note: "On the analysed practice run every remaining hit was an Aadhaar last-4 digit string inside another number or standing alone; no full name or phone survived." }) },
  { code: "A3", name: "Record linkage", unit: "released records",
    objective: "Match each released record to the electoral-roll registry on remaining quasi-identifiers (age, gender, place).",
    contributed: ["Age bands", "Village generalisation or suppression for small groups", "Removal of relatives' names and house numbers"],
    investigate: "Check which quasi-identifiers still allow a registry candidate for the remaining records.",
    get: (e) => ({ total: e.attacks.protected.A3.total, base: e.attacks.unprotected_baseline.A3.records_with_candidate, prot: e.attacks.protected.A3.records_with_candidate,
      baseText: `${e.attacks.unprotected_baseline.A3.records_with_candidate} of ${e.attacks.unprotected_baseline.A3.total}`,
      protText: `${e.attacks.protected.A3.records_with_candidate} of ${e.attacks.protected.A3.total}`,
      note: `Mean probability on the top candidate among those: ${e.attacks.unprotected_baseline.A3.mean_top_candidate_share.toFixed(2)} → ${e.attacks.protected.A3.mean_top_candidate_share.toFixed(2)}.` }) },
  { code: "A4", name: "Profile re-identification", unit: "assessed profiles",
    objective: "Pool every record that shares a pseudonym into a profile, then try to single the person out in the registry.",
    contributed: ["Generalisation of age and place", "Abstention: doubtful records stay unlinked"],
    investigate: "Generalise rare diagnoses and coarsen visit dates for small profiles (planned engine change).",
    get: (e) => ({ total: e.attacks.protected.A4.total, base: Math.round(e.attacks.unprotected_baseline.A4.rate * e.attacks.protected.A4.total), prot: e.attacks.protected.A4.reidentified,
      baseText: `${e.attacks.unprotected_baseline.A4.reidentified} of ${e.attacks.unprotected_baseline.A4.total}`, protText: `${e.attacks.protected.A4.reidentified} of ${e.attacks.protected.A4.total}`,
      note: "Stricter group sizes (10, 20) and 10-year age bands did not lower this; the remaining risk is in combined visit dates, diagnoses and hospital." }) },
  { code: "A5", name: "Targeted known-fact attack", unit: "known facts",
    objective: "Use known facts about specific people (a visit date, the hospital, sometimes the condition) to find their records, and try to recover a global date shift.",
    contributed: ["Per-patient date offsets: no single shift can be recovered"],
    investigate: "Assess how linking lets facts be pooled per patient; the fix belongs in the privacy layer.",
    get: (e) => ({ total: e.attacks.protected.A5.total, base: e.attacks.unprotected_baseline.A5.found, prot: e.attacks.protected.A5.found,
      baseText: `${e.attacks.unprotected_baseline.A5.found} of ${e.attacks.unprotected_baseline.A5.total}${e.attacks.unprotected_baseline.A5.global_shift_recoverable ? " · global shift recoverable" : ""}`,
      protText: `${e.attacks.protected.A5.found} of ${e.attacks.protected.A5.total}${e.attacks.protected.A5.global_shift_recoverable ? " · global shift RECOVERABLE" : " · global shift not recoverable"}`,
      note: e.attacks.protected.A5.found > e.attacks.unprotected_baseline.A5.found ? "More facts are matched on the protected release: shared pseudonyms let an attacker pool facts across one patient's records." : undefined }) },
  { code: "A6", name: "Pseudonym inversion", unit: "pseudonymised patients",
    objective: "Try to reverse pseudonyms by hashing known names and identifiers without the secret.",
    contributed: ["HMAC-SHA256 keyed by the release secret"], investigate: "None needed while the count is zero.",
    get: (e) => ({ total: e.attacks.A6.checked ?? 0, prot: e.attacks.A6.invertible ?? 0, protText: `${e.attacks.A6.invertible ?? "–"} of ${e.attacks.A6.checked ?? "–"}` }) },
  { code: "A7", name: "Cross-release linkability", unit: "record pairs",
    objective: "Compare two releases made with different secrets and look for pseudonyms or dates that stay the same.",
    contributed: ["Pseudonyms and date offsets are both derived from the release secret"], investigate: "None needed while counts stay near zero.",
    get: (e) => ({ total: e.attacks.A7.pairs, prot: Math.max(e.attacks.A7.stable_pseudonyms, e.attacks.A7.stable_dates),
      protText: `${e.attacks.A7.stable_pseudonyms} stable pseudonyms · ${e.attacks.A7.stable_dates} coincident dates of ${num(e.attacks.A7.pairs)}` }) },
];

export default function Risk() {
  const { evidence, view, actions, decisions, review } = useRelease();
  const [params, setParams] = useSearchParams();
  const reduce = useReducedMotion();
  const code = params.get("scenario") ?? "A4";
  const sc = SCENARIOS.find((s) => s.code === code) ?? SCENARIOS[2];
  const [mode, setMode] = useState<"protected" | "baseline">("protected");
  const [reviewing, setReviewing] = useState<string | null>(null);
  const relatedAction = actions.find((a) => a.id === `risk-${sc.code.toLowerCase()}`) ?? null;

  if (!evidence) {
    return (
      <>
        <PageHead eyebrow="Privacy risk" title="What an attacker can still learn" />
        <Panel><StateBlock title="Not evaluated in this session">Attack replay needs the organiser's practice attacker files. Run
          <span className="mono"> python tools/studio/evidence.py</span> with the Team Kit next to this repository, then restart the Studio server.</StateBlock></Panel>
      </>
    );
  }
  const r = sc.get(evidence);
  const showBase = mode === "baseline" && r.base !== undefined;
  return (
    <>
      <PageHead eyebrow="Privacy risk" title="Removing names is not enough">
        An attacker holding a voter list can still combine age, place, visit dates and a rare diagnosis to single someone out. The
        project's local attack lab replays the organiser's attack families on the protected release and on an unprotected copy of the
        same files. Development approximations, not official scores.
      </PageHead>
      {view.source !== "practice" && (
        <div className="notice" role="note"><span className="tag practice">practice evaluation</span>
          <span>Attacks need the organiser's attacker knowledge, which exists only for the practice data. These results are for the practice release, not for the release selected above.</span></div>
      )}
      <div className="ws-grid">
        <section className="panel scene-panel">
          <header className="panel-head"><h2>{sc.code} · {sc.name}</h2>
            <div className="chip-row" role="group" aria-label="Release compared">
              <button type="button" className={`chip ${mode === "baseline" ? "on" : ""}`} disabled={r.base === undefined} onClick={() => setMode("baseline")}>Unprotected copy</button>
              <button type="button" className={`chip ${mode === "protected" ? "on" : ""}`} onClick={() => setMode("protected")}>Anaam release</button>
            </div>
          </header>
          <SceneCanvas label={`${num(r.total)} ${sc.unit}; raised markers are those the attack succeeded on`} camera={[0, 4.2, 5.4]} target={[0, -0.4, 0]} fov={40} minHeight={360}
            fallback={<p className="muted">3D view unavailable; the numbers alongside are the same.</p>}>
            <Suspense fallback={null}><RiskLandscapeScene total={r.total} exposed={showBase ? r.base! : r.prot} /></Suspense>
          </SceneCanvas>
          <p className="scene-note">One marker per {sc.unit.replace(/s$/, "")} ({num(r.total)}). Raised terracotta markers: the attack succeeded ({showBase ? r.baseText : r.protText}).
            Markers are not positioned by any patient attribute.</p>
          <div className="filters" role="group" aria-label="Attack scenarios">
            {SCENARIOS.map((s) => (
              <button type="button" key={s.code} className={`chip ${s.code === sc.code ? "on" : ""}`} onClick={() => { setParams({ scenario: s.code }, { replace: true }); setMode("protected"); }}>
                {s.code} · {s.name}
              </button>
            ))}
          </div>
        </section>
        <div className="ws-side">
          <AnimatePresence mode="wait">
            <motion.div key={sc.code} initial={reduce ? false : { opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}>
              <Panel title="Attack result" aside={<span className="tag practice">practice data</span>}>
                <p style={{ fontSize: 13.5 }}>{sc.objective}</p>
                <div style={{ display: "grid", gap: 14, marginTop: 16 }}>
                  {r.base !== undefined && (
                    <div><div className="eyebrow plain">Unprotected copy</div><div className="metric"><div className="value" style={{ fontSize: 28 }}>{r.baseText}</div></div>
                      <Bar value={r.base} max={Math.max(1, r.total)} tone="terracotta" /></div>
                  )}
                  <div><div className="eyebrow plain">Anaam release</div><div className="metric"><div className="value" style={{ fontSize: 28 }}>{r.protText}</div>
                    <div className="label">{rate(r.total ? r.prot / r.total : 0)} of {sc.unit}</div></div>
                    <Bar value={r.prot} max={Math.max(1, r.total)} tone={r.base !== undefined && r.prot > r.base ? "terracotta" : ""} />
                    {r.base !== undefined && (r.prot < r.base ? <span className="badge ok" style={{ marginTop: 8 }}>lower than the unprotected copy</span>
                      : r.prot > r.base ? <span className="badge bad" style={{ marginTop: 8 }}>higher than the unprotected copy</span> : <span className="badge idle" style={{ marginTop: 8 }}>no change</span>)}
                  </div>
                </div>
                {r.note && <div className="notice warn" style={{ marginTop: 16 }}>{r.note}</div>}
              </Panel>
            </motion.div>
          </AnimatePresence>
          <Panel title="What contributed">
            <ul style={{ margin: 0, paddingLeft: 18, display: "grid", gap: 6, fontSize: 13.5 }}>{sc.contributed.map((c) => <li key={c}>{c}</li>)}</ul>
            <p style={{ fontSize: 13.5, marginTop: 12 }}><strong>Recommended investigation:</strong> {sc.investigate}</p>
            {relatedAction && !decisions.reviewed[relatedAction.id] && (
              <button type="button" className="btn btn-primary btn-sm" style={{ marginTop: 12 }} onClick={() => setReviewing(relatedAction.id)}>Mark this risk reviewed</button>
            )}
            {relatedAction && decisions.reviewed[relatedAction.id] && <span className="badge ok" style={{ marginTop: 12 }}>Reviewed</span>}
          </Panel>
        </div>
      </div>
      <ReviewDialog action={actions.find((a) => a.id === reviewing) ?? null} open={!!reviewing} onClose={() => setReviewing(null)}
        onConfirm={(note) => { if (reviewing) review(reviewing, note); setReviewing(null); }} />
    </>
  );
}
