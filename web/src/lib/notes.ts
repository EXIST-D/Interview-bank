import { api } from "./api";
import { readIds as readIdSet, setPref } from "./prefs";
import { queueState } from "./sync";
import { store, stored } from "./storage";

export type NotesSection = "knowledge" | "experiences" | "learning";
export const LEARNING_KINDS = ["roadmap", "tutorial", "resource", "career", "news"] as const;
export type LearningState = "unread" | "read" | "review" | "mastered";

export type ReadingGroup = { note_ids: string[]; content_digest: string };

export type Area = { id: string; title: string; count: number; topics: { id: string; title: string; count: number }[] };

export type SourceCard = {
  name: string;
  title: string;
  origin?: string;
  imported_at?: string;
  content_total: number;
  information_total: number;
  knowledge_total: number;
  experience_total: number;
  learning_total: number;
  content_ids: string[];
  information_ids: string[];
  reading_members?: Record<string, ReadingGroup>;
  reading_groups_incomplete?: number;
  marked: number;
  linked: number;
  public_linked: number;
  chapters: { index: number; title: string; count: number }[];
  areas: Area[];
  kinds: Record<string, number>;
  metadata: {
    author?: string;
    description?: string;
    homepage?: string;
    language?: string;
    license?: string;
    license_url?: string;
    updated_at?: string;
    version?: string;
  };
  history: { at: string; changed: { chapters?: number; notes?: number; areas?: boolean } }[];
  organization_updated_at?: string;
  organization_stale?: boolean;
};

export type Experience = {
  company?: string | null;
  role?: string | null;
  round?: string | null;
  year?: string | null;
  domain: string;
  interview_time?: string | null;
  published_time?: string | null;
  summary?: string | null;
  incomplete?: boolean;
  facts: { quote: string; url?: string }[];
};

export type NoteCardData = {
  id: string;
  title: string;
  collection: string;
  collection_title: string;
  chapter: number;
  chapter_title: string;
  marked: boolean;
  asked: number;
  area: string;
  area_title: string;
  topic: string;
  topic_title: string;
  tags: string[];
  kind: string;
  question_type?: string;
  verification: string;
  evidence: string[];
  study_note_count?: number;
  public_experience_count?: number;
  experience?: Experience;
  reading?: ReadingGroup;
  has_my_answer?: boolean;
};

export type StudyEdge = {
  id: string;
  title: string;
  relation: string;
  question_quote: string;
  answer_quote: string;
  reason: string;
  company?: string;
  interview_time?: string;
  area_title?: string;
  topic_title?: string;
};

export type NoteDetail = NoteCardData & {
  body: string;
  section: NotesSection;
  source: { collection: string; chapter: string; file: string; line: number; origin?: string; imported_at?: string };
  questions: { id: string; canonical: string; frequency: number; relation: string; answered: boolean }[];
  study_notes?: StudyEdge[];
  public_experiences?: StudyEdge[];
  study_links_incomplete?: number;
  my_answer?: { text: string; updated_at: string } | null;
};

export type NotesFacets = {
  tags: string[];
  kinds: Record<string, number>;
  question_types: Record<string, number>;
  verification: Record<string, number>;
  companies: string[];
  years: string[];
  experience_domains: Record<string, number>;
  experience_years: Record<string, number>;
  unknown_company: boolean;
  unknown_year: boolean;
};

export type NotesPage = {
  section: NotesSection;
  collections?: SourceCard[];
  section_counts: Record<NotesSection, number>;
  learning_categories: { kind: string; count: number; sources: number }[];
  facets: NotesFacets;
  total: number;
  ids: string[];
  notes: NoteCardData[];
};

// Source cards are large and rarely change: one request per section and session, then lists use meta=0.
const meta = new Map<NotesSection, Promise<NotesPage>>();

export function sourceCards(section: NotesSection, fresh = false) {
  if (fresh) meta.delete(section);
  if (!meta.has(section)) {
    meta.set(
      section,
      api<NotesPage>(`/api/notes?limit=1&section=${section}`).catch((error) => {
        meta.delete(section);
        throw error;
      }),
    );
  }
  return meta.get(section)!;
}

