import { density, Flow, Membrane, Pick, StatusRing, Sway, type V3 } from "../kit";
import { C } from "../palette";

export type Lane = "identity" | "clinical" | "metadata";
export const LANES: { id: Lane; y: number; label: string }[] = [
  { id: "identity", y: 0.62, label: "Personal identity information" },
  { id: "clinical", y: 0, label: "Clinical information" },
  { id: "metadata", y: -0.62, label: "Record metadata" },
];

/**
 * Privacy transformation. Three lanes cross the membrane. Identity (copper cubes) leaves as hollow
 * rings: a typed placeholder or a keyed pseudonym, never the value. Clinical values (forest
 * spheres) pass unchanged. Metadata (file names, keys) leaves as flat protected plates.
 * Lane density follows the real counts in the released output.
 */
export default function PrivacyTransformationScene({ counts, selected, onSelect, attention }: {
  counts: Record<Lane, number>; selected: Lane | null; onSelect: (l: Lane) => void; attention: boolean;
}) {
  const before = (y: number): V3[] => [[-3.3, y + 0.3, 0.4], [-1.8, y, 0.15], [-0.12, y, 0]];
  const after = (y: number): V3[] => [[0.12, y, 0], [1.8, y, 0.15], [3.3, y - 0.1, 0.4]];
  return (
    <Sway amount={0.05} speed={0.12}>
      <group position={[0, -0.05, 0]}>
        <group rotation={[0, Math.PI / 2 - 0.35, 0]}>
          <Membrane radius={1.25} status={attention ? C.amber : C.forest} />
        </group>
        {LANES.map((l) => {
          const n = density(counts[l.id], 26);
          const dim = selected !== null && selected !== l.id;
          return (
            <group key={l.id}>
              <Pick position={[-3.55, l.y + 0.3, 0.45]} selected={selected === l.id} onSelect={() => onSelect(l.id)} label={l.label}>
                <mesh>
                  {l.id === "identity" ? <boxGeometry args={[0.18, 0.18, 0.18]} /> : l.id === "clinical" ? <sphereGeometry args={[0.11, 20, 14]} /> : <boxGeometry args={[0.24, 0.06, 0.18]} />}
                  <meshStandardMaterial color={l.id === "identity" ? C.copper : l.id === "clinical" ? C.forest : C.sage} metalness={0.3} roughness={0.4} />
                </mesh>
                {selected === l.id && <StatusRing color={C.copper} radius={0.22} />}
              </Pick>
              {!dim && (
                <>
                  <Flow points={before(l.y)} count={n} speed={0.11}
                    color={l.id === "identity" ? C.copper : l.id === "clinical" ? C.forestLight : C.sage}
                    shape={l.id === "identity" ? "box" : l.id === "clinical" ? "sphere" : "plate"} size={0.035} />
                  <Flow points={after(l.y)} count={n} speed={0.11}
                    color={l.id === "identity" ? C.ivory : l.id === "clinical" ? C.forestLight : C.ivory}
                    shape={l.id === "identity" ? "ring" : l.id === "clinical" ? "sphere" : "plate"} size={0.035} />
                </>
              )}
            </group>
          );
        })}
      </group>
    </Sway>
  );
}
