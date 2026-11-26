import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { LocalChip, SourceTag, VerdictBadge, Wordmark } from "../components/ui";
import { when } from "../lib/format";
import { SOURCE_LABEL, useWorkspace } from "../lib/workspace";

const NAV = [
  { to: "/studio", label: "Overview", end: true },
  { to: "/studio/new", label: "New Release" },
  { to: "/studio/inventory", label: "Data Inventory" },
  { to: "/studio/clinical", label: "Clinical Integrity" },
  { to: "/studio/identity", label: "Identity Explorer" },
  { to: "/studio/attacks", label: "Attack Replay" },
  { to: "/studio/assurance", label: "Release Assurance" },
];

export default function Shell() {
  const { releases, current, select, health, serverChecked } = useWorkspace();
  const loc = useLocation();
  const reduce = useReducedMotion();
  return (
    <div className="app">
      <a href="#page" className="skip">Skip to content</a>
      <aside className="sidebar">
        <Wordmark to="/" sub="Studio" />
        <nav className="side-nav" aria-label="Studio">
          <div className="side-group">Workspace</div>
          {NAV.map((n, i) => (
            <NavLink key={n.to} to={n.to} end={n.end} className={({ isActive }) => (isActive ? "active" : "")}>
              {({ isActive }) => (
                <>
                  {isActive && <motion.span className="active-bg" layoutId="nav-active" transition={{ duration: reduce ? 0 : 0.25 }} />}
                  <span className="n">{String(i + 1).padStart(2, "0")}</span>
                  {n.label}
                </>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="side-foot">
          <LocalChip label={health ? "Local engine connected" : serverChecked ? "Demo only · engine offline" : "Checking engine…"} />
          <span>{health ? "Files are processed on this machine by main.py." : "Start tools/studio/server.py to run real releases."}</span>
        </div>
      </aside>
      <div className="main">
        <div className="topbar">
          <div className="release-picker">
            <label htmlFor="release" className="eyebrow plain">Release</label>
            <select id="release" value={current.id} onChange={(e) => select(e.target.value)}>
              {releases.map((r) => (
                <option key={r.id} value={r.id}>
                  {SOURCE_LABEL[r.source]} · {r.label} · {when(r.createdAt)}
                </option>
              ))}
            </select>
            <SourceTag source={current.source} />
          </div>
          <VerdictBadge verdict={current.status === "complete" ? current.assurance?.status : null} />
        </div>
        <AnimatePresence mode="wait">
          <motion.main id="page" key={loc.pathname + current.id} className="page"
            initial={reduce ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={reduce ? undefined : { opacity: 0, y: -4 }}
            transition={{ duration: 0.28, ease: [0.22, 0.61, 0.36, 1] }}>
            <Outlet />
          </motion.main>
        </AnimatePresence>
      </div>
    </div>
  );
}
