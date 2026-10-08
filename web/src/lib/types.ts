// Shapes returned by the API (app/api/routes.py). Only the fields the UI
// reads are typed.

export interface Role {
  title: string;
  start_date: string;
  end_date: string;
}

export interface JobDetails {
  id: string;
  company: string;
  location: string;
  bullets: number;
  groups: number;
  roles: Role[];
}

export interface CandidateDetails {
  name: string;
  headline: string;
  email: string;
  phone: string;
  location: string;
  links: string[];
}

export interface Details {
  candidate: CandidateDetails;
  experience: JobDetails[];
  /** Everything else read from the file, shown read-only (P8.26). */
  also_read?: { title: string; lines: string[] }[];
}

export interface UnplacedLine {
  id: string;
  text: string;
}

export interface ParseResult {
  details: Details;
  parse_issues: string[];
  /** How the file was read, e.g. as a LinkedIn profile export (P10.11): information, not a problem. */
  parse_notes?: string[];
  /** Lines of the file the parse put nowhere, for the user to assign (P8.26). */
  unplaced?: UnplacedLine[];
}

export type KeywordKind = "hard" | "title" | "education" | "certification" | "soft";

export interface KeywordRow {
  keyword: string;
  kind: KeywordKind;
  required: boolean;
  weight: number;
  found: boolean;
  credit: number;
  where: string[];
  /** Only listed under Skills, never shown in the work: half credit (P8.19). */
  skills_only?: boolean;
}

export interface BreakdownRow {
  Kind: string;
  Found: string;
  Points: string;
}

export interface KeywordMatch {
  rate: number;
  rows: KeywordRow[];
  target_band: [number, number];
  breakdown: BreakdownRow[];
  /** The job's keywords were picked by simple rules, not the AI (P8.18). */
  approximate?: boolean;
  /** What a low rate means here (P8.21). */
  guidance?: { kind: "stretch" | "different_field"; headline: string; text: string; tips: string[] } | null;
}

export type MatchStatus = "EXPLICIT" | "SUPPORTED" | "PARTIAL" | "SEMANTIC_PARTIAL" | "MISSING" | "UNCERTAIN";

export interface RequirementMatch {
  requirement_id: string;
  requirement_text: string;
  status: MatchStatus;
  explanation: string;
}

export interface Condition {
  id: string;
  text: string;
  kind: string;
  label: string;
  priority: "required" | "preferred";
  /** "met" / "not_met" when code can tell (years), else null: the user ticks it. */
  auto: "met" | "not_met" | null;
  note: string | null;
}

export interface AnalysisReport {
  alignment_score: number;
  required_matches: RequirementMatch[];
  preferred_matches: RequirementMatch[];
  missing_requirements: RequirementMatch[];
  score_components: Record<string, number> | null;
  keyword_match: KeywordMatch | null;
  conditions?: Condition[];
  /** Whether the AI read the job description, and why not (P8.23). */
  ai?: { used: boolean; reason: string | null };
  warnings?: string[];
}

export interface DiffSpan {
  text: string;
  changed?: boolean;
  keyword?: boolean;
}

export type ProposalState = "failed" | "dropped" | "check" | "unchanged" | "pass";

export interface Proposal {
  id: string;
  kind: "bullet" | "summary" | "skills" | "heading";
  section: { id: string; kind: "experience" | "project"; label: string } | null;
  target?: string | null; // the bullet's id (P10.13: its card hides with a left-out project)
  original: string;
  proposed: string;
  rationale: string | null;
  state: ProposalState;
  state_label: string;
  state_meaning: string;
  note: string | null;
  /** Starts unticked: the user's own text stays unless they pick this one (P8.10). */
  opt_in?: boolean;
  diff: { original: DiffSpan[]; proposed: DiffSpan[] };
}

export interface GapQuestion {
  id: string;
  requirement: string;
  priority: "required" | "preferred";
  keywords: string[];
  question: string;
  /** Worded by what is asked: "Tick the ones you hold:" for licences (P8.12). */
  tick_label?: string;
  kinds?: Record<string, string>;
  saved_keywords: string[];
  saved_answer: string;
}

export interface GapRow {
  "Missing keyword": string;
  Kind: string;
  Required: string;
  "Asked below": string;
}

export interface LlmStatus {
  available: boolean;
  provider?: string;
  provider_label: string;
  model?: string;
  reason?: string | null;
  attempted?: number;
  failed?: number;
  errors?: string[];
  fix_hint: string;
}

