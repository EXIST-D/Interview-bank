// Screenshot import: the server runs the Skill's intake with a model; the page uploads, shows progress and asks
// the person to confirm what was read. Images are prepared here so phone screenshots stay readable for the model.
import { api, upload } from "./api";

export type Flag = "low_confidence" | "contact";
export type IntakeQuestion = {
  id: string;
  original_text: string;
  canonical_suggestion: string;
  parent_id?: string;
  question_type: string;
  domains: string[];
  technologies: string[];
  flags: Flag[];
};
export type IntakeSource = {
  source_id: string;
  index: number;
  status: "pending" | "extracted" | "no_questions" | "unreadable" | "failed";
  reason: string | null;
  error?: string | null;
  metadata: { company?: string; round?: string; event_date?: string; platform?: string };
  questions: IntakeQuestion[];
  self_introductions_dropped?: number;
};
export type MergeAsk = { question_id: string; question: string; target_id: string; target: string; reason: string; canonical?: string | null };
export type Saved = { id: string; canonical: string; from?: string };
export type JobStatus = "collecting" | "extracting" | "review" | "saving" | "merge_review" | "answering" | "done" | "cancelled";
export type Job = {
  id: string;
  kind: "import" | "research";
  status: JobStatus;
  created_at: string;
  updated_at: string;
  hints: Hints;
  images: { index: number; size: number; mime: string; views: number[]; duplicate?: boolean }[];
  sources: IntakeSource[];
  progress: { phase: string; done: number; total: number } | null;
  error: string | null;
  notice: string | null;
  merge_review: MergeAsk[] | null;
  result: {
    added: Saved[];
    merged: Saved[];
    related: number;
    nothing_new?: boolean;
    answers_skipped_for_limit?: number;
    research?: boolean;
    questions?: Saved[];
    more?: number;
  } | null;
  answers: { pending: string[]; done: string[]; failed: Record<string, string>; sourced?: string[]; searched?: number } | null;
};
export type Hints = { company?: string; position?: string; round?: string; interview_type?: string; event_date?: string };
export type Overview = {
  enabled: boolean;
  models?: Record<"vision" | "text", { model: string; host: string }> & { search?: { provider: string; pages: number } };
  limits?: { max_images_per_job: number; images_left_today: number; max_image_bytes: number; max_view_bytes: number; max_views: number };
  research?: { candidates: number; per_job: number; left_today: number } | null;
  active?: Job | null;
  recent?: { id: string; kind?: Job["kind"]; status: JobStatus; created_at: string; images: number; result: Job["result"]; answers: Job["answers"] }[];
};

export const RUNNING: JobStatus[] = ["extracting", "saving", "answering"];
export const ROUNDS = ["technical-1", "technical-2", "technical-3", "manager", "hr", "cross", "written"] as const;

export const intake = {
  overview: () => api<Overview>("/api/intake"),
  job: (id: string) => api<Job>("/api/intake/job?id=" + encodeURIComponent(id)),
  create: (hints: Hints) => api<Job>("/api/intake/jobs", { hints }),
  start: (job: string) => api<Job>("/api/intake/start", { job }),
  confirm: (job: string, sources: unknown[]) => api<Job>("/api/intake/confirm", { job, sources }),
  merge: (job: string, decisions: { question_id: string; action: string }[]) => api<Job>("/api/intake/merge", { job, decisions }),
  retryAnswers: (job: string) => api<Job>("/api/intake/answers", { job }),
  retryRead: (job: string) => api<Job>("/api/intake/retry", { job }),
  cancel: (job: string) => api<Job>("/api/intake/cancel", { job }),
  research: (questionIds?: string[]) => api<Job>("/api/intake/research", questionIds ? { question_ids: questionIds } : {}),
  upload: (job: string, image: number, blob: Blob, view?: number) =>
    upload<Job>(`/api/intake/upload?job=${encodeURIComponent(job)}&image=${image}${view === undefined ? "" : `&view=${view}`}`, blob),
};

const SENDABLE = ["image/png", "image/jpeg", "image/webp", "image/gif"];
const TALL = 2.2;
const TILE_WIDTH = 1440;
const MAX_TILES = 8;
const LARGE_VIEW = 3.5 * 1024 * 1024;

export type Prepared = { key: string; name: string; original: Blob; views: Blob[]; thumb: string | null; preview: string | null; tiles: number };

function encode(canvas: HTMLCanvasElement, quality = 0.86) {
  return new Promise<Blob>((resolve, reject) => canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("encode"))), "image/jpeg", quality));
}

function draw(bitmap: ImageBitmap, sx: number, sy: number, sw: number, sh: number, scale: number) {
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(sw * scale));
  canvas.height = Math.max(1, Math.round(sh * scale));
  const context = canvas.getContext("2d")!;
  context.fillStyle = "#fff";
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.drawImage(bitmap, sx, sy, sw, sh, 0, 0, canvas.width, canvas.height);
  return canvas;
}

/**
 * The original bytes stay the source of record. Long screenshots also get overlapping parts (models shrink a tall
 * image until its text is unreadable), very large ones a smaller copy; formats the server does not take (HEIC on
 * Safari) or files above its limit are re-encoded as JPEG.
 */
export async function prepare(file: File, maxBytes: number): Promise<Prepared> {
  const key = `${file.name}:${file.size}:${file.lastModified}:${Math.random().toString(36).slice(2, 8)}`;
  let bitmap: ImageBitmap | null = null;
  try {
    bitmap = await createImageBitmap(file);
  } catch {
    if (!SENDABLE.includes(file.type)) throw new Error("unsupported");
  }
  if (!bitmap) return { key, name: file.name, original: file, views: [], thumb: null, preview: null, tiles: 0 };
  try {
    const { width, height } = bitmap;
    const thumbScale = Math.min(1, 240 / width, 480 / height);
    const thumb = draw(bitmap, 0, 0, width, height, thumbScale).toDataURL("image/jpeg", 0.7);
    // For checking the questions against the screenshot on the review page; data URLs keep the content policy.
    const preview = draw(bitmap, 0, 0, width, height, Math.min(1, 900 / width, Math.sqrt(6_000_000 / (width * height)))).toDataURL("image/jpeg", 0.8);
    let original: Blob = file;
    if (!SENDABLE.includes(file.type) || file.size > maxBytes) {
      const scale = Math.min(1, Math.sqrt(16_000_000 / (width * height)));
      original = await encode(draw(bitmap, 0, 0, width, height, scale), 0.9);
    }
    const views: Blob[] = [];
    const scale = Math.min(1, TILE_WIDTH / width);
    if (height / width > TALL) {
      let tile = Math.round(width * 1.5);
      let overlap = Math.round(width * 0.08);
      if (Math.ceil((height - overlap) / (tile - overlap)) > MAX_TILES) {
        tile = Math.ceil((height + overlap * (MAX_TILES - 1)) / MAX_TILES);
        overlap = Math.min(overlap, Math.round(tile * 0.08));
      }
      for (let top = 0; top < height && views.length < MAX_TILES; top += tile - overlap) {
        const piece = Math.min(tile, height - top);
        views.push(await encode(draw(bitmap, 0, top, width, piece, scale)));
        if (top + piece >= height) break;
      }
    } else if (original.size > LARGE_VIEW || Math.max(width, height) > 3000) {
      views.push(await encode(draw(bitmap, 0, 0, width, height, Math.min(1, 2048 / Math.max(width, height)))));
    }
    return { key, name: file.name, original, views, thumb, preview, tiles: views.length > 1 ? views.length : 0 };
  } finally {
    bitmap.close();
  }
}
