import { useEffect, useRef, useState } from "react";
import { Compartment, EditorSelection, EditorState, Prec, StateEffect, StateField, Transaction, type Range } from "@codemirror/state";
import { Decoration, EditorView, keymap, placeholder, WidgetType, type DecorationSet } from "@codemirror/view";
import { defaultKeymap, history, historyKeymap, isolateHistory, redo, undo } from "@codemirror/commands";
import { markdown } from "@codemirror/lang-markdown";
import { GFM, parser } from "@lezer/markdown";
import { Bold, Code2, Heading2, Italic, Link2, List, Quote } from "lucide-react";
import { useI18n } from "@/lib/i18n";
import { safeUrl } from "./markdown";

const LIMIT = 20000;
const markdownParser = parser.configure(GFM);
const focus = StateEffect.define<boolean>();
const composing = StateEffect.define<boolean>();
type Preview = { tree: ReturnType<typeof markdownParser.parse>; focused: boolean; composing: boolean; decorations: DecorationSet; atomic: DecorationSet };

class TextWidget extends WidgetType {
  constructor(readonly text: string, readonly className: string) { super(); }
  eq(other: TextWidget) { return this.text === other.text && this.className === other.className; }
  toDOM() {
    const span = document.createElement("span");
    span.className = this.className;
    span.textContent = this.text;
    span.setAttribute("aria-hidden", "true");
    return span;
  }
}

// React/textContent elsewhere and these text nodes keep raw HTML inert. No remote images are fetched.
function tableInline(parent: HTMLElement, value: string) {
  for (const part of value.split(/(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)\s]+\))/g)) {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      const strong = document.createElement("strong"); strong.textContent = part.slice(2, -2); parent.append(strong);
    } else if (part.startsWith("`") && part.endsWith("`") && part.length > 2) {
      const code = document.createElement("code"); code.textContent = part.slice(1, -1); parent.append(code);
    } else {
      const link = part.match(/^\[([^\]]+)\]\(([^)\s]+)\)$/);
      const url = link && safeUrl(link[2]);
      if (link && url) {
        const a = document.createElement("a"); a.textContent = link[1]; a.href = url.href; a.target = "_blank"; a.rel = "noopener noreferrer"; parent.append(a);
      } else parent.append(document.createTextNode(part));
    }
  }
}

class TableWidget extends WidgetType {
  constructor(readonly source: string, readonly from: number) { super(); }
  eq(other: TableWidget) { return this.source === other.source && this.from === other.from; }
  toDOM(view: EditorView) {
    const wrap = document.createElement("div"); wrap.className = "cm-md-table";
    const table = document.createElement("table");
    let offset = this.from;
    this.source.split("\n").forEach((line, index) => {
      const lineStart = offset; offset += line.length + 1;
      if (index === 1) return; // GFM's alignment/delimiter row.
      const row = document.createElement("tr");
      // Escaped pipes stay in their cells; the Markdown source itself is never rewritten.
      const body = line.trim().replace(/^\|/, "").replace(/(?<!\\)\|$/, "");
      let start = line.indexOf(body);
      for (const part of body.split(/(?<!\\)\|/)) {
        const cell = document.createElement(index === 0 ? "th" : "td");
        tableInline(cell, part.trim().replace(/\\\|/g, "|"));
        const position = Math.min(lineStart + Math.max(0, start) + 1, view.state.doc.length);
        cell.addEventListener("pointerdown", (event) => {
          if ((event.target as HTMLElement).closest("a") || view.state.readOnly) return;
          event.preventDefault();
          view.dispatch({ selection: { anchor: position }, effects: focus.of(true), scrollIntoView: true }); view.focus();
        });
        row.append(cell); start += part.length + 1;
      }
      table.append(row);
    });
    wrap.append(table); return wrap;
  }
  ignoreEvent() { return true; }
}