/** Paper and date style for the job (P10.3), with the JD's words that decided it. */
export interface RegionInfo {
  region: string; // "us" | "uk_eu" | "india" | "other"
  label: string; // "US (Letter)"
  evidence: string | null; // "Austin, TX"; null when nothing in the JD said
}

export const REGION_LABELS: Record<string, string> = {
  us: "US (Letter)", uk_eu: "UK / Europe (A4)", india: "India (A4)", other: "Other (A4)",
};

/** Standard resume, Academic CV or US Federal (P10.5), with the signals that suggested it. */
export interface CvModeInfo {
  mode: string; // "standard" | "academic" | "federal"
  label: string;
  evidence: string[];
}

export const CV_MODE_LABELS: Record<string, string> = {
  standard: "Standard resume", academic: "Academic CV", federal: "US Federal (USAJOBS)",
};

/** A project inside a job, kept for this job or left out, and why (P10.13). */
export interface ProjectChoice {
  key: string; // "<experience id>::<project>"
  experience_id: string;
  job: string;
  name: string;
  bullet_ids: string[];
  chosen: boolean;
  reason: string;
  relevance: number;
  impact: number;
}

export interface ProposalsResult {
  details?: Details; // what the server holds after the corrections (added jobs included)
  proposals: Proposal[];
  gap_questions: GapQuestion[];
  conditions?: Condition[]; // job conditions that aren't keywords (P8.20)
  keyword_match: KeywordMatch | null;
  gaps: GapRow[];
  pre_score: number;
  experience_options: { id: string; label: string }[];
  region?: RegionInfo;
  cv_mode?: CvModeInfo;
  projects?: ProjectChoice[]; // P10.13
  projects_ranked_by_impact?: boolean; // the job description was too short to rank projects by
  llm: LlmStatus;
}

export interface MatchPreview extends KeywordMatch {
  delta: number;
}

export interface LintIssue {
  check: string;
  where: string;
  message: string;
}

export interface TailorResult {
  success: boolean;
  alignment_score: number;
  initial_alignment_score: number;
  keyword_match: KeywordMatch | null;
  content_lint: { bullets: number; bullets_with_metrics: number; issues: LintIssue[] } | null;
  addition_note: string | null;
  warnings: string[];
  docx_warnings: string[];
  pdf_warnings: string[];
  target_pages: number | null;
  applied: { bullets: number; bullets_edited: number; summary: boolean; skills: boolean; rejected: number;
    strict_withheld: boolean } | null;
  pages: number;
  files: { docx: boolean; pdf: boolean; changes: boolean; html?: boolean };
  coverage?: { pct: number | null; counted: number; kept: number; reworded: number; trimmed: number; lost: string[] } | null;
  /** Read-back checks by weight (P8.26): serious ones fail the run, minor ones are advice. */
  file_checks?: { serious: string[]; minor: string[] };
  /** What the Arrange screen edits (P8.13); null for "keep my layout". */
  arrangement?: Arrangement | null;
  /** The region the files are formatted for (P10.3); null for "keep my layout". */
  region?: RegionInfo | null;
  /** The CV type the files use (P10.5). */
  cv_mode?: CvModeInfo | null;
}

export interface ArrangeBullet {
  id: string;
  text: string;
  /** The bullet as the uploaded file had it (null for one added in this run). */
  file_text: string | null;
  group: string | null;
}

export interface ArrangeEntry {
  id: string;
  title: string;
  subtitle: string;
  bullets: ArrangeBullet[];
}

export interface ArrangeSection {
  key: string;
  title: string;
  kind: "text" | "entries" | "other";
  lines?: string[];
  entries?: ArrangeEntry[];
}

export interface Layout {
  section_order: string[];
  hidden_sections: string[];
  entry_order: Record<string, string[]>;
  bullet_order: Record<string, string[]>;
  removed_bullets: string[];
  edits: Record<string, string>;
  pinned: string[];
  page_target: number | null;
  trim: boolean;
  region?: string | null; // P10.3: null keeps the run's
  cv_mode?: string | null; // P10.5: null keeps the run's
}

export interface TrimmedItem {
  kind: "bullet" | "project" | "interests";
  id: string;
  owner: string | null;
  owner_label?: string;
  text: string;
}

export interface Arrangement {
  sections: ArrangeSection[];
  layout: Layout;
  /** The layout tailoring produced ("Reset to the tailored version"). */
  default_layout?: Layout;
  source_order: { bullets: Record<string, string[]>; experience: string[]; projects: string[]; education: string[] };
  trimmed: TrimmedItem[];
}
