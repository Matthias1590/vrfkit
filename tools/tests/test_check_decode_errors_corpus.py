"""Guards for the corpus decode-error gate.

The gate's own docstring argues that "a counter that stops being printed must
not read as zero". Its exit path did not carry that argument one step further:
`Decoded OK` and `Struct blobs: N decoded` were summed and printed and then
never read, so an exporter that decoded NOTHING -- every counter a legitimate
zero -- printed "OK: every replay reported Decode errors: 0" and exited 0. A
counter that cannot move must not read as success either.

The second hole was the process exit status. The summary is printed before the
Parquet files are finalised, so an exporter that dies writing them has already
printed `Decode errors: 0`, and the run counted as a clean replay.

A third hole, unrelated to either of those: this file never parsed `No field
name`, even though summary.rs defines
`Rows offered = decoded_ok + decoded_err + raw_or_skip + not_in_table +
no_field_name`. The five categories this tool DID print therefore summed to
about 0.3% less than its own `rows offered` line, and a reader could not make
the numbers add up without going to read the Rust source. See `LIVE_EXPORT`
and `ReconcileTests`.
"""
import contextlib
import io
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_decode_errors_corpus as guard  # noqa: E402


#: A healthy export summary, labels as driver.rs prints them.
CLEAN = """
Rows offered:      130000
Decoded OK:        129000
Decode errors:     0
Raw/Skip:          900
Not in table:      100
No field name:     0
Struct blobs:      63 decoded / 0 failed
"""

#: The same summary from an exporter whose decoders never ran. Every counter is
#: a legitimate zero and `Decode errors: 0` is true, vacuously.
NOTHING_RAN = """
Rows offered:      0
Decoded OK:        0
Decode errors:     0
Raw/Skip:          0
Not in table:      0
No field name:     0
Struct blobs:      0 decoded / 0 failed
"""

#: Measured on a live export -- not synthesized. 742738 + 0 + 72644 + 171605 +
#: 1996 = 988983, an exact match to "Rows offered" only once `No field name`
#: is part of the sum.
LIVE_EXPORT = """
Rows offered:      988983
Decoded OK:        742738
Decode errors:     0
Raw/Skip:          72644
Not in table:      171605
No field name:     1996
Struct blobs:      63 decoded / 0 failed
"""


class ReadCountersTests(unittest.TestCase):
    def test_a_clean_summary_reads_as_counters(self):
        counters, err = guard.read_counters(CLEAN, 0)
        self.assertEqual(err, "")
        self.assertEqual(counters["decode_errors"], 0)
        self.assertEqual(counters["decoded_ok"], 129000)
        self.assertEqual(counters["struct_blobs_decoded"], 63)

    def test_a_nonzero_exit_is_not_a_clean_replay(self):
        """The summary prints before the Parquet files are finalised.

        An exporter that prints `Decode errors: 0` and then dies writing its
        output is not a replay that decoded cleanly, and counting it as one is
        how a whole corpus can pass on partial exports.
        """
        counters, err = guard.read_counters(CLEAN, 1)
        self.assertIsNone(counters)
        self.assertIn("exit 1", err)

    def test_a_summary_without_decoded_ok_is_unreadable(self):
        text = "\n".join(l for l in CLEAN.splitlines() if "Decoded OK" not in l)
        counters, err = guard.read_counters(text, 0)
        self.assertIsNone(counters)
        self.assertIn("Decoded OK", err)

    def test_a_summary_without_the_struct_blob_line_is_unreadable(self):
        text = "\n".join(l for l in CLEAN.splitlines() if "Struct blobs" not in l)
        counters, err = guard.read_counters(text, 0)
        self.assertIsNone(counters)

    def test_no_field_name_is_read(self):
        counters, err = guard.read_counters(LIVE_EXPORT, 0)
        self.assertEqual(err, "")
        self.assertEqual(counters["no_field_name"], 1996)

    def test_a_summary_without_no_field_name_is_unreadable(self):
        """`no_field_name` feeds the reconciliation, so it must be REQUIRED --
        the same "a counter that stops being printed must not read as zero"
        rule the other counters already get."""
        text = "\n".join(l for l in CLEAN.splitlines() if "No field name" not in l)
        counters, err = guard.read_counters(text, 0)
        self.assertIsNone(counters)
        self.assertIn("No field name", err)

    def test_every_overlay_summary_counter_is_required_even_when_zero(self):
        """Omitting a zero line must not be indistinguishable from printing 0."""
        for label in ("Raw/Skip", "Not in table", "Rows offered"):
            with self.subTest(label=label):
                text = "\n".join(
                    line for line in CLEAN.splitlines() if label not in line
                )
                counters, err = guard.read_counters(text, 0)
                self.assertIsNone(counters)
                self.assertIn(label, err)


