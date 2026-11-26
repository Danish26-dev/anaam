import { useFrame } from "@react-three/fiber";
import { useReducedMotion } from "framer-motion";
import { useRef } from "react";
import * as THREE from "three";
import { Pick, StatusRing, Sway } from "../kit";
import { C } from "../palette";

interface Cat { category: string; before: number; kept: number }

/** One column per clinical category: a glass column for values found in the inputs, a solid
 *  forest core for values still unchanged in the release, terracotta for any loss. */
function Column({ c, x, max, selected, onSelect }: { c: Cat; x: number; max: number; selected: boolean; onSelect: () => void }) {
  const h = 0.3 + 2.1 * (Math.log2(1 + c.before) / Math.log2(1 + max));
  const keptH = c.before ? h * (c.kept / c.before) : 0;
  const core = useRef<THREE.Mesh>(null);
  const reduce = useReducedMotion();
  const grown = useRef(reduce ? 1 : 0);
  useFrame((_, dt) => {
    if (!core.current) return;
    grown.current = Math.min(1, grown.current + dt * 0.8);
    const s = 1 - Math.pow(1 - grown.current, 3);
    core.current.scale.y = Math.max(0.001, s);
    core.current.position.y = (keptH * s) / 2;
  });
  return (
    <Pick position={[x, 0, 0]} selected={selected} onSelect={onSelect} label={c.category}>
      <mesh position={[0, h / 2, 0]}>
        <boxGeometry args={[0.36, h, 0.36]} />
        <meshPhysicalMaterial color="#E3ECE6" transparent opacity={0.35} roughness={0.15} clearcoat={1} depthWrite={false} />
      </mesh>
      <mesh ref={core} position={[0, keptH / 2, 0]}>
        <boxGeometry args={[0.24, Math.max(0.001, keptH), 0.24]} />
        <meshStandardMaterial color={C.forest} roughness={0.4} metalness={0.15} />
      </mesh>
      {c.kept < c.before && (
        <mesh position={[0, keptH + (h - keptH) / 2, 0]}>
          <boxGeometry args={[0.25, h - keptH, 0.25]} />
          <meshStandardMaterial color={C.terracotta} roughness={0.5} />
        </mesh>
      )}
      <mesh position={[0, -0.03, 0]}>
        <cylinderGeometry args={[0.3, 0.32, 0.04, 32]} />
        <meshStandardMaterial color={selected ? C.copper : C.line} />
      </mesh>
      {selected && <StatusRing color={C.copper} radius={0.34} />}
    </Pick>
  );
}

export default function ClinicalPreservationScene({ cats, selected, onSelect }: { cats: Cat[]; selected: string | null; onSelect: (c: string) => void }) {
  const max = Math.max(1, ...cats.map((c) => c.before));
  const gap = 0.62;
  const x0 = -((cats.length - 1) * gap) / 2;
  return (
    <Sway amount={0.08} speed={0.1}>
      <group position={[0, -1.0, 0]}>
        <mesh position={[0, -0.06, 0]}>
          <boxGeometry args={[cats.length * gap + 0.6, 0.04, 1.2]} />
          <meshStandardMaterial color="#F7F8F6" roughness={0.9} />
        </mesh>
        {cats.map((c, i) => (
          <Column key={c.category} c={c} x={x0 + i * gap} max={max} selected={selected === c.category} onSelect={() => onSelect(c.category)} />
        ))}
      </group>
    </Sway>
  );
}
