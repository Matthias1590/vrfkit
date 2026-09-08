"""Policy checks for the committed semantic-evidence catalog."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

import pyarrow as pa
import pyarrow.parquet as pq


TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

import summarize_value_coverage as coverage  # noqa: E402


CATALOG_PATH = TOOLS / "fixtures" / "semantic_evidence.json"


class SemanticEvidenceFixtureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = coverage.load_semantic_evidence(CATALOG_PATH)

    def test_reviewed_claims_are_exact_identity_selectors_with_build_scope(self) -> None:
        reviewed = [
            claim for claim in self.catalog["claims"]
            if claim["evidence_status"] == "reviewed"
        ]
        self.assertEqual(4, len(reviewed))
        for claim in reviewed:
            self.assertEqual(
                {"group_path", "field_name"}, set(claim["criteria"]), claim["id"]
            )
            self.assertEqual(
                [
                    "++Ares-Core+release-13.01",
                    "++Ares-Core+release-13.02",
                    "++Ares-Core+release-13.04",
                    "++Ares-Core+release-13.05",
                ],
                claim["applicability"]["replay_builds"],
            )

    def test_only_cross_source_identity_claims_are_reviewed(self) -> None:
        reviewed_fields = {
            claim["criteria"]["field_name"]
            for claim in self.catalog["claims"]
            if claim["evidence_status"] == "reviewed"
        }
        self.assertEqual({"Subject", "SpawnedCharacter"}, reviewed_fields)

    def test_unresolved_meanings_remain_unknown(self) -> None:
        status_by_field = {
            claim["criteria"]["field_name"]: claim["evidence_status"]
            for claim in self.catalog["claims"]
        }
        expected = {
            "ProfileName", "G", "R",
            "ClientReplayReceiveInputEventProcessingCapture.InputEventData",
            "MulticastStopContinuousEffect.StopEffectType",
            "ActiveGameplayEffects",
        }
        for field in expected:
            self.assertEqual("unknown", status_by_field[field])

    def test_fixture_counts_only_exact_reviewed_group_and_field_pairs(self) -> None:
        claims = [
            claim for claim in self.catalog["claims"]
            if claim["table"] == "fields"
        ]
        bomb = "/Game/GameModes/Bomb/BombPlayerState.BombPlayerState_C"
        table = pa.table({
            "group_path": [bomb, bomb, "/wrong/group", bomb],
            "field_name": ["Subject", "SpawnedCharacter", "Subject", "ProfileName"],
            "value_i64": [None, 42, None, None],
            "value_f64": [None, None, None, None],
            "value_bool": [None, None, None, None],
            "value_str": ["opaque-subject", None, "opaque-subject", "opaque-profile"],
        })
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fields.parquet"
            pq.write_table(table, path)
            result = coverage.count_semantic_table(path, claims)
        self.assertEqual(2, result["reviewed_rows"])
        self.assertEqual(2, result["reviewed_typed_rows"])
        self.assertEqual(
            {"fields-bomb-player-state-subject", "fields-bomb-player-state-spawned-character"},
            {claim["id"] for claim in result["claims"]},
        )

    def test_reviewed_claims_do_not_apply_to_an_unmeasured_build(self) -> None:
        reviewed = [
            claim for claim in self.catalog["claims"]
            if claim["table"] == "fields" and claim["evidence_status"] == "reviewed"
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.json").write_text(
                json.dumps({"replay_build": "++Ares-Core+release-99.99"}),
                encoding="utf-8",
            )
            selected = coverage.applicable_claims(root, reviewed)
        self.assertEqual([], selected)

    def test_fixture_contains_no_observed_player_values(self) -> None:
        raw = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        text = json.dumps(raw)
        self.assertNotIn("value_str", text)
        self.assertNotIn("player_values", text)
        self.assertNotIn("subject_values", text)


if __name__ == "__main__":
    unittest.main()
