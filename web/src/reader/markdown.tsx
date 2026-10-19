import { Fragment, type ReactNode } from "react";

// Answers and collection text are rendered as React nodes from a small Markdown subset;
// any HTML in the source stays literal text, and links accept only http(s) without credentials.

export function safeUrl(url: string): URL | null {
  try {
    const parsed = new URL(url);
    if (!["http:", "https:"].includes(parsed.protocol) || parsed.username || parsed.password) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function SafeLink({ url, children, className, title }: { url: string; children?: ReactNode; className?: string; title?: string }) {
  const parsed = safeUrl(url);
  if (!parsed) return <>{children}</>;
  return (
    <a href={parsed.href} target="_blank" rel="noopener noreferrer" className={className} title={title}>
      {children ?? parsed.hostname.replace(/^www\./, "")}
    </a>
  );
}

function inline(text: string): ReactNode[] {
  // Bold, code, links and <br>; everything else stays literal text.
  const out: ReactNode[] = [];
  String(text)
    .split(/(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)\s]+\)|<br\s*\/?>)/gi)
    .forEach((part, index) => {
      if (!part) return;
      const link = part.match(/^\[([^\]]+)\]\(([^)\s]+)\)$/);
      if (/^<br\s*\/?>$/i.test(part)) out.push(<br key={index} />);
      else if (part.length > 4 && part.startsWith("**") && part.endsWith("**")) out.push(<strong key={index}>{part.slice(2, -2)}</strong>);
      else if (part.length > 2 && part.startsWith("`") && part.endsWith("`")) out.push(<code key={index}>{part.slice(1, -1)}</code>);
      else if (link) out.push(safeUrl(link[2]) ? <SafeLink key={index} url={link[2]}>{link[1]}</SafeLink> : link[1]);
      else out.push(<Fragment key={index}>{part}</Fragment>);
    });
  return out;
}

