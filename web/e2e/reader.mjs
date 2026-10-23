// Browser checks of the built reader against a hosted-mode server (read-only bank, personal layer and practice allowed)
// on a throwaway demo bank. Run after `pnpm build`: `pnpm e2e`. PYTHON picks the interpreter; CHROMIUM a browser binary.
import { spawn, execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const cli = fileURLToPath(new URL("../../skills/interview-bank/scripts/ibank.py", import.meta.url));
const python = process.env.PYTHON || "python3";
const root = mkdtempSync(join(tmpdir(), "ibank-e2e-"));
const bank = join(root, "bank");
const ibank = (...args) => JSON.parse(execFileSync(python, ["-B", "-X", "utf8", cli, "--bank", bank, "--json", ...args], { encoding: "utf8" })).result;

const LONG = [
  "# Redis",
  "",
  "## Redis 高频面试题合集",
  "",
  ...[1, 2, 3, 4, 5].flatMap((i) => [`**${i}. 第 ${i} 个问题：缓存为什么会出问题？**`, "", "这一段是回答。".repeat(40), ""]),
].join("\n");

const results = [];
const check = (name, ok, detail = "") => results.push(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? "  — " + detail : ""}`);
let server;
let browser;
try {
  ibank("demo", "--v2");
  const source = join(root, "notes");
  mkdirSync(source);
  writeFileSync(join(source, "01-Redis.md"), LONG);
  writeFileSync(join(source, "02-HTTP.md"), "# 网络基础\n\n## HTTP 长连接是什么？\n\n同一连接复用多个请求。\n");
  ibank("notes", "import", "--source", source, "--name", "demo", "--title", "演示八股", "--origin", "测试");

  const tutorials = join(root, "tutorials");
  mkdirSync(tutorials);
  writeFileSync(join(tutorials, "01.md"), "# 配套课程\n\n## 01 环境安装\n\n准备环境的操作步骤。\n\n## 02 启动验证\n\n运行项目并检查结果。\n\n## 课程资源\n\n配套链接索引。\n");
  ibank("notes", "import", "--source", tutorials, "--name", "tutorials", "--title", "教程演示来源", "--origin", "测试");
  const catalog = ibank("notes", "catalog", "--name", "tutorials");
  const organization = join(root, "tutorial-organization.json");
  writeFileSync(organization, JSON.stringify({ schema_version: 1, collection: "tutorials", source_digest: catalog.source_digest, organization_digest: catalog.organization_digest,
    areas: [{ id: "lab", title: "实践", topics: [{ id: "course", title: "演示课程" }] }],
    notes: Object.fromEntries(catalog.notes.map((n) => [n.id, { area: "lab", topic: "course", kind: n.title === "课程资源" ? "resource" : "tutorial" }])) }));
  ibank("notes", "organize", "--name", "tutorials", "--input", organization);

  // A genuine reading group: earlier bookmarks can address a member instead of its visible anchor.
  const readingSource = join(root, "reading-source");
  mkdirSync(readingSource);
  writeFileSync(join(readingSource, "01.md"), "# 连续阅读\\n\\n## 第一部分\\n\\n先理解原理。\\n\\n原文：[查看来源](https://example.org/guide#one)\\n\\n## 第二部分\\n\\n再看代码。\\n\\n原文：[查看来源](https://example.org/guide#two)\\n".replaceAll("\\n", "\n"));
  ibank("notes", "import", "--source", readingSource, "--name", "reading-book", "--title", "连续阅读演示");
  const readingIds = JSON.parse(execFileSync(python, ["-B", "-X", "utf8", "-c", `
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from ibank_core import notes, note_organization, note_readings
bank = Path(sys.argv[2])
collection = next(c for c in notes.load_notes(bank)['collections'] if c['name'] == 'reading-book')
members = collection['notes']
catalog = note_organization.catalog(bank, 'reading-book')
payload = {'schema_version': 1, 'collection': 'reading-book', 'source_digest': catalog['source_digest'], 'organization_digest': catalog['organization_digest'],
    'reading_groups': {'guide': {'title': '连续阅读条目', 'note_ids': [n['id'] for n in members], 'source_url': 'https://example.org/guide',
        'content_digest': note_readings.digest(members), 'reason': '同一原文的连续章节，保留旧书签。'}}}
note_organization.organize(bank, 'reading-book', payload)
print(json.dumps({'head': members[0]['id'], 'alias': members[1]['id']}))
`, fileURLToPath(new URL("../../skills/interview-bank/scripts", import.meta.url)), bank], { encoding: "utf8" }));

  server = spawn(python, ["-B", "-X", "utf8", cli, "--bank", bank, "web", "--port", "0", "--read-only", "--allow-personal", "--allow-practice", "--json"]);
  const first = await new Promise((resolve, reject) => {
    createInterface({ input: server.stdout }).once("line", resolve);
    server.once("exit", (code) => reject(new Error(`reader exited ${code}`)));
  });
  const start = JSON.parse(first).result.url;
  const base = start.split("#")[0];

  browser = await chromium.launch(process.env.CHROMIUM ? { executablePath: process.env.CHROMIUM } : {});
  const violations = [];
  const errors = [];
  const open = async (viewport) => {
    const page = await browser.newPage({ viewport, acceptDownloads: true });
    page.on("console", (m) => /Content Security Policy|Refused to/.test(m.text()) && violations.push(JSON.stringify({ text: m.text(), location: m.location() })));
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("dialog", (d) => d.accept(d.type() === "prompt" ? "冲刺" : undefined));
    await page.goto(start);
    await page.waitForLoadState("networkidle");
    return page;
  };
  const settle = async (page) => {
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(300);
  };
  const api = (page, path) =>
    page.evaluate(async (p) => (await fetch(p.slice(1), { headers: { "X-Interview-Token": sessionStorage.getItem("ibank-token") } })).json(), path);

  // Select through the editor's native keymap before inserting plain text, just like select-all + paste.
  // DOM-only fill() can bypass a decorated editor's logical selection.
  const writeNote = async (p, target, text) => {
    await target.focus();
    await p.keyboard.press("ControlOrMeta+a");
    await p.context().grantPermissions(["clipboard-read", "clipboard-write"]);
    await p.evaluate((value) => navigator.clipboard.writeText(value), text);
    await p.keyboard.press("ControlOrMeta+v");
    await p.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  };

  const draftText = (p, id) => p.evaluate((item) => {
    const key = Object.keys(localStorage).find((k) => k.startsWith("ibank-note-draft:") && JSON.parse(k.slice("ibank-note-draft:".length))[2] === item);
    return key ? JSON.parse(localStorage.getItem(key)).text : null;
  }, id);

  const page = await open({ width: 1440, height: 900 });
  const question = (await api(page, "/api/library")).ids[0];
  const note = (await api(page, "/api/notes?section=knowledge&query=" + encodeURIComponent("合集"))).ids[0];
  check("the fixture entry is found by search", Boolean(note));

  // Own answer on a question, and a star that creates the default folder.
  await page.goto(base + "#/bank?open=" + question);
  await settle(page);
  const mine = page.getByRole("dialog", { name: "我的笔记", exact: true });
  await page.getByRole("button", { name: "笔记", exact: true }).click();
  await writeNote(page, mine.getByRole("textbox", { name: "我的笔记", exact: true }), "先讲结论，再举项目里的例子。");
  await mine.getByRole("button", { name: "保存" }).click();
  await settle(page);
  check("question note saves through the compatible personal API", (await api(page, "/api/question?id=" + question)).my_answer?.text.includes("项目里的例子"));
  check("the article has no bottom note editor", (await page.locator("article textarea").count()) === 0);
  await mine.getByRole("button", { name: "收起笔记", exact: true }).click();
  await page.getByRole("button", { name: "收藏", exact: true }).click();
  await settle(page);
  check("first star creates 我的收藏", (await api(page, "/api/favorites")).folders[0]?.name === "我的收藏");

  // A long entry: outline, own note, read state synced to the server.
  await page.goto(base + "#/knowledge?open=" + note);
  await settle(page);
  await page.getByRole("button", { name: "隐藏答案", exact: true }).click();
  await page.getByRole("button", { name: "笔记", exact: true }).click();
  await settle(page);
  check("notes do not reveal a deliberately hidden original", await page.locator("section[aria-label='阅读'] > header").getByRole("button", { name: "显示答案", exact: true }).isVisible() && (await page.locator("article .md").count()) === 0);
  await mine.getByRole("button", { name: "收起笔记", exact: true }).click();
  await page.locator("section[aria-label='阅读'] > header").getByRole("button", { name: "显示答案", exact: true }).click();
  await page.getByRole("button", { name: "本文目录" }).click();
  const entries = page.locator("[data-radix-popper-content-wrapper] button");
  check("outline lists the numbered questions", (await entries.count()) === 5, `${await entries.count()} entries`);
  await entries.nth(4).click();
  await page.waitForTimeout(800);
  check("outline entry scrolls the text", (await page.locator(".ib-reading").evaluate((n) => n.scrollTop)) > 200);
  await page.getByRole("button", { name: "笔记", exact: true }).click();
  check("opening notes keeps the long article away from its top", (await page.locator("article.ib-reading").evaluate((n) => n.scrollTop)) > 200);
  const noteText = "# 缓存复习\n\n穿透、击穿、雪崩三者要分清。\n\n- **穿透**：查询不存在的数据\n\n```python\ncache.get(key)\n```\n\n[文档](https://redis.io/docs/)";
  const area = mine.getByRole("textbox", { name: "我的笔记", exact: true });
  await writeNote(page, area, noteText);
  await mine.getByText("边写边呈现格式，光标所在处可编辑 Markdown 标记。", { exact: true }).click();
  check("Markdown notes render headings, code and safe links without switching preview", await mine.getByRole("heading", { name: "缓存复习", exact: true }).isVisible() && (await mine.locator(".cm-md-codeblock").allTextContents()).join("\n").includes("cache.get") && (await mine.getByRole("link", { name: "文档" }).getAttribute("rel")) === "noopener noreferrer", JSON.stringify({ source: await draftText(page, note), editor: await area.innerText(), errors }));
  check("the note is directly editable without mode tabs", await area.isVisible() && await mine.getByRole("button", { name: "预览", exact: true }).count() === 0 && await mine.getByRole("button", { name: "编辑", exact: true }).count() === 0);
  await mine.getByRole("button", { name: "收起笔记", exact: true }).click();
  await page.getByRole("button", { name: "笔记", exact: true }).click();
  check("closing and reopening restores this item's Markdown draft", await draftText(page, note) === noteText && (await area.innerText()).includes("雪崩"));
  await page.reload();
  await settle(page);
  check("reload restores the account-scoped draft and note deep link", await draftText(page, note) === noteText && (await area.innerText()).includes("雪崩") && page.url().includes("panel=notes"));
  await mine.getByRole("button", { name: "保存" }).click();
  await settle(page);
  const storedNote = (await api(page, "/api/note?id=" + note)).my_answer;
  await writeNote(page, area, noteText + "\n\n本地修订");
  // A real second-device save, followed by a stale UI save: the server must refuse overwriting.
  await page.evaluate(async ({ note, updated }) => {
    const response = await fetch("api/my-answer", { method: "POST", headers: { "X-Interview-Token": sessionStorage.getItem("ibank-token"), "Content-Type": "application/json" }, body: JSON.stringify({ item_id: note, text: "另一台设备写的笔记", expected_updated_at: updated }) });
    if (!response.ok) throw new Error("second-device fixture save failed");
  }, { note, updated: storedNote.updated_at });
  await mine.getByRole("button", { name: "保存", exact: true }).click();
  await settle(page);
  check("a stale save keeps the draft and the other device's note", (await mine.getByRole("alert").innerText()).includes("另一处已更新") && (await area.innerText()).includes("本地修订") && (await api(page, "/api/note?id=" + note)).my_answer.text === "另一台设备写的笔记");
  await mine.getByRole("button", { name: "读取最新版本并保留草稿" }).click();
  await settle(page);
  check("reload for conflict comparison retains the local draft", (await area.innerText()).includes("本地修订"));
  await mine.getByRole("button", { name: "保存", exact: true }).click();
  await settle(page);
  check("an explicitly reconciled note can be saved", (await api(page, "/api/note?id=" + note)).my_answer.text.includes("本地修订"));
  await page.route("**/api/my-answer", (route) => route.abort("failed"));
  await writeNote(page, area, noteText + "\n\n网络失败时的草稿");
  await mine.getByRole("button", { name: "保存", exact: true }).click();
  await settle(page);
  check("a failed save retains the draft and enables retry", (await area.innerText()).includes("网络失败时") && await mine.getByRole("alert").isVisible() && await mine.getByRole("button", { name: "保存", exact: true }).isEnabled());
  await page.unroute("**/api/my-answer");
  await writeNote(page, area, noteText + "\n\n本地修订");
  await mine.getByRole("button", { name: "收起笔记", exact: true }).click();
  await page.getByRole("button", { name: "收藏", exact: true }).click();
  await page.locator("[data-radix-popper-content-wrapper] button", { hasText: "我的收藏" }).click();
  await settle(page);
  await page.keyboard.press("Escape");
  await page.waitForTimeout(2000);
  const { read } = await api(page, "/api/learning");
  check("reading is synced to the server", Array.isArray(read) ? read.includes(question) : question in read);

  // The mine page: notes, search, export, folder, practice.
  await page.goto(base + "#/mine");
  await settle(page);
  check("my notes lists the answer and the note", (await page.locator("main a.surface").count()) === 2);
  await page.getByPlaceholder("搜索我的笔记").fill("雪崩 穿透");
  await settle(page);
  check("my notes search needs every term", (await page.locator("main a.surface").count()) === 1);
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "导出 Markdown" }).click();
  check("export is Markdown", readFileSync(await (await download).path(), "utf8").includes("三者要分清"));
  await page.locator("main a.surface").click();
  await settle(page);
  check("a note card opens both its original item and side panel", page.url().includes("panel=notes") && await mine.isVisible() && (await area.innerText()).includes("三者要分清"));
  await mine.getByRole("button", { name: "收起笔记", exact: true }).click();
  check("closing notes removes the panel from the link", !page.url().includes("panel=notes") && !await mine.isVisible());
  await page.goto(base + "#/mine?tab=favorites");
  await settle(page);
  await page.locator("main button.surface", { hasText: "我的收藏" }).click();
  await settle(page);
  check("the folder holds both items", (await page.locator("main .surface > div").count()) === 2);
  await page.getByRole("button", { name: "重命名" }).click();
  await settle(page);
  check("rename", (await page.locator("main h2").innerText()) === "冲刺");
  await page.getByRole("button", { name: "练习其中的面经题" }).click();
  await settle(page);
  await page.getByRole("button", { name: "查看参考答案" }).click();
  await page.getByRole("button", { name: "基本掌握" }).click();
  await settle(page);
  check("a folder round saves its rating", (await page.getByRole("dialog").innerText()).includes("这一轮完成了"));
  await page.getByRole("button", { name: "结束练习" }).click();

  // Home plan reflects the rating and starts a round.
  await page.goto(base + "#/");
  await settle(page);
  check("home shows today's plan", await page.getByRole("region", { name: "今日计划" }).isVisible());
  await page.getByRole("link", { name: "开始复习" }).click();
  await settle(page);
  check("start review opens a round setup", await page.getByRole("dialog").getByRole("button", { name: "开始", exact: true }).isVisible());

  // A course directory counts only this category, then opens the original entries in the reader.
  await page.goto(base + "#/learning/tutorial");
  await settle(page);
  const courseSource = page.getByRole("button", { name: "教程演示来源 1 组目录 · 2 篇内容", exact: true });
  check("learning source directories start collapsed", (await courseSource.getAttribute("aria-expanded")) === "false");
  await courseSource.click();
  check("tutorial directory excludes its resource entry", await page.getByRole("link", { name: "演示课程 2", exact: true }).isVisible());
  await page.getByRole("link", { name: "演示课程 2", exact: true }).click();
  await settle(page);
  check("course deep link scopes the list", (await page.locator("button[data-id]").count()) === 2 && page.url().includes("topic=course"));
  await page.getByRole("button", { name: /^01 环境安装/ }).click();
  await settle(page);
  check("a course opens the unchanged original reader", await page.getByRole("heading", { name: "01 环境安装", exact: true }).isVisible());

  // Phone: 我的 lives in the more sheet.
  const phone = await open({ width: 390, height: 844 });
  await phone.getByRole("button", { name: "更多" }).click();
  await phone.getByRole("link", { name: /我的/ }).click();
  await settle(phone);
  check("phone reaches 我的 from the more sheet", (await phone.locator("main h1").innerText()) === "我的笔记");

  await phone.goto(base + "#/learning/tutorial");
  await settle(phone);
  await phone.getByRole("button", { name: "教程演示来源 1 组目录 · 2 篇内容", exact: true }).click();
  await phone.getByRole("link", { name: "演示课程 2", exact: true }).click();
  await settle(phone);
  check("phone course navigation fits its viewport", (await phone.locator("button[data-id]").count()) === 2 && await phone.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));

  await phone.goto(base + "#/bank?open=" + question);
  await settle(phone);
  await phone.getByRole("button", { name: "笔记", exact: true }).click();
  const phoneNote = phone.getByRole("dialog", { name: "我的笔记", exact: true });
  await phoneNote.evaluate((n) => Promise.all(n.getAnimations().map((animation) => animation.finished.catch(() => {}))));
  const phoneBounds = await phoneNote.evaluate((n) => ({ modal: n.getAttribute("aria-modal"), ...n.getBoundingClientRect().toJSON(), viewport: { width: innerWidth, height: innerHeight } }));
  check("phone notes open as an accessible modal within the screen", phoneBounds.modal === "true" && phoneBounds.left >= 0 && phoneBounds.right <= phoneBounds.viewport.width && phoneBounds.top >= 0 && phoneBounds.bottom <= phoneBounds.viewport.height, JSON.stringify(phoneBounds));
  await phoneNote.getByRole("button", { name: "收起笔记", exact: true }).focus();
  for (let i = 0; i < 12; i++) await phone.keyboard.press("Tab");
  check("phone note keyboard focus stays inside its modal", await phoneNote.evaluate((n) => n.contains(document.activeElement)));
  const phoneArea = phoneNote.getByRole("textbox", { name: "我的笔记", exact: true });
  await writeNote(phone, phoneArea, "手机草稿，只属于这道题。");
  await phoneNote.getByRole("button", { name: "收起笔记", exact: true }).click();
  check("phone closing notes returns to the same article", !await phoneNote.isVisible() && await phone.locator("article .reading-title").isVisible());
  await phone.getByRole("button", { name: "下一题", exact: true }).click();
  await settle(phone);
  await phone.getByRole("button", { name: "笔记", exact: true }).click();
  check("switching items does not leak the previous note draft", await phoneArea.innerText() !== "手机草稿，只属于这道题。");
  await phoneNote.getByRole("button", { name: "收起笔记", exact: true }).click();
  await phone.getByRole("button", { name: "上一题", exact: true }).click();
  await settle(phone);
  await phone.getByRole("button", { name: "笔记", exact: true }).click();
  check("returning to an item restores its own draft", await phoneArea.innerText() === "手机草稿，只属于这道题。");

  // A slow save finishes after switching between two entries in the same source reader.
  await page.goto(base + "#/knowledge/demo?open=" + note + "&panel=notes");
  await settle(page);
  await writeNote(page, area, noteText + "\n\n延迟保存");
  let releaseSave;
  let seeSave;
  const blocked = new Promise((resolve) => { releaseSave = resolve; });
  const intercepted = new Promise((resolve) => { seeSave = resolve; });
  await page.route("**/api/my-answer", async (route) => { seeSave(); await blocked; await route.continue(); });
  await mine.getByRole("button", { name: "保存", exact: true }).click();
  await intercepted;
  const otherId = (await api(page, "/api/notes?section=knowledge&collection=demo&query=" + encodeURIComponent("HTTP 长连接"))).ids[0];
  if (!otherId) throw new Error("missing second entry fixture");
  await page.goto(base + "#/knowledge/demo?open=" + otherId + "&panel=notes");
  await settle(page);
  releaseSave();
  await settle(page);
  const late = { title: await page.locator("article .reading-title").innerText(), draft: await draftText(page, otherId), placeholder: await area.locator(".cm-placeholder").isVisible(), saved: (await api(page, "/api/note?id=" + note)).my_answer.text.includes("延迟保存") };
  check("a late save cannot replace the newly opened item's title or editor", late.title === "HTTP 长连接是什么？" && late.draft === null && late.placeholder && late.saved, JSON.stringify(late));
  await page.unroute("**/api/my-answer");

  // The single-surface editor preserves Markdown while rendering it; no editor-to-HTML round trip.
  await writeNote(page, area, "重点");
  await area.press("ControlOrMeta+a");
  await mine.getByRole("button", { name: "粗体（Ctrl/⌘+B）", exact: true }).click();
  check("the formatting toolbar inserts Markdown around the selection", await draftText(page, otherId) === "**重点**");
  await area.press("ControlOrMeta+z");
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  check("native undo restores the text before a formatting action", await draftText(page, otherId) === "重点");
  await area.press("ControlOrMeta+Shift+z");
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  check("native redo restores Markdown formatting", await draftText(page, otherId) === "**重点**", JSON.stringify(await draftText(page, otherId)));

  const liveText = "## 边写边看\n\n**加粗** 与 *斜体*、~~删除~~ 和 `cache.get()`\n\n> 引用不会改变原文\n\n- [ ] 待复习\n- [x] 已复习\n\n| 概念 | 结论 |\n| --- | --- |\n| **缓存** | 保留原文 |\n\n```js\nconst x = '<script>test</script>';\n```\n\n[安全链接](https://example.org/docs)\n\n最后一段";
  await writeNote(page, area, liveText);
  await area.press("ControlOrMeta+End");
  await mine.getByText("边写边呈现格式，光标所在处可编辑 Markdown 标记。", { exact: true }).click();
  check("live Markdown renders emphasis, strike, quotes, tasks and tables", await mine.locator(".cm-md-strong").count() > 0 && await mine.locator(".cm-md-emphasis").count() > 0 && await mine.locator(".cm-md-strike").count() > 0 && await mine.locator(".cm-md-quote").count() > 0 && await mine.locator(".cm-md-task").count() === 2 && await mine.locator(".cm-md-table table").count() === 1);
  await mine.getByRole("cell", { name: "保留原文", exact: true }).click();
  check("clicking a rendered table reveals its editable Markdown source", await mine.locator(".cm-md-table").count() === 0 && (await area.innerText()).includes("| 概念 | 结论 |"));
  await mine.getByText("边写边呈现格式，光标所在处可编辑 Markdown 标记。", { exact: true }).click();
  await mine.getByRole("button", { name: "保存", exact: true }).click();
  await settle(page);
  check("saving live Markdown retains its exact source including tables and code", (await api(page, "/api/note?id=" + otherId)).my_answer.text === liveText);
  const hostile = '<img src=x onerror="alert(1)">\n\n[bad](javascript:alert(1))\n\n![remote](https://example.org/image.png)\n\n尾段';
  await writeNote(page, area, hostile);
  await mine.getByText("边写边呈现格式，光标所在处可编辑 Markdown 标记。", { exact: true }).click();
  // CodeMirror uses src-less, aria-hidden img.cm-widgetBuffer nodes for caret navigation. Those
  // neither display nor fetch images; actual image sources, handlers and executable nodes are forbidden.
  const safe = { elements: await mine.locator(".ib-live-markdown").evaluate((element) => Array.from(element.querySelectorAll('img[src], img[onerror], script, iframe, object, embed, a[href^="javascript:"]')).map((node) => node.outerHTML)), text: await area.innerText(), source: await draftText(page, otherId) };
  check("Markdown HTML, dangerous links and images stay inert", safe.elements.length === 0 && safe.source === hostile, JSON.stringify(safe));
  await mine.getByRole("button", { name: "放弃本次草稿", exact: true }).click();
  await settle(page);
  check("discard restores the saved Markdown and clears its draft", await draftText(page, otherId) === null && await mine.getByRole("heading", { name: "边写边看", exact: true }).isVisible() && await mine.locator(".cm-md-table").count() === 1);
  await writeNote(page, area, "中文输入：");
  await area.press("ControlOrMeta+End");
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Input.imeSetComposition", { text: "连续", selectionStart: 2, selectionEnd: 2 });
  await cdp.send("Input.insertText", { text: "连续输入" });
  await cdp.detach();
  check("Chinese composition commits once without losing or repeating text", await draftText(page, otherId) === "中文输入：连续输入");
  await writeNote(page, area, "x".repeat(20001));
  await settle(page);
  check("oversize input is rejected visibly without truncating the existing draft", await draftText(page, otherId) === "中文输入：连续输入" && (await mine.getByRole("alert").innerText()).includes("20,000"));
  await writeNote(page, area, "末尾快捷保存");
  await area.press("ControlOrMeta+Enter");
  await settle(page);
  check("the live editor saves with the existing keyboard shortcut", (await api(page, "/api/note?id=" + otherId)).my_answer.text === "末尾快捷保存");

  await page.goto(base + "#/knowledge/reading-book?open=" + readingIds.alias + "&panel=notes");
  await settle(page);
  check("an earlier reading-group bookmark opens its article and note panel", (await page.locator("article .reading-title").innerText()) === "连续阅读条目" && await mine.isVisible());
  await writeNote(page, area, "这条笔记属于完整阅读条目。");
  await mine.getByRole("button", { name: "保存", exact: true }).click();
  await settle(page);
  check("a grouped bookmark saves to its actual reading item", (await api(page, "/api/note?id=" + readingIds.head)).my_answer?.text === "这条笔记属于完整阅读条目。");

  check("no page errors", errors.length === 0, errors.join(" | "));
  check("no Content-Security-Policy violations", violations.length === 0, violations.join(" | "));
} catch (error) {
  check("script finished", false, String(error));
  console.log("BROWSER_ERRORS", JSON.stringify(errors));
  console.log("CSP_ERRORS", JSON.stringify(violations));
} finally {
  await browser?.close();
  server?.kill();
  rmSync(root, { recursive: true, force: true });
}
console.log(results.join("\n"));
process.exit(results.some((line) => line.startsWith("FAIL")) ? 1 : 0);
