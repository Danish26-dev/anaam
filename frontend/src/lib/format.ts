export const pct = (n: number, d: number, digits = 1) => (d ? `${((100 * n) / d).toFixed(digits)}%` : "–");
export const num = (n: number | undefined | null) => (n == null ? "–" : n.toLocaleString("en-IN"));
export const rate = (r: number | undefined, digits = 1) => (r == null ? "–" : `${(100 * r).toFixed(digits)}%`);
export const bytes = (b: number) =>
  b < 1024 ? `${b} B` : b < 1024 ** 2 ? `${(b / 1024).toFixed(1)} KB` : `${(b / 1024 ** 2).toFixed(1)} MB`;
export const when = (iso: string) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
};
export const ext = (name: string) => (name.includes(".") ? name.slice(name.lastIndexOf(".")).toLowerCase() : "");
export const basename = (p: string) => p.split("/").pop() ?? p;
export const humanReason = (r: string | null | undefined) =>
  r
    ? {
        unsupported: "Format not recognised (e.g. truncated or malformed)",
        unsupported_format: "Unsupported file type",
        undecodable_text: "Text encoding could not be decoded",
        empty_file: "Empty file",
        json_nesting_too_deep: "JSON nested too deeply",
        release_verifier_failed: "Failed the release gate",
        detection_failed: "Detection failed for this file",
        fhir_patient_count_unsupported: "FHIR bundle without exactly one patient",
      }[r] ?? r.replace(/_/g, " ")
    : "";
