import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, Download, Folder as FolderIcon, Pencil, Play, Star, Trash2, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useBank } from "@/lib/bank";
import { useFavorites, type FavoriteChange, type FavoriteItem, type Folder } from "@/lib/favorites";
import { useToast } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import { href, navigate, type Board, type Route } from "@/lib/router";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { chipClass, Segmented } from "@/components/ui/segmented";
import { SearchField, useDebounced } from "./knowledge";
import { Practice, type PracticeStart } from "./practice";

type Section = FavoriteItem["section"];
type NoteRow = { id: string; section: Section; title: string; where: string | null; text: string; updated_at: string; missing: boolean; versions: number };

const SECTIONS: Section[] = ["bank", "knowledge", "experiences", "learning"];
const BOARD_OF: Record<Section, Board> = { bank: "bank", knowledge: "knowledge", experiences: "public", learning: "learning" };

// Where an item is read: questions in the bank, notes on their own board.
const itemHref = (section: Section, id: string) => href(BOARD_OF[section], [], { open: id });

function SectionLabel({ section }: { section: Section }) {
  const { t } = useI18n();
  return <span className="shrink-0 rounded-full bg-fill px-2 py-0.5 text-caption text-muted-foreground">{t(`board_${BOARD_OF[section]}`)}</span>;
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="rounded-2xl border border-dashed border-border px-4 py-10 text-center text-footnote text-muted-foreground">{children}</p>;
}

function download(name: string, text: string) {
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob([text], { type: "text/markdown;charset=utf-8" }));
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}

function NotesTab() {
  const { t, lang } = useI18n();
  const { library } = useBank();
  const [query, setQuery] = useState("");
  const [section, setSection] = useState<Section | "">("");
  const words = useDebounced(query);
  const [rows, setRows] = useState<NoteRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const search = new URLSearchParams();
      if (words) search.set("query", words);
      if (section) search.set("section", section);
      setRows((await api<{ notes: NoteRow[] }>("/api/my-notes?" + search)).notes);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t("failed"));
    }
  }, [words, section, t]);
  useEffect(() => {
    load();
  }, [load]);

  const date = (value: string) => new Date(value).toLocaleDateString(lang, { year: "numeric", month: "short", day: "numeric" });
  const exportAll = () => {
    if (!rows?.length) return;
    const parts = rows.map((row) =>
      [`## ${row.title || row.id}`, `> ${[t(`board_${BOARD_OF[row.section]}`), row.where, date(row.updated_at)].filter(Boolean).join(" · ")}`, "", row.text.trim()].join("\n"),
    );
    const stamp = new Date().toISOString().slice(0, 10);
    download(`my-notes-${library?.account || library?.name || "bank"}-${stamp}.md`, `# ${t("mine_notes")}\n\n${parts.join("\n\n---\n\n")}\n`);
  };

  return (
    <div className="flex flex-col gap-3">
      <p className="text-footnote text-muted-foreground">{t("mine_notes_hint")}</p>
      <SearchField id="mine-search" value={query} onChange={setQuery} placeholder={t("mine_search")} />
      <div className="no-scrollbar -mx-4 flex gap-2 overflow-x-auto px-4">
        <button type="button" aria-pressed={!section} onClick={() => setSection("")} className={chipClass(!section)}>
          {t("all")}
        </button>
        {SECTIONS.map((id) => (
          <button key={id} type="button" aria-pressed={section === id} onClick={() => setSection(section === id ? "" : id)} className={chipClass(section === id)}>
            {t(`board_${BOARD_OF[id]}`)}
          </button>
        ))}
      </div>
      <div className="flex items-center gap-2">
        <p className="min-w-0 flex-1 px-0.5 text-caption text-muted-foreground tabular-nums">{rows ? t("mine_count", { n: rows.length }) : t("loading")}</p>
        <Button variant="outline" size="sm" disabled={!rows?.length} onClick={exportAll}>
          <Download />
          {t("mine_export")}
        </Button>
      </div>
      {error && (
        <div role="alert" className="rounded-2xl bg-destructive/10 px-4 py-3 text-footnote text-destructive">
          {error}{" "}
          <button type="button" className="font-medium underline" onClick={load}>
            {t("retry")}
          </button>
        </div>
      )}
      {rows && !rows.length && !error && <Empty>{t("mine_empty_notes")}</Empty>}
      <div className="flex flex-col gap-2.5">
        {rows?.map((row) => (
          <a
            key={row.id}
            href={row.missing ? undefined : itemHref(row.section, row.id)}
            aria-disabled={row.missing || undefined}
            className={cn("block surface px-4 py-3.5 transition-shadow", row.missing ? "opacity-70" : "hover:shadow-soft-lg")}
          >
            <span className="flex items-start gap-2">
              <span className="min-w-0 flex-1 text-callout font-semibold">{row.title || row.id}</span>
              <SectionLabel section={row.section} />
            </span>
            <span className="mt-1.5 line-clamp-3 block text-footnote leading-relaxed whitespace-pre-line text-muted-foreground">{row.text}</span>
            <span className="mt-2 flex flex-wrap gap-x-2.5 text-caption text-tertiary-foreground">
              {row.where && <span className="truncate">{row.where}</span>}
              <span className="tabular-nums">{t("my_answer_updated", { d: date(row.updated_at) })}</span>
              {row.missing && <span className="text-warning">{t("mine_missing")}</span>}
            </span>
          </a>
        ))}
      </div>
    </div>
  );
}

