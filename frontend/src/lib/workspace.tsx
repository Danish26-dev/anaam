import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import demoFixture from "../fixtures/demo-release.json";
import { deriveActions, nextAction, readiness, type Decisions } from "../state/actions";
import { buildModel } from "../state/model";
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
  decisions: Record<string, Decisions>;
  review: (releaseId: string, actionId: string, note: string) => void;
  unreview: (releaseId: string, actionId: string) => void;
  authorise: (releaseId: string) => void;
  revokeAuthorisation: (releaseId: string) => void;
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
  // human decisions per release: in memory only (never browser storage), lost on reload by design
  const [decisions, setDecisions] = useState<Record<string, Decisions>>({});
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

  const patch = (id: string, f: (d: Decisions) => Decisions) =>
    setDecisions((all) => ({ ...all, [id]: f(all[id] ?? EMPTY) }));
  const value: Ctx = {
    decisions,
    review: (id, actionId, note) => patch(id, (d) => ({ ...d, reviewed: { ...d.reviewed, [actionId]: { at: new Date().toISOString(), note } } })),
    unreview: (id, actionId) => patch(id, (d) => { const r = { ...d.reviewed }; delete r[actionId]; return { ...d, reviewed: r, authorisedAt: null }; }),
    authorise: (id) => patch(id, (d) => ({ ...d, authorisedAt: new Date().toISOString() })),
    revokeAuthorisation: (id) => patch(id, (d) => ({ ...d, authorisedAt: null })),
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

const EMPTY: Decisions = { reviewed: {}, authorisedAt: null };

/** The selected release as every screen sees it: one model, one action list, one readiness. */
export function useRelease() {
  const ws = useWorkspace();
  const view = ws.current;
  const model = useMemo(() => buildModel(view), [view]);
  const actions = useMemo(() => deriveActions(model), [model]);
  const decisions = ws.decisions[view.id] ?? EMPTY;
  const ready = readiness(model, actions, decisions);
  const next = nextAction(model, actions, decisions, ready);
  return {
    ...ws, view, model, actions, decisions, readiness: ready, next,
    review: (actionId: string, note: string) => ws.review(view.id, actionId, note),
    unreview: (actionId: string) => ws.unreview(view.id, actionId),
    authorise: () => ws.authorise(view.id),
    revokeAuthorisation: () => ws.revokeAuthorisation(view.id),
  };
}

export const SOURCE_LABEL: Record<ReleaseView["source"], string> = {
  demo: "SYNTHETIC DEMO",
  practice: "PRACTICE EVALUATION",
  live: "LOCAL RELEASE",
};
