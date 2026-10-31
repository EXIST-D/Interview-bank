"""1.38 dedupe retrieval: concept keys, length-aware similarity and the candidate quotas."""
import json
import unittest
from unittest import mock

from support import Bank
from test_bank_import import add_post
from ibank_core.ai_prompts import extraction_prompt
from ibank_core.curation import stage_curate
from ibank_core.dedupe import candidate_task, similarity
from ibank_core.errors import ValidationError
from ibank_core.normalize import clean_concept, normalize_question_text
from ibank_core.runs import abandon_run, commit_run, run_path, stage_text
from ibank_core.web_intake import clean_source


def question(text, domains=(), technologies=()):
    return {"canonical": text, "normalized": normalize_question_text(text), "domains": list(domains),
            "technologies": list(technologies), "question_type": "concept"}


def commit_texts(bank, texts, domain="ai.agent.memory", concepts=None, name="base"):
    source = bank.root / f"{name}.txt"
    source.write_text("\n".join(texts) + "\n", encoding="utf-8")
    commit_run(bank.path, stage_text(bank.path, source, domains=[domain], concepts=concepts)["run_id"])


def stage(bank, texts, domain="ai.agent.memory", concepts=None, name="incoming"):
    source = bank.root / f"{name}.txt"
    source.write_text("\n".join(texts) + "\n", encoding="utf-8")
    return stage_text(bank.path, source, domains=[domain], concepts=concepts)["run_id"]


class ConceptKeyFormat(unittest.TestCase):
    def test_a_key_has_two_to_four_lowercase_segments(self):
        self.assertEqual(clean_concept("rag.chunking.strategy"), "rag.chunking.strategy")
        self.assertEqual(clean_concept("  Agent.Memory.Long-Term "), "agent.memory.long-term")
        self.assertEqual(clean_concept("algo.leetcode-200"), "algo.leetcode-200")
        for bad in ("rag", "a.b.c.d.e", "rag..x", "rag.chunk_ing", "rag.分块", "", None, 5, "x." + "y" * 70):
            self.assertIsNone(clean_concept(bad), bad)


class ConceptKeyData(unittest.TestCase):
    def setUp(self):
        self.bank = Bank()
        add_post(self.bank, "a", "https://example.org/posts/a", ["Redis 为什么快？", "Redis 持久化有哪些方式？", "MySQL 索引为什么用 B+ 树？"],
                 concepts={"Redis 为什么快？": "redis.performance.why-fast", "Redis 持久化有哪些方式？": "redis.persistence.rdb-aof"})

    def tearDown(self):
        self.bank.close()

    def ids(self):
        return {q["canonical"]: q["id"] for q in self.bank.result("search", "--limit", "20")["questions"]}

    def test_an_extracted_key_is_kept_and_searchable_by_key_or_prefix(self):
        cards = {q["canonical"]: q for q in self.bank.result("search", "--limit", "20")["questions"]}
        self.assertEqual(cards["Redis 为什么快？"]["concept"], "redis.performance.why-fast")
        self.assertNotIn("concept", cards["MySQL 索引为什么用 B+ 树？"])
        self.assertEqual([q["canonical"] for q in self.bank.result("search", "--concept", "redis.performance.why-fast")["questions"]], ["Redis 为什么快？"])
        self.assertEqual(self.bank.result("search", "--concept", "redis")["total"], 2)
        self.assertEqual(self.bank.result("search", "--concept", "redis.perf")["total"], 0)  # whole segments only

    def test_stats_list_the_vocabulary_and_what_has_no_key(self):
        stats = self.bank.result("stats")
        self.assertEqual(stats["concepts"], {"redis.performance.why-fast": 1, "redis.persistence.rdb-aof": 1})
        self.assertEqual(stats["without_concept"], 1)

    def test_a_malformed_key_is_refused_at_extraction(self):
        with self.assertRaises(AssertionError):
            add_post(self.bank, "b", "https://example.org/posts/b", ["什么是 TCP 三次握手？"], concepts={"什么是 TCP 三次握手？": "TCP Handshake"})

    def test_curate_sets_changes_and_clears_a_key(self):
        qid = self.ids()["MySQL 索引为什么用 B+ 树？"]
        for value, shown in (("MySQL.Index.B-Plus-Tree", "mysql.index.b-plus-tree"), (None, None)):
            self.bank.stage_commit("curate", payload={"schema_version": 1, "changes": [{"table": "questions", "id": qid, "set": {"concept": value}, "reason": "概念键"}]})
            self.assertEqual(self.bank.result("show", qid)["question"].get("concept"), shown)
        with self.assertRaises(ValidationError):
            stage_curate(self.bank.path, {"schema_version": 1, "changes": [{"table": "questions", "id": qid, "set": {"concept": "not a key"}, "reason": "x"}]})


