import { motion, useReducedMotion } from "framer-motion";
import { useMemo, useState } from "react";
import type { DemoFixture } from "../lib/types";

const DATE = /^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$/;
const CLIN = /^(?:\d+(?:[.,]\d+)*\s?(?:mg|g\/dL|mg\/dL|mmHg|\/min|\/cumm|%|units|L|hrs)|\d-\d-\d|[A-Z]\d{2}(?:\.\d+)?|\(A\d+\)|\(E\d+\.\d\)|\(N\d+\.\d\))$/;
const PH = /^\[[A-Z-]+\]$/;
const PSN = /^PSN-[0-9A-Z]+$/;

function tokens(line: string): string[] {
  return line.split(/(\s+|[,;:()]|\s?\/\s)/).filter((t) => t !== "");
}

/** Word-level LCS between two lines: which tokens were removed (before) or added (after). */
function diff(a: string[], b: string[]): [boolean[], boolean[]] {
  const n = a.length, m = b.length;
  const dp = Array.from({ length: n + 1 }, () => new Array<number>(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--)
    dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
  const ka = new Array<boolean>(n).fill(false), kb = new Array<boolean>(m).fill(false);
  let i = 0, j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) { ka[i] = kb[j] = true; i++; j++; }
    else if (dp[i + 1][j] >= dp[i][j + 1]) i++;
    else j++;
  }
  return [ka, kb];
}

function classify(tok: string, kept: boolean, side: "before" | "after"): string {
  if (/^\s+$/.test(tok)) return "";
  if (kept) return CLIN.test(tok) ? "hl-clin" : "";
  if (side === "after") return PSN.test(tok) ? "psn" : PH.test(tok) ? "ph" : DATE.test(tok) ? "hl-date" : "hl-id";
  return DATE.test(tok) ? "hl-date" : "hl-id";
}

function Render({ text, other, side }: { text: string; other: string; side: "before" | "after" }) {
  const lines = text.split("\n");
  const others = other.split("\n");
  return (
    <pre>
      {lines.map((ln, li) => {
        const a = tokens(ln), b = tokens(others[li] ?? "");
        const [ka] = diff(a, b);
        return (
          <span key={li}>
            {a.map((t, ti) => {
              const cls = classify(t, ka[ti], side);
              return cls ? <span key={ti} className={cls}>{t}</span> : t;
            })}
            {"\n"}
          </span>
        );
      })}
    </pre>
  );
}

export default function Transform({ examples }: { examples: DemoFixture["examples"] }) {
  const [i, setI] = useState(0);
  const reduce = useReducedMotion();
  const ex = examples[i];
  const label = useMemo(() => (name: string) =>
    name.includes("discharge") ? "Discharge summary · English" : name.includes("nursing") ? "Nursing note · Hindi / Hinglish" : "Registration export · CSV", []);
  if (!ex) return null;
  return (
    <div>
      <div role="tablist" aria-label="Synthetic example records" style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
        {examples.map((e, k) => (
          <button key={e.input_name} role="tab" aria-selected={k === i}
            className={`btn btn-sm ${k === i ? "btn-primary" : "btn-ghost"}`} onClick={() => setI(k)}>
            {label(e.input_name)}
          </button>
        ))}
      </div>
      <motion.div key={i} className="transform" initial={reduce ? false : { opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45 }}>
        <div className="side">
          <div className="side-head"><span className="eyebrow plain">Before · source record</span><span className="mono muted">{ex.input_name.split("/").pop()}</span></div>
          <Render text={ex.before} other={ex.after} side="before" />
        </div>
        <div className="side">
          <div className="side-head"><span className="eyebrow plain">After · released by Anaam</span><span className="mono muted">{ex.output.split("/").pop()}</span></div>
          <Render text={ex.after} other={ex.before} side="after" />
        </div>
      </motion.div>
      <div className="legend">
        <span><i style={{ background: "rgba(169,79,69,.25)" }} />identity removed</span>
        <span><i style={{ background: "rgba(184,117,82,.25)" }} />typed placeholder</span>
        <span><i style={{ background: "rgba(32,75,66,.18)" }} />keyed pseudonym / clinical value kept</span>
        <span><i style={{ background: "rgba(189,141,67,.3)" }} />date shifted by the patient's offset</span>
        <span className="tag demo">Synthetic data · real engine output</span>
      </div>
    </div>
  );
}
