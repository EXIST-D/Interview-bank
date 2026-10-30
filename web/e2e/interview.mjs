// Browser check of the AI mock interview against a hosted-mode reader whose --ai-config points at a stand-in
// OpenAI-compatible model on loopback. Run after `pnpm build` (part of `pnpm e2e`).
import { spawn, execFileSync } from "node:child_process";
import { createServer } from "node:http";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const cli = fileURLToPath(new URL("../../skills/interview-bank/scripts/ibank.py", import.meta.url));
const python = process.env.PYTHON || "python3";
const root = mkdtempSync(join(tmpdir(), "ibank-interview-e2e-"));
const bank = join(root, "bank");
const results = [];
const violations = [];
const errors = [];
const check = (name, ok, detail = "") => results.push(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? "  — " + detail : ""}`);
const shot = (page, name) => process.env.E2E_SHOTS ? page.screenshot({ path: join(process.env.E2E_SHOTS, `interview-${name}.png`), fullPage: true }) : null;

const requests = [];
const model = createServer((request, response) => {
  let raw = "";
  request.on("data", (part) => (raw += part));
  request.on("end", () => {
    const body = JSON.parse(raw);
    const system = body.messages[0].content;
    const text = body.messages[1].content[0].text;
    requests.push({ system: system.slice(0, 60), text });
    let reply;
    if (system.includes("give feedback on one answer")) {
      const answer = text.split("--- the person's response (verbatim) ---\n")[1];
      const limited = text.includes('basis: "limited"');
      reply = {
        observations: [
          { dimension: "coverage", verdict: "gap", quote: answer.slice(0, 6), note: "只讲到一个方面，其余要点没有展开。" },
          { dimension: "constraints", verdict: "gap", note: "没有说明适用边界。" },
        ],
        key_point_checks: [{ index: 0, status: "covered", note: "提到了" }, { index: 1, status: "partial", note: "只提了一半" }, { index: 2, status: "missed", note: "" }],
        review_topics: ["IO 多路复用"],
        follow_up: { prompt: "单线程会成为瓶颈吗？", reason: "回答没有讲边界" },
        limited_basis: limited,
      };
    } else {
      const ids = text.split("--- bank questions (id | count | text) ---\n")[1].split("\n").map((line) => line.split(" | ")[0]);
      reply = { picks: [{ id: ids[0], quote: "熟悉 Redis", reason: "直接考察缓存" }, { id: ids[1], quote: "不在原文里", reason: "相关" }], uncovered: ["有数据库性能优化经验"] };
    }
    response.writeHead(200, { "Content-Type": "application/json" });
    response.end(JSON.stringify({ choices: [{ message: { content: JSON.stringify(reply) } }],
      usage: { prompt_tokens: 3000, completion_tokens: 600, prompt_cache_hit_tokens: 0, prompt_cache_miss_tokens: 3000 } }));
  });
});

let server;
let browser;
let page;
try {
  await new Promise((resolve) => model.listen(0, "127.0.0.1", resolve));
  const config = join(root, "ai.json");
  writeFileSync(config, JSON.stringify({ vision: { base_url: `http://127.0.0.1:${model.address().port}/v1`, model: "stand-in-vl" }, text: { model: "stand-in-chat" },
    prices: { "stand-in-vl": { hit: 0.02, miss: 1, output: 4 }, "stand-in-chat": { hit: 0.02, miss: 1, output: 4 } } }));
  execFileSync(python, ["-B", "-X", "utf8", cli, "--bank", bank, "--json", "demo", "--v2"], { encoding: "utf8" });
  server = spawn(python, ["-B", "-X", "utf8", cli, "--bank", bank, "web", "--port", "0", "--read-only", "--allow-personal", "--allow-practice",
    "--allow-intake", "--ai-config", config, "--json"]);
  const first = await new Promise((resolve, reject) => {
    createInterface({ input: server.stdout }).once("line", resolve);
    server.once("exit", (code) => reject(new Error(`reader exited ${code}`)));
  });
  const started = JSON.parse(first).result;
  const base = started.url.split("#")[0];

  browser = await chromium.launch(process.env.CHROMIUM ? { executablePath: process.env.CHROMIUM } : {});
  page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  page.on("console", (m) => /Content Security Policy|Refused to/.test(m.text()) && violations.push(m.text()));
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("dialog", (dialog) => dialog.accept());
  await page.goto(started.url);
  await page.waitForLoadState("networkidle");
  const api = (path) => page.evaluate(async (p) => (await fetch(p.slice(1), { headers: { "X-Interview-Token": sessionStorage.getItem("ibank-token") } })).json(), path);
  const sessionId = async () => (await page.evaluate(() => location.hash)).split("/")[2];

  // --- by area -----------------------------------------------------------------------------------------------
  await page.locator(".ib-topbar").getByRole("link", { name: "模拟面试", exact: true }).click();
  await page.getByRole("heading", { name: "AI 模拟面试", exact: true }).waitFor();
  await page.getByText(/点评由 stand-in-chat 生成/).waitFor();
  check("the board is in the navigation and names the model", true);
  await shot(page, "setup");
  const redis = await page.getByLabel("技术栈").locator("option", { hasText: /redis/i }).first().getAttribute("value");
  await page.getByLabel("技术栈").selectOption(redis);
  await page.getByText(/^共 \d+ 题符合条件$/).waitFor();
  await page.getByRole("button", { name: "开始模拟面试", exact: true }).click();
  await page.locator(".reading-title").waitFor();
  const prompt = (await page.locator(".reading-title").innerText()).trim();
  check("the first prompt is asked without its reference answer", /Redis/.test(prompt) && !(await page.locator("main").innerText()).includes("数据集放在内存中"));
  const id = await sessionId();
  const matching = (await api("/api/interview/session?id=" + id)).total;
  check("the technology filter picked a few questions", matching >= 2 && matching < 19, String(matching));
  await shot(page, "question");
  await page.locator("#iv-answer").fill("它基于内存，并且用单线程避免锁竞争。");
  await page.reload();
  check("a draft survives a reload", (await page.locator("#iv-answer").inputValue()) === "它基于内存，并且用单线程避免锁竞争。");
  await page.getByRole("button", { name: "提交回答", exact: true }).click();
  await page.getByRole("heading", { name: "AI 点评", exact: true }).waitFor({ timeout: 20000 });
  check("feedback quotes the person's own words", await page.locator("blockquote", { hasText: "它基于内存，" }).isVisible());
  check("every reference key point is checked", await page.getByText("已覆盖").first().isVisible() && await page.getByText("部分覆盖").isVisible() && await page.getByText("遗漏").first().isVisible());
  check("the reference answer is shown only now", await page.locator(".answer-body").isVisible() && await page.locator(".answer-body").getByText("有来源").isVisible());
  check("the feedback names its model", await page.getByText("由 stand-in-chat 生成").isVisible());
  await shot(page, "feedback");
  const first_view = await api("/api/interview/session?id=" + id);
  const questionId = first_view.responses[0].question_id;
  const feedbackRequest = requests.find((r) => r.system.includes("feedback on one answer"));
  check("the model got the person's answer and the reference key points",
    feedbackRequest.text.includes("它基于内存，并且用单线程避免锁竞争。") && /Key points:\n0\. /.test(feedbackRequest.text));
  await page.getByRole("button", { name: "基本掌握", exact: true }).click();
  await page.getByText("已记录：基本掌握").waitFor();
  const detail = await api("/api/question?id=" + questionId);
  check("a self-rating is recorded as the person's own", detail.history.length === 1 && detail.history[0].rating === "good");

  await page.getByRole("button", { name: "回答追问", exact: true }).click();
  await page.getByText("追问", { exact: true }).first().waitFor();
  check("the AI's follow-up becomes the next prompt", (await page.locator(".reading-title").innerText()).includes("单线程会成为瓶颈吗？"));
  await page.locator("#iv-answer").fill("CPU 密集的命令会阻塞，可以拆分或用多实例。");
  await page.getByRole("button", { name: "提交回答", exact: true }).click();
  await page.getByRole("heading", { name: "AI 点评", exact: true }).waitFor({ timeout: 20000 });
  await page.getByRole("button", { name: "下一题", exact: true }).click();
  await page.locator("#iv-answer").waitFor();
  const second = (await page.locator(".reading-title").innerText()).trim();
  check("the next main question follows", second !== prompt && !second.includes("单线程会成为瓶颈吗？"));
  for (let n = 2; n <= matching; n++) {
    await page.locator("#iv-answer").fill(`第 ${n} 题的回答：RDB 是快照，AOF 记录写命令。`);
    await page.getByRole("button", { name: "提交回答", exact: true }).click();
    await page.getByRole("heading", { name: "AI 点评", exact: true }).waitFor({ timeout: 20000 });
    if (n < matching) {
      await page.getByRole("button", { name: "下一题", exact: true }).click();
      await page.locator("#iv-answer").waitFor();
    }
  }
  await page.getByRole("button", { name: "完成面试", exact: true }).click();
  await page.getByText("面试总结", { exact: true }).waitFor();
  check("the summary counts answers and weak topics", await page.getByText(`回答了 ${matching + 1} 题，AI 点评了 ${matching + 1} 题。`).isVisible() && await page.getByText("IO 多路复用").first().isVisible());
  await shot(page, "report");

  await page.goto(base + "#/interview");
  await page.getByRole("heading", { name: "最近的面试", exact: true }).waitFor();
  // The list is read again when the page returns to it; wait for the fresh rows.
  await page.getByText(new RegExp(`已答 ${matching + 1} / ${matching} 题 · 已点评 ${matching + 1}`)).waitFor({ timeout: 10000 });
  check("the finished interview is listed", await page.getByText("已完成", { exact: true }).isVisible());
  await page.getByText(new RegExp(`^今天：模型调用 ${matching + 1} 次`)).waitFor({ timeout: 10000 });
  check("today's usage includes the feedback calls", true);

  // --- by job description ------------------------------------------------------------------------------------
  await page.getByRole("radio", { name: "按岗位描述", exact: true }).click();
  await page.getByLabel("岗位描述（JD）").fill("岗位要求：熟悉 Redis，有数据库性能优化经验，了解分布式缓存。");
  await page.getByRole("button", { name: "让 AI 选题", exact: true }).click();
  await page.getByText(/^AI 从 \d+ 道题里选了 2 道/).waitFor({ timeout: 20000 });
  check("a pick shows the excerpt it comes from and a missing quote is left out",
    await page.getByText(/对应 JD：“熟悉 Redis”/).count() === 1 && await page.getByText("直接考察缓存").isVisible());
  check("uncovered requirements are listed", await page.getByText("题库没有覆盖的要求：有数据库性能优化经验").isVisible());
  await shot(page, "jd");
  await page.getByRole("button", { name: "开始模拟面试", exact: true }).click();
  await page.locator(".reading-title").waitFor();
  const planned = await api("/api/interview/session?id=" + (await sessionId()));
  check("the session records why each question was chosen", Object.keys(planned.meta.reasons).length === 2 && planned.meta.direction === "按岗位描述");
  await page.getByRole("button", { name: "结束面试", exact: true }).click();
  await page.getByText("这场面试没有作答。").waitFor();
  check("ending without an answer records nothing", true);

  // --- check my answer ---------------------------------------------------------------------------------------
  await page.goto(base + "#/bank?open=" + questionId);
  await page.getByRole("button", { name: "AI 批改我的答案", exact: true }).click();
  await page.getByText("批改我的答案", { exact: true }).waitFor();
  await page.getByRole("button", { name: "开始批改", exact: true }).click();
  await page.locator("#iv-answer").fill("因为数据都在内存里。");
  await page.getByRole("button", { name: "提交回答", exact: true }).click();
  await page.getByRole("heading", { name: "AI 点评", exact: true }).waitFor({ timeout: 20000 });
  await page.getByRole("button", { name: "完成面试", exact: true }).click();
  await page.getByText("面试总结", { exact: true }).waitFor();
  check("a single question can be checked on its own", await page.getByText("回答了 1 题，AI 点评了 1 题。").isVisible());

  // --- phone ---------------------------------------------------------------------------------------------------
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(base + "#/interview");
  await page.getByRole("heading", { name: "AI 模拟面试", exact: true }).waitFor();
  check("the setup page fits a phone", await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  await shot(page, "phone-setup");
  await page.getByRole("button", { name: "更多", exact: true }).click();
  check("the phone menu offers the board", await page.getByRole("dialog").getByRole("link", { name: /模拟面试/ }).isVisible());
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "开始模拟面试", exact: true }).click();
  await page.locator("#iv-answer").waitFor();
  check("a question fits a phone", await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  await shot(page, "phone-question");

  check("no page errors", errors.length === 0, errors.join(" | "));
  check("no Content-Security-Policy violations", violations.length === 0, violations.join(" | "));
} catch (error) {
  check("script finished", false, String(error));
  await shot(page, "failure");
  console.log("PAGE", (await page?.locator("main").innerText().catch(() => "")) ?? "");
  console.log("BROWSER_ERRORS", JSON.stringify(errors));
} finally {
  await browser?.close();
  server?.kill();
  model.close();
  rmSync(root, { recursive: true, force: true });
}
console.log(results.join("\n"));
process.exit(results.some((line) => line.startsWith("FAIL")) ? 1 : 0);
