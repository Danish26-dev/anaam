// Shapes produced by tools/studio/server.py (live releases), tools/studio/evidence.py (practice
// evidence) and tools/studio/record_demo.py (the synthetic demo fixture). All three share
// `Assurance`, computed by the same Python function.

export type Verdict = "VERIFIED" | "VERIFICATION REQUIRED" | "BLOCKED";
export type Source = "demo" | "practice" | "live";

export interface Inspection {
  extension: string | null;
  bytes: number;
  format: string;               // csv | tsv | json | fhir | text | unsupported | empty | undecodable
  encoding: string | null;      // utf-8 | utf-8-sig | utf-16-le | utf-16-be | cp1252
  delimiter?: string;
  rows?: number;
  columns?: number;
  scripts?: { devanagari: number; latin: number };
  script?: "latin" | "devanagari" | "mixed" | "none";
  hinglish_signals?: number;
  issues: string[];             // legacy_encoding, unrecognised_structure, empty_file, ...
}

export interface FileEntry {
  output: string | null;
  status: "sanitized" | "quarantined" | "suppressed";
  reason: string | null;
  input_sha256: string;
  records: number;
  residual: number;
  structure: string[];
  clinical_before: number;
  clinical_kept: number;
  inspection?: Inspection;
  path_renamed?: boolean;
  source?: string | null;     // input top-level folder, only when the engine finds no PII in it
  input_name?: string | null; // synthetic demo only
}

export interface Cluster {
  pseudonym: string;
  records: { file: string; loc: string }[];
}

export interface Assurance {
  status: Verdict;
  reason?: string;
  contract: { evaluated: boolean; ok?: boolean; errors?: number };
  files: FileEntry[];
  residual: { total: number; by_category: Record<string, number> };
  structure: { total: number; codes: Record<string, number> };
  clinical: { before: number; kept: number; by_category: { category: string; before: number; kept: number }[] };
  identity: {
    records: number; linked_records: number; patients: number; clusters: Cluster[];
    unlinked?: { file: string; loc: string }[]; unlinked_total?: number;
  };
  protection?: {
    placeholders: Record<string, number>;
    pseudonym_occurrences: number;
    keys_renamed: number;
    paths_renamed: number;
    records_generalized: number;
  };
  release_wide: { evaluated: boolean; passed: boolean; codes: string[] };
  counts: Record<string, number>;
  timing: { seconds?: number };
  resources: { peak_rss_mb?: number };
}

export interface ReleaseSummary {
  id: string;
  created_at: string;
  finished_at?: string;
  status: "queued" | "running" | "verifying" | "complete" | "failed";
  stage?: string;
  files_uploaded: number;
  bytes_uploaded?: number;
  unsupported_extensions?: number;
  error?: string;
  pipeline?: { exit_code: number; seconds: number; message: string };
  assurance?: Assurance;
}

export interface DemoFixture extends ReleaseSummary {
  source: "demo";
  label: string;
  examples: { input_name: string; output: string; before: string; after: string }[];
}

export interface AttackSet {
  records: number;
  A1: { exposed: number; total: number; rate: number };
  A3: { mean_top_candidate_share: number; records_with_candidate: number; total: number };
  A4: { reidentified: number; total: number; rate: number };
  A5: { found: number; total: number; rate: number; global_shift_recoverable: boolean };
}

export interface CheckDev {
  available: boolean;
  pii?: { visible: number; total: number; rate: number };
  pii_by_category?: { category: string; visible: number; total: number }[];
  pii_by_language?: Record<string, number>;
  pii_by_channel?: Record<string, number>;
  canaries?: { found: number; total: number };
  medical?: { kept: number; total: number };
  linking?: { precision: number; recall: number; f05: number; wrong_merges: number };
  raw_copies?: number;
}

export interface Evidence {
  schema: string;
  source: "practice";
  source_label: string;
  generated_at: string;
  git_commit: string | null;
  notes: string[];
  pipeline: { exit_code: number; summary: string; wall_seconds: number };
  contract: { contract_ok: boolean; errors: number; warnings: number };
  check_dev: CheckDev;
  release: Assurance;
  attacks: {
    protected: AttackSet;
    unprotected_baseline: AttackSet;
    A6: { checked: number | null; invertible: number | null };
    A7: { pairs: number; stable_pseudonyms: number; stable_dates: number; risk_rate: number };
  };
  holdout?: { seed: string; pipeline: { exit_code: number; summary: string }; check_dev: CheckDev }[];
}

export interface Health {
  ok: boolean;
  engine: string;
  offline: boolean;
  secret_source: "environment" | "session";
  kit_available: boolean;
  evidence_available: boolean;
  supported_extensions: string[];
}

/** One release as every screen sees it, whatever its source. */
export interface ReleaseView {
  id: string;
  source: Source;
  label: string;
  createdAt: string;
  status: ReleaseSummary["status"];
  stage?: string;
  pipeline?: ReleaseSummary["pipeline"];
  assurance?: Assurance;
  names: Record<string, string>; // input sha256 -> file name known to this browser (never sent back)
  evidence?: Evidence;
  examples?: DemoFixture["examples"];
  error?: string;
}
