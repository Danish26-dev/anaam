import { useMemo } from "react";
import type { IdentityRecord } from "../../state/model";
import { Links, Pick, StatusRing, Sway, type V3 } from "../kit";
import { C, sourceColor } from "../palette";

interface ClusterIn { pseudonym: string; records: IdentityRecord[] }

/**
 * Patient relationships. Each linked patient is a hub (forest sphere) with its records around it,
 * coloured by source and joined by links. Unlinked records (the engine abstained) float in a
 * separate field on the right with no links. Nothing here carries a name or identifier.
 */
export default function IdentityResolutionScene({ clusters, unlinked, sourceIndex, selected, selectedRecord, onCluster, onRecord }: {
  clusters: ClusterIn[]; unlinked: IdentityRecord[]; sourceIndex: Record<string, number>;
  selected: string | null; selectedRecord: string | null;
  onCluster: (p: string) => void; onRecord: (key: string) => void;
}) {
  const layout = useMemo(() => {
    const golden = Math.PI * (3 - Math.sqrt(5));
    return clusters.slice(0, 48).map((c, i) => {
      const r = 0.55 + 2.35 * Math.sqrt((i + 0.5) / Math.max(1, Math.min(48, clusters.length)));
      const a = i * golden;
      const hub: V3 = [Math.cos(a) * r - 1.0, 0, Math.sin(a) * r * 0.62];
      const recs = c.records.slice(0, 12).map((rec, k, arr) => {
        const b = (k / arr.length) * Math.PI * 2;
        const rr = 0.32 + 0.02 * arr.length;
        return { rec, p: [hub[0] + Math.cos(b) * rr, 0.12 * Math.sin(b * 2), hub[2] + Math.sin(b) * rr * 0.8] as V3 };
      });
      return { c, hub, recs };
    });
  }, [clusters]);
  const field = useMemo(() => unlinked.slice(0, 120).map((r, i) => {
    const col = i % 6, row = Math.floor(i / 6);
    return { r, p: [3.0 + col * 0.24, -0.1 + (i % 3) * 0.05, -1.2 + row * 0.24] as V3 };
  }), [unlinked]);
  const dim = (p: string) => selected !== null && selected !== p;

  return (
    <Sway amount={0.05} speed={0.1}>
      <group position={[-0.2, -0.3, 0]}>
        {layout.map(({ c, hub, recs }) => (
          <group key={c.pseudonym}>
            <Links pairs={recs.map(({ p }) => [hub, p] as [V3, V3])} color={C.forest} opacity={dim(c.pseudonym) ? 0.1 : 0.5} />
            <Pick position={hub} selected={selected === c.pseudonym} onSelect={() => onCluster(c.pseudonym)} label={c.pseudonym}>
              <mesh>
                <sphereGeometry args={[0.09 + 0.012 * Math.min(10, c.records.length), 24, 16]} />
                <meshStandardMaterial color={dim(c.pseudonym) ? C.sage : C.forest} metalness={0.2} roughness={0.4} transparent opacity={dim(c.pseudonym) ? 0.45 : 1} />
              </mesh>
              {selected === c.pseudonym && <StatusRing color={C.copper} radius={0.24} />}
            </Pick>
            {recs.map(({ rec, p }) => (
              <mesh key={`${rec.file}#${rec.loc}`} position={p}>
                <boxGeometry args={[0.09, 0.09, 0.09]} />
                <meshStandardMaterial color={sourceColor(sourceIndex[rec.sourceKey] ?? 0)} transparent opacity={dim(c.pseudonym) ? 0.3 : 1} roughness={0.45} />
              </mesh>
            ))}
          </group>
        ))}
        {/* abstention field: records released with patient: null */}
        {field.map(({ r, p }) => {
          const key = `${r.file}#${r.loc}`;
          return (
            <Pick key={key} position={p} selected={selectedRecord === key} onSelect={() => onRecord(key)} label="unlinked record">
              <mesh>
                <boxGeometry args={[0.1, 0.1, 0.1]} />
                <meshStandardMaterial color={selectedRecord === key ? C.copper : "#C3CBC4"} roughness={0.6} />
              </mesh>
            </Pick>
          );
        })}
        {field.length > 0 && (
          <mesh position={[3.6, -0.2, -0.6]} rotation={[-Math.PI / 2, 0, 0]}>
            <planeGeometry args={[1.8, Math.max(0.8, Math.ceil(field.length / 6) * 0.24 + 0.4)]} />
            <meshStandardMaterial color={C.amber} transparent opacity={0.08} />
          </mesh>
        )}
      </group>
    </Sway>
  );
}
