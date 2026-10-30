// Browser check of the preparation board (most-asked ranking, company view, saved job-description lists) against a hosted-mode
// reader whose --ai-config points at a stand-in model on loopback. Run after `pnpm build` (part of `pnpm e2e`).
import { spawn, execFileSync } from "node:child_process";
import { createServer } from "node:http";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const cli = fileURLToPath(new URL("../../skills/interview-bank/scripts/ibank.py", import.meta.url));
const python = process.env.PYTHON || "python3";
const root = mkdtempSync(join(tmpdir(), "ibank-prepare-e2e-"));
const bank = join(root, "bank");
const plain = join(root, "plain");
const results = [];
const violations = [];
const errors = [];
const check = (name, ok, detail = "") => results.push(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? "  — " + detail : ""}`);
const shot = (page, name) => process.env.E2E_SHOTS ? page.screenshot({ path: join(process.env.E2E_SHOTS, `prepare-${name}.png`), fullPage: true }) : null;

const model = createServer((request, response) => {
  let raw = "";
  request.on("data", (part) => (raw += part));
  request.on("end", () => {
    const body = JSON.parse(raw);
    const text = body.messages[1].content[0].text;
    const ids = text.split("--- bank questions (id | count | text) ---\n")[1].split("\n").map((line) => line.split(" | ")[0]);
    const reply = {
      picks: [{ id: ids[0], quote: "熟悉 Redis", coverage: "direct", priority: "must", reason: "直接考察缓存" },
              { id: ids[1], quote: "不在原文里", coverage: "partial", reason: "相关" }],
      uncovered: ["有数据库性能优化经验"],
    };
    response.writeHead(200, { "Content-Type": "application/json" });
    response.end(JSON.stringify({ choices: [{ message: { content: JSON.stringify(reply) } }], usage: { prompt_tokens: 3000, completion_tokens: 300 } }));
  });
});

let server;
let browser;
let page;
try {
  await new Promise((resolve) => model.listen(0, "127.0.0.1", resolve));
  const config = join(root, "ai.json");
  writeFileSync(config, JSON.stringify({ vision: { base_url: `http://127.0.0.1:${model.address().port}/v1`, model: "stand-in-vl" }, text: { model: "stand-in-chat" } }));
  const serve = async (path) => {
    const proc = spawn(python, ["-B", "-X", "utf8", cli, "--bank", path, "web", "--port", "0", "--read-only", "--allow-personal", "--allow-practice",
      "--allow-intake", "--ai-config", config, "--json"]);
    const line = await new Promise((resolve, reject) => {
      createInterface({ input: proc.stdout }).once("line", resolve);
      proc.once("exit", (code) => reject(new Error(`reader exited ${code}`)));
    });
    return { proc, url: JSON.parse(line).result.url };
  };
  for (const path of [bank, plain]) execFileSync(python, ["-B", "-X", "utf8", cli, "--bank", path, "--json", "demo", "--v2"], { encoding: "utf8" });
  // Interview dates relative to today (so the check holds whenever it runs): 1, 6, 18 and 48 months ago, and none.
  const month = (ago) => { const d = new Date(); d.setMonth(d.getMonth() - ago); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`; };
  const table = join(bank, "data/occurrences.jsonl");
  const dates = [month(1), month(6), month(18), month(48), null];
  writeFileSync(table, readFileSync(table, "utf8").split("\n").filter(Boolean).map((line, i) => JSON.stringify({ ...JSON.parse(line), event_date: dates[i % 5] }) + "\n").join(""));
  const main = await serve(bank);
  server = main.proc;
  const started = { url: main.url };
  const base = started.url.split("#")[0];

  browser = await chromium.launch(process.env.CHROMIUM ? { executablePath: process.env.CHROMIUM } : {});
  page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  page.on("console", (m) => /Content Security Policy|Refused to/.test(m.text()) && violations.push(m.text()));
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(started.url);
  await page.waitForLoadState("networkidle");
  const api = (path) => page.evaluate(async (p) => (await fetch(p.slice(1), { headers: { "X-Interview-Token": sessionStorage.getItem("ibank-token") } })).json(), path);

  // --- most asked ----------------------------------------------------------------------------------------------
  await page.locator(".ib-topbar").getByRole("link", { name: "备考", exact: true }).click();
  await page.getByRole("heading", { name: "备考", exact: true }).waitFor();
  await page.getByText(/^共 20 题/).waitFor();
  check("the board explains how heat is weighed", await page.getByText(/热度按面试时间加权：365 天前的一次算半次，没记日期的算 0.3 次/).isVisible());
  check("undated occurrences are counted openly", await page.getByText("4 次没有记录日期").isVisible());
  check("a row shows how often, how recently and how hot", await page.getByText(/被问 1 次 · 1 家公司 · 最近 20\d\d · 热度 [01]\.\d/).first().isVisible());
  await shot(page, "top");
  await page.getByRole("radio", { name: "近 1 年", exact: true }).click();
  await page.getByText(/^共 8 题/).waitFor();
  check("a one-year window keeps the two recent dates and leaves out what cannot be placed in time", true);
  await page.getByRole("radio", { name: "近 3 年", exact: true }).click();
  await page.getByText(/^共 12 题/).waitFor();
  check("a three-year window adds the 18-month-old ones", true);
  await page.getByRole("radio", { name: "全部", exact: true }).first().click();
  await page.getByRole("radio", { name: "按次数", exact: true }).click();
  await page.getByText(/^共 20 题/).waitFor();
  check("the half-life choice is for the heat order only", (await page.getByText("时效：越近的面试越重要").count()) === 0);
  const redis = await page.getByLabel("技术栈").locator("option", { hasText: /redis/i }).first().getAttribute("value");
  await page.getByLabel("技术栈").selectOption(redis);
  await page.getByText(/^共 3 题/).waitFor();
  check("the library's filters apply", true);
  await page.getByRole("button", { name: "练习一组", exact: true }).click();
  await page.getByRole("dialog").waitFor();
  await page.getByRole("dialog").locator("h1").waitFor();
  check("practising the shown questions opens the round", true);
  await page.keyboard.press("Escape");
  await page.getByRole("dialog").waitFor({ state: "detached" });

  // --- companies -----------------------------------------------------------------------------------------------
  await page.getByRole("radio", { name: "公司", exact: true }).click();
  await page.getByRole("link", { name: /演示网络/ }).waitFor();
  check("both companies are listed with their counts", await page.getByText("10 题 · 被问 10 次").count() === 2);
  await page.getByPlaceholder("搜索公司").fill("示例");
  check("the company search narrows the list", (await page.getByRole("link", { name: /演示网络/ }).count()) === 0 && await page.getByRole("link", { name: /示例科技/ }).isVisible());
  await shot(page, "companies");
  await page.getByRole("link", { name: /示例科技/ }).click();
  await page.getByRole("heading", { name: "示例科技", level: 2 }).waitFor();
  const all = await page.locator("ol > li").count();
  await page.getByRole("radio", { name: /^二面/ }).click();
  const second = await page.locator("ol > li").count();
  check("a round narrows the company's questions", second > 0 && second < all, `${second} of ${all}`);
  await shot(page, "company");
  await page.getByRole("button", { name: "模拟面试", exact: true }).click();
  await page.locator(".reading-title").waitFor();
  check("a mock interview starts from the company's questions", true);
  const sessionId = (await page.evaluate(() => location.hash)).split("/")[2];
  const started_session = await api("/api/interview/session?id=" + sessionId);
  check("the session remembers the company as its direction", started_session.meta.direction === "示例科技" && started_session.total === Math.min(10, second), JSON.stringify(started_session.meta));

  // --- lists ---------------------------------------------------------------------------------------------------
  await page.goto(base + "#/prepare/lists");
  await page.getByText(/^还没有备考清单/).waitFor();
  check("an empty state explains how to create a list", true);
  await page.getByRole("link", { name: "粘贴岗位描述，新建清单" }).click();
  await page.getByLabel("岗位描述（JD）").waitFor();
  check("the link opens the job-description tab", true);
  await page.getByLabel("岗位描述（JD）").fill("岗位要求：熟悉 Redis，有数据库性能优化经验，了解分布式缓存。");
  await page.getByRole("button", { name: "让 AI 选题", exact: true }).click();
  await page.getByText(/^AI 从 \d+ 道题里选了 2 道/).waitFor({ timeout: 20000 });
  await page.getByLabel("清单名称（可不填）").fill("后端岗位备考");
  await page.getByRole("button", { name: "保存为备考清单", exact: true }).click();
  await page.getByRole("heading", { name: "后端岗位备考", level: 2 }).waitFor();
  check("the picks are saved and the list opens", true);
  check("requirements show the job description's words and how the bank covers them",
    await page.getByText("“熟悉 Redis”").isVisible() && await page.getByText("直接覆盖", { exact: true }).isVisible() && await page.getByText("题库没有覆盖").isVisible()
    && await page.getByText("必须", { exact: true }).isVisible());
  check("the note says coverage is about the bank only", await page.getByText(/只说明题库里有没有相关的题/).isVisible());
  check("the list shows progress counts", await page.getByText(/没练习|未练习 2/).first().isVisible());
  await shot(page, "list");
  const saved = (await api("/api/prepare/lists")).lists;
  check("the list is a saved study set the CLI also reads", saved.length === 1 && saved[0].requirements === 2 && saved[0].covered === 1);
  await page.goto(base + "#/prepare/lists");
  await page.getByRole("link", { name: /后端岗位备考/ }).waitFor();
  check("the list appears under study lists", await page.getByText("岗位要求 2 项，直接覆盖 1 项").isVisible());

  // --- a bank with no interview dates -------------------------------------------------------------------------
  const other = await serve(plain);
  await page.goto(other.url);
  await page.waitForLoadState("networkidle");
  await page.goto(other.url.split("#")[0] + "#/prepare");
  await page.getByText(/题库里的出现记录都没有面试日期/).waitFor();
  check("a bank without dates says so and offers no recency controls", (await page.getByRole("radio", { name: "近 1 年", exact: true }).count()) === 0 &&
    (await page.getByText("时效：越近的面试越重要").count()) === 0);
  other.proc.kill();
  await page.goto(started.url);
  await page.waitForLoadState("networkidle");

  // --- phone ---------------------------------------------------------------------------------------------------
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(base + "#/prepare");
  await page.getByText(/^共 20 题/).waitFor();
  check("the ranking fits a phone", await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  await shot(page, "phone-top");
  await page.getByRole("button", { name: "更多", exact: true }).click();
  check("the phone menu offers the board", await page.getByRole("dialog").getByRole("link", { name: /备考/ }).isVisible());
  await page.keyboard.press("Escape");
  await page.goto(base + "#/prepare/companies");
  await page.getByRole("link", { name: /演示网络/ }).waitFor();
  check("the company view fits a phone", await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));

  check("no page errors", errors.length === 0, errors.join(" | "));
  check("no Content-Security-Policy violations", violations.length === 0, violations.join(" | "));
} catch (error) {
  check("script finished", false, String(error));
  await shot(page, "failure");
  console.log("PAGE", (await page?.locator("main").innerText().catch(() => "")) ?? "");
} finally {
  await browser?.close();
  server?.kill();
  model.close();
  rmSync(root, { recursive: true, force: true });
}
console.log(results.join("\n"));
process.exit(results.some((line) => line.startsWith("FAIL")) ? 1 : 0);
