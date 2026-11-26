import { useEffect, useRef, useState } from "react";
import * as THREE from "three";

/**
 * The Privacy Membrane. Fragmented record sheets (left) emit two kinds of particles toward a
 * ribbed membrane: clinical signal (forest spheres) passes through and continues as ordered
 * lanes; identity markers (copper cubes) stop at the membrane and fall away into the dark.
 */
const FOREST = 0x2f6b5e;
const COPPER = 0xb87552;
const IVORY = 0xfbfaf6;
const LANES = [-0.72, -0.36, 0, 0.36, 0.72];

function supportsWebGL(): boolean {
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch {
    return false;
  }
}

export default function Membrane() {
  const host = useRef<HTMLDivElement>(null);
  const [fallback, setFallback] = useState(false);

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    if (!supportsWebGL()) {
      setFallback(true);
      return;
    }
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "low-power" });
    } catch {
      setFallback(true);
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
    renderer.setClearColor(0x000000, 0);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    el.appendChild(renderer.domElement);
    renderer.domElement.setAttribute("aria-hidden", "true");

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 60);
    camera.position.set(0.9, 1.35, 10.4);
    camera.lookAt(0.15, -0.05, 0);

    scene.add(new THREE.HemisphereLight(0xffffff, 0xd9d3c4, 1.25));
    const key = new THREE.DirectionalLight(0xffffff, 1.6);
    key.position.set(3, 6, 7);
    scene.add(key);
    const rim = new THREE.DirectionalLight(0xf3c9a8, 0.9);
    rim.position.set(-4, 2, -6);
    scene.add(rim);

    const world = new THREE.Group();
    world.scale.setScalar(0.8);
    world.position.set(0.4, 0.05, 0);
    scene.add(world);
    const disposables: { dispose: () => void }[] = [];
    const track = <T extends { dispose: () => void }>(x: T) => (disposables.push(x), x);

    // ---------------------------------------------------------------- record sheets
    const sheetGeo = track(new THREE.PlaneGeometry(1.55, 2.05));
    const sheetMat = track(new THREE.MeshStandardMaterial({ color: IVORY, roughness: 0.75, metalness: 0, side: THREE.DoubleSide }));
    const edgeMat = track(new THREE.LineBasicMaterial({ color: 0x204b42, transparent: true, opacity: 0.45 }));
    const lineMat = track(new THREE.LineBasicMaterial({ color: 0xaab8a9, transparent: true, opacity: 0.9 }));
    const idLineMat = track(new THREE.LineBasicMaterial({ color: COPPER, transparent: true, opacity: 0.95 }));
    const sheets: THREE.Group[] = [];
    for (let i = 0; i < 5; i++) {
      const g = new THREE.Group();
      g.add(new THREE.Mesh(sheetGeo, sheetMat));
      g.add(new THREE.LineSegments(track(new THREE.EdgesGeometry(sheetGeo)), edgeMat));
      const pts: number[] = [];
      const ids: number[] = [];
      for (let r = 0; r < 9; r++) {
        const y = 0.78 - r * 0.18;
        const len = 0.5 + ((i * 7 + r * 13) % 9) / 10;
        const x0 = -0.62;
        if ((r + i) % 4 === 1) ids.push(x0, y, 0.002, x0 + 0.42, y, 0.002);
        else pts.push(x0, y, 0.002, x0 + len * 0.95, y, 0.002);
      }
      const lg = track(new THREE.BufferGeometry());
      lg.setAttribute("position", new THREE.Float32BufferAttribute(pts, 3));
      g.add(new THREE.LineSegments(lg, lineMat));
      const ig = track(new THREE.BufferGeometry());
      ig.setAttribute("position", new THREE.Float32BufferAttribute(ids, 3));
      g.add(new THREE.LineSegments(ig, idLineMat));
      g.position.set(-3.05 + i * 0.16, -0.12 + (i % 2) * 0.1, 0.9 - i * 0.42);
      g.rotation.set(-0.04, 0.62, (i - 2) * 0.025);
      world.add(g);
      sheets.push(g);
    }

    // ---------------------------------------------------------------- membrane
    const membrane = new THREE.Group();
    membrane.position.set(0.35, 0, 0);
    membrane.rotation.y = -0.68;
    world.add(membrane);
    const discGeo = track(new THREE.CircleGeometry(1.5, 128));
    const discMat = track(new THREE.MeshPhysicalMaterial({
      color: 0xe3ece6, roughness: 0.18, metalness: 0, transparent: true, opacity: 0.42, clearcoat: 1,
      clearcoatRoughness: 0.15, side: THREE.DoubleSide, depthWrite: false,
    }));
    for (const z of [-0.07, 0.07]) {
      const d = new THREE.Mesh(discGeo, discMat);
      d.position.z = z;
      membrane.add(d);
    }
    const rimMat = track(new THREE.MeshStandardMaterial({ color: COPPER, metalness: 0.75, roughness: 0.28 }));
    membrane.add(new THREE.Mesh(track(new THREE.TorusGeometry(1.5, 0.032, 20, 220)), rimMat));
    const inner = new THREE.Mesh(track(new THREE.TorusGeometry(1.62, 0.008, 8, 220)), rimMat);
    membrane.add(inner);
    const ribs: number[] = [];
    for (const r of [0.42, 0.78, 1.14]) {
      for (let a = 0; a < 128; a++) {
        const t0 = (a / 128) * Math.PI * 2, t1 = ((a + 1) / 128) * Math.PI * 2;
        ribs.push(Math.cos(t0) * r, Math.sin(t0) * r, 0, Math.cos(t1) * r, Math.sin(t1) * r, 0);
      }
    }
    for (let a = 0; a < 36; a++) {
      const t = (a / 36) * Math.PI * 2;
      ribs.push(Math.cos(t) * 0.2, Math.sin(t) * 0.2, 0, Math.cos(t) * 1.48, Math.sin(t) * 1.48, 0);
    }
    const ribGeo = track(new THREE.BufferGeometry());
    ribGeo.setAttribute("position", new THREE.Float32BufferAttribute(ribs, 3));
    membrane.add(new THREE.LineSegments(ribGeo, track(new THREE.LineBasicMaterial({ color: 0x204b42, transparent: true, opacity: 0.28 }))));

    // ---------------------------------------------------------------- preserved lanes
    const laneMat = track(new THREE.LineBasicMaterial({ color: 0x204b42, transparent: true, opacity: 0.22 }));
    const lanePts: number[] = [];
    for (const y of LANES) lanePts.push(0.5, y, 0.05, 3.4, y, 0.05);
    const laneGeo = track(new THREE.BufferGeometry());
    laneGeo.setAttribute("position", new THREE.Float32BufferAttribute(lanePts, 3));
    world.add(new THREE.LineSegments(laneGeo, laneMat));
    // lane terminals: small ivory blocks = the clinical record, intact
    const termGeo = track(new THREE.BoxGeometry(0.34, 0.16, 0.16));
    const termMat = track(new THREE.MeshStandardMaterial({ color: IVORY, roughness: 0.5 }));
    const termEdge = track(new THREE.LineBasicMaterial({ color: 0x204b42, transparent: true, opacity: 0.6 }));
    for (const y of LANES) {
      const m = new THREE.Mesh(termGeo, termMat);
      m.position.set(3.55, y, 0.05);
      world.add(m);
      const e = new THREE.LineSegments(track(new THREE.EdgesGeometry(termGeo)), termEdge);
      e.position.copy(m.position);
      world.add(e);
    }

    // ---------------------------------------------------------------- particles
    const NC = 96, NI = 38;
    const clin = new THREE.InstancedMesh(track(new THREE.SphereGeometry(0.036, 14, 10)),
      track(new THREE.MeshStandardMaterial({ color: FOREST, roughness: 0.35, metalness: 0.1 })), NC);
    const iden = new THREE.InstancedMesh(track(new THREE.BoxGeometry(0.07, 0.07, 0.07)),
      track(new THREE.MeshStandardMaterial({ color: COPPER, roughness: 0.3, metalness: 0.5 })), NI);
    world.add(clin, iden);
    const memWorld = new THREE.Vector3();
    membrane.getWorldPosition(memWorld);
    const sheetPoint = (out: THREE.Vector3) => {
      const s = sheets[Math.floor(Math.random() * sheets.length)];
      out.set((Math.random() - 0.5) * 1.3, (Math.random() - 0.5) * 1.7, 0.01);
      return s.localToWorld(out);
    };
    type P = { t: number; speed: number; a: THREE.Vector3; b: THREE.Vector3; lane: number; fall: THREE.Vector3 };
    const mk = (n: number, identity: boolean): P[] =>
      Array.from({ length: n }, () => {
        const lane = LANES[Math.floor(Math.random() * LANES.length)];
        const p: P = {
          t: Math.random() * (identity ? 1.7 : 2), speed: 0.16 + Math.random() * 0.1,
          a: sheetPoint(new THREE.Vector3()), lane,
          b: new THREE.Vector3(memWorld.x - 0.05, identity ? (Math.random() - 0.5) * 2.2 : lane, (Math.random() - 0.5) * 0.4),
          fall: new THREE.Vector3(-0.3 - Math.random() * 0.6, -1.4 - Math.random(), -0.8 - Math.random()),
        };
        return p;
      });
    const cp = mk(NC, false), ip = mk(NI, true);
    const dummy = new THREE.Object3D();
    const tmp = new THREE.Vector3();
    const ease = (x: number) => 1 - Math.pow(1 - x, 2.2);

    const step = (dt: number) => {
      cp.forEach((p, i) => {
        p.t += dt * p.speed;
        if (p.t >= 2) { p.t = 0; sheetPoint(p.a); }
        let s = 1;
        if (p.t < 1) tmp.lerpVectors(p.a, p.b, ease(p.t));
        else {
          const u = p.t - 1;
          tmp.set(THREE.MathUtils.lerp(p.b.x, 3.45, u), THREE.MathUtils.lerp(p.b.y, p.lane, Math.min(1, u * 3)), THREE.MathUtils.lerp(p.b.z, 0.05, Math.min(1, u * 3)));
          s = u > 0.9 ? (1 - u) * 10 : 1;
        }
        dummy.position.copy(tmp);
        dummy.scale.setScalar(Math.max(0.001, s * (p.t < 0.08 ? p.t / 0.08 : 1)));
        dummy.updateMatrix();
        clin.setMatrixAt(i, dummy.matrix);
      });
      ip.forEach((p, i) => {
        p.t += dt * p.speed;
        if (p.t >= 1.7) { p.t = 0; sheetPoint(p.a); }
        let s = 1;
        if (p.t < 1) tmp.lerpVectors(p.a, p.b, ease(p.t));
        else {
          const u = (p.t - 1) / 0.7;
          tmp.copy(p.b).addScaledVector(p.fall, u * u);
          s = 1 - u;
        }
        dummy.position.copy(tmp);
        dummy.rotation.set(p.t * 2, p.t * 3, 0);
        dummy.scale.setScalar(Math.max(0.001, s * (p.t < 0.08 ? p.t / 0.08 : 1)));
        dummy.updateMatrix();
        iden.setMatrixAt(i, dummy.matrix);
      });
      clin.instanceMatrix.needsUpdate = true;
      iden.instanceMatrix.needsUpdate = true;
    };

    // ---------------------------------------------------------------- loop
    const pointer = { x: 0, y: 0 };
    const onPointer = (e: PointerEvent) => {
      const r = el.getBoundingClientRect();
      pointer.x = ((e.clientX - r.left) / r.width - 0.5) * 2;
      pointer.y = ((e.clientY - r.top) / r.height - 0.5) * 2;
    };
    const resize = () => {
      const w = el.clientWidth, h = el.clientHeight || w;
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(el);

    let raf = 0, last = performance.now(), visible = true, elapsed = 0;
    const io = new IntersectionObserver(([e]) => (visible = e.isIntersecting));
    io.observe(el);
    const frame = (now: number) => {
      raf = requestAnimationFrame(frame);
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      if (!visible || document.hidden) return;
      elapsed += dt;
      step(dt);
      world.rotation.y = Math.sin(elapsed * 0.16) * 0.05 + pointer.x * 0.06;
      world.rotation.x = pointer.y * 0.03;
      membrane.rotation.z = elapsed * 0.04;
      inner.rotation.z = -elapsed * 0.06;
      renderer.render(scene, camera);
    };
    if (reduce) {
      step(0);
      renderer.render(scene, camera);
    } else {
      el.addEventListener("pointermove", onPointer);
      raf = requestAnimationFrame(frame);
    }

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      io.disconnect();
      el.removeEventListener("pointermove", onPointer);
      disposables.forEach((d) => d.dispose());
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, []);

  return (
    <div className="membrane-stage" ref={host}>
      {fallback && <StaticMembrane />}
      <div className="membrane-caption" style={{ left: "2%", top: "10%" }}>
        <b>Fragmented records</b>CSV · JSON · FHIR · notes
      </div>
      <div className="membrane-caption" style={{ left: "40%", bottom: "6%" }}>
        <b>Privacy membrane</b>identity separated
      </div>
      <div className="membrane-caption" style={{ right: "0%", top: "18%", textAlign: "right" }}>
        <b>Clinical signal</b>preserved, in order
      </div>
    </div>
  );
}