class DeadCounterTests(unittest.TestCase):
    """The counters that are summed for the whole corpus and must have moved."""

    def test_a_working_corpus_has_no_dead_counters(self):
        totals = {"decode_errors": 0, "decoded_ok": 129000, "raw_skip": 900,
                  "not_in_table": 100, "no_field_name": 0, "rows_offered": 130000,
                  "struct_blobs_decoded": 63, "struct_blobs_failed": 0}
        self.assertEqual(guard.dead_counters(totals), [])

    def test_a_corpus_where_no_overlay_row_decoded_is_not_a_pass(self):
        totals = {"decode_errors": 0, "decoded_ok": 0, "raw_skip": 0,
                  "not_in_table": 0, "no_field_name": 0, "rows_offered": 0,
                  "struct_blobs_decoded": 63, "struct_blobs_failed": 0}
        dead = guard.dead_counters(totals)
        self.assertTrue(dead)
        self.assertIn("Decoded OK", " ".join(dead))

    def test_a_corpus_where_no_struct_blob_decoded_is_not_a_pass(self):
        """The 13.02 shape: the decoders stop running and nothing else moves."""
        totals = {"decode_errors": 0, "decoded_ok": 129000, "raw_skip": 900,
                  "not_in_table": 100, "no_field_name": 0, "rows_offered": 130000,
                  "struct_blobs_decoded": 0, "struct_blobs_failed": 0}
        dead = guard.dead_counters(totals)
        self.assertTrue(dead)
        self.assertIn("Struct blobs", " ".join(dead))

    def test_an_exporter_that_decoded_nothing_at_all_fails_on_both(self):
        totals = {"decode_errors": 0, "decoded_ok": 0, "raw_skip": 0,
                  "not_in_table": 0, "no_field_name": 0, "rows_offered": 0,
                  "struct_blobs_decoded": 0, "struct_blobs_failed": 0}
        self.assertEqual(len(guard.dead_counters(totals)), 2)


class ReconcileTests(unittest.TestCase):
    """`Rows offered` is defined in summary.rs as the sum of five categories;
    this tool used to print only four of them. `reconcile()` is the check that
    the five categories this tool now prints actually add up to the sixth
    number it also prints, so a reader never has to go read Rust source to
    make the totals add up.
    """

    def test_the_live_export_reconciles(self):
        """742738 + 0 + 72644 + 171605 + 1996 = 988983 -- measured, not invented."""
        counters, err = guard.read_counters(LIVE_EXPORT, 0)
        self.assertEqual(err, "")
        self.assertIsNone(guard.reconcile(counters))

    def test_a_mismatch_is_reported_with_both_numbers(self):
        totals = dict(decoded_ok=742738, decode_errors=0, raw_skip=72644,
                      not_in_table=171605, no_field_name=0,  # dropped 1996
                      rows_offered=988983)
        problem = guard.reconcile(totals)
        self.assertIsNotNone(problem)
        self.assertIn("988,983", problem)
        self.assertIn("986,987", problem)  # the wrong sum without no_field_name

    def test_no_field_name_absent_from_totals_is_a_loud_error_not_a_silent_zero(self):
        """`.get(..., 0)` here would make an absent counter reconcile by
        accident -- the same doctrine violation this whole fix exists to
        close. Indexing directly means a missing key raises."""
        totals = dict(decoded_ok=129000, decode_errors=0, raw_skip=900,
                      not_in_table=100, rows_offered=130000)
        with self.assertRaises(KeyError):
            guard.reconcile(totals)


class ArgParsingTests(unittest.TestCase):
    """Defect 1 wiring: discovery now goes through corpus_scan.py."""

    def test_recursive_defaults_to_false(self):
        args = guard.parse_args(["vrfkit.exe", "corpus"])
        self.assertFalse(args.recursive)

    def test_recursive_flag_is_readable(self):
        args = guard.parse_args(["vrfkit.exe", "corpus", "--recursive"])
        self.assertTrue(args.recursive)

    def test_checkpoints_defaults_to_false(self):
        """The existing invocation in docs/USAGE.md must keep working
        unchanged -- checkpoints cost real time and disk, so opt-in only."""
        args = guard.parse_args(["vrfkit.exe", "corpus"])
        self.assertFalse(args.checkpoints)

    def test_checkpoints_flag_is_readable(self):
        args = guard.parse_args(["vrfkit.exe", "corpus", "--checkpoints"])
        self.assertTrue(args.checkpoints)


