// Talks only to the server that served this page: loopback, or the user's own proxy under a path such as /ibank/.

const launch = new URLSearchParams(location.hash.slice(1));
let token = launch.get("token");
try {
  if (token) sessionStorage.setItem("ibank-token", token);
  else token = sessionStorage.getItem("ibank-token");
} catch {
  /* storage blocked: the token lasts for this page only */
}
if (launch.has("token")) {
  launch.delete("token");
  const rest = launch.toString();
  history.replaceState(null, "", location.pathname + (rest ? "#" + rest : ""));
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(path.replace(/^\//, ""), {
    method: body ? "POST" : "GET",
    headers: { "X-Interview-Token": token ?? "", ...(body ? { "Content-Type": "application/json" } : {}) },
    body: body ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });
  let result: (T & { error?: string; login?: boolean }) | undefined;
  try {
    result = await response.json();
  } catch {
    throw new ApiError("unreachable", response.status);
  }
  // A hosted reader whose session ended shows its login page again.
  if (response.status === 401 && result?.login) {
    location.reload();
    return new Promise(() => {});
  }
  if (!response.ok) throw new ApiError(result?.error || "failed", response.status);
  return result as T;
}

export type Facet = { value: string; label: string; count: number };

export type QuestionRow = {
  id: string;
  canonical: string;
  frequency: number;
  answer_status: string;
  group: string;
  updated_at: string;
  has_my_answer?: boolean;
};

export type MyAnswer = { text: string; updated_at: string };

export type Library = {
  name: string;
  account?: string;
  version: string;
  schema_version: number;
  language: string;
  read_only: boolean;
  can_logout?: boolean;
  can_record: boolean;
  can_review: boolean;
  can_write_answer?: boolean;
  can_write_personal?: boolean;
  summary: { questions: number; answered: number; due: number; weak: number; unseen: number; stale: number };
  notes?: { total: number; collections: number };
  total: number;
  total_answered: number;
  facets: Record<"group" | "domain" | "technology" | "company" | "role" | "industry", Facet[]>;
  ids: string[];
  questions: QuestionRow[];
};

export type Answer = {
  id: string;
  short_answer: string;
  code_example?: string | null;
  key_points?: string[];
  evidence?: { key_point: number; source_urls?: string[] }[];
  sources?: { url: string; title?: string }[];
  spoken_answer?: string | string[] | null;
  follow_up_questions?: string | string[] | null;
  common_mistakes?: string | string[] | null;
  deep_dive?: string | string[] | null;
};

export type LinkedNote = { id: string; relation: string; title: string; marked: boolean; where: string };

export type QuestionDetail = QuestionRow & {
  revision: string;
  problem_url: { url: string } | null;
  technologies: string[];
  companies: string[];
  years: (string | number)[];
  answer: Answer | null;
  my_answer?: MyAnswer | null;
  notes?: LinkedNote[];
  occurrences: {
    text: string;
    year?: string | number | null;
    platform?: string | null;
    locator?: { start_seconds?: number; start?: number } | null;
  }[];
  history: { rating: string; occurred_at: string; note?: string; next_review_at?: string }[];
};

const details = new Map<string, Promise<QuestionDetail>>();

export function questionDetail(id: string, fresh = false) {
  if (fresh) details.delete(id);
  if (!details.has(id)) {
    details.set(
      id,
      api<QuestionDetail>("/api/question?id=" + encodeURIComponent(id)).catch((error) => {
        details.delete(id);
        throw error;
      }),
    );
  }
  return details.get(id)!;
}

export function clearDetails() {
  details.clear();
}

export type NotesOverview = {
  section: string;
  section_counts: { knowledge: number; learning: number; experiences: number };
  learning_categories: { kind: string; count: number; sources: number }[];
  collections: { name: string; title: string; knowledge_total: number; experience_total: number; learning_total: number }[];
  facets: { companies: string[] };
  total: number;
};