class BundleKeepsConcept(unittest.TestCase):
    def test_the_key_travels_and_a_key_that_does_not_fit_is_dropped(self):
        source, target = Bank(), Bank()
        self.addCleanup(source.close)
        self.addCleanup(target.close)
        add_post(source, "a", "https://example.org/posts/a", ["Redis 为什么快？", "MySQL 索引为什么用 B+ 树？"],
                 concepts={"Redis 为什么快？": "redis.performance.why-fast", "MySQL 索引为什么用 B+ 树？": "mysql.index.b-plus-tree"})
        path = source.root / "bundle.json"
        source.result("export-bundle", "--output", str(path))
        bundle = json.loads(path.read_text(encoding="utf-8"))
        by_text = {q["canonical"]: q for q in bundle["bundle"]["questions"]}
        self.assertEqual(by_text["Redis 为什么快？"]["concept"], "redis.performance.why-fast")
        by_text["MySQL 索引为什么用 B+ 树？"]["concept"] = "Not A Key"
        path.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
        staged = target.result("import-bundle", "--input", str(path))
        decisions = target.root / "decisions.json"
        decisions.write_text(json.dumps({"task_id": staged["dedupe"]["task_id"], "default_action": "KEEP_DISTINCT", "decisions": []}), encoding="utf-8")
        self.assertTrue(target.result("ingest", "finalize", "--task", staged["dedupe"]["task_id"], "--decisions", str(decisions))["committed"])
        cards = {q["canonical"]: q for q in target.result("search", "--limit", "10")["questions"]}
        self.assertEqual(cards["Redis 为什么快？"]["concept"], "redis.performance.why-fast")
        self.assertNotIn("concept", cards["MySQL 索引为什么用 B+ 树？"])


class WebImportKeys(unittest.TestCase):
    def reply(self, concept):
        row = {"id": "q1", "original_text": "RAG 的文档怎么切分？", "domains": [], "technologies": [], "question_type": "concept",
               "confidence": {"is_question": 0.99, "classification": 0.95}}
        if concept is not None:
            row["concept"] = concept
        return {"status": "extracted", "metadata": {}, "questions": [row]}

    def test_the_model_key_is_kept_only_when_it_fits(self):
        for given, kept in (("rag.chunking.strategy", "rag.chunking.strategy"), (" RAG.Chunking ", "rag.chunking"), ("RAG chunking", None), ("rag", None), (None, None)):
            (item,) = clean_source(self.reply(given), {}, {}, "s1")["questions"]
            self.assertEqual(item.get("concept"), kept, given)

    def test_the_prompt_lists_the_keys_of_the_bank_so_the_model_reuses_them(self):
        self.assertNotIn("Keys already in the bank", extraction_prompt((), ()))
        prompt = extraction_prompt((), ("rag.chunking.strategy", "agent.memory.long-term"))
        self.assertIn("Keys already in the bank", prompt)
        self.assertIn("rag.chunking.strategy, agent.memory.long-term", prompt)
        self.assertIn('"concept"', prompt)