#: The `=== Checkpoints ===` block, appended to a healthy main summary, exactly
#: as summary.rs's print_checkpoints prints it.
CLEAN_WITH_CHECKPOINTS = LIVE_EXPORT + """
=== Checkpoints ===
  Checkpoints:      12
  Overlay:          500 decoded / 0 errors / 20 raw-skip / 5 not-in-table / 2 unnamed / 4 conflicts / 1 effect blobs
  Checkpoint blobs: 8 decoded / 0 failed
  Checkpoint fails: 0 array / 0 truncated RPC / 0 movement
  Checkpoint CNC:   3 RPC rows
"""


class ExportCommandTests(unittest.TestCase):
    """The scope hole: `--checkpoints` must reach the `vrfkit export` argv,
    not just this tool's own flag parsing."""

    def test_without_the_flag_the_export_command_omits_checkpoints(self):
        cmd = guard.export_command(Path("vrfkit.exe"), Path("a.vrf"), Path("out"),
                                   with_checkpoints=False)
        self.assertNotIn("--checkpoints", cmd)

    def test_with_the_flag_the_export_command_carries_checkpoints(self):
        cmd = guard.export_command(Path("vrfkit.exe"), Path("a.vrf"), Path("out"),
                                   with_checkpoints=True)
        self.assertIn("--checkpoints", cmd)


class CheckpointCounterTests(unittest.TestCase):
    """Follows the module's own discipline: a checkpoint counter that stops
    being printed must be a failure, never read as a passing zero -- read the
    module docstring's RoundResults/13.02 incident, now one level down for the
    checkpoint pass specifically.
    """

    def test_default_call_does_not_require_checkpoint_counters(self):
        """Backward compatible: a summary with no checkpoint block at all is
        still readable when `--checkpoints` was not requested."""
        counters, err = guard.read_counters(LIVE_EXPORT, 0)
        self.assertEqual(err, "")
        self.assertNotIn("checkpoint_decoded", counters)

    def test_checkpoint_counters_are_read_when_required(self):
        counters, err = guard.read_counters(
            CLEAN_WITH_CHECKPOINTS, 0, require_checkpoints=True)
        self.assertEqual(err, "")
        self.assertEqual(counters["checkpoint_decoded"], 500)
        self.assertEqual(counters["checkpoint_errors"], 0)
        self.assertEqual(counters["checkpoint_unnamed"], 2)
        self.assertEqual(counters["checkpoint_conflicts"], 4)
        self.assertEqual(counters["checkpoint_effect_blobs"], 1)
        self.assertEqual(counters["checkpoint_blobs_decoded"], 8)
        self.assertEqual(counters["checkpoint_blobs_failed"], 0)
        self.assertEqual(counters["checkpoint_fail_array"], 0)
        self.assertEqual(counters["checkpoint_fail_truncated_rpc"], 0)
        self.assertEqual(counters["checkpoint_fail_movement"], 0)

    def test_a_summary_missing_the_checkpoint_block_is_unreadable_when_required(self):
        counters, err = guard.read_counters(
            LIVE_EXPORT, 0, require_checkpoints=True)
        self.assertIsNone(counters)

    def test_a_summary_missing_just_checkpoint_fails_is_unreadable_when_required(self):
        """Each of the three checkpoint lines packs several counters into one
        regex (see CHECKPOINT_COUNTERS), so a line either supplies all of its
        counters or none of them -- dropping just "Checkpoint fails" must
        still make the whole replay unreadable, not just those three counters
        silently absent from the total."""
        text = "\n".join(
            l for l in CLEAN_WITH_CHECKPOINTS.splitlines()
            if "Checkpoint fails" not in l)
        counters, err = guard.read_counters(text, 0, require_checkpoints=True)
        self.assertIsNone(counters)
        self.assertIn("Checkpoint fails", err)

    def test_a_summary_missing_just_the_overlay_line_is_unreadable_when_required(self):
        text = "\n".join(
            l for l in CLEAN_WITH_CHECKPOINTS.splitlines()
            if not l.strip().startswith("Overlay:"))
        counters, err = guard.read_counters(text, 0, require_checkpoints=True)
        self.assertIsNone(counters)

    def test_a_summary_missing_just_checkpoint_blobs_is_unreadable_when_required(self):
        text = "\n".join(
            l for l in CLEAN_WITH_CHECKPOINTS.splitlines()
            if "Checkpoint blobs" not in l)
        counters, err = guard.read_counters(text, 0, require_checkpoints=True)
        self.assertIsNone(counters)
        self.assertIn("Checkpoint blobs", err)
        self.assertIn("Checkpoint fails", err)


