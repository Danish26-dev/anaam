import type { Evidence, Health, ReleaseSummary } from "./types";

// Same-origin only: the local Studio server (tools/studio/server.py). No third-party requests.
async function get<T>(path: string): Promise<T> {
  const r = await fetch(path, { headers: { Accept: "application/json" }, cache: "no-store" });
  if (!r.ok) throw new Error(`${r.status}`);
  return (await r.json()) as T;
}

export const api = {
  health: () => get<Health>("/api/health"),
  evidence: () => get<Evidence>("/api/evidence"),
  releases: () => get<ReleaseSummary[]>("/api/releases"),
  release: (id: string) => get<ReleaseSummary>(`/api/releases/${id}`),
  fileUrl: (id: string, path: string, download = false) =>
    `/api/releases/${id}/${path.split("/").map(encodeURIComponent).join("/")}${download ? "?download=1" : ""}`,
  async createRelease(files: { path: string; data: string }[]): Promise<ReleaseSummary> {
    const r = await fetch("/api/releases", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ files }),
    });
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(body?.error ?? `${r.status}`);
    return body as ReleaseSummary;
  },
};

export async function sha256Hex(buf: ArrayBuffer): Promise<string> {
  const d = await crypto.subtle.digest("SHA-256", buf);
  return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export function toBase64(buf: ArrayBuffer): string {
  const bytes = new Uint8Array(buf);
  let s = "";
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(s);
}
