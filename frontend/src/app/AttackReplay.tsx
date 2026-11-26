import { motion, useReducedMotion } from "framer-motion";
import { useState } from "react";
import { Bar, PageHead, Panel, StateBlock } from "../components/ui";
import { num, rate } from "../lib/format";
import type { Evidence } from "../lib/types";
import { useWorkspace } from "../lib/workspace";

interface Row { label: string; base?: number; prot: number; baseText?: string; protText: string; lowerIsBetter: boolean }
interface Scenario {
  code: string; name: string; objective: string; contributed: string[]; note?: string;
  showNote?: (e: Evidence) => boolean; rows: (e: Evidence) => Row[];
}

const SCENARIOS: Scenario[] = [
  { code: "A1", name: "Direct exposure",
    objective: "Search the whole release (every file and file name) for any registry person's full name, phone number or Aadhaar last four digits.",
    contributed: ["Multilingual name and identifier detection, including relatives", "Hidden channels: file names, headers, keys, base64",
      "Typed placeholders and keyed pseudonyms instead of the original values"],
    note: "Analysed on the 11-hit practice run: every remaining hit was an Aadhaar last-4 digit string found inside another number or as a standalone 4-digit value; no full name or phone survived. Re-check if this number changes.",
    rows: (e) => [{ label: "registry people exposed", base: e.attacks.unprotected_baseline.A1.rate, prot: e.attacks.protected.A1.rate,
      baseText: `${e.attacks.unprotected_baseline.A1.exposed} of ${e.attacks.unprotected_baseline.A1.total}`,
      protText: `${e.attacks.protected.A1.exposed} of ${e.attacks.protected.A1.total}`, lowerIsBetter: true }] },
  { code: "A3", name: "Record linkage",
    objective: "Match each released record to the electoral-roll registry on remaining quasi-identifiers (age, gender, place).",
    contributed: ["Age bands", "Village generalisation or suppression for small groups", "Removal of relatives' names and house numbers"],
    rows: (e) => [{ label: "mean probability on the top candidate", base: e.attacks.unprotected_baseline.A3.mean_top_candidate_share,
      prot: e.attacks.protected.A3.mean_top_candidate_share, baseText: e.attacks.unprotected_baseline.A3.mean_top_candidate_share.toFixed(3),
      protText: e.attacks.protected.A3.mean_top_candidate_share.toFixed(3), lowerIsBetter: true }] },
  { code: "A4", name: "Profile re-identification",
    objective: "Pool every record that shares a pseudonym into a profile, then try to single the person out in the registry.",
    contributed: ["Generalisation of age and place", "Abstention: doubtful records stay unlinked"],
    note: "This is the largest remaining privacy risk. Stricter group sizes (10, 20) and 10-year age bands did not lower it; the next step is generalising rare diagnoses and visit dates for small profiles.",
    rows: (e) => [{ label: "profiles confidently re-identified", base: e.attacks.unprotected_baseline.A4.rate, prot: e.attacks.protected.A4.rate,
      baseText: `${e.attacks.unprotected_baseline.A4.reidentified} of ${e.attacks.unprotected_baseline.A4.total}`,
      protText: `${e.attacks.protected.A4.reidentified} of ${e.attacks.protected.A4.total}`, lowerIsBetter: true }] },
  { code: "A5", name: "Targeted known-fact attack",
    objective: "Use known facts about specific people (a visit date, the hospital, sometimes the condition) to find their records, and try to recover a global date shift.",
    contributed: ["Per-patient date offsets: no single shift can be recovered and applied to everyone"],
    note: "When the protected release matches more known facts than the unprotected copy, the likely cause is linking: shared pseudonyms let the attacker pool facts across a patient's records. This needs work in the privacy layer.",
    showNote: (e) => e.attacks.protected.A5.rate > e.attacks.unprotected_baseline.A5.rate,
    rows: (e) => [
      { label: "known facts matched", base: e.attacks.unprotected_baseline.A5.rate, prot: e.attacks.protected.A5.rate,
        baseText: `${e.attacks.unprotected_baseline.A5.found} of ${e.attacks.unprotected_baseline.A5.total}`,
        protText: `${e.attacks.protected.A5.found} of ${e.attacks.protected.A5.total}`, lowerIsBetter: true },
      { label: "global date shift recoverable", base: e.attacks.unprotected_baseline.A5.global_shift_recoverable ? 1 : 0,
        prot: e.attacks.protected.A5.global_shift_recoverable ? 1 : 0,
        baseText: e.attacks.unprotected_baseline.A5.global_shift_recoverable ? "yes" : "no",
        protText: e.attacks.protected.A5.global_shift_recoverable ? "yes" : "no", lowerIsBetter: true }] },
  { code: "A6", name: "Pseudonym inversion",
    objective: "Try to reverse pseudonyms by hashing known names and identifiers without the secret.",
    contributed: ["HMAC-SHA256 keyed by the release secret; the secret never appears in the output"],
    rows: (e) => [{ label: "patients with an invertible pseudonym", prot: e.attacks.A6.checked ? (e.attacks.A6.invertible ?? 0) / e.attacks.A6.checked : 0,
      protText: `${e.attacks.A6.invertible ?? "–"} of ${e.attacks.A6.checked ?? "–"}`, lowerIsBetter: true }] },
  { code: "A7", name: "Cross-release linkability",
    objective: "Compare two releases of the same data made with different secrets and look for pseudonyms or dates that stay the same.",
    contributed: ["Pseudonyms and date offsets are both derived from the release secret"],
    rows: (e) => [
      { label: "stable pseudonyms", prot: e.attacks.A7.pairs ? e.attacks.A7.stable_pseudonyms / e.attacks.A7.pairs : 0,
        protText: `${e.attacks.A7.stable_pseudonyms} of ${num(e.attacks.A7.pairs)}`, lowerIsBetter: true },
      { label: "coincidentally stable dates", prot: e.attacks.A7.pairs ? e.attacks.A7.stable_dates / e.attacks.A7.pairs : 0,
        protText: `${e.attacks.A7.stable_dates} of ${num(e.attacks.A7.pairs)}`, lowerIsBetter: true }] },
];

