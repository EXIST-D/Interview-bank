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
  ibank("notes", "import", "--source", source, "--name", "demo", "--title", "演示八股", "--origin", "测试");

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
  const mine = page.locator("section.my-answer");
  await mine.getByRole("button", { name: "写我的答案" }).click();
  await page.locator("textarea.my-answer-input").fill("先讲结论，再举项目里的例子。");
  await mine.getByRole("button", { name: "保存" }).click();
  await settle(page);
  check("own answer saves", (await mine.locator(".rich").innerText()).includes("项目里的例子"));
  await page.getByRole("button", { name: "收藏", exact: true }).click();
  await settle(page);
  check("first star creates 我的收藏", (await api(page, "/api/favorites")).folders[0]?.name === "我的收藏");

  // A long entry: outline, own note, read state synced to the server.
  await page.goto(base + "#/knowledge?open=" + note);
  await settle(page);
  await page.getByRole("button", { name: "本文目录" }).click();
  const entries = page.locator("[data-radix-popper-content-wrapper] button");
  check("outline lists the numbered questions", (await entries.count()) === 5, `${await entries.count()} entries`);
  await entries.nth(4).click();
  await page.waitForTimeout(800);
  check("outline entry scrolls the text", (await page.locator(".ib-reading").evaluate((n) => n.scrollTop)) > 200);
  await mine.getByRole("button", { name: "写我的笔记" }).click();
  await page.locator("textarea.my-answer-input").fill("穿透、击穿、雪崩三者要分清。");
  await mine.getByRole("button", { name: "保存" }).click();
  await settle(page);
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

  // Phone: 我的 lives in the more sheet.
  const phone = await open({ width: 390, height: 844 });
  await phone.getByRole("button", { name: "更多" }).click();
  await phone.getByRole("link", { name: /我的/ }).click();
  await settle(phone);
  check("phone reaches 我的 from the more sheet", (await phone.locator("main h1").innerText()) === "我的笔记");

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
