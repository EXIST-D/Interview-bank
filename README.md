# Interview Bank · 面试题库 Skill

把搜集的面试题截图整理成可分类、可追溯、可复习的本地题库，默认生成**带参考答案**和**纯题目**两份报告。

当前版本：**1.4.0**。适用于校招、实习、秋招和社招，覆盖前端、后端、全栈、Agent、RAG、数据库等方向。

## 如何使用

这是供具备看图、语义推理和联网工具的 Agent 使用的 Skill。Agent 负责识别截图、理解题意和阅读公开资料；Python 工具负责校验、入库、查询与导出。用户用自然语言提出要求，中间结构化数据由 Agent 准备。

1. 下载或克隆本仓库：

   ```powershell
   git clone https://github.com/EXIST-D/Interview-bank.git
   ```

2. 将 `skills/interview-bank` 整个目录放入所用 Agent 支持的技能目录，或直接让 Agent 阅读本仓库的 [SKILL.md](skills/interview-bank/SKILL.md) 并执行。
3. 准备截图文件夹，明确输入目录和独立的输出题库目录。将题库放在 Skill 目录之外。
4. 用自然语言下达任务，例如：

   > 严格使用 interview-bank Skill，将指定文件夹中的面试截图整理到指定题库。自动按岗位、领域、技术栈和公司分类，合并同义题，补充有来源支持的简洁参考答案，输出带答案和不带答案两份报告，保留处理记录。

也可以限定范围：

> 只整理题目，不生成答案。

> 从已有题库筛选后端 Redis 高频题，补充参考答案并导出。

> 为当前报告前 30 题补写答案；出现不确定信息时保留核验说明。

## 功能

| 阶段 | 能力 |
|---|---|
| M1 截图提取 | 文件夹批量登记、重复图片识别、题目/代码/追问提取、原始出处保留、部分保存与续跑 |
| M2 语义分类 | 岗位、技术领域、技术栈、公司及别名、行业、招聘类型、轮次、日期和难度；支持纠错及自定义扩展 |
| M3 去重合并 | 批内与历史题库候选匹配、完全重复及同义题合并、兼容子问题归并、原题与出现记录保留 |
| M4 分析导出 | 组合筛选、频次和时间统计、题目详情、Markdown/JSON/JSONL/CSV 导出 |
| M5 参考答案 | 公开资料研究、要点与来源映射、凝练回答、版本和过期状态、详细核验记录 |

分类目录含 **67 类岗位、186 个技术领域、229 个技术标签、83 个行业标签**。支持中文名称、别名、多标签和层级筛选；公司另支持组织类型、性质和商业模式。分类依据题意与来源，无法确认的公司或日期等信息留空。

## 默认策略

**提取 → 分类 → 去重 → 提交 → 分批研究答案 → 导出双版本报告。**

- 排除自我介绍、纯个人履历、薪资和到岗时间等问题，保留可复用的技术设计与排错题。
- 合并同义题及兼容补充问法，保留影响答案的版本、语言、场景和复杂度约束；不因相似分数高就直接合并。
- 同一标准题研究一次；在当前题意和版本仍适用时复用已有答案。
- 优先读取官方文档、原始论文和第一方资料。核对来源是否支持结论，必要时验证代码或算法边界。无法核验时明确保留缺口，不冒充已完成。
- 答案始终标注“答案（参考）”，通常为一句直接回答与少量要点，约 100—250 字；复合问题可适当延长。来源核验与人工审阅分开记录。
- 通常按 5—10 题分批，保存进度支持续跑。先去重、复用资料和有效答案能减少重复消耗；分批不保证首次全量研究的总 Token 消耗很低。

单独要求查询、导出或修改 Skill 时，不会自动研究整个既有题库。重复导入字节相同的截图不会增加出现次数；频次只反映搜集记录，不代表真实面试概率。

## 输出效果

默认在题库的 `exports/` 下生成：

```text
面试题整理报告.md                带参考答案
面试题整理报告（题目版）.md      只含题目
面试题整理报告.md.details.json  完整结构化附件
```

两份 Markdown 使用相同题目、频次与顺序，由同一份已提交数据渲染，题目版不需要再次调用模型生成。

报告顶部列各领域题数，领域使用二级标题，题目使用三级标题；各领域内按出现次数降序编号。每题展示答案（答案版）、参考资料、出现次数、公司、标签和有依据的年份。内部 ID、原始轮次、精确日期、原文和来源关联保留在结构化附件。

## 运行环境与 CLI

核心工具仅需 **Python 3.10+ 标准库**，无需额外 OCR 软件、模型 SDK、数据库服务器或单独的模型 API Key。Agent 本身必须具备相应的看图、推理与联网能力。

以下是 CLI 使用示例，不会单独完成看图或网络研究：

```powershell
# 在仓库根目录运行；示例题库位于仓库旁，避免把个人数据放进发布仓库。
python -B skills/interview-bank/scripts/ibank.py init --bank ../my-interview-bank --json
python -B skills/interview-bank/scripts/ibank.py images ../screenshots --bank ../my-interview-bank --retention reference --json
python -B skills/interview-bank/scripts/ibank.py search --bank ../my-interview-bank --role 后端 --technology redis --json
python -B skills/interview-bank/scripts/ibank.py export --bank ../my-interview-bank --output 复习报告.md --answers both --json
python -B skills/interview-bank/scripts/ibank.py doctor --bank ../my-interview-bank --json
```

`images` 只登记图片，后续由 Agent 实际查看并执行提取和入库协议。`export` 只渲染已提交的答案；未研究题会显示待核验。`--answers with|without|both` 控制导出版式。

数据以 JSONL 保存，SQLite 是可重建查询缓存。变更先暂存、校验再提交，保留审计与答案历史；支持中断恢复、重复提交保护和受条件约束的撤销。

## 当前边界与验证

已完成 M1—M5 的开发与实际截图整理、参考答案研究测试。1.4 开发验收中 94 项自动化测试通过；测试验证数据流程与约束，不构成对任意截图识别准确率或答案正确率的保证。

当前不包含音视频自动转写、社交平台自动抓取、独立 Web 管理界面、模拟面试或间隔复习。源码中的音视频来源类型预留不代表已实现对应接入能力。

本公开仓库仅发布 Skill 和本说明。个人截图、题库、答案研究记录、开发方案、测试工程及本地依赖环境不随仓库发布。

## 详细协议

- [Skill 入口与完整流程](skills/interview-bank/SKILL.md)
- [截图提取](skills/interview-bank/references/extraction.md)
- [语义分类与分类目录](skills/interview-bank/references/taxonomy.md)
- [公司与行业分类](skills/interview-bank/references/company-classification.md)
- [去重合并](skills/interview-bank/references/dedupe.md)
- [报告呈现规则](skills/interview-bank/references/report-policy.md)
- [查询与导出](skills/interview-bank/references/query-export.md)
- [答案研究和核验](skills/interview-bank/references/answer-policy.md)
- [数据结构](skills/interview-bank/references/schema.md)
- [验证范围与运行边界](skills/interview-bank/references/evaluation.md)