#: `crates/vrfkit/src/driver/summary.rs` -- read, not copied. See
#: `SummaryFormatDriftTests`.
SUMMARY_RS = (
    Path(__file__).resolve().parents[2]
    / "crates" / "vrfkit" / "src" / "driver" / "summary.rs"
)


def _overlay_format_string(source: str) -> str:
    """The checkpoint `Overlay:` format string as summary.rs literally spells it.

    Anchored on `Overlay:` inside a quoted Rust literal. The main pass prints
    its overlay counters one-per-line and has no such literal, so this is
    unambiguous -- but the count is asserted rather than assumed, because a
    second matching literal would make "the format string" a coin toss.
    """
    matches = re.findall(r'"(  Overlay:[^"]*)"', source)
    if len(matches) != 1:
        raise AssertionError(
            f"expected exactly one quoted '  Overlay:' format string in "
            f"{SUMMARY_RS.name}, found {len(matches)}: {matches!r}"
        )
    return matches[0]


class SummaryFormatDriftTests(unittest.TestCase):
    """The regex is pinned against the REAL format string, read off summary.rs.

    This is the defect that made the test necessary, not a hypothetical. The
    Rust side grew a seventh field -- `conflicts` -- and `CHECKPOINT_OVERLAY`
    still asked for six, so it matched NOTHING on a live `--checkpoints` run.
    The fixture in this very file pinned the stale six-field format, so the
    suite stayed green while the check it guards could not run at all.

    A hand-copied fixture cannot catch that: it drifts in exactly the same
    step as the regex. Reading summary.rs means the NEXT field added there
    turns this red, which is the only version of this test that works.
    """

    def setUp(self):
        if not SUMMARY_RS.is_file():
            self.fail(f"{SUMMARY_RS} is missing: this test cannot be vacuous")
        self.source = SUMMARY_RS.read_text(encoding="utf-8")

    def test_the_regex_matches_the_line_summary_rs_actually_prints(self):
        """Render summary.rs's own format string and match the regex on it.

        Each `{}` becomes a distinct number, so a regex that matched the line
        while mis-assigning its groups fails here too, not just one that fails
        to match at all.
        """
        fmt = _overlay_format_string(self.source)
        placeholders = fmt.count("{}")
        values = [str(11 * (n + 1)) for n in range(placeholders)]
        rendered = fmt
        for value in values:
            rendered = rendered.replace("{}", value, 1)

        match = guard.CHECKPOINT_OVERLAY.search(rendered)
        self.assertIsNotNone(
            match,
            f"CHECKPOINT_OVERLAY does not match the line summary.rs prints.\n"
            f"  summary.rs: {fmt}\n"
            f"  rendered  : {rendered}\n"
            f"  regex     : {guard.CHECKPOINT_OVERLAY.pattern}\n"
            f"A field was added to or removed from the Rust format string. "
            f"Update CHECKPOINT_OVERLAY, CHECKPOINT_COUNTERS group numbers, "
            f"and CHECKPOINT_REQUIRED together.",
        )
        self.assertEqual(
            list(match.groups()), values,
            "CHECKPOINT_OVERLAY matched but its capture groups are in the "
            "wrong order or the wrong count for summary.rs's field order",
        )

    def test_every_field_summary_rs_prints_is_a_named_counter(self):
        """A captured group nothing names is a counter that reaches no total.

        The group count and the CHECKPOINT_COUNTERS entries pointing at this
        pattern must agree, or a field is parsed and then dropped -- read but
        never summed, never required, never printed.
        """
        fmt = _overlay_format_string(self.source)
        named = [
            key for key, pattern, _group in guard.CHECKPOINT_COUNTERS
            if pattern is guard.CHECKPOINT_OVERLAY
        ]
        self.assertEqual(
            len(named), fmt.count("{}"),
            f"summary.rs prints {fmt.count('{}')} overlay fields but "
            f"CHECKPOINT_COUNTERS names {len(named)} of them: {named}",
        )
        groups = sorted(
            group for _key, pattern, group in guard.CHECKPOINT_COUNTERS
            if pattern is guard.CHECKPOINT_OVERLAY
        )
        self.assertEqual(
            groups, list(range(1, fmt.count("{}") + 1)),
            "the overlay capture groups CHECKPOINT_COUNTERS reads are not "
            f"exactly 1..{fmt.count('{}')}: {groups}",
        )

    def test_every_overlay_counter_is_required_and_reaches_a_total(self):
        """Parsed is not enough: each must be REQUIRED and must be printed.

        `conflicts` was the field the regex missed; a fix that parsed it but
        left it out of CHECKPOINT_REQUIRED would let a summary that stopped
        printing it read as fine, which is this repo's named failure mode.
        """
        required = {key for key, _label in guard.CHECKPOINT_REQUIRED}
        for key, pattern, _group in guard.CHECKPOINT_COUNTERS:
            if pattern is not guard.CHECKPOINT_OVERLAY:
                continue
            with self.subTest(counter=key):
                self.assertIn(
                    key, required,
                    f"{key} is parsed but not REQUIRED: a summary that stops "
                    f"printing it would read as a pass",
                )

    def test_the_fixture_in_this_file_matches_summary_rs_field_count(self):
        """CLEAN_WITH_CHECKPOINTS is the fixture that drifted. Pin it too.

        The stale fixture is what let the suite stay green: it described a
        six-field line the Rust side had stopped printing, so every test built
        on it agreed with the broken regex.
        """
        fmt = _overlay_format_string(self.source)
        fixture = [
            line for line in CLEAN_WITH_CHECKPOINTS.splitlines()
            if line.strip().startswith("Overlay:")
        ]
        self.assertEqual(len(fixture), 1, fixture)
        self.assertEqual(
            fixture[0].count(" / ") + 1, fmt.count("{}"),
            f"the fixture's Overlay line has a different field count from "
            f"summary.rs:\n  fixture   : {fixture[0]}\n  summary.rs: {fmt}",
        )


