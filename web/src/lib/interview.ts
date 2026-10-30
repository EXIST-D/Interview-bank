// Mock interviews and answer feedback: the server keeps the session, saves each answer verbatim and has a model write
// feedback against the sourced reference answer. The page never gets the reference before the answer is in.
import { api } from "./api";
import type { Usage } from "./intake";

export type Dimension = "accuracy" | "coverage" | "constraints" | "clarity";
export type Verdict = "met" | "gap" | "wrong";
export type CheckState = "covered" | "partial" | "missed";

export type Observation = { dimension: Dimension; verdict?: Verdict; quote?: string; note: string };
export type Feedback = {
  observations: Observation[];
  key_point_checks: { index: number; status: CheckState; note: string }[];
  review_topics: string[];
  limited_basis: boolean;
  reference_answer_id: string | null;
  reference_sources: { url: string; title?: string }[];
  suggested_follow_up?: { prompt: string; reason: string };
  generated_by?: { kind: "model"; model: string; checks: string[] };
  created_at: string;
};

export type Response = {
  id: string;
  question_id: string;
  prompt: string;
  text: string;
  created_at: string;
  follow_up: boolean;
  feedback: Feedback | null;
};

export type Current = {
  status: "question" | "awaiting_feedback" | "completed" | "cancelled";
  question_id?: string;
  prompt?: string;
  follow_up?: boolean;
  remaining?: number;
  changed_since_start?: boolean;
  response_id?: string;
};

export type Summary = {
  answered: number;
  graded: number;
  ungraded: number;
  limited: number;
  key_points: Record<CheckState, number>;
  weak_topics: string[];
};

export type Session = {
  id: string;
  name: string;
  status: "running" | "completed" | "cancelled";
  created_at: string;
  meta: { mode?: "mock" | "review"; direction?: string; jd?: string; reasons?: Record<string, { quote?: string | null; reason?: string }> };
  position: number;
  total: number;
  current: Current;
  grading: { state: "running" | "failed"; error?: string } | null;
  responses: Response[];
  follow_ups_left: number;
  left_today: number;
  summary: Summary | null;
};

export type SessionRow = { id: string; name: string; status: Session["status"]; position: number; total: number; created_at: string; mode: "mock" | "review"; answered: number; graded: number };
export type Overview =
  | { enabled: false }
  | { enabled: true; model: string; left_today: number; max_response: number; max_questions: number; usage: { today: Usage | null; priced: boolean; daily_budget: number | null }; sessions: SessionRow[] };

export type Pick = { id: string; canonical: string; frequency: number; answered: boolean; quote: string | null; reason: string };
export type Plan = { id: string; status: "running" | "done" | "failed"; picks: Pick[]; uncovered: string[]; error: string | null; considered: number };

export type StartBody = {
  mode?: "mock" | "review";
  question_ids?: string[];
  filters?: Record<string, string>;
  limit?: number;
  order?: "frequency" | "random";
  direction?: string;
  jd?: string;
  reasons?: Record<string, { quote: string | null; reason: string }>;
};

export const interview = {
  overview: () => api<Overview>("/api/interview"),
  session: (id: string) => api<Session>("/api/interview/session?id=" + encodeURIComponent(id)),
  start: (body: StartBody) => api<Session>("/api/interview/start", body),
  answer: (session: string, question_id: string, request_id: string, text: string) => api<Session>("/api/interview/answer", { session, question_id, request_id, text }),
  regrade: (session: string) => api<Session>("/api/interview/regrade", { session }),
  followUp: (session: string) => api<Session>("/api/interview/follow-up", { session }),
  end: (session: string) => api<Session>("/api/interview/end", { session }),
  plan: (jd_text: string, limit: number) => api<Plan>("/api/interview/plan", { jd_text, limit }),
  planResult: (id: string) => api<Plan>("/api/interview/plan?id=" + encodeURIComponent(id)),
};
