// Browser check of screenshot import against a hosted-mode reader whose --ai-config points at a stand-in
// OpenAI-compatible model on loopback. Run after `pnpm build` (part of `pnpm e2e`).
import { spawn, execFileSync } from "node:child_process";
import { createServer } from "node:http";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";
import { deflateSync } from "node:zlib";
import { chromium } from "playwright";

const cli = fileURLToPath(new URL("../../skills/interview-bank/scripts/ibank.py", import.meta.url));
const python = process.env.PYTHON || "python3";
const root = mkdtempSync(join(tmpdir(), "ibank-import-e2e-"));
const bank = join(root, "bank");
const results = [];
const violations = [];
const errors = [];
const check = (name, ok, detail = "") => results.push(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? "  — " + detail : ""}`);
// E2E_SHOTS=<dir> keeps screenshots of each step for a visual check.
const shot = (page, name) => process.env.E2E_SHOTS ? page.screenshot({ path: join(process.env.E2E_SHOTS, `import-${name}.png`), fullPage: true }) : null;

function crc32(bytes) {
  let crc = ~0;
  for (const byte of bytes) {
    crc ^= byte;
    for (let k = 0; k < 8; k++) crc = (crc >>> 1) ^ (0xedb88320 & -(crc & 1));
  }
  return ~crc >>> 0;
}

// A real, decodable PNG so the page can draw thumbnails and cut a tall screenshot into parts.
function png(width, height, shade) {
  const chunk = (type, data) => {
    const head = Buffer.alloc(8);
    head.writeUInt32BE(data.length);
    head.write(type, 4, "ascii");
    const crc = Buffer.alloc(4);
    crc.writeUInt32BE(crc32(Buffer.concat([Buffer.from(type, "ascii"), data])));
    return Buffer.concat([head, data, crc]);
  };
  const header = Buffer.alloc(13);
  header.writeUInt32BE(width);
  header.writeUInt32BE(height, 4);
  header.set([8, 2, 0, 0, 0], 8);
  const rows = Buffer.alloc((width * 3 + 1) * height);
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) rows.set([shade, (y * 7) % 256, (x * 5) % 256], y * (width * 3 + 1) + 1 + x * 3);
  return Buffer.concat([Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]), chunk("IHDR", header), chunk("IDAT", deflateSync(rows)), chunk("IEND", Buffer.alloc(0))]);
}

const seen = [];
const model = createServer((request, response) => {
  let raw = "";
  request.on("data", (part) => (raw += part));
  request.on("end", () => {
    const body = JSON.parse(raw);
    if (request.url === "/v1/web-search") {
      seen.push({ system: "search", images: 0, query: body.query });
      response.writeHead(200, { "Content-Type": "application/json" });
      return response.end(JSON.stringify({ code: 200, data: { webPages: { value: [] } } }));
    }
    const system = body.messages[0].content;
    const content = body.messages[1].content;
    const images = content.filter((part) => part.type === "image_url").length;
    seen.push({ system: system.slice(0, 80), images });
    let reply;
    if (system.includes("vision step")) {
      reply = seen.filter((s) => s.system.includes("vision step")).length === 1
        ? { status: "extracted", metadata: { round: "technical-1" }, questions: [
            { id: "a", original_text: "Redis 为什么快？", sequence: 1, domains: ["backend.cache"], technologies: ["redis"], confidence: { is_question: 0.99, classification: 0.95 } },
            { id: "b", original_text: "Redis 单线程模型为什么还这么快", canonical_suggestion: "Redis 单线程模型为什么还这么快？", sequence: 2, domains: ["backend.cache"], confidence: { is_question: 0.95, classification: 0.9 } },
            { id: "c", original_text: "讲讲 MCP", canonical_suggestion: "什么是 MCP 协议？", sequence: 3, domains: ["ai.agent.protocol"], confidence: { is_question: 0.95, classification: 0.9 } },
            { id: "d", parent_id: "c", original_text: "那和 function call 区别", canonical_suggestion: "MCP 和 Function Calling 有什么区别？", sequence: 4, domains: ["ai.agent.tool-use"], confidence: { is_question: 0.7, classification: 0.85 } },
            { id: "e", original_text: "期望薪资是多少", sequence: 5, confidence: { is_question: 0.9, classification: 0.9 } },
          ] }
        : { status: "no_questions", reason: "只有聊天记录" };
    } else if (system.includes("deduplication step")) {
      const listing = JSON.parse(content[0].text.split("candidates:\n")[1].split("\n\nThe review sheet")[0]);
      reply = { decisions: listing.filter((item) => item.question.includes("单线程")).map((item) => ({
        question_id: item.ref, action: "REVIEW", target_id: item.candidates.find((c) => c.question === "Redis 为什么快？").ref,
        confidence: 0.6, reason: "都在问 Redis 的性能来源", canonical: "Redis 为什么快？单线程模型为什么还这么快？" })) };
    } else {
      const questions = JSON.parse(content[0].text.split(":\n").slice(1).join(":\n"));
      reply = { answers: questions.map((q) => ({ question_id: q.question_id, short_answer: `${q.question} 的参考结论。`, key_points: ["第一点", "第二点"], follow_up_questions: ["还能怎么优化？"] })) };
    }
    const text = JSON.stringify({ choices: [{ message: { content: "```json\n" + JSON.stringify(reply) + "\n```" } }] });
    response.writeHead(200, { "Content-Type": "application/json" });
    response.end(text);
  });
});

let server;
let browser;
try {
  await new Promise((resolve) => model.listen(0, "127.0.0.1", resolve));
  const config = join(root, "ai.json");
  writeFileSync(config, JSON.stringify({ vision: { base_url: `http://127.0.0.1:${model.address().port}/v1`, model: "stand-in-vl" }, text: { model: "stand-in-chat" },
    search: { base_url: `http://127.0.0.1:${model.address().port}/v1/web-search`, api_key_env: "IBANK_E2E_SEARCH_KEY" } }));
  execFileSync(python, ["-B", "-X", "utf8", cli, "--bank", bank, "--json", "demo", "--v2"], { encoding: "utf8" });
  server = spawn(python, ["-B", "-X", "utf8", cli, "--bank", bank, "web", "--port", "0", "--read-only", "--allow-personal", "--allow-practice",
    "--allow-intake", "--ai-config", config, "--json"], { env: { ...process.env, IBANK_E2E_SEARCH_KEY: "stand-in" } });
  const first = await new Promise((resolve, reject) => {
    createInterface({ input: server.stdout }).once("line", resolve);
    server.once("exit", (code) => reject(new Error(`reader exited ${code}`)));
  });
  const started = JSON.parse(first).result;
  check("startup line names the models without keys", started.intake?.vision.model === "stand-in-vl" && !first.includes("_key"));
  const base = started.url.split("#")[0];

  browser = await chromium.launch(process.env.CHROMIUM ? { executablePath: process.env.CHROMIUM } : {});
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  page.on("console", (m) => /Content Security Policy|Refused to/.test(m.text()) && violations.push(m.text()));
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(started.url);
  await page.waitForLoadState("networkidle");
  const api = (path) => page.evaluate(async (p) => (await fetch(p.slice(1), { headers: { "X-Interview-Token": sessionStorage.getItem("ibank-token") } })).json(), path);

  await page.locator(".ib-topbar").getByRole("link", { name: "截图导入", exact: true }).click();
  await page.getByRole("heading", { name: "上传面经截图", exact: true }).waitFor();
  check("the import board is in the navigation when the server allows it", true);
  await page.locator("input[type=file]").setInputFiles([
    { name: "long.png", mimeType: "image/png", buffer: png(200, 1000, 40) },
    { name: "chat.png", mimeType: "image/png", buffer: png(300, 400, 200) },
  ]);
  await page.getByRole("button", { name: "开始识别 2 张", exact: true }).waitFor();
  check("a tall screenshot is cut into parts", await page.getByText("长图 4 段").isVisible());
  check("thumbnails are drawn as data URLs", (await page.locator("ul img").count()) === 2);
  await page.getByLabel("公司").fill("示例科技");
  await shot(page, "picker");
  await page.getByRole("button", { name: "开始识别 2 张", exact: true }).click();
  await page.getByRole("heading", { name: "确认识别结果", exact: true }).waitFor({ timeout: 20000 });
  check("the model read all parts of the tall screenshot in one request", seen.find((s) => s.system.includes("vision step"))?.images === 4);
  check("an unsure follow-up is highlighted for checking", await page.getByText("AI 不确定，请核对").isVisible());
  check("a screenshot without questions is explained", await page.getByText("没有面试题：只有聊天记录").isVisible());
  check("the company hint is applied", (await page.getByLabel("公司").first().inputValue()) === "示例科技");
  await shot(page, "review");
  await page.getByRole("button", { name: "查看截图 1 大图", exact: true }).click();
  check("a screenshot opens full size for checking", await page.getByRole("dialog").locator("img").isVisible() &&
    (await page.getByRole("dialog").locator("img").evaluate((img) => img.naturalWidth)) === 200);
  await page.getByRole("dialog").getByRole("button", { name: "关闭", exact: true }).click();
  const salary = page.locator("li", { has: page.locator("textarea", { hasText: "期望薪资是多少" }) });
  await salary.getByRole("checkbox").uncheck();
  await page.locator("textarea", { hasText: "MCP 和 Function Calling 有什么区别？" }).fill("MCP 与 Function Calling 的区别是什么？");
  await page.getByRole("button", { name: "确认保存 4 道题", exact: true }).click();

  await page.getByRole("heading", { name: "这些题可能已经在题库里", exact: true }).waitFor({ timeout: 20000 });
  check("the merged wording is shown before deciding", await page.getByText("选「同一题」后，题目会改为：Redis 为什么快？单线程模型为什么还这么快？").isVisible());
  check("an uncertain merge is shown with both wordings", await page.getByText("Redis 单线程模型为什么还这么快？").isVisible() && await page.getByText("都在问 Redis 的性能来源").isVisible());
  await shot(page, "merge");
  await page.getByRole("radio", { name: "相关但不同", exact: true }).click();
  await page.getByRole("button", { name: "确认并保存", exact: true }).click();
  await page.getByRole("heading", { name: "导入完成", exact: true }).waitFor({ timeout: 20000 });
  check("the summary counts new and merged questions", await page.getByText("新增 3 道题").isVisible() && await page.getByText(/合并到已有题目 1 道/).isVisible());
  await shot(page, "done");
  check("draft answers are reported as unverified", await page.getByText(/已为 3 道题生成 AI 草稿答案/).isVisible());

  const library = await api("/api/library?limit=100&sort=recent");
  const edited = library.questions.find((q) => q.canonical === "MCP 与 Function Calling 的区别是什么？");
  check("the edited wording is stored and the salary question is not", Boolean(edited) && !library.questions.some((q) => q.canonical.includes("期望薪资")));
  const detail = await api("/api/question?id=" + edited.id);
  check("a new question carries an AI draft answer and its occurrence", detail.answer_status === "ai_draft" && detail.answer.short_answer.includes("参考结论") && detail.occurrences.length === 1);
  await page.getByRole("link", { name: "什么是 MCP 协议？", exact: true }).click();
  await page.getByText("AI 草稿，尚未核验来源。").waitFor();
  check("the reader opens the imported question with the draft warning", true);

  check("new questions were searched before falling back to drafts", seen.filter((s) => s.system === "search").length === 3);
  check("the reader offers web research for a draft", await page.getByRole("button", { name: "联网补充出处", exact: true }).isVisible());

  await page.goto(base + "#/import");
  await page.getByRole("heading", { name: "最近的导入", exact: true }).waitFor();
  check("the finished import is listed", await page.getByText("2 张 · 新增 3 · 合并 1 · 答案 3").isVisible());
  await page.getByRole("heading", { name: "补充出处", exact: true }).waitFor();
  await shot(page, "research-card");
  await page.getByRole("button", { name: /^为其中 \d+ 道补充出处$/ }).click();
  await page.getByRole("heading", { name: "补充出处完成", exact: true }).waitFor({ timeout: 20000 });
  await shot(page, "research-done");
  check("a research job keeps answers it cannot support", await page.getByText(/^0\/\d+ 道题有了来源$/).isVisible() &&
    await page.getByText("没有找到依据，答案不变").first().isVisible() && await page.getByText(/没有找到足够的依据/).isVisible());
  await page.getByRole("button", { name: "再导入一批", exact: true }).click();
  await page.getByText(/^补充出处 · \d+ 道 · 有来源 0$/).waitFor();
  check("the research job is listed", true);

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(base + "#/import");
  await page.getByRole("button", { name: /^选择截图/ }).waitFor();
  await shot(page, "phone-picker");
  check("the import page fits a phone", await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  await page.getByRole("button", { name: "更多", exact: true }).click();
  check("the phone menu offers the import board", await page.getByRole("dialog").getByRole("link", { name: /截图导入/ }).isVisible());

  check("no page errors", errors.length === 0, errors.join(" | "));
  check("no Content-Security-Policy violations", violations.length === 0, violations.join(" | "));
} catch (error) {
  check("script finished", false, String(error));
  console.log("BROWSER_ERRORS", JSON.stringify(errors));
} finally {
  await browser?.close();
  server?.kill();
  model.close();
  rmSync(root, { recursive: true, force: true });
}
console.log(results.join("\n"));
process.exit(results.some((line) => line.startsWith("FAIL")) ? 1 : 0);
