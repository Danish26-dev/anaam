// Shared Three.js primitives: one geometry language for every Anaam scene.
import { useFrame, type ThreeEvent } from "@react-three/fiber";
import { useReducedMotion } from "framer-motion";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import * as THREE from "three";
import { C } from "./palette";

export type V3 = [number, number, number];

/** Seconds since mount, frozen under reduced motion. */
export function useClock() {
  const reduce = useReducedMotion();
  const t = useRef(0);
  useFrame((_, dt) => { if (!reduce) t.current += Math.min(dt, 0.05); });
  return t;
}

/** Hover + selection wrapper: pointer cursor, gentle scale, click handler. */
export function Pick({ children, onSelect, selected = false, position, label }: {
  children: ReactNode; onSelect?: () => void; selected?: boolean; position?: V3; label?: string;
}) {
  const g = useRef<THREE.Group>(null);
  const [hover, setHover] = useState(false);
  useEffect(() => () => { document.body.style.cursor = ""; }, []);
  useFrame(() => {
    if (!g.current) return;
    const target = selected ? 1.12 : hover ? 1.06 : 1;
    const s = g.current.scale.x + (target - g.current.scale.x) * 0.18;
    g.current.scale.setScalar(s);
  });
  return (
    <group ref={g} position={position} name={label}
      onClick={onSelect ? (e: ThreeEvent<MouseEvent>) => { e.stopPropagation(); onSelect(); } : undefined}
      onPointerOver={onSelect ? (e: ThreeEvent<PointerEvent>) => { e.stopPropagation(); setHover(true); document.body.style.cursor = "pointer"; } : undefined}
      onPointerOut={onSelect ? () => { setHover(false); document.body.style.cursor = ""; } : undefined}>
      {children}
    </group>
  );
}

/** Thin plate with a fine edge: record sheets, files, verification layers. */
export function Plate({ size = [1, 0.06, 0.7], color = C.ivory, edge = C.forest, edgeOpacity = 0.45, opacity = 1, position, rotation }: {
  size?: V3; color?: string; edge?: string; edgeOpacity?: number; opacity?: number; position?: V3; rotation?: V3;
}) {
  const geo = useMemo(() => new THREE.BoxGeometry(...size), [size[0], size[1], size[2]]); // eslint-disable-line react-hooks/exhaustive-deps
  const edges = useMemo(() => new THREE.EdgesGeometry(geo), [geo]);
  useEffect(() => () => { geo.dispose(); edges.dispose(); }, [geo, edges]);
  return (
    <group position={position} rotation={rotation}>
      <mesh geometry={geo}>
        <meshStandardMaterial color={color} roughness={0.6} metalness={0.02} transparent={opacity < 1} opacity={opacity} />
      </mesh>
      <lineSegments geometry={edges}>
        <lineBasicMaterial color={edge} transparent opacity={edgeOpacity} />
      </lineSegments>
    </group>
  );
}

/** Status ring around a node; pulses only while running or requiring attention. */
export function StatusRing({ color, radius = 0.5, pulse = false, tube = 0.025, rotation = [Math.PI / 2, 0, 0] as V3 }: {
  color: string; radius?: number; pulse?: boolean; tube?: number; rotation?: V3;
}) {
  const m = useRef<THREE.Mesh>(null);
  const t = useClock();
  useFrame(() => {
    if (!m.current) return;
    const s = pulse ? 1 + Math.sin(t.current * 3) * 0.05 : 1;
    m.current.scale.setScalar(s);
  });
  return (
    <mesh ref={m} rotation={rotation}>
      <torusGeometry args={[radius, tube, 12, 96]} />
      <meshStandardMaterial color={color} metalness={0.4} roughness={0.35} emissive={color} emissiveIntensity={pulse ? 0.25 : 0.08} />
    </mesh>
  );
}

/** Line segments between pairs of points (relationships, record streams). */
export function Links({ pairs, color = C.forest, opacity = 0.35 }: { pairs: [V3, V3][]; color?: string; opacity?: number }) {
  const geo = useMemo(() => {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(pairs.flatMap(([a, b]) => [...a, ...b]), 3));
    return g;
  }, [pairs]);
  useEffect(() => () => geo.dispose(), [geo]);
  return (
    <lineSegments geometry={geo}>
      <lineBasicMaterial color={color} transparent opacity={opacity} />
    </lineSegments>
  );
}

/**
 * Particles flowing along a curve. `count` is the number of particles shown (derived from real
 * counts by the caller); `extent` (0..1) limits how far along the path they travel, so a stream
 * stops where processing actually stopped.
 */
