# Interview Bank Skill

[English](README.en.md) | 简体中文

`interview-bank` 是一个面向 Claude Code、Codex 等支持 Agent Skills 的 Agent 的面试题整理 Skill。它可以帮助用户从碎片化搜集的面试题目截图、已选好的文字、网页、音视频中的语音或字幕转写稿中提取面试题，按岗位、技术领域、技术栈、公司和行业分类，合并同义问法，研究有来源支持的参考答案，并生成适合阅读和自测的两份报告，帮助用户将碎片化的面试题目积累成个人的面试题目参考库。

适用于校招、实习、秋招和社招。当前版本为 **1.14.0**。详见 [更新记录](CHANGELOG.md) 与 [GitHub Releases](https://github.com/EXIST-D/Interview-bank/releases)。

## 本次更新：1.14 真实环境测评后的修复

1.14 来自第一次真实环境测评：Skill 安装到 Claude Code，由只读 Skill 文档的全新 Opus、Sonnet Agent 端到端完成截图整理，并在真实 `claude -p` 会话中跑触发、去重判断与答案评测（结果见下方“验证情况”）。

- **去重审阅表**：每个去重任务生成按主题分组的 `review-sheet.md`，列出新题、候选和同主题已有题，字面不同的同义题也能被对照到。合并目标可以是题库中任意有效题目（审计中标记 `outside_candidates`），决策可用 `n3`/`e7` 简写，`default_action` 省去逐条写"不重复"。
- **不确定的合并不再卡住整批**：`ingest finalize --defer-review` 先提交确定的部分，拿不准的合并留给用户在 Web“合并裁决”里决定，再由 `dedupe --resolve` 应用。
- **答案引用可逐字核对**：新增 `page-text`，把引用页面的正文存下来供 `answer --page-texts` 校验摘录；重定向到其他页面会提示。
- **手机截图规则**：滚动截图重叠、跨图断题、超长图、同一面经发两次，以及缩写公司名与平台的证据规则。
- **其他**：大批量导入的输出不再超出 32 KB 上限、任务文件更小；新增“AI 应用开发”岗位与 Claude Code、Codex 等技术标签；报告按题量排列主题；并列高频题有明确规则。

详见 [更新记录](CHANGELOG.md)。本地 Web 用法见 [本地 Web 说明](skills/interview-bank/references/web.md)。

## 界面示例

![Interview Bank 本地 Web 界面：多维筛选、题目列表与参考答案阅读](assets/readme/web-preview.png)

上图由 `demo` 示例题库生成（合成题目与虚构公司），任何人都可以用 `demo --bank <新目录>` 和 `web` 复现。

## 仓库结构

```text
Interview-bank/
├── README.md / README.en.md
├── CHANGELOG.md                  # 版本记录
├── CONTRIBUTING.md / SECURITY.md
├── LICENSE
├── .github/workflows/ci.yml      # Windows/macOS/Linux × Python 3.10–3.13 测试、lint、旧格式回归与安装包检查
├── tests/                        # 标准库 unittest 测试（不随 Skill 安装）
├── evals/                        # 评测数据集、打分脚本、评测记录与宿主验证记录
├── tools/                        # 打包、发布检查、合成夹具、度量与评测运行器
├── examples/                     # 结构化答案样例
├── assets/readme/                # 主页示意图，不随 Skill 安装
└── skills/
    └── interview-bank/           # 可安装的 Skill 本体
        ├── SKILL.md
        ├── LICENSE.txt
        ├── agents/openai.yaml
        ├── assets/web/           # 本地 Web 页面（HTML/CSS/JS，无构建步骤）
        ├── references/           # 各环节协议
        └── scripts/
            ├── ibank.py          # CLI 入口
            └── ibank_core/       # 数据引擎
```

## 功能范围

| 环节 | 能做什么 |
|---|---|
| 素材入库 | 截图、已选文字、网页正文、录音与视频音轨、SRT/VTT/TXT/JSON 字幕（含 B 站与 YouTube 自动字幕）；相同文件不重复计数 |
| 抽取 | Agent 看图或阅读转写稿，保留原文、追问关系、公司/轮次/日期；低置信度与联系方式会成为审阅项 |
| 分类 | 67 类岗位、186 个技术领域、229 个技术标签、83 个行业，支持中文名、别名、多标签与层级筛选 |
| 去重 | 候选检索（去除问句套话、常见英文术语映射）+ Agent 语义判断；不确定的可交给用户在 Web 中裁决 |
| 参考答案 | 搜索并阅读一手资料，按要点映射来源；可附原文摘录并校验；措辞变化时用 `answer-recheck` 低成本复核 |
| 报告 | 带答案与纯题目两版 Markdown + 结构化附件；JSON/JSONL/CSV/Anki 导出；可切换英文 |
| 持续维护 | V2 个人状态、字段保护、禁止合并、研究工作流、撤销、增量快照、`gc` 清理、独立备份与恢复 |
| 备考 | JD 专题选题与覆盖缺口、每日计划日历、复习队列（简单间隔或 FSRS）、逐题模拟面试 |
| 本地 Web | 浏览、筛选、练习自评、人工审阅、合并裁决；中英文、暗色模式 |

## Agent 能力与环境要求

本 Skill 使用 Agent 的看图、推理和联网工具，不绑定某一家模型 API。Agent 负责理解材料和研究答案，Python CLI 负责数据校验、事务入库、查询与导出。

- Python **3.10 或更高版本**；核心与字幕解析只使用标准库。原始音视频的本地转写可选安装 `faster-whisper==1.2.1`。
- Agent 能查看本地图片、读写用户授权的文件，并执行 Python 命令；生成有来源的答案时需要搜索和读取网页。
- 通过 `npx` 安装时需要 Node.js/npm；Python 核心工具本身不依赖 Node.js。
- 题库与输出目录应位于已安装 Skill 目录之外。
- CLI 默认不联网；只有用户要求时运行的 `verify-citations`（检查引用链接）和研究答案时的 `page-text`（保存引用页面正文）会访问网络。

## 安装方式

如果不熟悉安装命令，可以直接告诉你的 Agent：

> 请你为我安装这个 [https://github.com/EXIST-D/Interview-bank](https://github.com/EXIST-D/Interview-bank) Skill，并且进行简要介绍。

可在 [skills.sh 的 interview-bank 页面](https://skills.sh/exist-d/interview-bank/interview-bank) 查看本 Skill。使用 `skills` CLI 安装（以 Codex 为例）：

```powershell
npx skills add EXIST-D/Interview-bank --skill interview-bank --agent codex --yes --copy
```

其他 Agent 替换 `--agent` 即可（路径来自 [skills CLI](https://github.com/vercel-labs/skills)，加 `-g` 为全局安装）：

| Agent | `--agent` | 项目目录 | 全局目录 | 调用方式 |
|---|---|---|---|---|
| Claude Code | `claude-code` | `.claude/skills/` | `~/.claude/skills/` | 自然语言，按 Skill 描述自动匹配 |
| Codex | `codex` | `.agents/skills/` | `~/.codex/skills/` | `$interview-bank …` 或自然语言 |
| Cursor | `cursor` | `.agents/skills/` | `~/.cursor/skills/` | 自然语言 |
| Trae / Trae CN | `trae` / `trae-cn` | `.trae/skills/` | `~/.trae/skills/` / `~/.trae-cn/skills/` | 自然语言 |
| Qwen Code | `qwen-code` | `.qwen/skills/` | `~/.qwen/skills/` | 自然语言 |
| Gemini CLI | `gemini-cli` | `.agents/skills/` | `~/.gemini/skills/` | 自然语言 |

各宿主的实际验证情况记录在 [宿主验证记录](evals/host-verification.md)。也可以把 `skills/interview-bank` 整个目录复制到所用 Agent 的技能目录，或从 [Releases](https://github.com/EXIST-D/Interview-bank/releases) 下载带校验值的 ZIP。若客户端没有刷新技能列表，请重新加载项目或重启客户端。

## 快速体验

```text
python -B <Skill目录>/scripts/ibank.py demo --bank <新目录>
python -B <Skill目录>/scripts/ibank.py web --bank <新目录> --open
```

`demo` 生成 20 道合成题（8 道附有核对过官方文档的参考答案），可以直接浏览、导出和练习。

## 使用示例

```text
使用 interview-bank 整理这些面试题截图，自动分类和合并同义题，补充有来源的参考答案，输出带答案和纯题目两份报告。

只整理题目，不生成答案；排除自我介绍等纯个人问题。

这篇牛客面经帮我整理进题库（我已经打开了这个页面）。

请找出已有题库中后端 Redis 的高频题，补充官方资料支持的参考答案。

根据这份 JD，从个人题库中选出 30 道相关题，说明覆盖和缺口，生成两份专题报告，并安排成每天 10 题的计划。

从这个专题问我 10 题，每次一题；我回答后给出反馈，结束时总结薄弱点。

把题库导出成 Anki 卡片。

打开本地 Web，我想自己审一下答案，也处理一下不确定的合并。
```

完整模板：

```text
使用 interview-bank，整理“<截图输入目录>”中的全部面试题截图，
将题库和整理结果保存到“<输出题库目录>”。

输入文件仅供读取，所有新文件写入输出题库目录，不要修改已安装的 Skill。

请根据题意自动分类，合并同义题与兼容补充问法，保留原题和出处；
排除自我介绍等纯个人问题，不要猜测无法确认的公司、年份或模糊文字。

为去重后的题目搜索并读取可信资料，核对结论和适用条件，
将答案凝练为简短要点，标注“答案（参考）”并附来源。

输出带答案和纯题目两份 Markdown 报告，以及完整结构化附件。
请分批保存和提交，完成后说明题目数量、答案覆盖、输出文件及未解决事项。
```

## 本地 Web 查阅与练习

> 请用 interview-bank 打开我指定题库的本地 Web 界面，让我浏览题目和练习。

```text
python -B <Skill目录>/scripts/ibank.py web --bank <已有题库目录> --open
```

服务只监听本机（`127.0.0.1` 与 `localhost` 均可），使用启动时返回的完整链接；终端中按 Ctrl+C 停止，`--read-only` 禁用所有写入。页面支持：多维筛选与搜索、答案与原始问法阅读、练习自评（V2 题库保存，刷新后可继续本轮）、**人工审阅**（只有你本人能点击）、**合并裁决**（Agent 不确定的合并由你判断）、中英文与暗色模式。Web 不调用 AI，也不自动判分。

## 处理策略

默认流程：**提取 → 分类 → 去重 → 提交 → 研究参考答案 → 导出两版报告**。

- 相似度只用于寻找候选，是否合并由 Agent 结合完整题意判断；不确定时交给用户。不会为了减少数量而丢掉语言、版本、场景或复杂度约束。
- 答案优先使用官方文档、原始论文和第一方资料，每个要点映射来源；“已核验来源”与“已人工审阅”是不同状态，后者只能由用户本人产生。
- 研究超过 20 题前，Agent 会先告诉你题数和批次，让你选择全部研究、只研究高频题或先出题目版。
- 通常按 5—10 题分批处理，先去重再研究；两版报告由同一份数据渲染，不需要再次生成答案。
- 只整理题目时跳过答案研究；单独查询、导出或修改 Skill 不会触发全库研究。

## 生成题库与报告

```text
<输出题库目录>/
├── manifest.json / config.json
├── data/                         # 题目、出现记录、来源、公司、答案、关系；V2 另有 state.json
├── runs/                         # 任务包、暂存（增量变更集）、提交回执与审计
├── media/                        # 选择复制保留时的原始素材
├── backups/                      # backup create 与迁移生成的校验备份
└── exports/
    ├── 面试题整理报告.md
    ├── 面试题整理报告（题目版）.md
    └── 面试题整理报告.md.details.json
```

- **参考答案版**：顶部汇总领域题数；每题包含参考答案、资料链接、出现次数、公司、标签和有依据的年份；口述版、常见追问与易错点折叠展示。
- **题目版**：与答案版题目和顺序一致，去掉答案，便于自测。
- **结构化附件**：保留内部 ID、原题、精确日期、来源关联、完整分类与答案历史。

`data/` 中的 JSONL 是唯一事实来源，查询直接读取；所有修改都经过暂存、校验和提交，保留历史与审计。出现次数代表搜集记录，不代表面试人数或真实市场概率。

## 当前状态与计划

**v1.14.0** 已实现上面“功能范围”表中的全部能力。已有 V1 题库可继续使用提取、分类、去重、答案研究与导出；保存专题、持久研究工作流和复习状态需要先备份并升级到 V2。更新 Skill 不会自动迁移个人题库，也不会把旧答案标记为重新核验。

**尚未实现：**

| 方向 | 说明 |
|---|---|
| 视频画面题目提取 | 只处理视频语音；画面中未被念出的文字需另行截图 |
| 说话人分离与长录音断点续转 | 可保留工具提供的说话人信息，按文件恢复 |
| Web 内编辑 | 题目编辑与素材导入仍由 Agent 完成；Web 负责阅读、练习、审阅和合并裁决 |
| MCP 形态 | 计划作为独立可选包，核心保持零依赖 |

**其他边界：**复习队列按需生成，没有后台提醒；精确 Token 和费用统计依赖宿主；任意历史合并的拆分尚不支持，仅支持满足条件的最近操作撤销。

**验证情况：** v1.14.0 在 CI 中通过 298 项自动化测试（Windows、macOS、Linux；Python 3.10–3.13），另以旧快照格式回归一遍，并做 lint 与安装包检查；可用 `python -B -m unittest discover -s tests` 自行运行。评测结果与宿主验证见 [evals](evals/README.md)：去重召回 recall@10 为 1.00；盲测的去重判断误合并 0%、漏合并 3.4%（Opus、Sonnet）；盲测答案经独立评审平均 1.7/2，无无依据断言；Claude Code 上 Sonnet 的触发评测达标，Haiku 召回 0.73–0.80 未达标。识别结果与参考答案仍需结合原文、来源和适用条件核对。

仓库包含 Skill、测试、评测与开发工具、介绍、许可证及本页示意图。个人素材、题库、答案研究记录和本地依赖环境不随仓库发布；测试与评测数据均为合成数据。

## 作者与维护

本项目由 [EXIST-D](https://github.com/EXIST-D) 创建并维护。

欢迎通过 [GitHub Issues](https://github.com/EXIST-D/Interview-bank/issues) 提交问题、使用反馈或改进建议，流程见 [CONTRIBUTING](CONTRIBUTING.md)；安全问题见 [SECURITY](SECURITY.md)。提交示例时请先移除个人信息、私有截图和敏感题库内容。

## 许可证

本仓库使用 **MIT License**，详见 [LICENSE](LICENSE)。Skill 内部也包含一份许可证副本：[skills/interview-bank/LICENSE.txt](skills/interview-bank/LICENSE.txt)。

许可证适用于本仓库的代码和说明；用户输入的截图、题库材料以及引用的第三方资料仍遵循各自的权利与使用条件。
