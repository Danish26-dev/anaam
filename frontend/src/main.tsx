import { MotionConfig } from "framer-motion";
import { lazy, StrictMode, Suspense, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import Shell from "./app/Shell";
import { StateBlock } from "./components/ui";
import Landing from "./landing/Landing";
import { WorkspaceProvider } from "./lib/workspace";
import "./styles.css";
import "./ops.css";

const CommandCentre = lazy(() => import("./app/CommandCentre"));
const Intake = lazy(() => import("./app/Intake"));
const IdentityPage = lazy(() => import("./app/IdentityPage"));
const Protection = lazy(() => import("./app/Protection"));
const ClinicalPage = lazy(() => import("./app/ClinicalPage"));
const Risk = lazy(() => import("./app/Risk"));
const AssurancePage = lazy(() => import("./app/AssurancePage"));

function ScrollTop() {
  const { pathname } = useLocation();
  // Block body on purpose: window.scrollTo returns a Promise in some browsers, and an effect that
  // returns a non-function crashes React on the next route change.
  useEffect(() => { window.scrollTo(0, 0); }, [pathname]);
  return null;
}

const Loading = () => <div className="page"><div className="skeleton" style={{ height: 360 }} aria-busy="true" /></div>;

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <MotionConfig reducedMotion="user">
      <BrowserRouter>
        <WorkspaceProvider>
          <ScrollTop />
          <Suspense fallback={<Loading />}>
            <Routes>
              <Route path="/" element={<Landing />} />
              <Route element={<Shell />}>
                <Route path="/workspace" element={<CommandCentre />} />
                <Route path="/intake" element={<Intake />} />
                <Route path="/identity" element={<IdentityPage />} />
                <Route path="/protection" element={<Protection />} />
                <Route path="/clinical-integrity" element={<ClinicalPage />} />
                <Route path="/risk" element={<Risk />} />
                <Route path="/assurance" element={<AssurancePage />} />
              </Route>
              {/* earlier Studio URLs */}
              <Route path="/studio" element={<Navigate to="/workspace" replace />} />
              <Route path="/studio/new" element={<Navigate to="/intake" replace />} />
              <Route path="/studio/inventory" element={<Navigate to="/intake" replace />} />
              <Route path="/studio/clinical" element={<Navigate to="/clinical-integrity" replace />} />
              <Route path="/studio/identity" element={<Navigate to="/identity" replace />} />
              <Route path="/studio/attacks" element={<Navigate to="/risk" replace />} />
              <Route path="/studio/assurance" element={<Navigate to="/assurance" replace />} />
              <Route path="*" element={<div className="wrap"><StateBlock title="Page not found" action={<Link to="/" className="btn btn-ghost btn-sm">Back to Anaam</Link>} /></div>} />
            </Routes>
          </Suspense>
        </WorkspaceProvider>
      </BrowserRouter>
    </MotionConfig>
  </StrictMode>,
);
