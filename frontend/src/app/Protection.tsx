import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Suspense, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ReviewDialog, StatusDot } from "../components/ops";
import { PageHead, Panel } from "../components/ui";
import { num } from "../lib/format";
import { useRelease } from "../lib/workspace";
import SceneCanvas from "../three/SceneCanvas";
import PrivacyTransformationScene, { LANES, type Lane } from "../three/scenes/PrivacyTransformationScene";


const CATS: { label: string; lane: Lane; keys: string[]; extra?: "pseudonyms" | "paths" | "keys" }[] = [
  { label: "Personal names", lane: "identity", keys: ["PATIENT", "RELATIVE", "PERSON"], extra: "pseudonyms" },
  { label: "Phone numbers", lane: "identity", keys: ["PHONE"] },
  { label: "Addresses", lane: "identity", keys: ["ADDRESS", "HOUSE", "LOCALITY", "LANDMARK", "VILLAGE", "PIN"] },
  { label: "Patient identifiers", lane: "identity", keys: ["ID", "AADHAAR", "ABHA", "PAN", "INSURANCE-ID", "DOB"] },
  { label: "Filename information", lane: "metadata", keys: [], extra: "paths" },
  { label: "Metadata and attachments", lane: "metadata", keys: ["ATTACHMENT"], extra: "keys" },
];