/** Static composition for browsers without WebGL. */
function StaticMembrane() {
  return (
    <svg viewBox="0 0 640 640" role="img" aria-label="Record sheets passing through a privacy membrane">
      <defs>
        <radialGradient id="mem" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#e3ece6" stopOpacity="0.2" />
          <stop offset="100%" stopColor="#aab8a9" stopOpacity="0.55" />
        </radialGradient>
      </defs>
      {[0, 1, 2, 3, 4].map((i) => (
        <g key={i} transform={`translate(${70 + i * 18} ${200 + i * 10}) skewY(-12)`}>
          <rect width="130" height="170" fill="#FBFAF6" stroke="#204B42" strokeOpacity="0.4" />
          {[0, 1, 2, 3, 4, 5, 6].map((r) => (
            <line key={r} x1="14" x2={r % 3 === 1 ? 60 : 110} y1={22 + r * 20} y2={22 + r * 20}
              stroke={r % 3 === 1 ? "#B87552" : "#AAB8A9"} strokeWidth="3" />
          ))}
        </g>
      ))}
      <ellipse cx="350" cy="320" rx="70" ry="170" fill="url(#mem)" stroke="#B87552" strokeWidth="4" />
      {[-80, -40, 0, 40, 80].map((y) => (
        <g key={y}>
          <line x1="380" x2="560" y1={320 + y} y2={320 + y} stroke="#204B42" strokeOpacity="0.3" />
          <circle cx={430 + (y + 80) * 0.6} cy={320 + y} r="5" fill="#2F6B5E" />
          <rect x="560" y={312 + y} width="34" height="16" fill="#FBFAF6" stroke="#204B42" />
        </g>
      ))}
      {[0, 1, 2].map((i) => (
        <rect key={i} x={300 - i * 22} y={430 + i * 34} width="9" height="9" fill="#B87552" opacity={0.8 - i * 0.25} />
      ))}
    </svg>
  );
}
