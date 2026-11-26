import { motion, useReducedMotion } from "framer-motion";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import type { Source, Verdict } from "../lib/types";
import { SOURCE_LABEL } from "../lib/workspace";

export function Glyph({ className = "glyph" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="7" fill="#204B42" />
      <path d="M9 23.5 16 8l7 15.5" stroke="#F2F0E8" strokeWidth="2.2" fill="none" strokeLinejoin="round" />
      <path d="M11.6 18h8.8" stroke="#B87552" strokeWidth="2.2" strokeLinecap="round" />
    </svg>
  );
}

export function Wordmark({ to = "/", sub }: { to?: string; sub?: string }) {
  return (
    <Link to={to} className="wordmark" aria-label="Anaam home">
      <Glyph />
      <span>Anaam</span>
      {sub && <small>{sub}</small>}
    </Link>
  );
}

export function LocalChip({ label = "Runs locally · offline" }: { label?: string }) {
  return (
    <span className="local-chip">
      <i aria-hidden="true" />
      {label}
    </span>
  );
}

const VERDICT_CLASS: Record<string, string> = {
  VERIFIED: "ok", "VERIFICATION REQUIRED": "warn", BLOCKED: "bad",
};
export function VerdictBadge({ verdict }: { verdict?: Verdict | null }) {
  if (!verdict) return <span className="badge idle">Not evaluated</span>;
  return <span className={`badge ${VERDICT_CLASS[verdict]}`}>{verdict}</span>;
}

export function StatusBadge({ status }: { status: string }) {
  const cls =
    status === "sanitized" || status === "complete" ? "ok"
      : status === "quarantined" ? "warn"
      : status === "failed" ? "bad"
      : ["queued", "running", "verifying"].includes(status) ? "run" : "idle";
  return <span className={`badge ${cls}`}>{status}</span>;
}

export function SourceTag({ source }: { source: Source }) {
  return <span className={`tag ${source}`}>{SOURCE_LABEL[source]}</span>;
}

export function Panel({ title, aside, children, className = "", bodyClass = "panel-body" }: {
  title?: ReactNode; aside?: ReactNode; children: ReactNode; className?: string; bodyClass?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      {title && (
        <header className="panel-head">
          <h2>{title}</h2>
          {aside}
        </header>
      )}
      <div className={bodyClass}>{children}</div>
    </section>
  );
}

export function Metric({ value, unit, label }: { value: ReactNode; unit?: string; label: ReactNode }) {
  return (
    <div className="metric">
      <div className="value">
        {value}
        {unit && <small>{unit}</small>}
      </div>
      <div className="label">{label}</div>
    </div>
  );
}

export function Bar({ value, max, tone = "" }: { value: number; max: number; tone?: string }) {
  const w = max > 0 ? Math.min(100, (100 * value) / max) : 0;
  return (
    <div className={`bar ${tone}`} role="img" aria-label={`${value} of ${max}`}>
      <span style={{ width: `${w}%` }} />
    </div>
  );
}

export function StateBlock({ title, children, action, center }: {
  title: string; children?: ReactNode; action?: ReactNode; center?: boolean;
}) {
  return (
    <div className={`state ${center ? "center" : ""}`}>
      <h3>{title}</h3>
      {children && <p>{children}</p>}
      {action}
    </div>
  );
}

export function Skeleton({ h = 14, w = "100%" }: { h?: number; w?: number | string }) {
  return <div className="skeleton" style={{ height: h, width: w }} aria-hidden="true" />;
}

/** Fade-and-rise on first view; no motion when the user prefers reduced motion. */
export function Reveal({ children, delay = 0, y = 18, className }: {
  children: ReactNode; delay?: number; y?: number; className?: string;
}) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial={reduce ? false : { opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.7, delay, ease: [0.22, 0.61, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}

export function PageHead({ eyebrow, title, children, aside }: {
  eyebrow: string; title: string; children?: ReactNode; aside?: ReactNode;
}) {
  return (
    <header className="page-head">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        {children && <p>{children}</p>}
      </div>
      {aside}
    </header>
  );
}
