"""Physical coverage counts rows once and never substitutes truthiness for null."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import summarize_value_coverage as coverage


class PhysicalCoverageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, directory, filename="fields.parquet"):
        directory.mkdir(exist_ok=True)
        pq.write_table(pa.table({
            "group_path": pa.array(["/Game/Test"] * 5),
            "field_name": pa.array(["ReviewedField"] * 5),
            "marker": pa.array([None, "other", None, None, None], type=pa.string()),
            "value_i64": pa.array([0, None, None, None, 7], type=pa.int64()),
            "value_f64": pa.array([None, None, None, None, 2.5], type=pa.float64()),
            "value_bool": pa.array([None, False, None, None, None], type=pa.bool_()),
            "value_str": pa.array([None, None, "", None, None], type=pa.string()),
        }), directory / filename)

    def test_null_union_and_checkpoint_denominators_are_independent(self):
        first, second = self.root / "first", self.root / "second"
        self.write(first)
        self.write(first, "checkpoint_fields.parquet")
        self.write(second)
        paths = coverage.discover([self.root, first])
        self.assertEqual(len(paths), 2)
        report = coverage.summarize(paths, 2)
        main = report["tables"]["fields"]
        cp = report["tables"]["checkpoint_fields"]
        self.assertTrue(report["complete"])
        self.assertEqual((main["rows"], main["typed_rows"], main["multi_value_rows"]), (10, 8, 2))
        self.assertEqual(main["typed_fraction"], 0.8)
        self.assertEqual((cp["exports_with_table"], cp["rows"], cp["typed_rows"]), (1, 5, 4))

    def test_bad_export_is_explicit_and_cli_fails(self):
        self.write(self.root / "good")
        broken = self.root / "broken"
        broken.mkdir()
        (broken / "fields.parquet").write_bytes(b"not parquet")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = coverage.main([str(self.root)])
        report = json.loads(output.getvalue())
        self.assertEqual(code, 1)
        self.assertFalse(report["complete"])
        self.assertEqual(report["successful_exports"], 1)
        self.assertEqual(len(report["errors"]), 1)

    def test_empty_table_has_unknown_fraction_and_schema_is_required(self):
        empty = self.root / "fields.parquet"
        pq.write_table(pa.table({name: pa.array([], type=pa.int64())
                                for name in coverage.VALUE_COLUMNS}), empty)
        self.assertEqual(coverage.count_table(empty)["rows"], 0)
        report = coverage.summarize([self.root], 1)
        self.assertTrue(report["complete"])
        self.assertIsNone(report["tables"]["fields"]["typed_fraction"])
        self.assertIsNone(report["tables"]["checkpoint_fields"]["typed_fraction"])
        pq.write_table(pa.table({"different": [1]}), empty)
        with self.assertRaisesRegex(ValueError, "missing value columns"):
            coverage.count_table(empty)

    def evidence_catalog(self, claims):
        path = self.root / "semantic-evidence.json"
        path.write_text(json.dumps({
            "schema_version": 1,
            "catalog_version": "review-2026-09-08",
            "sources": [{
                "id": "wire-review",
                "version": "abc123",
                "scope": {"build": "13.05", "replay_count": 1, "commands": ["export"]},
            }],
            "claims": claims,
        }), encoding="utf-8")
        return path

    def test_reviewed_semantic_rows_need_catalog_criteria_and_keep_unknown_unknown(self):
        self.write(self.root / "one")
        catalog = self.evidence_catalog([
            {
                "id": "zero-is-a-reviewed-observation",
                "source_id": "wire-review",
                "table": "fields",
                "evidence_status": "reviewed",
                "semantic_label": "reviewed test observation",
                "reviewed_at": "2026-09-08",
                "evidence": "independent fixture check",
                "applicability": {"export_ids": ["one"]},
                "criteria": {"group_path": "/Game/Test", "field_name": "ReviewedField", "value_i64": 0},
            },
            {
                "id": "typed-is-not-semantic",
                "source_id": "wire-review",
                "table": "fields",
                "evidence_status": "unknown",
                "criteria": {"value_i64": 7},
            },
        ])
        report = coverage.summarize(coverage.discover([self.root]), 1,
                                    coverage.load_semantic_evidence(catalog))
        semantic = report["semantic_evidence"]
        self.assertTrue(report["complete"])
        self.assertEqual(semantic["sources"][0]["scope"]["build"], "13.05")
        self.assertEqual(semantic["tables"]["fields"]["reviewed_rows"], 1)
        self.assertEqual(semantic["tables"]["fields"]["reviewed_typed_rows"], 1)
        self.assertEqual(semantic["tables"]["fields"]["unknown_or_unsupported_claim_count"], 1)

    def test_duplicate_claim_and_mismatched_criteria_field_are_rejected(self):
        duplicate = {
            "id": "same", "source_id": "wire-review", "table": "fields",
            "evidence_status": "unknown", "criteria": {"value_i64": 7},
        }
        catalog = self.evidence_catalog([duplicate, duplicate.copy()])
        with self.assertRaisesRegex(coverage.EvidenceError, "duplicate semantic evidence claim id"):
            coverage.load_semantic_evidence(catalog)

        self.write(self.root / "one")
        catalog = self.evidence_catalog([{
            "id": "false-field", "source_id": "wire-review", "table": "fields",
            "evidence_status": "reviewed", "semantic_label": "bad selector",
            "reviewed_at": "2026-09-08", "evidence": "none",
            "applicability": {"export_ids": ["one"]},
            "criteria": {"group_path": "/Game/Test", "field_name": "ReviewedField", "invented_field": "plausible"},
        }])
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = coverage.main([str(self.root), "--semantic-evidence", str(catalog)])
        report = json.loads(output.getvalue())
        self.assertEqual(code, 1)
        self.assertFalse(report["complete"])
        self.assertIn("criteria fields absent", report["errors"][0]["error"])

    def test_reviewed_claim_scope_and_null_masks_are_enforced(self):
        self.write(self.root / "one")
        self.write(self.root / "outside")
        catalog = self.evidence_catalog([
            {
                "id": "zero", "source_id": "wire-review", "table": "fields",
                "evidence_status": "reviewed", "semantic_label": "zero observation",
                "reviewed_at": "2026-09-08", "evidence": "fixture",
                "applicability": {"export_ids": ["one"]},
                "criteria": {"group_path": "/Game/Test", "field_name": "ReviewedField", "value_i64": 0},
            },
            {
                "id": "marker", "source_id": "wire-review", "table": "fields",
                "evidence_status": "reviewed", "semantic_label": "marker observation",
                "reviewed_at": "2026-09-08", "evidence": "fixture",
                "applicability": {"export_ids": ["one"]},
                "criteria": {"group_path": "/Game/Test", "field_name": "ReviewedField", "marker": "other"},
            },
        ])
        report = coverage.summarize(coverage.discover([self.root]), 1,
                                    coverage.load_semantic_evidence(catalog))
        table = report["semantic_evidence"]["tables"]["fields"]
        self.assertTrue(report["complete"])
        self.assertEqual(table["applicable_exports"], 1)
        self.assertEqual(table["reviewed_rows"], 2)
        self.assertEqual(table["claims"], [{"id": "marker", "rows": 1}, {"id": "zero", "rows": 1}])
        self.assertEqual(len(report["semantic_evidence"]["catalog_sha256"]), 64)

    def test_reviewed_claim_requires_identity_scope_and_finite_values(self):
        base = {
            "id": "bad", "source_id": "wire-review", "table": "fields",
            "evidence_status": "reviewed", "semantic_label": "bad", "reviewed_at": "2026-09-08",
            "evidence": "fixture", "criteria": {"value_i64": 0},
        }
        with self.assertRaisesRegex(coverage.EvidenceError, "group_path and field_name"):
            coverage.load_semantic_evidence(self.evidence_catalog([base]))
        base["criteria"] = {"group_path": "/Game/Test", "field_name": "ReviewedField", "value_f64": float("nan")}
        with self.assertRaisesRegex(coverage.EvidenceError, "JSON scalar"):
            coverage.load_semantic_evidence(self.evidence_catalog([base]))

    def test_replay_build_applicability_reads_manifest(self):
        for name, build in (("matching", "release-ok"), ("other", "release-other")):
            directory = self.root / name
            self.write(directory)
            (directory / "manifest.json").write_text(json.dumps({"replay_build": build}), encoding="utf-8")
        catalog = self.evidence_catalog([{
            "id": "build-scoped", "source_id": "wire-review", "table": "fields",
            "evidence_status": "reviewed", "semantic_label": "build observation",
            "reviewed_at": "2026-09-08", "evidence": "fixture",
            "applicability": {"replay_builds": ["release-ok"]},
            "criteria": {"group_path": "/Game/Test", "field_name": "ReviewedField"},
        }])
        report = coverage.summarize(coverage.discover([self.root]), 1,
                                    coverage.load_semantic_evidence(catalog))
        table = report["semantic_evidence"]["tables"]["fields"]
        self.assertTrue(report["complete"])
        self.assertEqual((table["applicable_exports"], table["reviewed_rows"]), (1, 5))

        # Both restrictions narrow the claim: a matching ID cannot override
        # a mismatching build, and a matching build cannot override the ID.
        scoped = coverage.load_semantic_evidence(catalog)
        scoped["claims"][0]["applicability"]["export_ids"] = ["other"]
        report = coverage.summarize(coverage.discover([self.root]), 1, scoped)
        table = report["semantic_evidence"]["tables"]["fields"]
        self.assertEqual((table["applicable_exports"], table["reviewed_rows"]), (0, 0))


if __name__ == "__main__":
    unittest.main()