export function Flow({ points, count, color = C.forestLight, speed = 0.12, size = 0.04, extent = 1, shape = "sphere" }: {
  points: V3[]; count: number; color?: string; speed?: number; size?: number; extent?: number; shape?: "sphere" | "box" | "ring" | "plate";
}) {
  const mesh = useRef<THREE.InstancedMesh>(null);
  const curve = useMemo(() => new THREE.CatmullRomCurve3(points.map((p) => new THREE.Vector3(...p))), [points]);
  const n = Math.max(0, Math.min(160, Math.round(count)));
  const offsets = useMemo(() => Array.from({ length: n }, (_, i) => i / Math.max(1, n)), [n]);
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const reduce = useReducedMotion();
  const t = useRef(0);
  const place = () => {
    if (!mesh.current) return;
    offsets.forEach((o, i) => {
      const u = ((o + t.current * speed) % 1) * extent;
      curve.getPointAt(Math.min(0.999, u), dummy.position);
      const fade = extent < 1 && u > extent - 0.04 ? Math.max(0.15, (extent - u) / 0.04) : 1;
      dummy.scale.setScalar(fade);
      dummy.rotation.set(u * 6, u * 4, 0);
      dummy.updateMatrix();
      mesh.current!.setMatrixAt(i, dummy.matrix);
    });
    mesh.current.instanceMatrix.needsUpdate = true;
  };
  useEffect(place);
  useFrame((_, dt) => { if (!reduce) { t.current += Math.min(dt, 0.05); place(); } });
  if (n === 0) return null;
  return (
    <instancedMesh ref={mesh} args={[undefined, undefined, n]} frustumCulled={false}>
      {shape === "box" ? <boxGeometry args={[size * 1.6, size * 1.6, size * 1.6]} />
        : shape === "ring" ? <torusGeometry args={[size * 1.1, size * 0.28, 8, 24]} />
        : shape === "plate" ? <boxGeometry args={[size * 2.2, size * 0.4, size * 1.6]} />
        : <sphereGeometry args={[size, 12, 10]} />}
      <meshStandardMaterial color={color} roughness={0.35} metalness={shape === "box" ? 0.45 : 0.1} />
    </instancedMesh>
  );
}

/** The privacy membrane: translucent ribbed disc with a copper rim. */
export function Membrane({ radius = 1.4, status = C.copper, spin = true, opacity = 0.42 }: {
  radius?: number; status?: string; spin?: boolean; opacity?: number;
}) {
  const g = useRef<THREE.Group>(null);
  const t = useClock();
  const ribs = useMemo(() => {
    const pts: number[] = [];
    for (const r of [0.3, 0.55, 0.8].map((k) => k * radius)) {
      for (let a = 0; a < 96; a++) {
        const t0 = (a / 96) * Math.PI * 2, t1 = ((a + 1) / 96) * Math.PI * 2;
        pts.push(Math.cos(t0) * r, Math.sin(t0) * r, 0, Math.cos(t1) * r, Math.sin(t1) * r, 0);
      }
    }
    for (let a = 0; a < 32; a++) {
      const th = (a / 32) * Math.PI * 2;
      pts.push(Math.cos(th) * radius * 0.14, Math.sin(th) * radius * 0.14, 0, Math.cos(th) * radius * 0.98, Math.sin(th) * radius * 0.98, 0);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.Float32BufferAttribute(pts, 3));
    return geo;
  }, [radius]);
  useEffect(() => () => ribs.dispose(), [ribs]);
  useFrame(() => { if (g.current && spin) g.current.rotation.z = t.current * 0.04; });
  return (
    <group>
      {[-0.06, 0.06].map((z) => (
        <mesh key={z} position={[0, 0, z]}>
          <circleGeometry args={[radius, 96]} />
          <meshPhysicalMaterial color="#E3ECE6" roughness={0.2} transparent opacity={opacity} clearcoat={1} side={THREE.DoubleSide} depthWrite={false} />
        </mesh>
      ))}
      <group ref={g}>
        <lineSegments geometry={ribs}>
          <lineBasicMaterial color={C.forest} transparent opacity={0.26} />
        </lineSegments>
      </group>
      <mesh>
        <torusGeometry args={[radius, 0.028, 16, 160]} />
        <meshStandardMaterial color={C.copper} metalness={0.75} roughness={0.28} />
      </mesh>
      <mesh>
        <torusGeometry args={[radius * 1.07, 0.012, 8, 160]} />
        <meshStandardMaterial color={status} metalness={0.4} roughness={0.35} emissive={status} emissiveIntensity={0.15} />
      </mesh>
    </group>
  );
}

/** Slow sway of a whole composition; off under reduced motion. */
export function Sway({ children, amount = 0.05, speed = 0.16 }: { children: ReactNode; amount?: number; speed?: number }) {
  const g = useRef<THREE.Group>(null);
  const t = useClock();
  useFrame(({ pointer }) => {
    if (!g.current) return;
    g.current.rotation.y = Math.sin(t.current * speed) * amount + pointer.x * 0.04;
    g.current.rotation.x = -pointer.y * 0.02;
  });
  return <group ref={g}>{children}</group>;
}

/** Log-scaled particle count: real counts drive density without flooding the scene. */
export const density = (n: number, max = 40) => (n <= 0 ? 0 : Math.max(3, Math.min(max, Math.round(6 * Math.log2(1 + n)))));