export function notesPage(params: URLSearchParams) {
  params.set("meta", "0");
  return api<NotesPage>("/api/notes?" + params);
}

const details = new Map<string, Promise<NoteDetail>>();

export function noteDetail(id: string, fresh = false) {
  if (fresh) details.delete(id);
  if (!details.has(id)) {
    details.set(
      id,
      api<NoteDetail>("/api/note?id=" + encodeURIComponent(id)).catch((error) => {
        details.delete(id);
        throw error;
      }),
    );
  }
  return details.get(id)!;
}

export function clearNotes() {
  meta.clear();
  details.clear();
}

export const sectionOf = (note: { section?: NotesSection; experience?: unknown; kind: string }): NotesSection =>
  note.section ?? (note.experience ? "experiences" : (LEARNING_KINDS as readonly string[]).includes(note.kind) ? "learning" : "knowledge");

// ---------------------------------------------------------------- learning state (this browser only)

type LearningRecord = { state: LearningState; at: string; reading_digest?: string };
const VALID: LearningState[] = ["unread", "read", "review", "mastered"];
let account = "local";
let groups: Record<string, ReadingGroup> = {};

export function setLearningAccount(name: string) {
  account = name || "local";
}

export function rememberReadingGroups(cards: SourceCard[]) {
  for (const card of cards) Object.assign(groups, card.reading_members ?? {});
}

const learningKey = () => "ibank-notes-learning:" + account;
// Parsed once per change: shelf progress asks for thousands of entries at a time.
let cached: { key: string; values: Record<string, LearningRecord> } | null = null;
const records = () => {
  if (cached?.key !== learningKey()) cached = { key: learningKey(), values: stored<Record<string, LearningRecord>>(learningKey(), {}) };
  return cached.values;
};
window.addEventListener("storage", () => {
  cached = null;
});

export function learningState(id: string, group: ReadingGroup | undefined = groups[id], read?: Set<string>): LearningState {
  const values = records();
  const readIds = read ?? readIdSet();
  const raw = (member: string): LearningState =>
    VALID.includes(values[member]?.state) ? values[member].state : readIds.has(member) ? "read" : "unread";
  if (!group) return raw(id);
  // A reading unit keeps its own state while its text is unchanged; otherwise it sums up its members.
  if (values[id]?.reading_digest === group.content_digest && VALID.includes(values[id].state)) return values[id].state;
  const states = group.note_ids.map(raw);
  if (states.includes("review")) return "review";
  if (states.every((s) => s === "mastered")) return "mastered";
  return states.every((s) => s === "read" || s === "mastered") ? "read" : "unread";
}

export function recordVisit(id: string, group: ReadingGroup | undefined = groups[id]) {
  const values = records();
  if (group) {
    const current = learningState(id, group);
    const state = current === "review" || current === "mastered" ? current : "read";
    if (values[id]?.state === state && values[id]?.reading_digest === group.content_digest) return;
    values[id] = { state, at: new Date().toISOString(), reading_digest: group.content_digest };
  } else if (!values[id] || values[id].state === "unread") values[id] = { state: "read", at: new Date().toISOString() };
  else return;
  save(values, id);
}

export function setLearning(id: string, state: LearningState | "", group?: ReadingGroup) {
  const values = records();
  values[id] = { state: state || "unread", at: new Date().toISOString(), ...(group ? { reading_digest: group.content_digest } : {}) };
  save(values, id);
}

function save(values: Record<string, LearningRecord>, changed: string) {
  store(learningKey(), values);
  cached = { key: learningKey(), values };
  queueState(changed, values[changed]);
  setPref("ibank-notes-learning", Date.now());
}

// The server's state merged into this browser (lib/sync) replaces the stored records.
window.addEventListener("ibank-pref", (event) => {
  if ((event as CustomEvent).detail === "ibank-notes-learning") cached = null;
});
