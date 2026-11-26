import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { LocalChip, SourceTag, Wordmark } from "../components/ui";
import { ReadinessBadge } from "../components/ops";
import { when } from "../lib/format";
import { SOURCE_LABEL, useRelease } from "../lib/workspace";
import type { StageId } from "../state/model";

const NAV: { to: string; label: string; stages: StageId[] }[] = [
  { to: "/workspace", label: "Command Centre", stages: [] },
  { to: "/intake", label: "Source Intake", stages: ["intake"] },
  { to: "/identity", label: "Identity Resolution", stages: ["identity"] },
  { to: "/protection", label: "Privacy Protection", stages: ["protection"] },
  { to: "/clinical-integrity", label: "Clinical Integrity", stages: ["clinical"] },
  { to: "/risk", label: "Privacy Risk", stages: ["risk"] },
  { to: "/assurance", label: "Release Assurance", stages: ["verification", "authorisation"] },
];

export default function Shell() {
  const { releases, view, select, health, serverChecked, actions, decisions, readiness } = useRelease();
  const loc = useLocation();
  const reduce = useReducedMotion();
  const open = actions.filter((a) => a.severity !== "info" && (a.blocking || !decisions.reviewed[a.id]));
  return (
    <div className="app">
      <a href="#page" className="skip">Skip to content</a>
      <aside className="sidebar">
        <Wordmark to="/" sub="Workspace" />
        <nav className="side-nav" aria-label="Workspace">
          <div className="side-group">Research release</div>
          {NAV.map((n, i) => {
            const count = n.stages.length ? open.filter((a) => n.stages.includes(a.stage)).length : open.length;
            return (
              <NavLink key={n.to} to={n.to} className={({ isActive }) => (isActive ? "active" : "")}>
                {({ isActive }) => (
                  <>
                    {isActive && <motion.span className="active-bg" layoutId="nav-active" transition={{ duration: reduce ? 0 : 0.25 }} />}
                    <span className="n">{String(i + 1).padStart(2, "0")}</span>
                    <span className="label">{n.label}</span>
                    {count > 0 && <span className="count" aria-label={`${count} open`}>{count}</span>}
                  </>
                )}
              </NavLink>
            );
          })}
        </nav>
        <div className="side-foot">
          <LocalChip label={health ? "Local engine connected" : serverChecked ? "Engine offline · demo only" : "Checking engine…"} />
          <span>{health ? "Releases run on this machine with main.py. Nothing leaves it." : "Start tools/studio/server.py to run real releases."}</span>
        </div>
      </aside>
      <div className="main">
        <div className="topbar">
          <div className="release-picker">
            <label htmlFor="release" className="eyebrow plain">Release</label>
            <select id="release" value={view.id} onChange={(e) => select(e.target.value)}>
              {releases.map((r) => (
                <option key={r.id} value={r.id}>{SOURCE_LABEL[r.source]} · {r.label} · {when(r.createdAt)}</option>
              ))}
            </select>
            <SourceTag source={view.source} />
          </div>
          <ReadinessBadge r={readiness} />
        </div>
        <AnimatePresence mode="wait" initial={false}>
          <motion.main id="page" key={loc.pathname} className="page" tabIndex={-1}
            initial={reduce ? false : { opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={reduce ? undefined : { opacity: 0 }}
            transition={{ duration: 0.22, ease: [0.22, 0.61, 0.36, 1] }}>
            <Outlet />
          </motion.main>
        </AnimatePresence>
      </div>
    </div>
  );
}
