import { Canvas, useThree } from "@react-three/fiber";
import { useReducedMotion } from "framer-motion";
import { useEffect, useRef, useState, type ReactNode } from "react";
import * as THREE from "three";

function supportsWebGL(): boolean {
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch {
    return false;
  }
}

/** Renders on demand: one frame after state changes, continuously only while `animate`. */
function FrameControl({ animate, target }: { animate: boolean; target: [number, number, number] }) {
  const { invalidate, camera } = useThree();
  useEffect(() => { camera.lookAt(...target); camera.updateProjectionMatrix(); invalidate(); }, [camera, target[0], target[1], target[2]]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { invalidate(); });
  void animate;
  return null;
}

export function Lights() {
  return (
    <>
      <hemisphereLight args={["#ffffff", "#d7dcd5", 1.2]} />
      <directionalLight position={[3, 6, 7]} intensity={1.5} />
      <directionalLight position={[-5, 2, -6]} intensity={0.7} color="#f3c9a8" />
    </>
  );
}

/**
 * Shared canvas for every Anaam scene. One canvas per screen; pauses when off-screen or when the
 * tab is hidden; a single still frame under prefers-reduced-motion; a DOM fallback without WebGL.
 * The canvas is decorative for assistive technology: every fact it shows is also in the DOM.
 */
export default function SceneCanvas({ children, fallback, camera = [0, 2.2, 9], target = [0, 0, 0], fov = 34, className = "", label, minHeight = 360 }: {
  children: ReactNode; fallback: ReactNode; camera?: [number, number, number]; target?: [number, number, number]; fov?: number;
  className?: string; label: string; minHeight?: number;
}) {
  const host = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();
  const [visible, setVisible] = useState(true);
  const [webgl] = useState(supportsWebGL);
  const [lost, setLost] = useState(false);

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    const io = new IntersectionObserver(([e]) => setVisible(e.isIntersecting && !document.hidden));
    io.observe(el);
    const onVis = () => setVisible(!document.hidden);
    document.addEventListener("visibilitychange", onVis);
    return () => { io.disconnect(); document.removeEventListener("visibilitychange", onVis); };
  }, []);

  const animate = visible && !reduce;
  return (
    <div ref={host} className={`scene ${className}`} style={{ minHeight }} role="img" aria-label={label}>
      {!webgl || lost ? (
        <div className="scene-fallback">{fallback}</div>
      ) : (
        <Canvas
          frameloop={animate ? "always" : "demand"}
          dpr={[1, 1.75]}
          camera={{ position: camera, fov, near: 0.1, far: 80 }}
          gl={{ antialias: true, alpha: true, powerPreference: "low-power" }}
          onCreated={({ gl }) => {
            gl.setClearColor(0x000000, 0);
            gl.toneMapping = THREE.ACESFilmicToneMapping;
            gl.toneMappingExposure = 1.05;
            gl.domElement.addEventListener("webglcontextlost", () => setLost(true), { once: true });
          }}
        >
          <FrameControl animate={animate} target={target} />
          <Lights />
          {children}
        </Canvas>
      )}
    </div>
  );
}