export default function Protection() {
  const { model, actions, decisions, review, view } = useRelease();
  const [params] = useSearchParams();
  const reduce = useReducedMotion();
  const [lane, setLane] = useState<Lane | null>(null);
  const [reviewing, setReviewing] = useState(false);
  const p = model.assurance?.protection;
  const ph = p?.placeholders ?? {};
  const catCount = (c: typeof CATS[number]) =>
    c.keys.reduce((s, k) => s + (ph[k] ?? 0), 0) + (c.extra === "pseudonyms" ? p?.pseudonym_occurrences ?? 0 : c.extra === "paths" ? p?.paths_renamed ?? 0 : c.extra === "keys" ? p?.keys_renamed ?? 0 : 0);
  const counts: Record<Lane, number> = {
    identity: CATS.filter((c) => c.lane === "identity").reduce((s, c) => s + catCount(c), 0),
    clinical: model.assurance?.clinical.kept ?? 0,
    metadata: CATS.filter((c) => c.lane === "metadata").reduce((s, c) => s + catCount(c), 0),
  };
  const resid = model.files.filter((f) => f.residual > 0);
  const focus = params.get("file");
  const residAction = actions.find((a) => a.id === "residual-pii") ?? null;
  const ev = model.evidence;

  const ops = [
    { name: "Pseudonymisation", value: p ? `${num(p.pseudonym_occurrences)} pseudonym occurrences in released files` : "Not evaluated",
      how: "Linked patients receive one HMAC-SHA256 pseudonym keyed by the release secret; the mapping is never written or shown." },
    { name: "Date shifting", value: ev ? `per-patient offsets; global shift ${ev.attacks.protected.A5.global_shift_recoverable ? "RECOVERABLE" : "not recoverable"} (attack A5)` : "Applied per patient by the engine; not separately counted",
      how: "Every date of a patient moves by one secret offset, so intervals and lengths of stay stay exact." },
    { name: "Generalisation", value: p ? `${num(p.records_generalized)} records generalised` : "Not evaluated",
      how: "Ages become 5-year bands; rare villages lift to tehsil or district, or are suppressed." },
    { name: "Filename protection", value: p ? `${num(p.paths_renamed)} file path${p.paths_renamed === 1 ? "" : "s"} renamed` : "Not evaluated",
      how: "Names and identifiers in file and folder names are replaced with keyed tokens." },
    { name: "Metadata protection", value: p ? `${num(p.keys_renamed)} JSON key${p.keys_renamed === 1 ? "" : "s"} renamed · ${num(ph.ATTACHMENT ?? 0)} attachment${(ph.ATTACHMENT ?? 0) === 1 ? "" : "s"} scrubbed` : "Not evaluated",
      how: "PII in JSON keys, CSV headers and base64 or escaped attachments is found and rewritten." },
  ];

  return (
    <>
      <PageHead eyebrow="Privacy protection" title="Identity is transformed; clinical meaning passes through">
        Counts below are measured in the released files of this release: typed placeholders, pseudonyms, renamed paths and keys.
        Original values and the original-to-pseudonym mapping never appear in Anaam's interface.
      </PageHead>
      <div className="ws-grid">
        <section className="panel scene-panel">
          <header className="panel-head"><h2>Privacy membrane</h2><span className="muted" style={{ fontSize: 12.5 }}>select a lane</span></header>
          <SceneCanvas label="Three lanes of information crossing the privacy membrane" camera={[0, 1.6, 6.2]} target={[0, 0, 0]} fov={40} minHeight={380}
            fallback={<p className="muted">3D view unavailable; the table shows the same counts.</p>}>
            <Suspense fallback={null}>
              <PrivacyTransformationScene counts={counts} selected={lane} onSelect={(l) => setLane(l === lane ? null : l)} attention={resid.length > 0} />
            </Suspense>
          </SceneCanvas>
          <div className="filters" role="group" aria-label="Lanes">
            {LANES.map((l) => (
              <button type="button" key={l.id} className={`chip ${lane === l.id ? "on" : ""}`} onClick={() => setLane(l.id === lane ? null : l.id)}>
                {l.label} · {num(counts[l.id])}
              </button>
            ))}
          </div>
        </section>
        <div className="ws-side">
          <AnimatePresence mode="wait">
            <motion.div key={lane ?? "all"} initial={reduce ? false : { opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}>
              <Panel title={lane ? LANES.find((l) => l.id === lane)!.label : "What was protected"} bodyClass="">
                <table className="data">
                  <tbody>
                    {(lane === "clinical"
                      ? [{ label: "Clinical values kept unchanged", n: counts.clinical, s: "complete" }]
                      : CATS.filter((c) => !lane || c.lane === lane).map((c) => ({ label: c.label, n: catCount(c), s: catCount(c) ? "complete" : "not_evaluated" }))
                    ).map((r) => (
                      <tr key={r.label}><td>{r.label}</td><td className="r num">{num(r.n)}</td><td><StatusDot status={r.s} label={r.n ? "protected" : "none found"} /></td></tr>
                    ))}
                  </tbody>
                </table>
                {lane === "clinical" && <p className="muted" style={{ fontSize: 12.5, padding: "12px 22px" }}>See Clinical Integrity for every category.</p>}
              </Panel>
            </motion.div>
          </AnimatePresence>
          <Panel title="Residual PII verification" aside={resid.length ? <span className="badge warn">{resid.length} file(s)</span> : <span className="badge ok">clean</span>}>
            {resid.length === 0 ? (
              <p className="muted" style={{ fontSize: 13.5 }}>An independent re-scan of every released file found no residual personal data.</p>
            ) : (
              <>
                <ul className="detail-list">
                  {resid.map((f) => <li key={f.input_sha256} style={{ fontWeight: f.input_sha256 === focus ? 600 : 400 }}><span className="mono">{f.output}</span> · {f.residual} span(s)</li>)}
                </ul>
                {residAction && !decisions.reviewed[residAction.id] && (
                  <button type="button" className="btn btn-primary btn-sm" style={{ marginTop: 12 }} onClick={() => setReviewing(true)}>Mark reviewed</button>
                )}
              </>
            )}
          </Panel>
        </div>
      </div>
      <Panel title="Protection operations" bodyClass="">
        <div className="table-wrap">
          <table className="data">
            <thead><tr><th>Operation</th><th>This release</th><th>How</th></tr></thead>
            <tbody>{ops.map((o) => <tr key={o.name}><td style={{ fontWeight: 600, whiteSpace: "nowrap" }}>{o.name}</td><td>{o.value}</td><td className="muted">{o.how}</td></tr>)}</tbody>
          </table>
        </div>
        <p className="muted" style={{ fontSize: 12.5, padding: "12px 22px" }}>
          {view.source === "demo" ? "Synthetic demo: recorded output of the real engine on invented data." : "Counts are computed by the local Studio server from the released files; no values are transferred."}
        </p>
      </Panel>
      <ReviewDialog action={residAction} open={reviewing} onClose={() => setReviewing(false)}
        onConfirm={(note) => { if (residAction) review(residAction.id, note); setReviewing(false); }} />
    </>
  );
}
