"""Dedupe retrieval ignores question boilerplate and maps common English terms to their Chinese names."""
import unittest

from support import Bank  # noqa: F401  (puts the skill's scripts on sys.path)
from ibank_core.dedupe import retrieval_text, similarity
from ibank_core.normalize import normalize_question_text


def question(text, domain="frontend.javascript"):
    return {"normalized": normalize_question_text(text), "canonical": text, "question_type": "concept",
            "domains": [domain], "technologies": []}


class RetrievalText(unittest.TestCase):
    def test_boilerplate_is_dropped(self):
        self.assertEqual(retrieval_text(normalize_question_text("什么是闭包？")), "闭包")
        self.assertIn("闭包", retrieval_text(normalize_question_text("JavaScript 中闭包是什么？")))

    def test_english_terms_meet_chinese_wording(self):
        self.assertIn("事件循环", retrieval_text(normalize_question_text("浏览器的 Event Loop 机制是怎样的？")))
        self.assertIn("三次握手", retrieval_text(normalize_question_text("Explain the TCP three-way handshake.")))

    def test_rewordings_now_outscore_unrelated_questions(self):
        target = question("JavaScript 中闭包是什么？")
        self.assertGreater(similarity(question("什么是闭包？"), target), similarity(question("什么是原型链？"), target))

    def test_exact_text_still_wins(self):
        self.assertEqual(similarity(question("什么是闭包？"), question("什么是闭包?")), 1.0)


if __name__ == "__main__":
    unittest.main()
