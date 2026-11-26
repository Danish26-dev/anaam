import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import demoFixture from "../fixtures/demo-release.json";
import { api } from "./api";
import type { DemoFixture, Evidence, Health, ReleaseSummary, ReleaseView } from "./types";

const demo = demoFixture as unknown as DemoFixture;

function demoView(): ReleaseView {
  const names: Record<string, string> = {};
  for (const f of demo.assurance?.files ?? []) if (f.input_name) names[f.input_sha256] = f.input_name;
  return {
    id: "synthetic-demo", source: "demo", label: "Synthetic demo workspace", createdAt: demo.created_at,
    status: "complete", pipeline: demo.pipeline, assurance: demo.assurance, names, examples: demo.examples,
  };
}

function practiceView(ev: Evidence): ReleaseView {
  return {
    id: "practice", source: "practice", label: "Practice evaluation", createdAt: ev.generated_at, status: "complete",
    pipeline: { exit_code: ev.pipeline.exit_code, seconds: ev.pipeline.wall_seconds, message: ev.pipeline.summary },
    assurance: ev.release, names: {}, evidence: ev,
  };
}

function liveView(s: ReleaseSummary, names: Record<string, string>): ReleaseView {
  return {
    id: s.id, source: "live", label: `Release ${s.id.slice(0, 6)}`, createdAt: s.created_at, status: s.status,
    stage: s.stage, pipeline: s.pipeline, assurance: s.assurance, names, error: s.error,
  };
}

interface Ctx {
  health: Health | null;           // null: Studio server not reachable (static demo only)
  serverChecked: boolean;
  evidence: Evidence | null;
  releases: ReleaseView[];         // demo, practice (if measured), live releases
  current: ReleaseView;
  select: (id: string) => void;
  registerNames: (id: string, names: Record<string, string>) => void;
  refresh: () => Promise<void>;
}

const WorkspaceContext = createContext<Ctx | null>(null);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [health, setHealth] = useState<Health | null>(null);
  const [serverChecked, setServerChecked] = useState(false);
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const [live, setLive] = useState<ReleaseSummary[]>([]);
  const [selected, setSelected] = useState<string>("synthetic-demo");
  // file names typed by this browser's user, kept in memory only (never persisted, never sent)
  const names = useRef<Record<string, Record<string, string>>>({});
  const [nameVersion, bump] = useState(0);

  const refresh = useCallback(async () => {
    try {
      const h = await api.health();
      setHealth(h);
      const list = await api.releases();
      const full = await Promise.all(list.map((r) => api.release(r.id).catch(() => null)));
      setLive(full.filter((x): x is ReleaseSummary => x !== null));
      if (h.evidence_available) setEvidence(await api.evidence().catch(() => null));
    } catch {
      setHealth(null);
    } finally {
      setServerChecked(true);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // poll while any live release is still running
  useEffect(() => {
    if (!live.some((r) => ["queued", "running", "verifying"].includes(r.status))) return;
    const t = window.setInterval(() => void refresh(), 1200);
    return () => window.clearInterval(t);
  }, [live, refresh]);

  const releases = useMemo(() => {
    const out: ReleaseView[] = live.map((s) => liveView(s, names.current[s.id] ?? {}));
    if (evidence) out.push(practiceView(evidence));
    out.push(demoView());
    return out;
  }, [live, evidence, nameVersion]);

  const current = releases.find((r) => r.id === selected) ?? releases[releases.length - 1];

  const value: Ctx = {
    health, serverChecked, evidence, releases, current,
    select: setSelected,
    registerNames: (id, n) => {
      names.current[id] = n;
      bump((x) => x + 1);
    },
    refresh,
  };
  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspace(): Ctx {
  const c = useContext(WorkspaceContext);
  if (!c) throw new Error("WorkspaceProvider missing");
  return c;
}

export const SOURCE_LABEL: Record<ReleaseView["source"], string> = {
  demo: "SYNTHETIC DEMO",
  practice: "PRACTICE EVALUATION",
  live: "LOCAL RELEASE",
};
