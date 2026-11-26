import { motion, useReducedMotion } from "framer-motion";
import { useMemo, useState } from "react";
import { Metric, PageHead, Panel, StateBlock } from "../components/ui";
import { basename, num } from "../lib/format";
import type { Cluster } from "../lib/types";
import { useWorkspace } from "../lib/workspace";

const locLabel = (loc: string) => (loc === "doc" ? "document" : loc.startsWith("row:") ? `row ${loc.slice(4)}` : loc.replace(/^\//, "").replace(/\//g, " › "));
const source = (file: string) => file.replace(/^sanitized\//, "").split("/")[0].replace(/_/g, " ");

export default function Identity() {
  const { current } = useWorkspace();
  const a = current.assurance;
  const clusters = a?.identity.clusters ?? [];
  const [sel, setSel] = useState<string | null>(null);
  const cluster = clusters.find((c) => c.pseudonym === sel) ?? clusters[0];
  const multi = clusters.filter((c) => new Set(c.records.map((r) => r.file)).size > 1).length;
  const lk = current.source === "practice" ? current.evidence?.check_dev.linking : undefined;
  if (!a) return <Panel><StateBlock title="Not evaluated">No identity results for this release.</StateBlock></Panel>;

  return (
    <>
      <PageHead eyebrow="Identity explorer" title="One patient across files, without the person">
        The engine links records of the same patient and gives them one keyed pseudonym. Names, phone numbers and
        identifiers are never shown here: only pseudonyms, released file names and record positions.
      </PageHead>
      <section className="panel">
        <div className="metric-row" style={{ borderTop: 0 }}>
          <Metric value={num(a.identity.patients)} label="pseudonymous patients" />
          <Metric value={num(a.identity.linked_records)} unit={`of ${num(a.identity.records)}`} label="records carrying a pseudonym" />
          <Metric value={num(multi)} label="patients linked across more than one file" />
          {lk ? <Metric value={lk.f05.toFixed(2)} label={`linking F0.5 vs the organiser's answer key · ${lk.wrong_merges} wrong merge${lk.wrong_merges === 1 ? "" : "s"}`} />
            : <Metric value="–" label="linking accuracy: not measurable without an answer key" />}
        </div>
      </section>

      {clusters.length === 0 ? (
        <Panel><StateBlock title="No linked patients">No record in this release carries a pseudonym. Unlinked records are released with <span className="mono">patient: null</span>.</StateBlock></Panel>
      ) : (
        <div className="grid-2">
          <Panel title="Linked records" aside={cluster && <span className="psn">{cluster.pseudonym}</span>}>
            {cluster && <Graph cluster={cluster} />}
            <p className="muted" style={{ fontSize: 12.5, marginTop: 12 }}>
              Match confidence: the engine links only on a strong identifier, or an exact name plus a supporting clue, and
              does not export a score. Records without enough evidence stay unlinked.
            </p>
          </Panel>
          <Panel title={`Patients (${clusters.length}${clusters.length === 200 ? "+" : ""})`} bodyClass="">
            <div className="table-wrap" style={{ maxHeight: 560 }}>
              <table className="data">
                <thead><tr><th>Pseudonym</th><th className="r">Records</th><th className="r">Files</th></tr></thead>
                <tbody>
                  {clusters.map((c) => (
                    <tr key={c.pseudonym} className="clickable" tabIndex={0} aria-selected={c.pseudonym === cluster?.pseudonym}
                      onClick={() => setSel(c.pseudonym)} onKeyDown={(e) => e.key === "Enter" && setSel(c.pseudonym)}>
                      <td><span className="psn">{c.pseudonym}</span></td>
                      <td className="r">{c.records.length}</td>
                      <td className="r">{new Set(c.records.map((r) => r.file)).size}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </div>
      )}
    </>
  );
}

function Graph({ cluster }: { cluster: Cluster }) {
  const reduce = useReducedMotion();
  const files = useMemo(() => {
    const m = new Map<string, string[]>();
    for (const r of cluster.records) m.set(r.file, [...(m.get(r.file) ?? []), r.loc]);
    return [...m.entries()];
  }, [cluster]);
  const W = 560, H = 380, cx = W / 2, cy = H / 2, R = 132;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${cluster.pseudonym} linked to ${files.length} files`} style={{ width: "100%", height: "auto" }}>
      {files.map(([file, locs], i) => {
        const ang = (i / files.length) * Math.PI * 2 - Math.PI / 2;
        const x = cx + Math.cos(ang) * R * 1.45, y = cy + Math.sin(ang) * R;
        return (
          <g key={file}>
            <motion.line x1={cx} y1={cy} x2={x} y2={y} stroke="#204B42" strokeOpacity="0.35" strokeWidth={1 + Math.min(3, locs.length)}
              initial={reduce ? false : { pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.6, delay: 0.1 + i * 0.08 }} />
            <motion.g initial={reduce ? false : { opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.35 + i * 0.08 }}
              style={{ transformOrigin: `${x}px ${y}px` }}>
              <rect x={x - 92} y={y - 30} width="184" height="60" rx="6" fill="#FBFAF6" stroke="#D9D9D0" />
              <text x={x} y={y - 10} textAnchor="middle" fontSize="10" fill="#68746D" style={{ letterSpacing: "0.08em", textTransform: "uppercase" }}>{source(file).slice(0, 28)}</text>
              <text x={x} y={y + 6} textAnchor="middle" fontSize="11.5" fill="#1D2926" fontFamily="var(--mono)">{basename(file).slice(0, 26)}</text>
              <text x={x} y={y + 21} textAnchor="middle" fontSize="10.5" fill="#204B42">{locs.slice(0, 2).map(locLabel).join(", ")}{locs.length > 2 ? ` +${locs.length - 2}` : ""}</text>
            </motion.g>
          </g>
        );
      })}
      <circle cx={cx} cy={cy} r="46" fill="#204B42" />
      <circle cx={cx} cy={cy} r="52" fill="none" stroke="#B87552" strokeWidth="1.5" />
      <text x={cx} y={cy - 4} textAnchor="middle" fontSize="10" fill="#AAB8A9" style={{ letterSpacing: "0.1em" }}>PATIENT</text>
      <text x={cx} y={cy + 12} textAnchor="middle" fontSize="10" fill="#F2F0E8" fontFamily="var(--mono)">{cluster.pseudonym.slice(0, 12)}…</text>
    </svg>
  );
}