class TaskWidget extends WidgetType {
  constructor(readonly checked: boolean, readonly position: number, readonly disabled: boolean) { super(); }
  eq(other: TaskWidget) { return this.checked === other.checked && this.position === other.position && this.disabled === other.disabled; }
  toDOM(view: EditorView) {
    const input = document.createElement("input"); input.type = "checkbox"; input.checked = this.checked;
    input.className = "cm-md-task"; input.disabled = this.disabled; input.tabIndex = -1;
    input.setAttribute("aria-label", view.state.doc.lineAt(this.position).text.replace(/^\s*[-+*]\s+\[[ xX]\]\s*/, "").trim() || (this.checked ? "[x]" : "[ ]"));
    input.addEventListener("mousedown", (event) => event.preventDefault());
    input.addEventListener("change", () => {
      if (!view.state.readOnly) view.dispatch({ changes: { from: this.position + 1, to: this.position + 2, insert: input.checked ? "x" : " " }, userEvent: "input" });
    });
    return input;
  }
  ignoreEvent() { return true; }
}

function decorate(state: EditorState, tree: Preview["tree"], focused: boolean, isComposing: boolean): Pick<Preview, "decorations" | "atomic"> {
  const ranges: Range<Decoration>[] = [], atomic: Range<Decoration>[] = [];
  const active = (from: number, to: number) => focused && !state.readOnly && state.selection.ranges.some((r) => state.doc.lineAt(r.from).from <= to && state.doc.lineAt(r.to).to >= from);
  const mark = (from: number, to: number, className: string, attributes?: Record<string, string>) => {
    if (to > from) ranges.push(Decoration.mark({ class: className, attributes, tagName: attributes?.["data-note-url"] ? "a" : undefined }).range(from, to));
  };
  const hide = (from: number, to: number, widget?: WidgetType, block = false) => {
    if (to <= from) return;
    const decoration = Decoration.replace({ widget, block, inclusive: false }).range(from, to);
    ranges.push(decoration); atomic.push(decoration);
  };
  const line = (from: number, className: string, attributes?: Record<string, string>) => ranges.push(Decoration.line({ class: className, attributes }).range(state.doc.lineAt(from).from));
  tree.iterate({ enter(ref) {
    const node = ref.node, name = node.name, editing = active(node.from, node.to);
    if (isComposing && editing && name !== "Document") return false;
    if (name === "Table" && !editing) { hide(node.from, node.to, new TableWidget(state.sliceDoc(node.from, node.to), node.from), true); return false; }
    if (name === "FencedCode" || name === "CodeBlock") {
      const first = state.doc.lineAt(node.from), last = state.doc.lineAt(node.to);
      for (let n = first.number; n <= last.number; n++) line(state.doc.line(n).from, "cm-md-codeblock" + (n === first.number ? " cm-md-code-first" : "") + (n === last.number ? " cm-md-code-last" : ""));
      if (name === "FencedCode" && !editing) {
        const label = first.text.trim().replace(/^(`{3,}|~{3,})\s*/, "") || "code";
        hide(first.from, first.to, new TextWidget(label, "cm-md-code-language"));
        if (last.number > first.number && /^\s*(`{3,}|~{3,})\s*$/.test(last.text)) hide(last.from, last.to);
      }
      return false;
    }
    if (/^ATXHeading[1-6]$/.test(name)) line(node.from, "cm-md-heading cm-md-h" + name.slice(-1), { role: "heading", "aria-level": name.slice(-1) });
    if (/^SetextHeading/.test(name)) line(node.from, "cm-md-heading cm-md-h2", { role: "heading", "aria-level": name.endsWith("1") ? "1" : "2" });
    if (name === "Blockquote") {
      for (let n = state.doc.lineAt(node.from).number; n <= state.doc.lineAt(node.to).number; n++) line(state.doc.line(n).from, "cm-md-quote");
    }
    if (name === "StrongEmphasis") mark(node.from, node.to, "cm-md-strong");
    if (name === "Emphasis") mark(node.from, node.to, "cm-md-emphasis");
    if (name === "Strikethrough") mark(node.from, node.to, "cm-md-strike");
    if (name === "InlineCode") mark(node.from, node.to, "cm-md-inline-code");
    if (name === "HorizontalRule" && !editing) { hide(node.from, node.to, new TextWidget("", "cm-md-rule")); return false; }
    if (name === "TaskMarker") {
      if (!editing) hide(node.from, node.to, new TaskWidget(/x/i.test(state.sliceDoc(node.from, node.to)), node.from, state.readOnly));
      return false;
    }
    if (name === "Image") { mark(node.from, node.to, "cm-md-image-source"); return false; }
    if (name === "Link" && !editing) {
      const source = state.sliceDoc(node.from, node.to), match = source.match(/^\[([\s\S]*?)\]\(([^\s]+?)(?:\s+"[^"]*")?\)$/);
      if (match) {
        const url = safeUrl(match[2]);
        hide(node.from, node.from + 1);
        mark(node.from + 1, node.from + 1 + match[1].length, url ? "cm-md-link" : "", url ? { "data-note-url": url.href, title: url.href, href: url.href, target: "_blank", rel: "noopener noreferrer" } : undefined);
        hide(node.from + 1 + match[1].length, node.to);
        return false;
      }
    }
    if (["HeaderMark", "QuoteMark", "EmphasisMark", "StrikethroughMark", "CodeMark"].includes(name)) {
      if (active(node.from, node.to)) mark(node.from, node.to, "cm-md-formatting");
      else hide(node.from, node.to);
    }
    if (name === "ListMark") {
      const text = state.sliceDoc(node.from, node.to);
      const task = /^\s+\[[ xX]\]/.test(state.sliceDoc(node.to, state.doc.lineAt(node.to).to));
      if (!active(node.from, node.to) && /^[-+*]$/.test(text)) hide(node.from, node.to, task ? undefined : new TextWidget("•", "cm-md-bullet"));
      else mark(node.from, node.to, "cm-md-formatting");
    }
  } });
  return { decorations: Decoration.set(ranges, true), atomic: Decoration.set(atomic, true) };
}

const livePreview = StateField.define<Preview>({
  create(state) {
    const tree = markdownParser.parse(state.doc.toString());
    return { tree, focused: false, composing: false, ...decorate(state, tree, false, false) };
  },
  update(previous, tr) {
    const focused = tr.effects.find((effect) => effect.is(focus))?.value ?? previous.focused;
    const isComposing = tr.effects.find((effect) => effect.is(composing))?.value ?? previous.composing;
    if (!tr.docChanged && !tr.selection && !tr.reconfigured && focused === previous.focused && isComposing === previous.composing) return previous;
    const tree = tr.docChanged ? markdownParser.parse(tr.newDoc.toString()) : previous.tree;
    return { tree, focused, composing: isComposing, ...decorate(tr.state, tree, focused, isComposing) };
  },
  provide: (field) => [EditorView.decorations.from(field, (value) => value.decorations), EditorView.atomicRanges.of((view) => view.state.field(field).atomic)],
});

type Format = "heading" | "bold" | "italic" | "list" | "quote" | "code" | "link";
function format(view: EditorView, kind: Format) {
  if (view.state.readOnly || view.composing) return false;
  const { from, to } = view.state.selection.main, text = view.state.sliceDoc(from, to);
  if (["heading", "list", "quote"].includes(kind)) {
    const start = view.state.doc.lineAt(from), end = view.state.doc.lineAt(to), prefix = { heading: "## ", list: "- ", quote: "> " }[kind as "heading" | "list" | "quote"];
    const lines = view.state.sliceDoc(start.from, end.to).split("\n");
    const remove = lines.every((value) => value.startsWith(prefix));
    const insert = lines.map((value) => remove ? value.slice(prefix.length) : prefix + value).join("\n");
    view.dispatch({ changes: { from: start.from, to: end.to, insert }, selection: EditorSelection.cursor(start.from + insert.length), userEvent: "input.format", annotations: isolateHistory.of("full") });
  } else {
    const pair = { bold: ["**", "**"], italic: ["*", "*"], code: ["`", "`"], link: ["[", "](https://)"] }[kind as "bold" | "italic" | "code" | "link"];
    const [before, after] = pair;
    const wrapped = kind !== "link" && from >= before.length && view.state.sliceDoc(from - before.length, from) === before && view.state.sliceDoc(to, to + after.length) === after;
    if (wrapped) view.dispatch({ changes: { from: from - before.length, to: to + after.length, insert: text }, selection: { anchor: from - before.length, head: to - before.length }, userEvent: "input.format", annotations: isolateHistory.of("full") });
    else {
      const insert = before + text + after;
      const anchor = kind === "link" ? from + before.length + text.length + 2 : from + before.length;
      const head = kind === "link" ? anchor + 8 : anchor + text.length;
      view.dispatch({ changes: { from, to, insert }, selection: { anchor, head }, userEvent: "input.format", annotations: isolateHistory.of("full") });
    }
  }
  view.focus(); return true;
}

export function LiveMarkdownEditor({ value, resetRevision, readOnly, onChange, onSave }: { value: string; resetRevision: number; readOnly: boolean; onChange: (value: string) => void; onSave: () => void }) {
  const { t } = useI18n();
  const host = useRef<HTMLDivElement>(null), view = useRef<EditorView | null>(null);
  const config = useRef(new Compartment());
  const latest = useRef({ onChange, onSave }); latest.current = { onChange, onSave };
  const [limited, setLimited] = useState(false);
  const label = t("my_note"), hint = t("my_answer_placeholder");
  const settings = (locked: boolean) => [EditorState.readOnly.of(locked), EditorView.editable.of(!locked), EditorView.contentAttributes.of({ "aria-label": label, "aria-multiline": "true", "aria-readonly": String(locked), "aria-describedby": "ib-note-live-hint", spellcheck: "false", autocapitalize: "sentences" })];
  useEffect(() => {
    let alive = true;
    const nonce = document.querySelector<HTMLMetaElement>('meta[name="csp-nonce"]')?.content;
    const editor = new EditorView({ parent: host.current!, state: EditorState.create({ doc: value, extensions: [
      config.current.of(settings(readOnly)), EditorView.cspNonce.of(nonce && nonce !== "__CSP_NONCE__" ? nonce : ""),
      history(), markdown({ extensions: GFM, completeHTMLTags: false, pasteURLAsLink: false }), livePreview, EditorView.lineWrapping, placeholder(hint),
      Prec.highest(EditorView.domEventHandlers({ keydown: (event, v) => {
        if (v.composing || event.isComposing || event.altKey || !(event.ctrlKey || event.metaKey)) return false;
        const key = event.key.toLowerCase();
        if (key !== "z" && key !== "y") return false;
        event.preventDefault();
        if (!v.state.readOnly) (key === "y" || event.shiftKey ? redo : undo)(v);
        return true; // Never let browser DOM history modify decorated Markdown.
      } })),
      keymap.of([{ key: "Mod-Enter", run: (v) => { if (v.composing) return false; latest.current.onSave(); return true; } },
        { key: "Mod-Shift-z", run: redo, preventDefault: true },
        { key: "Mod-b", run: (v) => format(v, "bold") }, { key: "Mod-i", run: (v) => format(v, "italic") }, { key: "Mod-e", run: (v) => format(v, "code") },
        ...defaultKeymap, ...historyKeymap]),
      EditorState.transactionFilter.of((tr) => {
        if (tr.docChanged && tr.annotation(Transaction.addToHistory) !== false && tr.newDoc.length > LIMIT && tr.newDoc.length > tr.startState.doc.length) { queueMicrotask(() => { if (alive) setLimited(true); }); return []; }
        return tr;
      }),
      EditorView.updateListener.of((update) => {
        if (update.docChanged) { setLimited(false); latest.current.onChange(update.state.doc.toString()); }
      }),
      EditorView.domEventHandlers({
        beforeinput: (event, v) => {
          if (event.inputType === "historyUndo" || event.inputType === "historyRedo") {
            event.preventDefault();
            if (!v.state.readOnly) (event.inputType === "historyUndo" ? undo : redo)(v);
            return true;
          }
          // Chromium may insert styled <span> nodes for multiline insertText. Keep this path plain-text,
          // just as CodeMirror's paste handler does, without allowing inline styles or touching IME.
          if (event.inputType === "insertText" && event.data?.includes("\n") && !event.isComposing && !v.composing && !v.state.readOnly) {
            event.preventDefault();
            v.dispatch({ ...v.state.replaceSelection(event.data), userEvent: "input.type", scrollIntoView: true });
            return true;
          }
          return false;
        },
        focus: (_event, v) => { v.dispatch({ effects: focus.of(true) }); },
        blur: (_event, v) => { v.dispatch({ effects: focus.of(false) }); },
        compositionstart: (_event, v) => { v.dispatch({ effects: composing.of(true) }); },
        compositionend: (_event, v) => { queueMicrotask(() => { if (alive) v.dispatch({ effects: composing.of(false) }); }); },
        click: (event) => {
          const target = (event.target as HTMLElement).closest<HTMLElement>("[data-note-url]");
          if (target) event.preventDefault();
          if (target && (event.ctrlKey || event.metaKey)) {
            const url = safeUrl(target.dataset.noteUrl ?? ""); if (url) window.open(url.href, "_blank", "noopener,noreferrer");
          }
        },
      }),
    ] }) });
    view.current = editor;
    return () => { alive = false; view.current = null; editor.destroy(); };
    // The document and settings are synchronized below without remounting the editor or losing its undo history.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => { view.current?.dispatch({ effects: config.current.reconfigure(settings(readOnly)) }); }, [readOnly, label]);
  // Only an explicit external reset may replace the document. Echoing React's asynchronous text
  // updates into CodeMirror can map stale text through undo/redo and invalidate the redo branch.
  useEffect(() => {
    const editor = view.current;
    if (editor && editor.state.doc.toString() !== value) editor.dispatch({ changes: { from: 0, to: editor.state.doc.length, insert: value }, annotations: Transaction.addToHistory.of(false) });
  }, [resetRevision]);
  const tools = [
    ["heading", Heading2, "note_format_heading"], ["bold", Bold, "note_format_bold"], ["italic", Italic, "note_format_italic"],
    ["list", List, "note_format_list"], ["quote", Quote, "note_format_quote"], ["code", Code2, "note_format_code"], ["link", Link2, "note_format_link"],
  ] as const;
  return <div className="ib-live-note">
    <div className="ib-note-tools" role="toolbar" aria-label={t("note_format_tools")}>
      {tools.map(([kind, Icon, key]) => <button key={kind} type="button" className="ib-note-format" title={t(key)} aria-label={t(key)} disabled={readOnly}
        onMouseDown={(event) => event.preventDefault()} onClick={() => { if (view.current) format(view.current, kind); }}><Icon className="size-4" /></button>)}
      <span className="ml-auto text-caption text-tertiary-foreground">Markdown</span>
    </div>
    <p className="ib-note-live-hint" id="ib-note-live-hint">{t(readOnly ? "note_read_only" : "note_live_hint")}</p>
    {limited && <p role="alert" className="px-4 pb-2 text-caption text-warning">{t("note_limit")}</p>}
    <div className="ib-live-markdown" ref={host} />
  </div>;
}
