import { useMemo } from "react";
import type { ReleaseModel, StageId } from "../../state/model";
import { C, sourceColor, statusColor } from "../palette";
import { density, Flow, Membrane, Pick, Plate, StatusRing, Sway, type V3 } from "../kit";

const PROCESSED = new Set(["complete", "attention"]);

function gatePos(i: number): V3 {
  return [-2.5 + i * 1.12, 0, -Math.sin((i / 6) * Math.PI) * 0.9];
}

/** Small element inside each gate that says what the stage does. */
function GateGlyph({ id, color }: { id: StageId; color: string }) {
  switch (id) {
    case "intake":
      return <>{[0, 1, 2].map((k) => <Plate key={k} size={[0.34, 0.03, 0.26]} position={[0, -0.08 + k * 0.08, 0]} />)}</>;
    case "identity":
      return <>{([[-0.14, -0.08, 0], [0.14, -0.08, 0], [0, 0.14, 0]] as V3[]).map((p, k) => (
        <mesh key={k} position={p}><sphereGeometry args={[0.06, 16, 12]} /><meshStandardMaterial color={C.forestLight} /></mesh>))}</>;
    case "protection":
      return <group rotation={[0, -0.5, 0]} scale={0.26}><Membrane radius={1.2} spin={false} /></group>;
    case "clinical":
      return <>{[0, 1, 2].map((k) => (
        <mesh key={k} position={[0, -0.14 + k * 0.14, 0]}><sphereGeometry args={[0.05, 14, 10]} /><meshStandardMaterial color={C.forest} /></mesh>))}</>;
    case "risk":
      return <>{[-0.12, 0, 0.12].map((x, k) => (
        <mesh key={k} position={[x, -0.1 + k * 0.04, 0]}><boxGeometry args={[0.07, 0.12 + k * 0.08, 0.07]} /><meshStandardMaterial color={k === 2 ? C.copper : C.sage} /></mesh>))}</>;
    case "verification":
      return <>{[0, 1, 2, 3].map((k) => <Plate key={k} size={[0.3, 0.025, 0.3]} position={[0, -0.12 + k * 0.08, 0]} color={C.ivory} edge={color} edgeOpacity={0.8} />)}</>;
    default:
      return <mesh><cylinderGeometry args={[0.16, 0.16, 0.04, 40]} /><meshStandardMaterial color={color} metalness={0.3} roughness={0.4} /></mesh>;
  }
}

export default function ReleaseOverviewScene({ model, selectedStage, selectedSource, highlight, onStage, onSource }: {
  model: ReleaseModel; selectedStage: StageId | null; selectedSource: string | null; highlight: StageId | null;
  onStage: (id: StageId) => void; onSource: (key: string) => void;
}) {
  const { stages, sources } = model;
  // how far the record stream really got: the last stage with results
  const reached = useMemo(() => {
    let last = -1;
    stages.forEach((s, i) => { if (PROCESSED.has(s.status)) last = i; });
    const running = stages.findIndex((s) => s.status === "running");
    return running >= 0 ? running : last;
  }, [stages]);
  const srcPos = (j: number, n: number): V3 => [-4.7, (j - (n - 1) / 2) * 0.82, 0.7 - j * 0.12];
  const main: V3[] = stages.map((_, i) => gatePos(i));
  const shownSources = sources.slice(0, 8);

  return (
    <Sway amount={0.04}>
      <group position={[0.35, -0.15, 0]} scale={1.22}>
        {/* hospital / source nodes */}
        {shownSources.map((s, j) => {
          const p = srcPos(j, shownSources.length);
          const plates = Math.min(6, s.files.length);
          return (
            <group key={s.key}>
              <Pick position={p} selected={selectedSource === s.key} onSelect={() => onSource(s.key)} label={s.label}>
                <mesh position={[0, -0.12, 0]}>
                  <cylinderGeometry args={[0.3, 0.34, 0.05, 40]} />
                  <meshStandardMaterial color={sourceColor(j)} metalness={0.2} roughness={0.5} />
                </mesh>
                {Array.from({ length: plates }, (_, k) => (
                  <Plate key={k} size={[0.42, 0.025, 0.3]} position={[0, -0.06 + k * 0.05, 0]}
                    edge={k < s.quarantined ? C.terracotta : C.forest} edgeOpacity={k < s.quarantined ? 1 : 0.4} />
                ))}
                {selectedSource === s.key && <StatusRing color={C.copper} radius={0.42} />}
              </Pick>
              <Flow points={[p, [(p[0] + main[0][0]) / 2, p[1] * 0.5, (p[2] + main[0][2]) / 2], main[0]]}
                count={reached >= 0 ? density(s.records, 14) : 0} color={sourceColor(j)} speed={0.18} size={0.03} />
            </group>
          );
        })}
        {/* the main record stream, only as far as processing got */}
        {reached >= 0 && <Flow points={main} count={density(model.counts.records, 46)} extent={Math.max(0.02, reached / (main.length - 1))} speed={0.05} />}
        {/* stage gates */}
        {stages.map((s, i) => {
          const color = statusColor(s.status);
          const sel = selectedStage === s.id;
          return (
            <Pick key={s.id} position={gatePos(i)} selected={sel} onSelect={() => onStage(s.id)} label={s.label}>
              <group rotation={[0, 0.25, 0]}>
                <StatusRing color={color} radius={0.42} tube={sel ? 0.04 : 0.028} rotation={[0, 0, 0]}
                  pulse={s.status === "running" || highlight === s.id} />
                {highlight === s.id && <StatusRing color={C.copper} radius={0.52} tube={0.01} rotation={[0, 0, 0]} pulse />}
                <GateGlyph id={s.id} color={color} />
              </group>
              <mesh position={[0, -0.72, 0]}>
                <cylinderGeometry args={[0.18, 0.2, 0.04, 32]} />
                <meshStandardMaterial color={s.status === "not_evaluated" || s.status === "waiting" ? C.line : color} />
              </mesh>
            </Pick>
          );
        })}
      </group>
    </Sway>
  );
}
