// Operational components shared by every workspace screen: action cards, the review dialog,
// readiness, and the stage strip (the accessible DOM counterpart of the 3D release scene).
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import type { ActionItem, Readiness, Severity } from "../state/actions";
import type { Stage, StageId } from "../state/model";
import { STATUS_LABEL, statusColor } from "../three/palette";

const SEV_LABEL: Record<Severity, string> = { critical: "Critical", warning: "Warning", attention: "Attention", info: "Info", ready: "Ready" };
export const SEV_CLASS: Record<Severity, string> = { critical: "bad", warning: "warn", attention: "warn", info: "idle", ready: "ok" };

export function SeverityBadge({ s }: { s: Severity }) {
  return <span className={`badge ${SEV_CLASS[s]}`}>{SEV_LABEL[s]}</span>;
}

export function StatusDot({ status, label }: { status: string; label?: string }) {
  return (
    <span className="status-dot">
      <i style={{ background: statusColor(status as never) }} aria-hidden="true" />
      {label ?? STATUS_LABEL[status] ?? status}
    </span>
  );
}

/** Modal dialog: focus moves in, Escape closes, focus returns to the opener. */
export function Dialog({ open, title, onClose, children }: { open: boolean; title: string; onClose: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const reduce = useReducedMotion();
  useEffect(() => {
    if (!open) return;
    const opener = document.activeElement as HTMLElement | null;
    const t = window.setTimeout(() => ref.current?.querySelector<HTMLElement>("textarea, input, button")?.focus(), 30);
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => { window.clearTimeout(t); document.removeEventListener("keydown", onKey); opener?.focus?.(); };
  }, [open, onClose]);
  return (
    <AnimatePresence>
      {open && (
        <motion.div className="dialog-backdrop" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
          <motion.div ref={ref} className="dialog" role="dialog" aria-modal="true" aria-labelledby={titleId}
            initial={reduce ? false : { opacity: 0, y: 12, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={reduce ? undefined : { opacity: 0, y: 8 }} transition={{ duration: 0.22 }}>
            <h2 id={titleId}>{title}</h2>
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/** Records that a person reviewed a finding. The finding stays visible, marked as reviewed. */
export function ReviewDialog({ action, open, onClose, onConfirm }: {
  action: ActionItem | null; open: boolean; onClose: () => void; onConfirm: (note: string) => void;
}) {
  return (
    <Dialog open={open && !!action} title="Record your review" onClose={onClose}>
      {/* The form mounts with each opening, so every review starts empty (no reset effect racing the user's typing). */}
      {action && <ReviewForm action={action} onClose={onClose} onConfirm={onConfirm} />}
    </Dialog>
  );
}

function ReviewForm({ action, onClose, onConfirm }: { action: ActionItem; onClose: () => void; onConfirm: (note: string) => void }) {
  const [note, setNote] = useState("");
  return (
        <form onSubmit={(e) => { e.preventDefault(); if (note.trim()) onConfirm(note.trim()); }}>
          <p className="muted" style={{ marginBottom: 12 }}><strong style={{ color: "var(--ink)" }}>{action.title}.</strong> {action.impact}</p>
          <label htmlFor="review-note" className="field-label">What did you check, and what did you decide?</label>
          <textarea id="review-note" value={note} onChange={(e) => setNote(e.target.value)} rows={4} maxLength={500}
            placeholder="e.g. Opened the released file; decoded text reads correctly." />
          <p className="muted" style={{ fontSize: 12.5, margin: "8px 0 16px" }}>
            Do not enter patient details. The note is kept in this browser tab only and is lost on reload.
          </p>
          <div className="dialog-actions">
            <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary btn-sm" disabled={!note.trim()}>Record review</button>
          </div>
        </form>
  );
}

/** One operations-queue item with its full context. */
export function ActionCard({ a, reviewed, onReview, onUnreview, compact = false, index = 0 }: {
  a: ActionItem; reviewed?: { at: string; note: string }; onReview?: () => void; onUnreview?: () => void; compact?: boolean; index?: number;
}) {
  const nav = useNavigate();
  const reduce = useReducedMotion();
  return (
    <motion.article className={`action ${reviewed ? "reviewed" : ""}`} layout={!reduce}
      initial={reduce ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
      transition={{ duration: 0.3, delay: Math.min(index, 8) * 0.04 }}>
      <header>
        <SeverityBadge s={a.severity} />
        <span className="mono muted">{a.stage}</span>
        {a.blocking && <span className="badge bad">Blocks release</span>}
        {reviewed && <span className="badge ok">Reviewed</span>}
      </header>
      <h3>{a.title}</h3>
      {!compact && <p className="why">{a.why}</p>}
      <dl className="kv small">
        <dt>Affected</dt><dd>{a.affected.join(" · ")}</dd>
        <dt>Impact</dt><dd>{a.impact}</dd>
        {!compact && <><dt>After</dt><dd>{a.after}</dd></>}
        {reviewed && <><dt>Review</dt><dd>{reviewed.note} <span className="mono muted">({new Date(reviewed.at).toLocaleTimeString("en-GB")})</span></dd></>}
      </dl>
      <footer>
        <button type="button" className="btn btn-primary btn-sm" onClick={() => nav(a.route)}>{a.recommendation} <span className="arrow">→</span></button>
        {a.reviewable && !reviewed && onReview && <button type="button" className="btn btn-ghost btn-sm" onClick={onReview}>Mark reviewed</button>}
        {reviewed && onUnreview && <button type="button" className="btn btn-quiet btn-sm" onClick={onUnreview}>Reopen</button>}
      </footer>
    </motion.article>
  );
}

export function ReadinessBadge({ r }: { r: Readiness }) {
  const cls = r.state === "ready" || r.state === "authorised" ? "ok" : r.state === "blocked" || r.state === "failed" ? "bad"
    : r.state === "in_progress" ? "run" : r.state === "not_evaluated" ? "idle" : "warn";
  return <span className={`badge ${cls}`} title={r.detail}>{r.label}</span>;
}

/** The release lifecycle as a DOM strip; selecting a stage mirrors selecting its 3D gate. */
export function StageStrip({ stages, selected, onSelect, highlight }: {
  stages: Stage[]; selected: StageId | null; onSelect: (id: StageId) => void; highlight?: StageId | null;
}) {
  return (
    <ol className="stage-strip" aria-label="Release lifecycle">
      {stages.map((s, i) => (
        <li key={s.id}>
          <button type="button" aria-pressed={selected === s.id} onClick={() => onSelect(s.id)}
            className={highlight === s.id ? "hl" : ""}>
            <span className="mono">{String(i + 1).padStart(2, "0")}</span>
            <span className="name">{s.label}</span>
            <StatusDot status={s.status} />
          </button>
        </li>
      ))}
    </ol>
  );
}
