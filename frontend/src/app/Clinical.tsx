import { motion, useReducedMotion } from "framer-motion";
import { Bar, Metric, PageHead, Panel, StateBlock } from "../components/ui";
import { num, pct } from "../lib/format";
import { useWorkspace } from "../lib/workspace";
import { useFileName } from "./Overview";

const CAT_LABEL: Record<string, string> = {
  MEDICATION: "Medication", DOSE: "Dose", FREQUENCY: "Schedule (1-0-1)", VITAL: "Vitals", LAB: "Lab values",
  DIAGNOSIS: "Diagnoses", DIAGNOSIS_CODE: "ICD codes", PROCEDURE: "Procedures", COMPLAINT: "Complaints",
  HISTORY: "History", EPONYM: "Eponyms", DOCTOR: "Treating doctor",
};

// Lines from the recorded synthetic output that show exact preservation and permitted change.
const PAIRS: { label: string; kind: "exact" | "transformed"; match: RegExp }[] = [
  { label: "Diagnosis + ICD code", kind: "exact", match: /^Diagnosis:/ },
  { label: "Medicine, dose, schedule", kind: "exact", match: /Paracetamol 650 mg 1-1-1/ },
  { label: "Vitals", kind: "exact", match: /^At discharge:/ },
  { label: "Lab value", kind: "exact", match: /^Course:/ },
  { label: "Admission date", kind: "transformed", match: /^Date of admission/ },
  { label: "Discharge date", kind: "transformed", match: /^Date of discharge/ },
];

export default function Clinical() {
  const { current } = useWorkspace();
  const a = current.assurance;
  const name = useFileName(current);
  const reduce = useReducedMotion();
  if (!a) return <Panel><StateBlock title="Not evaluated">No clinical comparison for this release.</StateBlock></Panel>;
  const c = a.clinical;
  const max = Math.max(1, ...c.by_category.map((x) => x.before));
  const kit = current.source === "practice" ? current.evidence?.check_dev.medical : undefined;
  const ex = current.examples?.find((e) => e.input_name.includes("discharge"));
  const lost = c.by_category.filter((x) => x.kept < x.before);

  return (
    <>
      <PageHead eyebrow="Clinical integrity" title="Medical meaning survives the release">
        Clinical values detected in each input file are compared with the released file. Exact preservation is separated
        from the transformations the privacy layer is allowed to make.
      </PageHead>

      <section className="panel">
        <header className="panel-head"><h2>Preservation</h2>
          {lost.length ? <span className="badge warn">{lost.length} categor{lost.length > 1 ? "ies" : "y"} with loss</span> : c.before ? <span className="badge ok">no loss detected</span> : <span className="badge idle">nothing to compare</span>}
        </header>
        <div className="metric-row">
          <Metric value={c.before ? pct(c.kept, c.before) : "–"} label={`clinical values kept exactly (${num(c.kept)} of ${num(c.before)}, engine's clinical detector)`} />
          {kit && <Metric value={pct(kit.kept, kit.total)} label={`organiser's medical probes kept (${num(kit.kept)} of ${num(kit.total)}, check_dev)`} />}
          <Metric value={num(a.counts.records_generalized)} label="records with truthful generalisation (age band, place)" />
          <Metric value={num(a.counts.records_suppressed)} label="records suppressed" />
        </div>
      </section>

      <div className="grid-2">
        <Panel title="By category" aside={<span className="muted" style={{ fontSize: 12.5 }}>kept / found in inputs</span>}>
          {c.by_category.length === 0 ? <StateBlock title="No clinical values found" /> : (
            <div style={{ display: "grid", gap: 14 }}>
              {c.by_category.map((x, i) => (
                <motion.div key={x.category} initial={reduce ? false : { opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.03 }}
                  style={{ display: "grid", gridTemplateColumns: "150px 1fr 110px", gap: 14, alignItems: "center", fontSize: 13.5 }}>
                  <span>{CAT_LABEL[x.category] ?? x.category}</span>
                  <div style={{ display: "grid", gap: 4 }}>
                    <Bar value={x.before} max={max} tone="copper" />
                    <Bar value={x.kept} max={max} tone={x.kept < x.before ? "terracotta" : ""} />
                  </div>
                  <span className="mono r" style={{ textAlign: "right" }}>{num(x.kept)} / {num(x.before)}</span>
                </motion.div>
              ))}
              <p className="muted" style={{ fontSize: 12.5 }}>Upper bar: values found in the inputs. Lower bar: still present, unchanged, in the release.</p>
            </div>
          )}
        </Panel>

        <Panel title="Exact versus permitted change">
          <dl className="kv" style={{ gridTemplateColumns: "max-content 1fr" }}>
            <dt><span className="badge ok">exact</span></dt><dd>Medicines, doses, schedules, vitals, labs, diagnoses, ICD codes, procedures, treating doctor.</dd>
            <dt><span className="badge warn">shifted</span></dt><dd>Every date of a patient moves by the same secret offset, so lengths of stay and intervals are exact.</dd>
            <dt><span className="badge warn">banded</span></dt><dd>Ages become 5-year bands that always contain the true age.</dd>
            <dt><span className="badge warn">generalised</span></dt><dd>Villages lift to tehsil or district, or are suppressed, when too few patients share them.</dd>
          </dl>
        </Panel>
      </div>

      {ex ? (
        <Panel title="Recorded example · synthetic discharge summary" aside={<span className="tag demo">synthetic data · real engine output</span>} bodyClass="">
          <div className="table-wrap">
            <table className="data">
              <thead><tr><th>Field</th><th>Before</th><th>After</th><th>Result</th></tr></thead>
              <tbody>
                {PAIRS.map((p) => {
                  const b = ex.before.split("\n").find((l) => p.match.test(l)) ?? "";
                  const af = ex.after.split("\n").find((l) => p.match.test(l) || (p.kind === "transformed" && l.startsWith(b.split(":")[0]))) ?? "";
                  const same = b.trim() === af.trim();
                  return (
                    <tr key={p.label}>
                      <td>{p.label}</td>
                      <td className="mono" style={{ fontSize: 12.5 }}>{b.trim()}</td>
                      <td className="mono" style={{ fontSize: 12.5 }}>{af.trim()}</td>
                      <td>{same ? <span className="badge ok">exact</span> : p.kind === "transformed" ? <span className="badge warn">shifted</span> : <span className="badge bad">changed</span>}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Panel>
      ) : (
        <Panel title="Per file" bodyClass="">
          <div className="table-wrap">
            <table className="data">
              <thead><tr><th>Released file</th><th className="r">Clinical values</th><th className="r">Kept</th></tr></thead>
              <tbody>
                {a.files.filter((f) => f.status === "sanitized" && f.clinical_before > 0).slice(0, 40).map((f) => (
                  <tr key={f.input_sha256}>
                    <td className="mono">{name(f.input_sha256, f.output)}</td>
                    <td className="r">{num(f.clinical_before)}</td>
                    <td className="r">{f.clinical_kept === f.clinical_before ? <span className="badge ok">{num(f.clinical_kept)}</span> : <span className="badge bad">{num(f.clinical_kept)}</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
    </>
  );
}
