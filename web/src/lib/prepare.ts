// Preparation: the most-asked ranking (weighted by how recently each question was asked), the company view and saved
// job-description lists. The server computes everything; the page only reads and, for lists, saves.
import { api, type QuestionRow } from "./api";

export type State = "unseen" | "weak" | "changed" | "familiar";
export type Card = QuestionRow & { progress: { state: State; due: boolean; rating: string | null }; domains: { id: string; label: string }[] };

export type Ranked = Card & { rank: number; count: number; score: number; companies_n: number; last_year: number | null };
export type Top = {
  total: number;
  offset: number;
  limit: number;
  window: Window;
  order: Order;
  half_life: number;
  unknown_weight: number;
  undated: number;
  dated: number;
  occurrences: number;
  questions: Ranked[];
};

export type Window = "all" | "3y" | "1y";
export type Order = "weighted" | "count";
export const WINDOWS: Window[] = ["all", "3y", "1y"];
export const HALF_LIVES = [180, 365, 730] as const;

export type CompanyRow = {
  id: string;
  name: string;
  questions: number;
  occurrences: number;
  years: string[];
  rounds: Record<string, number>;
  domains: { id: string; count: number; label: string }[];
};
export type CompanyQuestion = Card & { count: number; score: number; rounds: string[]; years_here: string[] };
export type Company = { id: string; name: string; summary: CompanyRow | null; total: number; questions: CompanyQuestion[] };

export type ListRow = { id: string; name: string; created_at: string; intent: string; questions: number; changed: number; requirements: number; covered: number; has_jd: boolean };
export type Requirement = {
  id: string;
  quote: string;
  priority: "must" | "nice" | "unspecified";
  matches: { question_id: string; title: string | null; coverage: "direct" | "partial" | "uncertain"; reason: string; needs_recheck: boolean }[];
};
export type ListDetail = {
  id: string;
  name: string;
  created_at: string;
  intent: string;
  requirements: Requirement[];
  coverage: { requirements: number; directly_covered: number; uncovered: string[] };
  changed: string[];
  summary: { questions: number; unseen: number; weak: number; familiar: number; due: number };
  questions: Card[];
};

const query = (params: Record<string, string | number | undefined>) =>
  new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== "").map(([k, v]) => [k, String(v)])).toString();

export const prepare = {
  top: (params: Record<string, string | number | undefined>) => api<Top>("/api/prepare/top?" + query(params)),
  companies: () => api<{ companies: CompanyRow[]; total: number }>("/api/prepare/companies"),
  company: (id: string) => api<Company>("/api/prepare/company?id=" + encodeURIComponent(id)),
  lists: () => api<{ lists: ListRow[]; can_save: boolean }>("/api/prepare/lists"),
  list: (id: string) => api<ListDetail>("/api/prepare/list?id=" + encodeURIComponent(id)),
  save: (plan_id: string, question_ids: string[], name: string) => api<{ id: string }>("/api/prepare/save", { plan_id, question_ids, name }),
};