/** The short subset used by reference answers: paragraphs, flat lists, code fences, bold and code. */
export function RichText({ text }: { text: string }) {
  const blocks: ReactNode[] = [];
  let code: string[] | null = null;
  let list: ReactNode[] | null = null;
  const flushList = () => {
    if (list) blocks.push(<ul key={blocks.length}>{list}</ul>);
    list = null;
  };
  const parts = (line: string) =>
    line.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((part, i) =>
      part.startsWith("**") && part.endsWith("**") && part.length > 4 ? (
        <strong key={i}>{part.slice(2, -2)}</strong>
      ) : part.startsWith("`") && part.endsWith("`") && part.length > 2 ? (
        <code key={i}>{part.slice(1, -1)}</code>
      ) : (
        part
      ),
    );
  for (const line of String(text || "").split("\n")) {
    if (/^\s*```/.test(line)) {
      flushList();
      if (code) {
        blocks.push(<pre key={blocks.length}>{code.join("\n") + "\n"}</pre>);
        code = null;
      } else code = [];
      continue;
    }
    if (code) {
      code.push(line);
      continue;
    }
    const clean = line.replace(/^\s*(?:[-*•]|\d+[.)、])\s+/, "").replace(/^#{1,6}\s+/, "");
    if (/^\s*(?:[-*•]|\d+[.)、])\s+/.test(line)) {
      list ??= [];
      list.push(<li key={list.length}>{parts(clean)}</li>);
      continue;
    }
    flushList();
    if (line.trim()) blocks.push(<p key={blocks.length}>{parts(clean)}</p>);
  }
  flushList();
  if (code) blocks.push(<pre key={blocks.length}>{(code as string[]).join("\n") + "\n"}</pre>);
  return <div className="rich">{blocks}</div>;
}

const LIST_ITEM = /^(\s*)([-*+•]|\d+[.)、])\s+(.*)$/;
const OUTLINE_LINE = /^\*\*\s*(?:\d{1,3}\s*[.、)．:：]|Q\s*\d{0,3}\s*[.:：]|问题?\s*\d{0,3}\s*[.:：])[^*]{2,}\*\*[:：]?$/;
const indentOf = (line: string) => line.match(/^\s*/)![0].length;

function table(rows: string[], key: number) {
  const cells = (row: string) => row.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((cell) => cell.trim());
  const parsed = rows.map(cells);
  const headed = parsed.length > 1 && parsed[1].every((cell) => /^:?-+:?$/.test(cell));
  return (
    <div className="table-wrap" key={key}>
      <table>
        {headed && (
          <thead>
            <tr>{parsed[0].map((cell, i) => <th key={i}>{inline(cell)}</th>)}</tr>
          </thead>
        )}
        <tbody>
          {parsed.slice(headed ? 2 : 0).map((row, r) => (
            <tr key={r}>{row.map((cell, i) => <td key={i}>{inline(cell)}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function list(lines: string[], start: number, key: number): [ReactNode, number] {
  // A list and everything indented under its items: nested lists, paragraphs, quotes and code.
  const first = lines[start].match(LIST_ITEM)!;
  const indent = first[1].length;
  const ordered = /\d/.test(first[2]);
  const items: ReactNode[][] = [];
  let i = start;
  while (i < lines.length) {
    const line = lines[i];
    const item = items[items.length - 1];
    if (!line.trim()) {
      const next = lines[i + 1];
      if (item && next !== undefined && next.trim() && indentOf(next) > indent) { i++; continue; }
      if (next !== undefined && LIST_ITEM.test(next) && indentOf(next) === indent) { i++; continue; }
      break;
    }
    const match = line.match(LIST_ITEM);
    if (match && match[1].length === indent) {
      items.push([<Fragment key="text">{inline(match[3])}</Fragment>]);
      i++;
    } else if (match && match[1].length > indent && item) {
      const [child, next] = list(lines, i, item.length);
      item.push(child);
      i = next;
    } else if (item && indentOf(line) > indent) {
      const block: string[] = [];
      const cut = indentOf(line);
      while (i < lines.length && lines[i].trim() && indentOf(lines[i]) > indent && !LIST_ITEM.test(lines[i])) {
        block.push(lines[i].slice(Math.min(cut, indentOf(lines[i]))));
        i++;
      }
      item.push(<Fragment key={item.length}>{blocksOf(block.join("\n"))}</Fragment>);
    } else break;
  }
  const children = items.map((content, n) => <li key={n}>{content}</li>);
  const startAt = ordered ? parseInt(first[2], 10) : 1;
  return [ordered ? <ol key={key} start={startAt > 1 ? startAt : undefined}>{children}</ol> : <ul key={key}>{children}</ul>, i];
}

function blocksOf(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  const lines = String(text || "").replace(/\r\n/g, "\n").split("\n");
  const anchorWrapper = /^\s*<\/?a(?:\s+[^>]*)?>\s*$/i;
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const key = out.length;
    if (/^\s*(```|~~~)/.test(line)) {
      const fence = line.trim().slice(0, 3);
      const code: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith(fence)) code.push(lines[i++]);
      i++;
      out.push(<pre key={key}>{code.join("\n")}</pre>);
      continue;
    }
    if (!line.trim() || anchorWrapper.test(line)) { i++; continue; }
    const heading = line.match(/^(#{1,6})\s+(.*?)\s*#*\s*$/);
    if (heading) {
      out.push(heading[1].length <= 3 ? <h3 key={key}>{inline(heading[2])}</h3> : <h4 key={key}>{inline(heading[2])}</h4>);
      i++;
      continue;
    }
    if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(line)) { out.push(<hr key={key} />); i++; continue; }
    if (/^\s*>/.test(line)) {
      const quote: string[] = [];
      while (i < lines.length && /^\s*>/.test(lines[i])) quote.push(lines[i++].replace(/^\s*>\s?/, ""));
      out.push(<blockquote key={key}>{blocksOf(quote.join("\n"))}</blockquote>);
      continue;
    }
    if (/^\s*\|/.test(line)) {
      const rows: string[] = [];
      while (i < lines.length && /^\s*\|/.test(lines[i])) rows.push(lines[i++]);
      out.push(table(rows, key));
      continue;
    }
    if (LIST_ITEM.test(line)) {
      const [node, next] = list(lines, i, key);
      out.push(node);
      i = next;
      continue;
    }
    const paragraph: ReactNode[] = [];
    const raw: string[] = [];
    while (i < lines.length && lines[i].trim() && !/^\s*(```|~~~|>|\||#{1,6}\s)/.test(lines[i]) && !LIST_ITEM.test(lines[i])) {
      if (anchorWrapper.test(lines[i])) { i++; continue; }
      if (paragraph.length) paragraph.push(<br key={"br" + paragraph.length} />);
      raw.push(lines[i].trim());
      paragraph.push(<Fragment key={paragraph.length}>{inline(lines[i++].trim())}</Fragment>);
    }
    // Long write-ups mark each question as a bold numbered line instead of a heading; those enter the outline.
    const question = raw.length === 1 && OUTLINE_LINE.test(raw[0]);
    out.push(
      <p key={key} data-toc={question ? "" : undefined}>
        {paragraph}
      </p>,
    );
  }
  return out;
}

/** Markdown as written in the collections: headings, lists, quotes, tables and code. */
export function Markdown({ text }: { text: string }) {
  return <div className="rich md">{blocksOf(text)}</div>;
}
