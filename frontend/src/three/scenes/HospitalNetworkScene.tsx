import type { Source } from "../../state/model";
import { density, Flow, Membrane, Pick, Plate, StatusRing, Sway, type V3 } from "../kit";
import { C, sourceColor } from "../palette";

/**
 * Hospital network: each source is a node (a pedestal with one sheet per file, up to 8) on a ring
 * around the Anaam core. Quarantined files are terracotta sheets, legacy-encoded files amber.
 * Stream density follows the source's real released record count.
 */
export default function HospitalNetworkScene({ sources, selected, onSelect }: {
  sources: Source[]; selected: string | null; onSelect: (key: string) => void;
}) {
  const n = sources.length;
  const pos = (i: number): V3 => {
    const a = (i / Math.max(1, n)) * Math.PI * 2 + Math.PI * 0.75;
    return [Math.cos(a) * 3.1, 0, Math.sin(a) * 1.9];
  };
  return (
    <Sway amount={0.06} speed={0.12}>
      <group position={[0, -0.25, 0]}>
        {/* the Anaam core */}
        <group position={[0, 0.55, 0]} rotation={[0, -0.4, 0]} scale={0.5}><Membrane radius={1.3} /></group>
        <mesh position={[0, -0.1, 0]}>
          <cylinderGeometry args={[0.7, 0.8, 0.08, 64]} />
          <meshStandardMaterial color={C.forest} metalness={0.25} roughness={0.45} />
        </mesh>
        {sources.map((s, i) => {
          const p = pos(i);
          const sheets = s.files.slice(0, 8);
          const lift = selected === s.key ? 0.25 : 0;
          return (
            <group key={s.key}>
              <Pick position={[p[0], p[1] + lift, p[2]]} selected={selected === s.key} onSelect={() => onSelect(s.key)} label={s.label}>
                <mesh position={[0, -0.12, 0]}>
                  <cylinderGeometry args={[0.46, 0.52, 0.07, 48]} />
                  <meshStandardMaterial color={sourceColor(i)} metalness={0.2} roughness={0.5} />
                </mesh>
                {sheets.map((f, k) => {
                  const q = f.status !== "sanitized";
                  const legacy = f.inspection?.issues.includes("legacy_encoding");
                  return (
                    <Plate key={f.input_sha256} size={[0.58, 0.03, 0.42]} position={[0, -0.04 + k * 0.065, 0]} rotation={[0, k * 0.07, 0]}
                      color={q ? "#F6E7E4" : legacy ? "#F6EFE1" : C.ivory}
                      edge={q ? C.terracotta : legacy ? C.amber : C.forest} edgeOpacity={q || legacy ? 1 : 0.4} />
                  );
                })}
                {selected === s.key && <StatusRing color={C.copper} radius={0.62} />}
              </Pick>
              <Flow points={[[p[0], p[1] + 0.1, p[2]], [p[0] * 0.5, 0.75, p[2] * 0.5], [0, 0.55, 0]]}
                count={density(s.records, 18)} color={sourceColor(i)} speed={0.16} size={0.032} />
            </group>
          );
        })}
      </group>
    </Sway>
  );
}