function FolderDetail({ folder, index, total, onBack }: { folder: Folder; index: number; total: number; onBack: () => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const { library } = useBank();
  const { canWrite, change } = useFavorites();
  const [busy, setBusy] = useState(false);
  const [practice, setPractice] = useState<PracticeStart | null>(null);
  const questions = folder.items.filter((item) => item.section === "bank" && !item.missing).map((item) => item.target);

  const run = async (payload: FavoriteChange, done?: string) => {
    setBusy(true);
    try {
      await change(payload);
      if (done) toast(done);
    } catch (cause) {
      toast(cause instanceof Error ? cause.message : t("failed"));
    } finally {
      setBusy(false);
    }
  };
  const rename = () => {
    const name = window.prompt(t("fav_name"), folder.name)?.trim();
    if (name && name !== folder.name) run({ action: "rename", folder: folder.id, name });
  };
  const remove = () => {
    if (window.confirm(t("fav_delete_confirm", { f: folder.name }))) run({ action: "delete", folder: folder.id }).then(onBack);
  };

  return (
    <div className="flex flex-col gap-3">
      <button type="button" onClick={onBack} className="flex items-center gap-1 self-start text-footnote font-medium text-primary">
        <ChevronLeft className="size-4" />
        {t("fav_all")}
      </button>
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="min-w-0 flex-1 truncate text-title-2 font-bold">{folder.name}</h2>
        <span className="text-footnote text-muted-foreground tabular-nums">{t("fav_items", { n: folder.items.length })}</span>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="tinted" disabled={!questions.length} onClick={() => setPractice({ kind: "ids", ids: questions })}>
          <Play />
          {t("fav_practise")}
        </Button>
        {canWrite && (
          <>
            <Button size="sm" variant="outline" disabled={busy} onClick={rename}>
              <Pencil />
              {t("fav_rename")}
            </Button>
            <Button size="sm" variant="outline" aria-label={t("fav_move_up")} title={t("fav_move_up")} disabled={busy || index === 0} onClick={() => run({ action: "move", folder: folder.id, position: index - 1 })}>
              <ArrowUp />
            </Button>
            <Button size="sm" variant="outline" aria-label={t("fav_move_down")} title={t("fav_move_down")} disabled={busy || index >= total - 1} onClick={() => run({ action: "move", folder: folder.id, position: index + 1 })}>
              <ArrowDown />
            </Button>
            <Button size="sm" variant="outline" className="text-destructive" disabled={busy} onClick={remove}>
              <Trash2 />
              {t("fav_delete")}
            </Button>
          </>
        )}
      </div>
      {folder.items.length > 0 && !questions.length && <p className="text-caption text-muted-foreground">{t("fav_no_questions")}</p>}
      {!folder.items.length && <Empty>{t("fav_empty")}</Empty>}
      <div className="overflow-hidden surface">
        {folder.items.map((item) => (
          <div key={item.id} className="flex items-center gap-2 border-t border-border first:border-t-0">
            <a
              href={item.missing ? undefined : itemHref(item.section, item.target)}
              className={cn("flex min-w-0 flex-1 items-center gap-3 px-4 py-3", item.missing ? "opacity-70" : "hover:bg-fill/60")}
            >
              <span className="min-w-0 flex-1">
                <span className="line-clamp-2 block text-callout">{item.title || item.id}</span>
                <span className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-caption text-muted-foreground">
                  <SectionLabel section={item.section} />
                  {item.where && <span className="truncate">{item.where}</span>}
                  {item.missing && <span className="text-warning">{t("mine_missing")}</span>}
                </span>
              </span>
            </a>
            {canWrite && (
              <button
                type="button"
                disabled={busy}
                aria-label={t("fav_remove")}
                title={t("fav_remove")}
                onClick={() => run({ action: "remove", folder: folder.id, item: item.id }, t("fav_removed", { f: folder.name }))}
                className="mr-2 grid size-8 shrink-0 place-items-center rounded-full text-tertiary-foreground hover:bg-fill hover:text-foreground"
              >
                <X className="size-4" />
              </button>
            )}
          </div>
        ))}
      </div>
      <Practice start={practice} onClose={() => setPractice(null)} params={() => new URLSearchParams()} canRecord={Boolean(library?.can_record)} />
    </div>
  );
}

function FavoritesTab({ route }: { route: Route }) {
  const { t } = useI18n();
  const toast = useToast();
  const { folders, canWrite, change } = useFavorites();
  const [name, setName] = useState("");
  const openId = route.params.get("folder");
  const open = (id: string | null) => navigate("mine", [], id ? { tab: "favorites", folder: id } : { tab: "favorites" });

  if (!folders) return <p className="text-footnote text-muted-foreground">{t("loading")}</p>;
  const index = folders.findIndex((f) => f.id === openId);
  if (index >= 0) return <FolderDetail folder={folders[index]} index={index} total={folders.length} onBack={() => open(null)} />;

  const create = async () => {
    try {
      await change({ action: "create", name: name.trim() });
      setName("");
    } catch (cause) {
      toast(cause instanceof Error ? cause.message : t("failed"));
    }
  };

  return (
    <div className="flex flex-col gap-3">
      {canWrite && (
        <form
          className="flex gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            if (name.trim()) create();
          }}
        >
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            maxLength={60}
            placeholder={t("fav_new")}
            aria-label={t("fav_name")}
            className="h-10 min-w-0 flex-1 rounded-xl bg-fill px-3.5 text-subhead outline-none focus:ring-2 focus:ring-ring/30"
          />
          <Button type="submit" disabled={!name.trim()}>
            {t("fav_create")}
          </Button>
        </form>
      )}
      {!folders.length && <Empty>{t("fav_empty_folders")}</Empty>}
      <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
        {folders.map((folder) => {
          const sections = SECTIONS.filter((s) => folder.items.some((item) => item.section === s));
          return (
            <button key={folder.id} type="button" onClick={() => open(folder.id)} className="flex items-center gap-3 surface px-4 py-3.5 text-left transition-shadow hover:shadow-soft-lg">
              <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-orange/14 text-warning">
                <FolderIcon className="size-5" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-callout font-semibold">{folder.name}</span>
                <span className="mt-0.5 block truncate text-caption text-muted-foreground">
                  {[t("fav_items", { n: folder.items.length }), ...sections.map((s) => t(`board_${BOARD_OF[s]}`))].join(" · ")}
                </span>
              </span>
              <ChevronRight className="size-4 text-tertiary-foreground" />
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function MinePage({ route }: { route: Route }) {
  const { t } = useI18n();
  const tab = route.params.get("tab") === "favorites" ? "favorites" : "notes";
  return (
    <div className="mx-auto max-w-[880px] px-4 pt-6 pb-28 sm:px-6 md:pt-8 md:pb-16">
      <p className="flex items-center gap-1.5 text-caption font-semibold tracking-wide text-primary">
        <Star className="size-3.5" />
        {t("board_mine")}
      </p>
      <h1 className="mt-0.5 mb-4 text-title-1 font-bold">{t(tab === "notes" ? "mine_notes" : "mine_favorites")}</h1>
      <div className="mb-4">
        <Segmented
          value={tab}
          onChange={(next) => navigate("mine", [], next === "favorites" ? { tab: next } : undefined)}
          options={[
            { value: "notes", label: t("mine_notes") },
            { value: "favorites", label: t("mine_favorites") },
          ]}
        />
      </div>
      {tab === "notes" ? <NotesTab /> : <FavoritesTab route={route} />}
    </div>
  );
}