class CandidateRetrieval(unittest.TestCase):
    def setUp(self):
        self.bank = Bank()

    def tearDown(self):
        self.bank.close()

    def matches(self, run_id, top_k=10):
        task = candidate_task(self.bank.path, run_id, top_k=top_k)
        return task, [[m for m in item["matches"]] for item in task["items"]]

    def test_a_same_concept_question_is_offered_even_with_no_shared_wording_and_ranks_first(self):
        commit_texts(self.bank, ["Function Calling 的原理是什么？", "RAG 是什么？", "Agent 的长期记忆怎么设计？", "什么是 KV Cache？"],
                     concepts={"Function Calling 的原理是什么？": "agent.tool-use.function-calling"})
        run = stage(self.bank, ["大模型是怎么实现工具调用的？"], concepts={"大模型是怎么实现工具调用的？": "agent.tool-use.function-calling"})
        task, (found,) = self.matches(run)
        by_text = {m["question"]["canonical"]: m for m in found}
        self.assertTrue(by_text["Function Calling 的原理是什么？"]["same_concept"])
        self.assertEqual(found[0]["question"]["canonical"], "Function Calling 的原理是什么？")
        self.assertTrue(all("same_concept" not in m for m in found[1:]))
        self.assertEqual(task["items"][0]["incoming"]["concept"], "agent.tool-use.function-calling")
        abandon_run(self.bank.path, run)

    def test_a_question_without_a_key_is_retrieved_exactly_as_before(self):
        commit_texts(self.bank, ["Function Calling 的原理是什么？", "RAG 是什么？"])
        run = stage(self.bank, ["大模型是怎么实现工具调用的？"])
        task, (found,) = self.matches(run)
        self.assertTrue(all("same_concept" not in m for m in found))
        self.assertNotIn("concept", task["items"][0]["incoming"])
        abandon_run(self.bank.path, run)

    def test_the_review_sheet_shows_keys_and_marks_same_key_candidates(self):
        commit_texts(self.bank, ["Function Calling 的原理是什么？", "RAG 是什么？"], concepts={"Function Calling 的原理是什么？": "agent.tool-use.function-calling"})
        run = stage(self.bank, ["大模型是怎么实现工具调用的？"], concepts={"大模型是怎么实现工具调用的？": "agent.tool-use.function-calling"})
        task, _ = self.matches(run)
        sheet = (run_path(self.bank.path, task["id"]) / "review-sheet.md").read_text(encoding="utf-8")
        self.assertIn("大模型是怎么实现工具调用的？ [agent.tool-use.function-calling]", sheet)
        self.assertIn("(existing) Function Calling 的原理是什么？ [agent.tool-use.function-calling]", sheet)
        self.assertRegex(sheet, r"→ e1 [0-9.]+ key")
        abandon_run(self.bank.path, run)

    def test_questions_of_the_same_import_cannot_crowd_the_banks_own_out_of_the_list(self):
        commit_texts(self.bank, ["Redis 为什么快？"], domain="backend.cache")
        siblings = [f"Redis 为什么这么快呢，原因第{n}点" for n in range(1, 9)]
        run = stage(self.bank, [*siblings, "Redis 为什么快"], domain="backend.cache")
        task, found = self.matches(run, top_k=3)
        last = {m["question"]["canonical"] for m in found[-1]}
        self.assertIn("Redis 为什么快？", last)
        self.assertEqual(sum(1 for m in found[-1] if m["question"]["canonical"] != "Redis 为什么快？"), 3)
        abandon_run(self.bank.path, run)


class LengthAwareSimilarity(unittest.TestCase):
    algo = ("computer-science.algorithm",)
    short = question("岛屿数量", algo)
    long = question("算法手撕：LeetCode 200 岛屿数量，使用 Python 或 Java 实现，同时分析 DFS、BFS 两种解法的时间、空间复杂度", algo)
    other = question("手撕算法：合并 K 个有序链表（LeetCode 23），使用堆或分治实现并分析复杂度", algo)

    def test_a_short_question_inside_a_long_one_scores_higher_than_before(self):
        with mock.patch("ibank_core.dedupe.CONTAINMENT", 0.0):
            before = similarity(self.short, self.long)
        self.assertLess(before, 0.2)
        self.assertGreater(similarity(self.short, self.long), 0.4)
        # Another long question that merely shares the topic gains nothing.
        self.assertEqual(similarity(self.short, self.other), 0.05)

    def test_two_questions_of_equal_length_are_scored_as_before(self):
        a, b = question("缓存穿透方案", ["backend.cache"]), question("缓存击穿方案", ["backend.cache"])
        with mock.patch("ibank_core.dedupe.CONTAINMENT", 0.0):
            before = similarity(a, b)
        self.assertEqual(similarity(a, b), before)

    def test_a_contained_question_never_outranks_an_equivalent_one(self):
        self.assertLess(similarity(self.short, self.long), 1.0)
        self.assertEqual(similarity(question("什么是闭包？"), question("什么是闭包?")), 1.0)


if __name__ == "__main__":
    unittest.main()
