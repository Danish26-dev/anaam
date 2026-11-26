import { motion, useInView, useReducedMotion } from "framer-motion";
import { useEffect, useRef, useState } from "react";

type Kind = "name" | "phone" | "dob" | "id" | "clin" | "text";
interface Tok { raw: string; kind: Kind; out?: string }

// One invented record line, the same one the stages transform.
const LINE: Tok[] = [
  { raw: "Ritika Venkataraman", kind: "name", out: "PSN-E9F0PBB84CGVN519" },
  { raw: "·", kind: "text" },
  { raw: "+91 93810 46627", kind: "phone", out: "[PHONE]" },
  { raw: "·", kind: "text" },
  { raw: "DOB 14/03/1987", kind: "dob", out: "DOB 27/10/1986" },
  { raw: "·", kind: "text" },
  { raw: "UHID SHY-2026-00418", kind: "id", out: "UHID [ID]" },
  { raw: "·", kind: "text" },
  { raw: "Dengue fever (A91)", kind: "clin" },
  { raw: "·", kind: "text" },
  { raw: "Paracetamol 650 mg 1-1-1", kind: "clin" },
];

const STAGES = [
  { key: "INGEST", title: "Ingest", where: "src/ingest",
    text: "Every file is sniffed, decoded and parsed into records. Empty, truncated or unsupported files are quarantined, never copied out." },
  { key: "DETECT", title: "Detect", where: "src/detection",
    text: "The clinical shield runs first, then names, IDs, dates and addresses in English, Hindi and Hinglish, including file names, headers, keys and base64." },
  { key: "RESOLVE", title: "Resolve", where: "src/identity",
    text: "Records of one patient are linked across files on a strong identifier, or an exact name plus a supporting clue. Doubtful links stay apart." },
  { key: "PROTECT", title: "Protect", where: "src/privacy",
    text: "Identifiers become typed placeholders or one keyed pseudonym. Every date of a patient moves by one secret offset; ages band; rare places generalise." },
  { key: "PRESERVE", title: "Preserve", where: "clinical shield",
    text: "Diagnoses, doses, schedules, vitals and labs are kept exactly as written, and intervals between a patient's dates stay exact." },
  { key: "VERIFY", title: "Verify", where: "src/verify",
    text: "An independent gate re-reads every output file and then the whole release. A file that fails is quarantined; nothing unverified is published." },
];

function tokenClass(t: Tok, stage: number): string {
  if (t.kind === "text") return "muted";
  const identity = t.kind !== "clin";
  if (stage === 0) return "";
  if (identity) return stage >= 3 ? (t.kind === "name" ? "psn" : t.kind === "dob" ? "hl-date" : "ph") : "hl-id";
  return stage >= 1 ? "hl-clin" : "";
}

export default function Pipeline() {
  const [stage, setStage] = useState(0);
  const [auto, setAuto] = useState(true);
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { margin: "-120px" });
  const reduce = useReducedMotion();

  useEffect(() => {
    if (!auto || !inView || reduce) return;
    const t = window.setTimeout(() => setStage((s) => (s + 1) % STAGES.length), 3400);
    return () => window.clearTimeout(t);
  }, [stage, auto, inView, reduce]);

  const pick = (i: number) => { setAuto(false); setStage(i); };

  return (
    <div ref={ref}>
      <div className="pipeline" role="tablist" aria-label="How Anaam processes a release">
        {STAGES.map((s, i) => (
          <button key={s.key} className="stage" role="tab" aria-selected={i === stage} aria-current={i === stage}
            onClick={() => pick(i)}>
            <span className="idx">{String(i + 1).padStart(2, "0")} · {s.key}</span>
            <h3>{s.title}</h3>
            <p>{s.text}</p>
            <span className="mono muted" style={{ marginTop: "auto", fontSize: 11.5 }}>{s.where}</span>
            {i === stage && (
              <motion.span className="fill" layoutId="stage-fill"
                initial={{ width: auto && !reduce ? "0%" : "100%" }} animate={{ width: "100%" }}
                transition={{ duration: auto && !reduce ? 3.4 : 0.3, ease: "linear" }} />
            )}
            {i < stage && <span className="fill" style={{ width: "100%", opacity: 0.25 }} />}
          </button>
        ))}
      </div>

      <div className="panel" style={{ marginTop: 18 }}>
        <div className="panel-head">
          <h3>One record line, at stage {stage + 1}: {STAGES[stage].title.toLowerCase()}</h3>
          <span className="tag demo">Synthetic example</span>
        </div>
        <div className="panel-body" aria-live="polite">
          <p style={{ font: "14px/2.2 var(--mono)", display: "flex", flexWrap: "wrap", gap: "4px 10px", alignItems: "center" }}>
            {LINE.map((t, i) => {
              const shown = stage >= 3 && t.out ? t.out : t.raw;
              return (
                <motion.span key={`${i}-${shown}-${tokenClass(t, stage)}`} className={tokenClass(t, stage)}
                  initial={reduce ? false : { opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.35, delay: t.kind === "text" ? 0 : 0.03 * i }}>
                  {shown}
                </motion.span>
              );
            })}
            {stage === 2 && (
              <motion.span className="tag practice" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                linked: registration row 0 · OPD visit 0 · discharge summary
              </motion.span>
            )}
            {stage === 5 && (
              <motion.span className="badge ok" initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }}>
                passed release gate
              </motion.span>
            )}
          </p>
          <p className="muted" style={{ fontSize: 13, marginTop: 10 }}>{STAGE_NOTE[stage]}</p>
        </div>
      </div>
    </div>
  );
}

const STAGE_NOTE = [
  "Raw text as it arrives: identity and clinical meaning are mixed in one line.",
  "Copper marks identity; green marks clinical values the shield protects from being mistaken for identifiers.",
  "The same patient appears in three files at two hospitals; the engine's evidence links them.",
  "The name becomes the patient's keyed pseudonym, the phone and ID typed placeholders, the DOB shifts by this patient's offset.",
  "The diagnosis, the ICD code, the dose and the 1-1-1 schedule are untouched.",
  "The released file is re-scanned independently before publication. These are the engine's real outputs for this synthetic patient.",
];