class DeadCheckpointCounterTests(unittest.TestCase):
    """Mirrors DeadCounterTests for the checkpoint pass: a corpus where the
    checkpoint decoders never ran must not read as a clean checkpoint sweep.
    """

    def test_a_working_checkpoint_corpus_has_no_dead_counters(self):
        totals = {"checkpoint_decoded": 500, "checkpoint_blobs_decoded": 8}
        self.assertEqual(guard.dead_checkpoint_counters(totals), [])

    def test_a_corpus_where_no_checkpoint_field_decoded_is_not_a_pass(self):
        totals = {"checkpoint_decoded": 0, "checkpoint_blobs_decoded": 8}
        dead = guard.dead_checkpoint_counters(totals)
        self.assertTrue(dead)

    def test_a_corpus_where_no_checkpoint_blob_decoded_is_not_a_pass(self):
        totals = {"checkpoint_decoded": 500, "checkpoint_blobs_decoded": 0}
        dead = guard.dead_checkpoint_counters(totals)
        self.assertTrue(dead)


#: Stand-in for `vrfkit.exe`, playing the part `_export_one` expects --
#: `[str(exe), "export", str(replay), "--out", str(out)]`. Run under
#: `sys.executable`, the "export" token becomes the script Python executes (the
#: same trick `test_check_export_baseline.py` uses for its fake `export`), so a
#: file literally named `export` in the process's cwd stands in for the real
#: binary. Every helper above (`read_counters`, `dead_counters`, `reconcile`)
#: is proven correct on synthetic text; none of that proves `main()` actually
#: calls them and acts on what they return -- which is exactly the shape of
#: this file's own recorded defect ("OK: every replay reported Decode errors:
#: 0" printed over an exporter that never ran). These tests are that call.
FAKE_EXPORT_SCRIPT = '''\
import sys
from pathlib import Path

argv = sys.argv
replay = Path(argv[1])
out = Path(argv[argv.index("--out") + 1])
out.mkdir(parents=True, exist_ok=True)
name = replay.name

if "badexit" in name:
    print("exporter crashed", file=sys.stderr)
    raise SystemExit(9)

if "nothingran" in name:
    # The 13.02 shape one level down: every counter a legitimate zero.
    print("""
Rows offered:      0
Decoded OK:        0
Decode errors:     0
Raw/Skip:          0
Not in table:      0
No field name:     0
Struct blobs:      0 decoded / 0 failed
""")
    raise SystemExit(0)

if "decodeerr" in name:
    print("""
Rows offered:      100
Decoded OK:        90
Decode errors:     10
Raw/Skip:          0
Not in table:      0
No field name:     0
Struct blobs:      5 decoded / 0 failed
""")
    raise SystemExit(0)

if "blobfail" in name:
    print("""
Rows offered:      100
Decoded OK:        95
Decode errors:     0
Raw/Skip:          3
Not in table:      2
No field name:     0
Struct blobs:      5 decoded / 1 failed
""")
    raise SystemExit(0)

if "missingcounter" in name:
    # "No field name" omitted entirely -- must not read as 0.
    print("""
Rows offered:      100
Decoded OK:        100
Decode errors:     0
Raw/Skip:          0
Not in table:      0
Struct blobs:      5 decoded / 0 failed
""")
    raise SystemExit(0)

if "mismatch" in name:
    # Every REQUIRED counter present, but the five categories that make up
    # "Rows offered" undercount it by one -- summary.rs grew a sixth category
    # this tool does not know to parse yet.
    print("""
Rows offered:      100
Decoded OK:        90
Decode errors:     0
Raw/Skip:          5
Not in table:      3
No field name:     1
Struct blobs:      5 decoded / 0 failed
""")
    raise SystemExit(0)

print("""
Rows offered:      100
Decoded OK:        90
Decode errors:     0
Raw/Skip:          5
Not in table:      3
No field name:     2
Struct blobs:      5 decoded / 0 failed
""")
'''


class MainWiringTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "export").write_text(FAKE_EXPORT_SCRIPT, encoding="utf-8")
        self.corpus = self.root / "corpus"
        self.corpus.mkdir()
        self._previous_cwd = Path.cwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, self._previous_cwd)
        self._argv = sys.argv

    def make_replay(self, name: str) -> None:
        (self.corpus / name).write_bytes(b"not a real replay")

    def run_main(self, extra_args=()):
        argv = [sys.executable, str(self.corpus), "--jobs", "1", *extra_args]
        sys.argv = ["check_decode_errors_corpus.py", *argv]
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                code = guard.main()
        finally:
            sys.argv = self._argv
        return code, out.getvalue()

    def test_a_clean_corpus_exits_zero(self):
        self.make_replay("a.vrf")
        code, output = self.run_main()
        self.assertEqual(code, 0, output)
        self.assertIn("OK:", output)

    def test_decode_errors_fail_the_run(self):
        self.make_replay("decodeerr.vrf")
        code, output = self.run_main()
        self.assertEqual(code, 1, output)
        self.assertIn("decode errors", output)

    def test_struct_blob_failures_fail_the_run(self):
        self.make_replay("blobfail.vrf")
        code, output = self.run_main()
        self.assertEqual(code, 1, output)
        self.assertIn("struct-blob", output)

    def test_an_exporter_that_decoded_nothing_fails_the_run(self):
        """The 13.02 shape, one script down from the Rust regression: every
        counter is a legitimate zero, `Decode errors: 0` is vacuously true,
        and only `dead_counters` -- consulted by `main()` -- can catch it."""
        self.make_replay("nothingran.vrf")
        code, output = self.run_main()
        self.assertEqual(code, 1, output)
        self.assertIn("never moved", output)

    def test_a_missing_required_counter_fails_the_run(self):
        self.make_replay("missingcounter.vrf")
        code, output = self.run_main()
        self.assertEqual(code, 1, output)
        self.assertIn("did not report the counter", output)

    def test_a_nonzero_exporter_exit_fails_the_run(self):
        self.make_replay("badexit.vrf")
        code, output = self.run_main()
        self.assertEqual(code, 1, output)
        self.assertIn("did not report the counter", output)

    def test_a_reconciliation_mismatch_fails_the_run(self):
        self.make_replay("mismatch.vrf")
        code, output = self.run_main()
        self.assertEqual(code, 1, output)
        self.assertIn("do not reconcile", output)

    def test_no_vrf_files_is_a_controlled_failure(self):
        code, output = self.run_main()
        self.assertEqual(code, 2, output)


if __name__ == "__main__":
    unittest.main()