export default function AttackReplay() {
  const { evidence, current } = useWorkspace();
  const [code, setCode] = useState("A1");
  const reduce = useReducedMotion();
  const sc = SCENARIOS.find((s) => s.code === code)!;

  return (
    <>
      <PageHead eyebrow="Attack replay" title="What an attacker can still learn">
        The project's local attack lab replays the organiser's attack families against the protected release and against
        an unprotected copy of the same files. Approximations for development, not the official scores.
      </PageHead>
      {evidence && current.source !== "practice" && (
        <div className="notice" role="note">
          <span className="tag practice">practice evaluation</span>
          <span>Attacks need the organiser's attacker knowledge, which exists only for the practice data. These results are for
            the practice release, not for the release selected above ({current.label}).</span>
        </div>
      )}
      {!evidence ? (
        <Panel><StateBlock title="Not evaluated in this session">
          Attacks need the organiser's practice attacker files. Run <span className="mono">python tools/studio/evidence.py</span> with the Team Kit next to this repository, then restart the Studio server.
        </StateBlock></Panel>
      ) : (
        <div className="grid-2" style={{ gridTemplateColumns: "minmax(0,0.75fr) minmax(0,1.6fr)" }}>
          <div className="attack-pick" role="group" aria-label="Attack scenarios">
            {SCENARIOS.map((s) => (
              <button key={s.code} aria-pressed={s.code === code} onClick={() => setCode(s.code)}>
                <span className="code">{s.code}</span>
                <strong style={{ fontWeight: 600 }}>{s.name}</strong>
              </button>
            ))}
            <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>Practice data · measured {new Date(evidence.generated_at).toLocaleDateString("en-GB")}</p>
          </div>
          <motion.section key={code} className="panel" initial={reduce ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }}>
            <header className="panel-head"><h2>{sc.code} · {sc.name}</h2><span className="tag practice">practice evaluation</span></header>
            <div className="panel-body"><span className="eyebrow plain">Objective</span><p style={{ marginTop: 8 }}>{sc.objective}</p></div>
            {sc.rows(evidence).map((r) => (
              <div key={r.label} className="compare">
                <div>
                  <span className="eyebrow plain">Unprotected copy</span>
                  {r.base === undefined ? <p className="muted">No baseline: this attack needs pseudonyms or a second release.</p> : <>
                    <div className="metric"><div className="value">{r.baseText}</div><div className="label">{r.label} · {rate(r.base)}</div></div>
                    <Bar value={r.base} max={1} tone="terracotta" />
                  </>}
                </div>
                <div>
                  <span className="eyebrow plain">Anaam release</span>
                  <div className="metric"><div className="value">{r.protText}</div><div className="label">{r.label} · {rate(r.prot)}</div></div>
                  <Bar value={r.prot} max={1} tone={r.base !== undefined && r.prot > r.base ? "terracotta" : ""} />
                  {r.base !== undefined && (
                    r.prot < r.base ? <span className="badge ok">lower than baseline</span>
                      : r.prot > r.base ? <span className="badge bad">higher than baseline</span>
                      : <span className="badge idle">no change</span>
                  )}
                </div>
              </div>
            ))}
            <div className="panel-body" style={{ borderTop: "1px solid var(--line)" }}>
              <span className="eyebrow plain">What contributed</span>
              <ul style={{ margin: "10px 0 0", paddingLeft: 18, display: "grid", gap: 6 }}>{sc.contributed.map((c) => <li key={c}>{c}</li>)}</ul>
              {sc.note && (sc.showNote ? sc.showNote(evidence) : true) && <div className="notice warn" style={{ marginTop: 16 }}>{sc.note}</div>}
            </div>
          </motion.section>
        </div>
      )}
    </>
  );
}
