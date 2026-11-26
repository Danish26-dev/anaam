import { motion, useReducedMotion, useScroll, useTransform } from "framer-motion";
import { lazy, Suspense, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import demoFixture from "../fixtures/demo-release.json";
import { LocalChip, Metric, Reveal, Wordmark } from "../components/ui";
import { num, pct } from "../lib/format";
import type { DemoFixture } from "../lib/types";
import { useWorkspace } from "../lib/workspace";
import Pipeline from "./Pipeline";
import Transform from "./Transform";

const Membrane = lazy(() => import("./Membrane"));
const demo = demoFixture as unknown as DemoFixture;
const REPO = "https://github.com/Danish26-dev/anaam";

export default function Landing() {
  const reduce = useReducedMotion();
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const on = () => setScrolled(window.scrollY > 8);
    on();
    window.addEventListener("scroll", on, { passive: true });
    return () => window.removeEventListener("scroll", on);
  }, []);
  const { scrollY } = useScroll();
  const drift = useTransform(scrollY, [0, 600], [0, reduce ? 0 : -40]);
  const rise = (d: number) => ({
    initial: reduce ? false : { opacity: 0, y: 22 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.9, delay: d, ease: [0.22, 0.61, 0.36, 1] as const },
  });

  return (
    <>
      <a href="#main" className="skip">Skip to content</a>
      <header className={`site-nav ${scrolled ? "scrolled" : ""}`}>
        <Wordmark sub="Secret Wards" />
        <nav aria-label="Primary">
          <a href="#problem" className="hide-sm">Problem</a>
          <a href="#how" className="hide-sm">How it works</a>
          <a href="#evidence" className="hide-sm">Evidence</a>
          <LocalChip label="Local" />
          <Link to="/studio" className="btn btn-primary btn-sm">Open Release Studio</Link>
        </nav>
      </header>

      <main id="main">
        {/* ------------------------------------------------------------ 1. hero */}
        <section className="wrap hero">
          <div>
            <motion.span className="eyebrow" {...rise(0.05)}>Privacy firewall for healthcare data</motion.span>
            <motion.h1 {...rise(0.15)} style={{ marginTop: 22 }}>
              Keep the clinical signal. <em>Leave the identity behind.</em>
            </motion.h1>
            <motion.p className="lede" {...rise(0.3)}>
              Hospital records contain information that can advance research, and personal identities that should
              never travel with them. Anaam protects one while preserving the other.
            </motion.p>
            <motion.div className="ctas" {...rise(0.42)}>
              <Link to="/studio" className="btn btn-primary">Open Release Studio <span className="arrow">→</span></Link>
              <a href="#how" className="btn btn-ghost">Explore the Firewall</a>
            </motion.div>
            <motion.div className="meta" {...rise(0.55)}>
              <span><b>Offline</b> · no network at runtime</span>
              <span><b>CPU only</b> · no language models</span>
              <span><b>English · हिन्दी · Hinglish</b></span>
            </motion.div>
          </div>
          <motion.div style={{ y: drift }} initial={reduce ? false : { opacity: 0, scale: 0.97 }}
            animate={{ opacity: 1, scale: 1 }} transition={{ duration: 1.4, delay: 0.2, ease: [0.22, 0.61, 0.36, 1] }}>
            <Suspense fallback={<div className="membrane-stage" />}>
              <Membrane />
            </Suspense>
          </motion.div>
        </section>

        {/* ------------------------------------------------------------ 2. problem */}
        <section className="section" id="problem">
          <div className="wrap">
            <div className="section-head">
              <Reveal>
                <span className="eyebrow">01 · The problem</span>
                <h2>A hospital record carries two things.</h2>
              </Reveal>
              <Reveal delay={0.1}>
                <p>
                  The same lines that hold a diagnosis also hold the person. Deleting whole fields removes the
                  identity, and with it the dates, doses and lab values that make the record useful for research.
                  The work is to separate the two precisely.
                </p>
              </Reveal>
            </div>
            <Reveal className="split">
              <div className="clinical">
                <span className="eyebrow plain">Clinical meaning · keep</span>
                <h3>What research needs</h3>
                <ul>
                  <li><span>Diagnoses</span><span>Dengue fever (A91)</span></li>
                  <li><span>Procedures</span><span>IV fluids, NS 1 L / 8 hrs</span></li>
                  <li><span>Medication</span><span>Paracetamol 650 mg 1-1-1</span></li>
                  <li><span>Lab values</span><span>Platelets 48,000 /cumm</span></li>
                  <li><span>Treatment timeline</span><span>admitted → discharged, 5 days</span></li>
                </ul>
              </div>
              <div className="divider" aria-hidden="true" />
              <div className="identity">
                <span className="eyebrow plain">Personal identity · separate</span>
                <h3>What must not travel</h3>
                <ul>
                  <li><span>Names</span><span>patient, relatives, in two scripts</span></li>
                  <li><span>Phone numbers</span><span>+91 93810 46627</span></li>
                  <li><span>Addresses</span><span>house, mohalla, landmark, village</span></li>
                  <li><span>Patient identifiers</span><span>UHID, Aadhaar, ABHA</span></li>
                  <li><span>Dates and demographics</span><span>DOB + village + age together</span></li>
                </ul>
              </div>
            </Reveal>
            <p className="muted" style={{ fontSize: 12.5, marginTop: 12 }}>Example values are invented.</p>
          </div>
        </section>

        {/* ------------------------------------------------------------ 3. how */}
        <section className="section" id="how">
          <div className="wrap">
            <div className="section-head">
              <Reveal>
                <span className="eyebrow">02 · How Anaam works</span>
                <h2>Six stages, one release.</h2>
              </Reveal>
              <Reveal delay={0.1}>
                <p>
                  Each stage is a module of the command-line engine that the evaluator runs. Follow one record line
                  through them, or select a stage.
                </p>
              </Reveal>
            </div>
            <Reveal><Pipeline /></Reveal>
          </div>
        </section>

        {/* ------------------------------------------------------------ 4. transformation */}
        <section className="section" id="demo">
          <div className="wrap">
            <div className="section-head">
              <Reveal>
                <span className="eyebrow">03 · Before and after</span>
                <h2>The same record, released.</h2>
              </Reveal>
              <Reveal delay={0.1}>
                <p>
                  These files belong to a synthetic demo workspace: three fictional hospitals and five invented
                  patients. The right-hand side is the engine's actual output for them, recorded from a real run.
                </p>
              </Reveal>
            </div>
            <Reveal><Transform examples={demo.examples} /></Reveal>
          </div>
        </section>

        {/* ------------------------------------------------------------ 5. capabilities */}
        <section className="section" id="capabilities">
          <div className="wrap">
            <div className="section-head">
              <Reveal>
                <span className="eyebrow">04 · Capabilities</span>
                <h2>Built and tested, not promised.</h2>
              </Reveal>
              <Reveal delay={0.1}><p>Every capability below is implemented in the repository and covered by its test suite.</p></Reveal>
            </div>
            <div className="caps">
              {CAPS.map((c, i) => (
                <Reveal key={c.title} className="cap" delay={(i % 3) * 0.06}>
                  <span className="where">{c.where}</span>
                  <h3>{c.title}</h3>
                  <p>{c.text}</p>
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        {/* ------------------------------------------------------------ 6. evidence */}
        <section className="section" id="evidence">
          <div className="wrap">
            <div className="section-head">
              <Reveal>
                <span className="eyebrow">05 · Evidence</span>
                <h2>Measured, with the source stated.</h2>
              </Reveal>
              <Reveal delay={0.1}>
                <p>
                  Numbers come from the organiser's practice data and checkers, run locally. They are not results on
                  the hidden evaluation datasets.
                </p>
              </Reveal>
            </div>
            <Evidence />
          </div>
        </section>

        {/* ------------------------------------------------------------ 7. closing */}
        <section className="section closing">
          <div className="wrap">
            <Reveal>
              <h2>Research needs the data. <em>Patients deserve their privacy.</em></h2>
            </Reveal>
            <Reveal delay={0.15}>
              <div className="ctas" style={{ display: "flex", gap: 12, marginTop: 40, flexWrap: "wrap" }}>
                <Link to="/studio" className="btn btn-primary">Enter Anaam <span className="arrow">→</span></Link>
                <Link to="/studio/new" className="btn btn-ghost">Start a release</Link>
              </div>
            </Reveal>
          </div>
        </section>
      </main>

      <footer className="wrap footer">
        <div>
          <Wordmark />
          <p style={{ marginTop: 14 }}>Anaam protects patient identity while preserving the clinical information that makes hospital data valuable for research.</p>
        </div>
        <div><h4>Track</h4><p>Yugaantar DevForge · Track 3, Secret Wards</p></div>
        <div><h4>Technology</h4><p>Python standard library engine · rules, gazetteers, transliteration · React studio served from localhost</p></div>
        <div><h4>Local processing</h4><p>No network calls at runtime. Files never leave this machine.</p>
          <p style={{ marginTop: 8 }}><a href={REPO} rel="noreferrer noopener" target="_blank">Repository</a></p></div>
      </footer>
    </>
  );
}

const CAPS = [
  { where: "src/detection/names.py · transliteration.py", title: "Multilingual PII detection",
    text: "Names, relatives, phones, Aadhaar, ABHA, PAN, hospital IDs, dates and addresses in English, Devanagari and Hinglish, matched across scripts and spellings." },
  { where: "src/identity/*", title: "Cross-file identity resolution",
    text: "Blocking, conflict-aware scoring and constrained clustering link one patient across files and hospitals, and abstain when evidence is weak." },
  { where: "src/privacy/pseudonyms.py", title: "Deterministic pseudonymisation",
    text: "HMAC-SHA256 pseudonyms keyed by the release secret: identical for the same secret, different under another." },
  { where: "src/privacy/date_shift.py", title: "Patient-specific date shifting",
    text: "One secret offset per patient moves every date, so stays and intervals between events remain exact." },
  { where: "src/detection/clinical*.py", title: "Clinical value preservation",
    text: "A clinical shield protects medicines, doses, 1-0-1 schedules, vitals, labs, ICD codes, diagnoses and procedures." },
  { where: "tools/attack_lab/*", title: "Privacy risk evaluation",
    text: "Local approximations of the organiser's attacks: direct exposure, record linkage, profiles, targeted facts, inversion and cross-release." },
  { where: "src/verify/*", title: "Release verification",
    text: "Every file is re-checked for residual PII, clinical loss and structure before publication; the release is checked as a whole." },
  { where: "src/detection/attachments.py · engine.py", title: "Hidden channels",
    text: "PII in file names, CSV headers, JSON keys, metadata and base64 or escaped attachments is found and rewritten." },
  { where: "src/ingest/*", title: "Fail-safe ingestion",
    text: "Truncated, empty, undecodable or unsupported files are quarantined with a reason code and never copied out raw." },
];

function Evidence() {
  const { evidence, serverChecked } = useWorkspace();
  if (!serverChecked) return <div className="evidence-grid" aria-busy="true" style={{ minHeight: 200 }} />;
  if (!evidence) {
    return (
      <div className="panel">
        <div className="state">
          <h3>Not evaluated in this session</h3>
          <p>Measured evidence appears when the local Studio server is running and has built it:
            <span className="mono"> python tools/studio/evidence.py</span>, then <span className="mono">python tools/studio/server.py</span>.</p>
        </div>
      </div>
    );
  }
  const cd = evidence.check_dev;
  const lk = cd.linking;
  return (
    <Reveal>
      <div className="evidence-grid">
        <Metric value={cd.pii ? num(cd.pii.visible) : "–"} unit={cd.pii ? `of ${num(cd.pii.total)}` : undefined} label="personal-data pieces still visible" />
        <Metric value={cd.canaries ? `${cd.canaries.found}` : "–"} unit={cd.canaries ? `of ${cd.canaries.total}` : undefined} label="planted canaries found in the output" />
        <Metric value={cd.medical ? pct(cd.medical.kept, cd.medical.total) : "–"} label={cd.medical ? `medical values kept (${num(cd.medical.kept)} of ${num(cd.medical.total)})` : "medical values kept"} />
        <Metric value={lk ? lk.f05.toFixed(2) : "–"} label={lk ? `linking F0.5 · precision ${lk.precision.toFixed(2)}, recall ${lk.recall.toFixed(2)}` : "linking"} />
        <Metric value={evidence.pipeline.wall_seconds.toFixed(1)} unit="s" label={evidence.pipeline.summary} />
        <Metric value={evidence.release.resources.peak_rss_mb ? evidence.release.resources.peak_rss_mb.toFixed(0) : "–"} unit="MB"
          label={evidence.release.resources.peak_rss_mb ? "peak memory (report.json)" : "peak memory not reported on this OS"} />
        <Metric value={evidence.contract.contract_ok ? "OK" : "FAIL"} label="output contract (organiser's validate_output.py)" />
        <Metric value={evidence.release.status === "VERIFIED" ? "Verified" : evidence.release.status} label="release gate and release-wide checks" />
      </div>
      <div className="provenance">
        <span>Source: {evidence.source_label}</span>
        <span className="mono">measured {new Date(evidence.generated_at).toLocaleString("en-GB")} · commit {evidence.git_commit ?? "unknown"}</span>
      </div>
    </Reveal>
  );
}
