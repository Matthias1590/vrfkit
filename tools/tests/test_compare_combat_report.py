"""Guards for the CombatReport comparison.

This script is listed in `docs/USAGE.md` among the regression gates, and it
could not fail. Everything ran at module import, the verdict was printed, and
there was no exit path at all -- so `SOME SHAPES DIFFER` and
`ALL INTERESTING SHAPES MATCH` both left the process at 0. Anything gating on
`$?` read a broken decoder as a pass.
"""
import collections
import io
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import compare_combat_report as guard  # noqa: E402

SHAPE = "Rounds[].Reports[].Interactions[].DamageDealt"


def counters(pairs):
    return collections.defaultdict(collections.Counter,
                                   {s: collections.Counter(c) for s, c in pairs})


class CompareTests(unittest.TestCase):
    def test_identical_multisets_match(self):
        both = [(SHAPE, {35: 2, 40: 1})]
        _rows, ok = guard.compare(counters(both), counters(both), {SHAPE})
        self.assertTrue(ok)

    def test_a_differing_count_does_not_match(self):
        _rows, ok = guard.compare(counters([(SHAPE, {35: 2})]),
                                  counters([(SHAPE, {35: 1})]), {SHAPE})
        self.assertFalse(ok)

    def test_a_shape_absent_on_both_sides_still_matches(self):
        _rows, ok = guard.compare(counters([]), counters([]), {SHAPE})
        self.assertTrue(ok)

    def test_a_shape_present_on_one_side_only_does_not_match(self):
        _rows, ok = guard.compare(counters([(SHAPE, {35: 1})]), counters([]),
                                  {SHAPE})
        self.assertFalse(ok)


class VacuousMatchTests(unittest.TestCase):
    """`ALL INTERESTING SHAPES MATCH` was printed after comparing nothing.

    Empty counters satisfy `a == b`, so a replay carrying none of the ten
    shapes -- a wrong parquet path, a CombatReport decoder that stopped
    emitting, the wrong reference bundle -- reported every shape IDENTICAL and
    exited 0. `compare` keeps saying they matched, because per shape that is
    the truth; what was missing is anyone asking whether a shape was there to
    compare at all.

    The `absent both sides` arm at the same spot was unreachable for exactly
    the same reason: it sat below the equality test that empty counters pass.
    """

    def test_nothing_to_compare_is_counted_as_nothing_compared(self):
        self.assertEqual(guard.compared_shapes(counters([]), counters([]),
                                               {SHAPE}), 0)

    def test_a_shape_on_either_side_counts_as_compared(self):
        self.assertEqual(guard.compared_shapes(counters([(SHAPE, {35: 1})]),
                                               counters([]), {SHAPE}), 1)
        self.assertEqual(guard.compared_shapes(counters([]),
                                               counters([(SHAPE, {35: 1})]),
                                               {SHAPE}), 1)

    def test_the_absent_on_both_sides_verdict_is_reachable_again(self):
        rows, _ok = guard.compare(counters([]), counters([]), {SHAPE})
        self.assertIn("absent both sides", " ".join(rows))
        self.assertNotIn("IDENTICAL", " ".join(rows))


class ExitCodeTests(unittest.TestCase):
    """The part that was actually broken: the verdict reaching the caller."""

    def test_matching_data_exits_zero(self):
        both = [(SHAPE, {35: 2})]
        self.assertEqual(guard.main(counters(both), counters(both), {SHAPE}), 0)

    def test_differing_data_exits_nonzero(self):
        code = guard.main(counters([(SHAPE, {35: 2})]),
                          counters([(SHAPE, {35: 1})]), {SHAPE})
        self.assertNotEqual(code, 0)

    def test_comparing_nothing_does_not_exit_zero(self):
        self.assertNotEqual(guard.main(counters([]), counters([]), {SHAPE}), 0)

    def test_one_shape_missing_from_both_sides_is_not_a_pass(self):
        """A matching shape used to carry the run past one nobody compared."""
        other = "Rounds[].Reports[].Interactions[].DidKill"
        both = [(SHAPE, {35: 2})]
        self.assertEqual(guard.main(counters(both), counters(both), {SHAPE, other}), 2)

    def test_a_disagreement_outranks_a_missing_shape(self):
        other = "Rounds[].Reports[].Interactions[].DidKill"
        self.assertEqual(guard.main(counters([(SHAPE, {35: 2})]),
                                    counters([(SHAPE, {35: 1})]), {SHAPE, other}), 1)


class InputTests(unittest.TestCase):
    """The reference used to be a valplay path that no longer held it."""

    def test_a_missing_reference_exits_2_and_says_where_it_looked(self):
        missing = Path(__file__).with_name("no-such-reference.ndjson")
        with mock.patch("sys.stderr", new_callable=io.StringIO) as err:
            code = guard.main(argv=["--reference", str(missing), "--ours", str(missing)])
        self.assertEqual(code, 2)
        self.assertIn(str(missing), err.getvalue())

    def test_the_default_reference_is_not_the_valplay_bundle(self):
        self.assertNotIn("valplay", guard.DEFAULT_REFERENCE.lower())
        self.assertIn("csharp-reference", guard.DEFAULT_REFERENCE)


if __name__ == "__main__":
    unittest.main()
