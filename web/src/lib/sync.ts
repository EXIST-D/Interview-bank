import { api } from "./api";
import { readIds, setPref } from "./prefs";
import { store, stored } from "./storage";

// Learning state (read marks, review/mastered states, source order) lives in the browser and, when the server keeps
// the person's layer, also in personal/learning.json. Opening the page merges both; later changes are sent in small
// batches. Each device sends what it did with its own time, so devices merge instead of overwriting each other.

type StateRecord = { state: string; at: string; reading_digest?: string };
type Shelf = { order: string[]; at: string };
type ServerLearning = { read: Record<string, string>; states: Record<string, StateRecord>; shelf: Shelf | null; can_write: boolean };

let writable = false;
let account = "local";
let pending: { read: Record<string, string>; states: Record<string, StateRecord>; shelf?: Shelf } = { read: {}, states: {} };
let timer: number | undefined;

const learningKey = () => "ibank-notes-learning:" + account;
export const shelfKey = (name = account) => "ibank-source-shelf:" + name;

function schedule(delay = 1500) {
  if (!writable) return;
  clearTimeout(timer);
  timer = window.setTimeout(flush, delay);
}

async function flush() {
  const batch = pending;
  if (!Object.keys(batch.read).length && !Object.keys(batch.states).length && !batch.shelf) return;
  pending = { read: {}, states: {} };
  try {
    await api("/api/learning", { read: batch.read, states: batch.states, ...(batch.shelf ? { shelf: batch.shelf } : {}) });
  } catch {
    // Keep what failed (newer local changes win) and try again later.
    pending = { read: { ...batch.read, ...pending.read }, states: { ...batch.states, ...pending.states }, shelf: pending.shelf ?? batch.shelf };
    schedule(15000);
  }
}

window.addEventListener("online", () => schedule(500));
window.addEventListener("pagehide", () => {
  if (writable) flush();
});

export function queueRead(id: string) {
  pending.read[id] ??= new Date().toISOString();
  schedule();
}

export function queueState(id: string, record: StateRecord) {
  pending.states[id] = record;
  schedule();
}

export function queueShelf(order: string[]) {
  pending.shelf = { order, at: new Date().toISOString() };
  schedule();
}

/** Merge the server's learning state into this browser, then send what only this browser knows. */
export async function startSync(name: string) {
  account = name || "local";
  let server: ServerLearning;
  try {
    server = await api<ServerLearning>("/api/learning");
  } catch {
    return;
  }
  writable = server.can_write;

  const read = readIds();
  const before = read.size;
  for (const id of Object.keys(server.read)) read.add(id);
  for (const id of read) if (!(id in server.read)) pending.read[id] = new Date().toISOString();
  if (read.size !== before) setPref("ibank-read", [...read].slice(-5000));

  const local = stored<Record<string, StateRecord>>(learningKey(), {});
  let changed = false;
  for (const [id, record] of Object.entries(server.states)) {
    if (!local[id] || (local[id].at ?? "") < record.at) {
      local[id] = record;
      changed = true;
    }
  }
  for (const [id, record] of Object.entries(local)) {
    if (!server.states[id] || server.states[id].at < (record.at ?? "")) pending.states[id] = record;
  }
  if (changed) {
    store(learningKey(), local);
    setPref("ibank-notes-learning", Date.now());
  }

  const shelf = stored<{ version: 1; order: string[]; expanded: string[]; at?: string } | null>(shelfKey(), null);
  if (server.shelf && (!shelf?.at || shelf.at < server.shelf.at)) {
    setPref(shelfKey(), { version: 1, order: server.shelf.order, expanded: shelf?.expanded ?? [], at: server.shelf.at });
  } else if (shelf?.at && (!server.shelf || server.shelf.at < shelf.at)) {
    pending.shelf = { order: shelf.order, at: shelf.at };
  }
  schedule(300);
}
