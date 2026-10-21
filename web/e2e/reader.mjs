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
    page.on("console", (m) => /Content Security Policy|Refused to/.test(m.text()) && violations.push(m.text().slice(0, 160)));
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

  const page = await open({ width: 1440, height: 900 });
  const question = (await api(page, "/api/library")).ids[0];
  const note = (await api(page, "/api/notes?section=knowledge&query=" + encodeURIComponent("合集"))).ids[0];
  check("the fixture entry is found by search", Boolean(note));

  // Own answer on a question, and a star that creates the default folder.
  await page.goto(base + "#/bank?open=" + question);
  await settle(page);
  const mine = page.getByRole("dialog", { name: "我的笔记", exact: true });
  await page.getByRole("button", { name: "笔记", exact: true }).click();
  await mine.getByRole("textbox", { name: "我的笔记", exact: true }).fill("先讲结论，再举项目里的例子。");
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
  check("notes do not reveal a deliberately hidden original", await page.getByRole("button", { name: "显示答案", exact: true }).isVisible() && (await page.locator("article .md").count()) === 0);
  await mine.getByRole("button", { name: "收起笔记", exact: true }).click();
  await page.getByRole("button", { name: "显示答案", exact: true }).click();
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
  await area.fill(noteText);
  await mine.getByRole("button", { name: "预览", exact: true }).click();
  check("Markdown notes preview headings, code and safe links", await mine.getByRole("heading", { name: "缓存复习", exact: true }).isVisible() && (await mine.locator("pre").innerText()).includes("cache.get") && (await mine.getByRole("link", { name: "文档" }).getAttribute("rel")) === "noopener noreferrer");
  await mine.getByRole("button", { name: "收起笔记", exact: true }).click();
  await page.getByRole("button", { name: "笔记", exact: true }).click();
  check("closing and reopening restores this item's Markdown draft", await area.inputValue() === noteText);
  await page.reload();
  await settle(page);
  check("reload restores the account-scoped draft and note deep link", await area.inputValue() === noteText && page.url().includes("panel=notes"));
  await mine.getByRole("button", { name: "保存" }).click();
  await settle(page);
  const storedNote = (await api(page, "/api/note?id=" + note)).my_answer;
  await area.fill(noteText + "\n\n本地修订");
  // A real second-device save, followed by a stale UI save: the server must refuse overwriting.
  await page.evaluate(async ({ note, updated }) => {
    const response = await fetch("api/my-answer", { method: "POST", headers: { "X-Interview-Token": sessionStorage.getItem("ibank-token"), "Content-Type": "application/json" }, body: JSON.stringify({ item_id: note, text: "另一台设备写的笔记", expected_updated_at: updated }) });
    if (!response.ok) throw new Error("second-device fixture save failed");
  }, { note, updated: storedNote.updated_at });
  await mine.getByRole("button", { name: "保存", exact: true }).click();
  await settle(page);
  check("a stale save keeps the draft and the other device's note", (await mine.getByRole("alert").innerText()).includes("另一处已更新") && (await area.inputValue()).includes("本地修订") && (await api(page, "/api/note?id=" + note)).my_answer.text === "另一台设备写的笔记");
  await mine.getByRole("button", { name: "读取最新版本并保留草稿" }).click();
  await settle(page);
  check("reload for conflict comparison retains the local draft", (await area.inputValue()).includes("本地修订"));
  await mine.getByRole("button", { name: "保存", exact: true }).click();
  await settle(page);
  check("an explicitly reconciled note can be saved", (await api(page, "/api/note?id=" + note)).my_answer.text.includes("本地修订"));
  await page.route("**/api/my-answer", (route) => route.abort("failed"));
  await area.fill(noteText + "\n\n网络失败时的草稿");
  await mine.getByRole("button", { name: "保存", exact: true }).click();
  await settle(page);
  check("a failed save retains the draft and enables retry", (await area.inputValue()).includes("网络失败时") && await mine.getByRole("alert").isVisible() && await mine.getByRole("button", { name: "保存", exact: true }).isEnabled());
  await page.unroute("**/api/my-answer");
  await area.fill(noteText + "\n\n本地修订");
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
  check("a note card opens both its original item and side panel", page.url().includes("panel=notes") && await mine.isVisible() && (await mine.locator(".md").innerText()).includes("三者要分清"));
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
  check("phone notes open as an accessible modal within the screen", (await phoneNote.getAttribute("aria-modal")) === "true" && await phoneNote.evaluate((n) => { const r = n.getBoundingClientRect(); return r.left >= 0 && r.right <= innerWidth && r.top >= 0 && r.bottom <= innerHeight; }));
  await phoneNote.getByRole("button", { name: "编辑", exact: true }).click();
  const phoneArea = phoneNote.getByRole("textbox", { name: "我的笔记", exact: true });
  await phoneArea.fill("手机草稿，只属于这道题。");
  await phoneNote.getByRole("button", { name: "收起笔记", exact: true }).click();
  check("phone closing notes returns to the same article", !await phoneNote.isVisible() && await phone.locator("article .reading-title").isVisible());
  await phone.getByRole("button", { name: "下一题", exact: true }).click();
  await settle(phone);
  await phone.getByRole("button", { name: "笔记", exact: true }).click();
  check("switching items does not leak the previous note draft", await phoneArea.inputValue() !== "手机草稿，只属于这道题。");
  await phoneNote.getByRole("button", { name: "收起笔记", exact: true }).click();
  await phone.getByRole("button", { name: "上一题", exact: true }).click();
  await settle(phone);
  await phone.getByRole("button", { name: "笔记", exact: true }).click();
  check("returning to an item restores its own draft", await phoneArea.inputValue() === "手机草稿，只属于这道题。");

  // A slow save finishes after switching between two entries in the same source reader.
  await page.goto(base + "#/knowledge/demo?open=" + note + "&panel=notes");
  await settle(page);
  if (!await area.isVisible()) await mine.getByRole("button", { name: "编辑", exact: true }).click();
  await area.fill(noteText + "\n\n延迟保存");
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
  check("a late save cannot replace the newly opened item's title or editor", (await page.locator("article .reading-title").innerText()) === "HTTP 长连接是什么？" && await area.inputValue() === "" && (await api(page, "/api/note?id=" + note)).my_answer.text.includes("延迟保存"));
  await page.unroute("**/api/my-answer");

  check("no page errors", errors.length === 0, errors.join(" | "));
  check("no Content-Security-Policy violations", violations.length === 0, violations.join(" | "));
} catch (error) {
  check("script finished", false, String(error).split("\n")[0]);
} finally {
  await browser?.close();
  server?.kill();
  rmSync(root, { recursive: true, force: true });
}
console.log(results.join("\n"));
process.exit(results.some((line) => line.startsWith("FAIL")) ? 1 : 0);
