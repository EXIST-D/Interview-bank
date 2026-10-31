"""FSRS-6: the reference implementation's published sequences, the parameter bounds and the scheduler setting."""
import math
import unittest

from support import Bank
from ibank_core.errors import ValidationError
from ibank_core.scheduler import BOUNDS6, W6, fsrs6_parameters, fsrs6_step, fsrs_step, retrievability6

MINUTES = 10 / 1440


def run(ratings, gaps, **options):
    """Review a card with the given ratings and days since the previous review (None for the first). Intervals and the last state."""
    state, days = None, []
    for rating, gap in zip(ratings, gaps):
        interval, state = fsrs6_step(rating, state, 0 if gap is None else gap, **options)
        days.append(interval)
    return days, state


class Reference(unittest.TestCase):
    """The sequences of py-fsrs' own tests (default weights, no fuzzing), whose expected numbers were read from its test file."""

    def test_stability_and_difficulty_after_a_lapse_and_five_good_reviews(self):
        # test_memo_state: Again, then Good five times, 0, 1, 3, 8 and 21 days apart.
        _, state = run(["again", "good", "good", "good", "good", "good"], [None, 0, 1, 3, 8, 21])
        self.assertAlmostEqual(state["stability"], 53.62691, delta=1e-4)
        self.assertAlmostEqual(state["difficulty"], 6.3574867, delta=1e-4)

    def test_intervals_of_a_long_run_with_a_lapse(self):
        # test_review_card: Good x6, Again x2, Good x5; each review comes when the previous one was due. The reference
        # answers a minutes-long learning step where this scheduler has none, so those three intervals are not compared.
        ratings = ["good"] * 6 + ["again", "again"] + ["good"] * 5
        gaps = [None, MINUTES, 2, 11, 46, 163, 498, MINUTES, MINUTES, 2, 4, 7, 12]
        days, _ = run(ratings, gaps)
        expected = [0, 2, 11, 46, 163, 498, 0, 0, 2, 4, 7, 12, 21]  # 0 = a learning or relearning step in the reference
        self.assertEqual([d for d, e in zip(days, expected) if e], [e for e in expected if e])

    def test_a_same_day_hard_never_lowers_stability(self):
        _, state = fsrs6_step("good", None, 0)
        _, after = fsrs6_step("hard", state, 1 / 1440)
        self.assertEqual(after["stability"], state["stability"])

    def test_ten_easy_reviews_in_a_row_leave_difficulty_at_its_floor(self):
        _, state = run(["easy"] * 10, [None] + [1e-6] * 9)
        self.assertEqual(state["difficulty"], 1.0)

    def test_a_day_of_reviews_with_custom_weights_is_not_an_error(self):
        # The reference's second weight set, which it only stores; the steps must still give finite numbers inside the bounds.
        weights = (0.1456, 0.4186, 1.1104, 4.1315, 5.2417, 1.3098, 0.8975, 0.001, 1.5674, 0.0567, 0.9661, 2.0275, 0.1592, 0.2446,
                   1.5071, 0.2272, 2.8755, 1.234, 0.56789, 0.1437, 0.2)
        days, state = run(["good", "good", "again", "good", "easy"], [None, 3, 9, 1, 6], parameters=fsrs6_parameters(weights))
        self.assertTrue(all(isinstance(d, int) and d >= 1 for d in days))
        self.assertTrue(all(math.isfinite(v) for v in (state["stability"], state["difficulty"])))


class Formulas(unittest.TestCase):
    def test_the_defaults_are_inside_their_bounds(self):
        self.assertEqual(len(W6), 21)
        self.assertEqual(fsrs6_parameters(W6), W6)

    def test_recall_is_nine_in_ten_when_the_elapsed_time_is_the_stability(self):
        for decay in (0.1, 0.1542, 0.8):
            weights = (*W6[:20], decay)
            self.assertAlmostEqual(retrievability6(7, 7, weights), 0.9, places=9)
        self.assertEqual(retrievability6(0, 7), 1.0)
        self.assertLess(retrievability6(30, 7), retrievability6(7, 7))

    def test_first_reviews_take_the_weights_of_their_rating(self):
        self.assertEqual([fsrs6_step(r, None, 0)[1]["stability"] for r in ("again", "hard", "good", "easy")], [0.212, 1.2931, 2.3065, 8.2956])
        # An Easy first rating would start below the floor: difficulty is limited to 1..10.
        self.assertEqual(fsrs6_step("easy", None, 0)[1]["difficulty"], 1.0)
        self.assertAlmostEqual(fsrs6_step("again", None, 0)[1]["difficulty"], 6.4133, places=4)

    def test_the_interval_is_the_stability_at_nine_in_ten_and_follows_the_desired_retention(self):
        self.assertEqual([fsrs6_step(r, None, 0)[0] for r in ("again", "hard", "good", "easy")], [1, 1, 2, 8])
        _, state = fsrs6_step("good", None, 0)
        days = {retention: fsrs6_step("good", state, 3, desired_retention=retention)[0] for retention in (0.8, 0.9, 0.95)}
        self.assertGreater(days[0.8], days[0.9])
        self.assertGreater(days[0.9], days[0.95])

    def test_success_grows_stability_a_lapse_shrinks_it_and_hard_grows_less_than_easy(self):
        _, state = run(["good", "good"], [None, 2])
        grown = {r: fsrs6_step(r, state, 6)[1] for r in ("again", "hard", "good", "easy")}
        self.assertLess(grown["again"]["stability"], state["stability"])
        self.assertLess(state["stability"], grown["hard"]["stability"])
        self.assertLess(grown["hard"]["stability"], grown["good"]["stability"])
        self.assertLess(grown["good"]["stability"], grown["easy"]["stability"])
        self.assertGreater(grown["again"]["difficulty"], state["difficulty"])
        self.assertLess(grown["easy"]["difficulty"], state["difficulty"])

    def test_a_same_day_review_does_not_use_the_recall_curve(self):
        _, state = run(["good"], [None])
        same_day = fsrs6_step("good", state, 0.5)[1]["stability"]
        next_day = fsrs6_step("good", state, 1)[1]["stability"]
        self.assertEqual(same_day, state["stability"])  # a Good the same day gains nothing at the default weights
        self.assertGreater(next_day, same_day)

    def test_a_card_that_stays_unseen_for_years_is_capped_at_ten_years(self):
        state = {"stability": 5000.0, "difficulty": 1.0}
        self.assertEqual(fsrs6_step("easy", state, 5000)[0], 3650)

    def test_the_state_records_the_algorithm_and_fsrs_4_5_is_untouched(self):
        self.assertEqual(fsrs6_step("good", None, 0)[1]["algorithm"], "fsrs-6")
        days, state = fsrs_step("good", None, 0)
        self.assertEqual((days, state), (4, {"stability": 3.7145, "difficulty": state["difficulty"]}))


