import { useFrame } from "@react-three/fiber";
import { useReducedMotion } from "framer-motion";
import { useRef } from "react";
import * as THREE from "three";
import type { Layer } from "../../state/model";
import { Pick, Plate, StatusRing, Sway, useClock } from "../kit";
import { C, statusColor } from "../palette";

/** The seven verification layers as stacked plates, bottom (input accounting) to top
 *  (release-wide). They stay apart while any layer is not passed; when every layer passes they
 *  close into one sealed stack. The seal ring appears only after a person authorises. */
const PLATE: Record<string, string> = {
  passed: "#D5E3DB", attention: "#F1E4CB", failed: "#EBCFCA", running: "#EFDDD2", not_evaluated: "#EEF1EE",
};

function LayerPlate({ layer, index, gap, selected, onSelect }: {
  layer: Layer; index: number; gap: number; selected: boolean; onSelect: () => void;
}) {
  const g = useRef<THREE.Group>(null);
  const reduce = useReducedMotion();
  const y = index * gap;
  useFrame(() => {
    if (!g.current) return;
    const tx = selected ? 0.55 : 0;
    const k = reduce ? 1 : 0.12;
    g.current.position.x += (tx - g.current.position.x) * k;
    g.current.position.y += (y - g.current.position.y) * k;
  });
  const col = statusColor(layer.status);
  const pending = layer.status === "attention" || layer.status === "running";
  return (
    <group ref={g} position={[0, reduce ? y : 0, 0]}>
      <Pick selected={selected} onSelect={onSelect} label={layer.label}>
        <Plate size={[2.4, 0.08, 1.6]} color={PLATE[layer.status] ?? C.ivory} edge={col} edgeOpacity={0.9} />
        <mesh position={[-1.05, 0.05, 0.62]}>
          <cylinderGeometry args={[0.07, 0.07, 0.03, 24]} />
          <meshStandardMaterial color={col} emissive={col} emissiveIntensity={pending ? 0.3 : 0.1} />
        </mesh>
        {(selected || layer.status === "failed") && (
          <StatusRing color={selected ? C.copper : col} radius={1.5} tube={0.012} pulse={layer.status === "failed"} />
        )}
      </Pick>
    </group>
  );
}

function Seal({ height }: { height: number }) {
  const m = useRef<THREE.Mesh>(null);
  const t = useClock();
  useFrame(() => { if (m.current) m.current.rotation.z = t.current * 0.15; });
  return (
    <group position={[0, height / 2, 0]}>
      <mesh ref={m} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[1.75, 0.03, 12, 128]} />
        <meshStandardMaterial color={C.forest} metalness={0.5} roughness={0.3} emissive={C.forest} emissiveIntensity={0.2} />
      </mesh>
    </group>
  );
}

export default function ReleaseAssuranceScene({ layers, selected, onSelect, authorised }: {
  layers: Layer[]; selected: string | null; onSelect: (id: string) => void; authorised: boolean;
}) {
  const allPassed = layers.length > 0 && layers.every((l) => l.status === "passed");
  const gap = allPassed ? 0.12 : 0.36;
  const height = (layers.length - 1) * gap;
  return (
    <Sway amount={0.12} speed={0.08}>
      <group position={[0, -height / 2 - 0.2, 0]} rotation={[0, -0.5, 0]}>
        {layers.map((l, i) => (
          <LayerPlate key={l.id} layer={l} index={i} gap={gap} selected={selected === l.id} onSelect={() => onSelect(l.id)} />
        ))}
        {allPassed && authorised && <Seal height={height} />}
        <mesh position={[0, -0.12, 0]}>
          <cylinderGeometry args={[1.7, 1.75, 0.04, 64]} />
          <meshStandardMaterial color="#F7F8F6" roughness={0.9} />
        </mesh>
      </group>
    </Sway>
  );
}
