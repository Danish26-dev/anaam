import { MotionConfig } from "framer-motion";
import { StrictMode, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Link, Route, Routes, useLocation } from "react-router-dom";
import AttackReplay from "./app/AttackReplay";
import Assurance from "./app/Assurance";
import Clinical from "./app/Clinical";
import Identity from "./app/Identity";
import Inventory from "./app/Inventory";
import NewRelease from "./app/NewRelease";
import Overview from "./app/Overview";
import Shell from "./app/Shell";
import { StateBlock } from "./components/ui";
import Landing from "./landing/Landing";
import { WorkspaceProvider } from "./lib/workspace";
import "./styles.css";

function ScrollTop() {
  const { pathname } = useLocation();
  useEffect(() => window.scrollTo(0, 0), [pathname]);
  return null;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <MotionConfig reducedMotion="user">
      <BrowserRouter>
        <WorkspaceProvider>
          <ScrollTop />
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/studio" element={<Shell />}>
              <Route index element={<Overview />} />
              <Route path="new" element={<NewRelease />} />
              <Route path="inventory" element={<Inventory />} />
              <Route path="clinical" element={<Clinical />} />
              <Route path="identity" element={<Identity />} />
              <Route path="attacks" element={<AttackReplay />} />
              <Route path="assurance" element={<Assurance />} />
            </Route>
            <Route path="*" element={<div className="wrap"><StateBlock title="Page not found" action={<Link to="/" className="btn btn-ghost btn-sm">Back to Anaam</Link>} /></div>} />
          </Routes>
        </WorkspaceProvider>
      </BrowserRouter>
    </MotionConfig>
  </StrictMode>,
);