class Parameters(unittest.TestCase):
    def test_what_is_refused(self):
        bad = [list(W6[:20]), [*W6, 1.0], "weights", None, {"w": 1}]
        for index, (low, high) in enumerate(BOUNDS6):
            for value in (low - 0.5, high + 0.5, float("nan"), float("inf"), True, "1"):
                weights = list(W6)
                weights[index] = value
                bad.append(weights)
        for value in bad:
            with self.assertRaises(ValidationError, msg=str(value)[:60]):
                fsrs6_parameters(value)

    def test_the_bounds_are_inclusive(self):
        for index, (low, high) in enumerate(BOUNDS6):
            for edge in (low, high):
                weights = list(W6)
                weights[index] = edge
                self.assertEqual(fsrs6_parameters(weights)[index], float(edge))


class Setting(unittest.TestCase):
    def setUp(self):
        self.bank = Bank()
        self.bank.add_questions("backend.cache", "Redis 为什么快？")
        self.question = self.bank.result("search")["questions"][0]["id"]
        self.bank.result("migrate", "apply")

    def tearDown(self):
        self.bank.close()

    def record(self, request, rating="good", **extra):
        self.bank.result("study", "record", "--commit", payload={"request_id": request, "question_id": self.question, "rating": rating,
                                                                 "user_quote": "会了", **extra})
        return self.bank.result("study", "history")["events"][-1]

    def configure(self, **review):
        self.bank.stage_commit("config", payload={"review": review})

    def test_fsrs6_schedules_practice_and_records_its_state(self):
        self.configure(scheduler="fsrs6", desired_retention=0.9)
        event = self.record("a1")
        self.assertEqual((event["interval_days"], event["fsrs"]["stability"], event["fsrs"]["algorithm"]), (2, 2.3065, "fsrs-6"))

    def test_custom_weights_change_the_schedule(self):
        weights = list(W6)
        weights[2] = 5.0
        self.configure(scheduler="fsrs6", fsrs_parameters=weights)
        self.assertEqual(self.record("a1")["interval_days"], 5)

    def test_the_weights_are_checked_when_the_setting_is_saved(self):
        for review in ({"scheduler": "fsrs6", "fsrs_parameters": [1.0] * 21}, {"scheduler": "fsrs6", "fsrs_parameters": list(W6[:20])},
                       {"scheduler": "fsrs", "fsrs_parameters": list(W6)}, {"scheduler": "simple", "fsrs_parameters": list(W6)},
                       {"scheduler": "fsrs7"}):
            proc = self.bank.cli("config", payload={"review": review}, check=False)
            self.assertNotEqual(proc.returncode, 0, review)

    def test_a_bank_on_fsrs_4_5_keeps_its_schedule_and_can_move_on(self):
        self.configure(scheduler="fsrs", desired_retention=0.9)
        first = self.record("a1", occurred_at="2026-09-20T08:00:00+00:00")
        self.assertEqual((first["interval_days"], first["fsrs"]["stability"], "algorithm" in first["fsrs"]), (4, 3.7145, False))
        self.configure(scheduler="fsrs6")
        # The card keeps the stability and difficulty it had; the next review is worked out with the FSRS-6 formulas.
        second = self.record("a2")
        self.assertEqual(second["fsrs"]["algorithm"], "fsrs-6")
        self.assertGreater(second["fsrs"]["stability"], first["fsrs"]["stability"])
        self.assertGreater(second["interval_days"], first["interval_days"])

    def test_the_default_is_still_the_doubling_schedule(self):
        event = self.record("a1")
        self.assertEqual((event["interval_days"], "fsrs" in event), (3, False))


if __name__ == "__main__":
    unittest.main()
