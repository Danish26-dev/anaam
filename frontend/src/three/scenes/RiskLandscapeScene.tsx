import { useFrame } from "@react-three/fiber";
import { useReducedMotion } from "framer-motion";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { Sway } from "../kit";
import { C } from "../palette";

/**
 * Risk landscape for one attack scenario. One marker per assessed unit (people, records, profiles
 * or facts); exactly `exposed` of them are raised and coloured. Markers are NOT positioned by any
 * patient attribute: the arrangement is a fixed pseudo-random grid so counts are comparable.
 * Switching baseline/protected animates the markers to the new count.
 */
export default function RiskLandscapeScene({ total, exposed }: { total: number; exposed: number }) {
  const n = Math.max(1, Math.min(900, total));
  const cols = Math.ceil(Math.sqrt(n * 1.8));
  const mesh = useRef<THREE.InstancedMesh>(null);
  const reduce = useReducedMotion();
  // deterministic shuffle so the raised markers are spread, and stable between renders
  const order = useMemo(() => {
    const idx = Array.from({ length: n }, (_, i) => i);
    let s = 7;
    for (let i = n - 1; i > 0; i--) { s = (s * 16807) % 2147483647; const j = s % (i + 1); [idx[i], idx[j]] = [idx[j], idx[i]]; }
    const rank = new Array<number>(n);
    idx.forEach((v, k) => { rank[v] = k; });
    return rank;
  }, [n]);
  const heights = useRef<Float32Array>(new Float32Array(n));
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const color = useMemo(() => new THREE.Color(), []);
  const spacing = Math.min(0.22, 5.4 / cols);
  const pos = (i: number) => {
    const c = i % cols, r = Math.floor(i / cols);
    const x = (c - (cols - 1) / 2) * spacing, z = (r - (Math.ceil(n / cols) - 1) / 2) * spacing;
    return [x, Math.sin(x * 1.3) * 0.08 + Math.cos(z * 1.7) * 0.06, z] as const;
  };
  const target = (i: number) => (order[i] < Math.round(exposed / Math.max(1, total) * n) ? 0.55 : 0.08);
  const apply = (instant: boolean) => {
    if (!mesh.current) return;
    for (let i = 0; i < n; i++) {
      const t = target(i);
      heights.current[i] = instant ? t : heights.current[i] + (t - heights.current[i]) * 0.12;
      const h = heights.current[i];
      const [x, y, z] = pos(i);
      dummy.position.set(x, y + h / 2, z);
      dummy.scale.set(1, h, 1);
      dummy.updateMatrix();
      mesh.current.setMatrixAt(i, dummy.matrix);
      color.set(h > 0.3 ? C.terracotta : h > 0.15 ? C.amber : C.sage);
      mesh.current.setColorAt(i, color);
    }
    mesh.current.instanceMatrix.needsUpdate = true;
    if (mesh.current.instanceColor) mesh.current.instanceColor.needsUpdate = true;
  };
  useEffect(() => { apply(!!reduce); }); // eslint-disable-line react-hooks/exhaustive-deps
  useFrame(() => { if (!reduce) apply(false); });
  const size = spacing * 0.62;
  return (
    <Sway amount={0.06} speed={0.09}>
      <group position={[0, -0.55, 0]} rotation={[0, -0.35, 0]}>
        <mesh position={[0, -0.02, 0]}>
          <boxGeometry args={[cols * spacing + 0.4, 0.03, Math.ceil(n / cols) * spacing + 0.4]} />
          <meshStandardMaterial color="#F7F8F6" roughness={0.9} />
        </mesh>
        <instancedMesh ref={mesh} args={[undefined, undefined, n]} frustumCulled={false}>
          <boxGeometry args={[size, 1, size]} />
          <meshStandardMaterial roughness={0.5} metalness={0.05} />
        </instancedMesh>
      </group>
    </Sway>
  );
}
