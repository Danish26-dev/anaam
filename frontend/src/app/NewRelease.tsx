import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useRef, useState, type DragEvent } from "react";
import { useNavigate } from "react-router-dom";
import { PageHead, Panel, StateBlock } from "../components/ui";
import { api, sha256Hex, toBase64 } from "../lib/api";
import { bytes, ext } from "../lib/format";
import { useWorkspace } from "../lib/workspace";

interface Picked { path: string; size: number; file?: File; url?: string }
const SUPPORTED = [".csv", ".tsv", ".json", ".txt"];
const MAX_BYTES = 60 * 1024 * 1024;

export default function NewRelease() {
  const { health, serverChecked, registerNames, refresh, select } = useWorkspace();
  const [files, setFiles] = useState<Picked[]>([]);
  const [over, setOver] = useState(false);
  const [phase, setPhase] = useState<"idle" | "reading" | "uploading" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const folder = useRef<HTMLInputElement>(null);
  const nav = useNavigate();
  const reduce = useReducedMotion();

  const add = (list: FileList | File[]) => {
    const next = [...files];
    for (const f of Array.from(list)) {
      const path = (f as File & { webkitRelativePath?: string }).webkitRelativePath || f.name;
      if (!next.some((x) => x.path === path)) next.push({ path, size: f.size, file: f });
    }
    setFiles(next);
    setError(null);
  };
  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setOver(false);
    if (e.dataTransfer.files.length) add(e.dataTransfer.files);
  };
  const loadDemo = async () => {
    try {
      const idx: string[] = await (await fetch("/demo-input/index.json")).json();
      setFiles(idx.map((p) => ({ path: p, size: 0, url: `/demo-input/${p.split("/").map(encodeURIComponent).join("/")}` })));
      setError(null);
    } catch {
      setError("The synthetic demo files are not available in this build.");
    }
  };

  const supported = files.filter((f) => SUPPORTED.includes(ext(f.path)));
  const total = files.reduce((s, f) => s + f.size, 0);
  const tooBig = total > MAX_BYTES;
  const ready = !!health && files.length > 0 && !tooBig && phase !== "reading" && phase !== "uploading";

  const start = async () => {
    if (!ready) return;
    setPhase("reading");
    setError(null);
    try {
      const names: Record<string, string> = {};
      const payload: { path: string; data: string }[] = [];
      for (const f of files) {
        const buf = f.file ? await f.file.arrayBuffer() : await (await fetch(f.url!)).arrayBuffer();
        names[await sha256Hex(buf)] = f.path;   // kept in this tab's memory only
        payload.push({ path: f.path, data: toBase64(buf) });
      }
      setPhase("uploading");
      const rel = await api.createRelease(payload);
      registerNames(rel.id, names);
      await refresh();
      select(rel.id);
      nav("/studio/assurance");
    } catch (e) {
      setPhase("error");
      setError(`The release could not be started (${(e as Error).message}). Nothing was processed.`);
    }
  };

  return (
    <>
      <PageHead eyebrow="New release" title="Prepare a release">
        Add hospital exports. The local engine (<span className="mono">main.py</span>) processes them on this machine; the
        uploaded copies are deleted after the run and only the released output is kept.
      </PageHead>

      {serverChecked && !health && (
        <div className="notice warn" role="status">
          <strong>Engine offline.</strong>
          <span>Releases need the local Studio server: <span className="mono">python tools/studio/server.py</span>. The synthetic demo workspace stays available.</span>
        </div>
      )}

      <div className="grid-2">
        <div style={{ display: "grid", gap: 16 }}>
          <div className={`drop ${over ? "over" : ""}`} onDragOver={(e) => { e.preventDefault(); setOver(true); }}
            onDragLeave={() => setOver(false)} onDrop={onDrop}>
            <span className="eyebrow plain">Drop files or a folder here</span>
            <h2>Hospital exports, any mix of formats</h2>
            <div className="formats">{SUPPORTED.map((s) => <span key={s} className="tag">{s.slice(1)}</span>)}<span className="tag">FHIR R4 (JSON)</span></div>
            <p className="muted" style={{ fontSize: 13, maxWidth: 440 }}>
              CSV and TSV tables, JSON exports, FHIR R4 bundles and plain-text notes. Other file types are accepted but
              will be quarantined by the engine, never copied into the release.
            </p>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap", justifyContent: "center" }}>
              <button className="btn btn-ghost btn-sm" onClick={() => input.current?.click()}>Browse files</button>
              <button className="btn btn-ghost btn-sm" onClick={() => folder.current?.click()}>Browse folder</button>
              <button className="btn btn-quiet btn-sm" onClick={loadDemo}>Load synthetic demo files</button>
            </div>
            <input ref={input} type="file" multiple hidden onChange={(e) => e.target.files && add(e.target.files)} />
            <input ref={folder} type="file" hidden onChange={(e) => e.target.files && add(e.target.files)}
              {...({ webkitdirectory: "", directory: "" } as Record<string, string>)} />
          </div>

          <Panel title={`Files (${files.length})`} bodyClass="" aside={files.length > 0 &&
            <button className="btn btn-quiet btn-sm" onClick={() => setFiles([])}>Clear</button>}>
            {files.length === 0 ? (
              <StateBlock title="No files yet">Add files above, or load the synthetic demo set to see a complete run.</StateBlock>
            ) : (
              <div className="table-wrap">
                <table className="data">
                  <thead><tr><th>File</th><th>Format</th><th className="r">Size</th><th>Engine support</th><th /></tr></thead>
                  <tbody>
                    <AnimatePresence initial={false}>
                      {files.map((f) => {
                        const ok = SUPPORTED.includes(ext(f.path));
                        return (
                          <motion.tr key={f.path} initial={reduce ? false : { opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                            <td className="mono" style={{ wordBreak: "break-all" }}>{f.path}</td>
                            <td>{ext(f.path).slice(1) || "–"}</td>
                            <td className="r mono">{f.size ? bytes(f.size) : "demo"}</td>
                            <td>{ok ? <span className="badge ok">supported</span> : <span className="badge warn">will be quarantined</span>}</td>
                            <td className="r"><button className="btn btn-quiet btn-sm" aria-label={`Remove ${f.path}`}
                              onClick={() => setFiles(files.filter((x) => x.path !== f.path))}>Remove</button></td>
                          </motion.tr>
                        );
                      })}
                    </AnimatePresence>
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </div>

        <div style={{ display: "grid", gap: 16, position: "sticky", top: 84 }}>
          <Panel title="Readiness">
            <dl className="kv">
              <dt>Engine</dt><dd>{health ? <span className="badge ok">connected</span> : <span className="badge bad">offline</span>}</dd>
              <dt>Files</dt><dd className="num">{files.length} ({supported.length} supported)</dd>
              <dt>Size</dt><dd className="num">{bytes(total)}{tooBig && <span className="badge bad" style={{ marginLeft: 8 }}>over 60 MB</span>}</dd>
              <dt>Secret</dt><dd>{health ? (health.secret_source === "environment" ? "RAKSHA_SECRET from the server's environment" : "random per-session secret") : "–"}<br />
                <span className="muted" style={{ fontSize: 12 }}>never shown, logged or sent to this page</span></dd>
              <dt>Validation</dt><dd>{health?.kit_available ? "organiser's validate_output.py" : "organiser validator not found"}</dd>
            </dl>
            <button className="btn btn-primary" style={{ width: "100%", marginTop: 20 }} disabled={!ready} onClick={start}>
              {phase === "reading" ? "Reading files…" : phase === "uploading" ? "Starting release…" : "Start release"}
              {phase === "idle" && <span className="arrow">→</span>}
            </button>
            {error && <div className="notice bad" role="alert" style={{ marginTop: 12 }}>{error}</div>}
          </Panel>
          <Panel title="What happens">
            <ol className="timeline">
              {["Files are copied to a private folder on this machine", "main.py runs: detect, resolve, protect, verify",
                "The organiser's validator and independent checks run on the output", "Uploaded copies are deleted; only the release remains"].map((s, i) => (
                <li key={i}><span className="dot ok" /><span>{s}</span><span className="mono muted">{String(i + 1).padStart(2, "0")}</span></li>
              ))}
            </ol>
          </Panel>
        </div>
      </div>
    </>
  );
}
