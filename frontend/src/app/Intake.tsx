import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { lazy, Suspense, useEffect, useMemo, useRef, useState, type DragEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { StatusDot } from "../components/ops";
import { PageHead, Panel, StateBlock, StatusBadge } from "../components/ui";
import { api, sha256Hex, toBase64 } from "../lib/api";
import { bytes, ext, humanReason, num } from "../lib/format";
import type { Inspection } from "../lib/types";
import { useRelease } from "../lib/workspace";
import type { FileRow, Source } from "../state/model";
import SceneCanvas from "../three/SceneCanvas";

const HospitalNetworkScene = lazy(() => import("../three/scenes/HospitalNetworkScene"));
const SUPPORTED = [".csv", ".tsv", ".json", ".txt"];

export const scriptLabel = (i?: Inspection) =>
  !i?.script || i.script === "none" ? "–"
    : i.script === "devanagari" ? "Hindi (Devanagari)"
    : i.script === "mixed" ? `Devanagari + Latin${(i.hinglish_signals ?? 0) > 2 ? " · Hinglish" : ""}`
    : (i.hinglish_signals ?? 0) > 2 ? "Latin · Hinglish signals" : "English (Latin)";
const ISSUE: Record<string, string> = {
  legacy_encoding: "Legacy encoding", unrecognised_structure: "Structure not recognised", empty_file: "Empty file",
  undecodable_text: "Text cannot be decoded", unsupported_extension: "Unsupported file type", malformed_json: "Malformed JSON",
  ragged_rows: "Rows with differing widths", malformed_rows: "Rows cannot be parsed",
};

export default function Intake() {
  const { model, view } = useRelease();
  const [params, setParams] = useSearchParams();
  const reduce = useReducedMotion();
  const fileParam = params.get("file");
  const initialSource = params.get("source") ?? model.files.find((f) => f.input_sha256 === fileParam)?.sourceKey ?? null;
  const [source, setSource] = useState<string | null>(initialSource);
  const [file, setFile] = useState<string | null>(fileParam);
  useEffect(() => { setSource(initialSource); setFile(fileParam); }, [view.id]); // eslint-disable-line react-hooks/exhaustive-deps
  const sel: Source | null = model.sources.find((s) => s.key === source) ?? null;
  const selFile: FileRow | null = model.files.find((f) => f.input_sha256 === file) ?? null;
  const list = sel ? sel.files : model.files;
  const pick = (k: string | null) => { setSource(k); setFile(null); setParams(k ? { source: k } : {}, { replace: true }); };
  const pickFile = (f: FileRow) => { setFile(f.input_sha256); setParams({ ...(source ? { source } : {}), file: f.input_sha256 }, { replace: true }); };
  const langs = useMemo(() => [...new Set(model.files.map((f) => scriptLabel(f.inspection)).filter((x) => x !== "–"))], [model.files]);

  return (
    <>
      <PageHead eyebrow="Source intake" title="What arrived, and what Anaam made of it">
        Each hospital is a source. Files are inspected with the engine's own format and encoding detection; a file that
        cannot be processed safely is quarantined, never copied. {view.source === "demo" && "Hospitals here are fictional."}
      </PageHead>
      <div className="ws-grid">
        <section className="panel scene-panel">
          <header className="panel-head"><h2>Hospital network</h2><span className="muted" style={{ fontSize: 12.5 }}>{model.sources.length} sources · select one</span></header>
          <SceneCanvas label="Hospital sources arranged around the Anaam core with record streams" camera={[0, 2.9, 5.6]} target={[0, -0.05, 0.15]} fov={40} minHeight={380}
            fallback={<p className="muted">3D view unavailable; use the source list below.</p>}>
            <Suspense fallback={null}><HospitalNetworkScene sources={model.sources} selected={source} onSelect={(k) => pick(k === source ? null : k)} /></Suspense>
          </SceneCanvas>
          <div className="scene-legend">
            <span><i style={{ background: "var(--surface)", border: "1px solid var(--forest)" }} />file processed</span>
            <span><i style={{ background: "#F6EFE1", border: "1px solid var(--ochre)" }} />legacy encoding</span>
            <span><i style={{ background: "#F6E7E4", border: "1px solid var(--terracotta)" }} />quarantined</span>
          </div>
          <div className="filters" role="group" aria-label="Sources">
            <button type="button" className={`chip ${!source ? "on" : ""}`} onClick={() => pick(null)}>All sources</button>
            {model.sources.map((s) => (
              <button type="button" key={s.key} className={`chip ${source === s.key ? "on" : ""}`} onClick={() => pick(s.key)}>
                {s.label}{s.issues ? ` · ${s.issues}` : ""}
              </button>
            ))}
          </div>
        </section>

        <div className="ws-side">
          <AnimatePresence mode="wait">
            <motion.section key={sel?.key ?? "all"} className="panel" initial={reduce ? false : { opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}>
              <header className="panel-head"><h2>{sel ? sel.label : "All sources"}</h2>{sel && <span className="mono muted">{sel.files.length} files</span>}</header>
              <div className="panel-body">
                <dl className="kv small">
                  <dt>Files received</dt><dd>{num(list.length)}</dd>
                  <dt>Formats detected</dt><dd>{[...new Set(list.map((f) => f.format).filter(Boolean))].join(", ") || "–"}</dd>
                  <dt>Languages</dt><dd>{(sel ? [...new Set(sel.files.map((f) => scriptLabel(f.inspection)).filter((x) => x !== "–"))] : langs).join("; ") || "–"}</dd>
                  <dt>Files parsed</dt><dd>{num(list.filter((f) => f.status === "sanitized").length)}</dd>
                  <dt>Need attention</dt><dd>{num(list.filter((f) => (f.inspection?.issues.length ?? 0) > 0).length)}</dd>
                  <dt>Quarantined</dt><dd>{num(list.filter((f) => f.status !== "sanitized").length)}</dd>
                  <dt>Records released</dt><dd>{num(list.reduce((s, f) => s + (f.status === "sanitized" ? f.records : 0), 0))}</dd>
                </dl>
              </div>
            </motion.section>
          </AnimatePresence>
          <FileDetail f={selFile} releaseId={view.id} live={view.source === "live"} onClose={() => { setFile(null); setParams(source ? { source } : {}, { replace: true }); }} />
        </div>
      </div>

      <Panel title={`Files${sel ? ` · ${sel.label}` : ""}`} bodyClass="">
        {list.length === 0 ? <StateBlock title="No files">This release has no file results.</StateBlock> : (
          <div className="table-wrap">
            <table className="data">
              <thead><tr><th>File</th><th>Format</th><th>Encoding</th><th>Language</th><th className="r">Records</th><th>Inspection</th><th>Status</th></tr></thead>
              <tbody>
                {list.map((f) => (
                  <tr key={f.input_sha256} className="clickable" tabIndex={0} aria-selected={f.input_sha256 === file}
                    onClick={() => pickFile(f)} onKeyDown={(e) => e.key === "Enter" && pickFile(f)}>
                    <td className="mono" style={{ wordBreak: "break-all", maxWidth: 340 }}>{f.name}</td>
                    <td>{f.format || "–"}{f.inspection?.delimiter ? ` · ${f.inspection.delimiter}` : ""}</td>
                    <td className="mono">{f.inspection?.encoding ?? "–"}</td>
                    <td>{scriptLabel(f.inspection)}</td>
                    <td className="r">{f.status === "sanitized" ? num(f.records) : "–"}</td>
                    <td>{f.inspection?.issues.length ? f.inspection.issues.map((i) => ISSUE[i] ?? i).join(", ") : <span className="muted">no issues</span>}</td>
                    <td><StatusBadge status={f.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
      <AddFiles />
    </>
  );
}

function FileDetail({ f, releaseId, live, onClose }: { f: FileRow | null; releaseId: string; live: boolean; onClose: () => void }) {
  if (!f) return <Panel title="File"><p className="muted">Select a file in the table to inspect its processing. Raw input content is never shown.</p></Panel>;
  const i = f.inspection;
  return (
    <Panel title="File" aside={<button type="button" className="btn btn-quiet btn-sm" onClick={onClose}>Close</button>}>
      <dl className="kv small">
        <dt>File</dt><dd className="mono" style={{ wordBreak: "break-all" }}>{f.name}</dd>
        <dt>Status</dt><dd><StatusBadge status={f.status} />{f.reason && <span className="muted"> · {humanReason(f.reason)}</span>}</dd>
        <dt>Format</dt><dd>{f.format || "–"}{i?.columns ? ` · ${i.columns} columns, ${i.rows} rows` : ""}</dd>
        <dt>Encoding</dt><dd className="mono">{i?.encoding ?? "–"}{i?.issues.includes("legacy_encoding") ? " (decoded; released as UTF-8)" : ""}</dd>
        <dt>Language</dt><dd>{scriptLabel(i)}</dd>
        <dt>Size</dt><dd>{i ? bytes(i.bytes) : "–"}</dd>
        <dt>Released as</dt><dd className="mono" style={{ wordBreak: "break-all" }}>{f.output ?? "not released"}{f.path_renamed ? " (name protected)" : ""}</dd>
        <dt>Records</dt><dd>{f.status === "sanitized" ? num(f.records) : "–"}</dd>
        <dt>Re-scan</dt><dd>{f.status === "sanitized" ? (f.residual ? <StatusDot status="attention" label={`${f.residual} span(s) to review`} /> : <StatusDot status="complete" label="no residual PII" />) : "–"}</dd>
        <dt>SHA-256</dt><dd className="mono">{f.input_sha256.slice(0, 20)}…</dd>
      </dl>
      {live && f.output && <a className="btn btn-ghost btn-sm" style={{ marginTop: 14 }} href={api.fileUrl(releaseId, f.output)} target="_blank" rel="noreferrer">Open released file</a>}
    </Panel>
  );
}

interface Picked { path: string; size: number; file?: File; url?: string }

function AddFiles() {
  const { health, serverChecked, registerNames, refresh, select } = useRelease();
  const [files, setFiles] = useState<Picked[]>([]);
  const [over, setOver] = useState(false);
  const [phase, setPhase] = useState<"idle" | "inspecting" | "reading" | "uploading">("idle");
  const [inspect, setInspect] = useState<Record<string, Inspection>>({});
  const [error, setError] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const folder = useRef<HTMLInputElement>(null);
  const nav = useNavigate();

  const read = async (f: Picked) => (f.file ? f.file.arrayBuffer() : (await fetch(f.url!)).arrayBuffer());
  // automatic, non-destructive preflight: the server inspects in memory and writes nothing
  useEffect(() => {
    if (!health || files.length === 0) { setInspect({}); return; }
    let cancelled = false;
    setPhase("inspecting");
    (async () => {
      try {
        const payload = await Promise.all(files.map(async (f) => ({ path: f.path, data: toBase64(await read(f)) })));
        const r = await fetch("/api/inspect", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ files: payload }) });
        const body = await r.json();
        if (!cancelled) { if (r.ok) setInspect(body.files); else setError(`Inspection failed (${body.error ?? r.status}).`); }
      } catch {
        if (!cancelled) setError("Inspection failed.");
      } finally {
        if (!cancelled) setPhase("idle");
      }
    })();
    return () => { cancelled = true; };
  }, [files, health]);

  const add = (list: FileList | File[]) => {
    const next = [...files];
    for (const f of Array.from(list)) {
      const path = (f as File & { webkitRelativePath?: string }).webkitRelativePath || f.name;
      if (!next.some((x) => x.path === path)) next.push({ path, size: f.size, file: f });
    }
    setFiles(next); setError(null);
  };
  const loadDemo = async () => {
    try {
      const idx: string[] = await (await fetch("/demo-input/index.json")).json();
      setFiles(idx.map((p) => ({ path: p, size: 0, url: `/demo-input/${p.split("/").map(encodeURIComponent).join("/")}` })));
      setError(null);
    } catch { setError("The synthetic demo files are not available in this build."); }
  };
  const tasks = Object.entries(inspect).flatMap(([p, i]) => i.issues.map((iss) => ({ p, iss })));
  const start = async () => {
    setPhase("reading"); setError(null);
    try {
      const names: Record<string, string> = {};
      const payload: { path: string; data: string }[] = [];
      for (const f of files) {
        const buf = await read(f);
        names[await sha256Hex(buf)] = f.path;      // this tab's memory only
        payload.push({ path: f.path, data: toBase64(buf) });
      }
      setPhase("uploading");
      const rel = await api.createRelease(payload);
      registerNames(rel.id, names);
      await refresh();
      select(rel.id);
      setFiles([]);
      nav("/workspace");
    } catch (e) {
      setPhase("idle");
      setError(`The release could not be started (${(e as Error).message}). Nothing was processed.`);
    }
  };

  return (
    <section className="panel" id="add">
      <header className="panel-head"><h2>Start a new release</h2>
        <span className="muted" style={{ fontSize: 12.5 }}>{health ? "local engine connected" : serverChecked ? "engine offline" : "checking engine…"}</span></header>
      <div className="panel-body" style={{ display: "grid", gap: 16 }}>
        {!health && serverChecked && <div className="notice warn">Releases need the local Studio server: <span className="mono">python tools/studio/server.py</span>.</div>}
        <div className={`drop ${over ? "over" : ""}`} onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
          onDrop={(e: DragEvent) => { e.preventDefault(); setOver(false); if (e.dataTransfer.files.length) add(e.dataTransfer.files); }}>
          <span className="eyebrow plain">Drop hospital exports here</span>
          <div className="formats">{SUPPORTED.map((s) => <span key={s} className="tag">{s.slice(1)}</span>)}<span className="tag">FHIR R4 (JSON)</span></div>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", justifyContent: "center" }}>
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => input.current?.click()}>Browse files</button>
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => folder.current?.click()}>Browse folder</button>
            <button type="button" className="btn btn-quiet btn-sm" onClick={loadDemo}>Load synthetic demo files</button>
          </div>
          <input ref={input} type="file" multiple hidden onChange={(e) => e.target.files && add(e.target.files)} />
          <input ref={folder} type="file" hidden onChange={(e) => e.target.files && add(e.target.files)} {...({ webkitdirectory: "", directory: "" } as Record<string, string>)} />
          <p className="muted" style={{ fontSize: 12.5 }}>Files are inspected and processed on this machine. Source files are never modified; uploaded copies are deleted after the run.</p>
        </div>
        {files.length > 0 && (
          <>
            <div className="table-wrap">
              <table className="data">
                <thead><tr><th>File</th><th>Format</th><th>Encoding</th><th>Language</th><th className="r">Size</th><th>Preflight</th><th /></tr></thead>
                <tbody>
                  {files.map((f) => {
                    const i = inspect[f.path];
                    return (
                      <tr key={f.path}>
                        <td className="mono" style={{ wordBreak: "break-all" }}>{f.path}</td>
                        <td>{i ? i.format : phase === "inspecting" ? "…" : ext(f.path).slice(1)}</td>
                        <td className="mono">{i?.encoding ?? "–"}</td>
                        <td>{scriptLabel(i)}</td>
                        <td className="r mono">{i ? bytes(i.bytes) : f.size ? bytes(f.size) : "–"}</td>
                        <td>{!i ? <span className="muted">{phase === "inspecting" ? "inspecting" : "–"}</span> : i.issues.length ? <span className="badge warn">{i.issues.map((x) => ISSUE[x] ?? x).join(", ")}</span> : <span className="badge ok">ready</span>}</td>
                        <td className="r"><button type="button" className="btn btn-quiet btn-sm" onClick={() => setFiles(files.filter((x) => x.path !== f.path))}>Remove</button></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {tasks.length > 0 && (
              <div className="notice warn" role="status">
                <div><strong>Preflight found {tasks.length} item{tasks.length > 1 ? "s" : ""} to note before the run.</strong>
                  <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>
                    {tasks.map((t, k) => <li key={k}><span className="mono">{t.p}</span>: {ISSUE[t.iss] ?? t.iss}{t.iss === "legacy_encoding" ? " (the engine decodes it and releases UTF-8)" : t.iss === "unrecognised_structure" || t.iss === "empty_file" ? " (will be quarantined)" : ""}</li>)}
                  </ul></div>
              </div>
            )}
            <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
              <button type="button" className="btn btn-primary" disabled={!health || phase !== "idle"} onClick={start}>
                {phase === "reading" ? "Reading files…" : phase === "uploading" ? "Starting release…" : phase === "inspecting" ? "Inspecting…" : `Process ${files.length} file${files.length > 1 ? "s" : ""}`}
              </button>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setFiles([])}>Clear</button>
            </div>
          </>
        )}
        {error && <div className="notice bad" role="alert">{error}</div>}
      </div>
    </section>
  );
}
