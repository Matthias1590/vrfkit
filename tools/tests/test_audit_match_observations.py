"""Focused regression coverage for the ammo/RPC corroboration audit."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import audit_match_observations as audit  # noqa: E402


def write_export(root: Path, rows: list[tuple]) -> None:
    pq.write_table(pa.table({
        "net_guid": [10, 20],
        "path": ["MagazineAmmo", "/Game/Equippables/Guns/Rifles/Test.Test_C"],
        "outer_net_guid": [20, None],
    }), root / "net_guids.parquet")
    names = ("time_ms", "packet_id", "actor_net_guid", "object_net_guid",
             "group_path", "field_name", "value_i64")
    pq.write_table(pa.table({name: [row[index] for row in rows]
                             for index, name in enumerate(names)}),
                   root / "fields.parquet")


class MatchObservationAuditTests(unittest.TestCase):
    ammo_group = "/Script/ShooterGame.AmmoComponent"
    rpc_group = "/Game/Equippables/Guns/Rifles/Test.Test_C_ClassNetCache"

    def test_unique_weapon_identity_match_is_corroborated(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_export(root, [
                (100, 10, 20, 10, self.ammo_group, audit.AMMO_FIELD, 30),
                (120, 12, 20, 10, self.ammo_group, audit.AMMO_FIELD, 29),
                (121, 13, 20, 0, self.rpc_group, audit.EFFECT_FIELD, 7),
            ])
            result = audit.audit_export(root)
        self.assertEqual(result["counts"]["corroborated_unique_rpc"], 1)
        self.assertEqual(result["counts"]["corroborated_same_packet"], 0)
        self.assertEqual(result["unique_rpc_time_offset_ms"], {"1": 1})

    def test_multiple_and_missing_rpc_evidence_stay_visible(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_export(root, [
                (100, 10, 20, 10, self.ammo_group, audit.AMMO_FIELD, 30),
                (120, 12, 20, 10, self.ammo_group, audit.AMMO_FIELD, 29),
                (121, 13, 20, 0, self.rpc_group, audit.EFFECT_FIELD, 7),
                (122, 14, 20, 0, self.rpc_group, audit.EFFECT_FIELD, 8),
                (500, 20, 20, 10, self.ammo_group, audit.AMMO_FIELD, 28),
            ])
            result = audit.audit_export(root, window_ms=30)
        self.assertEqual(result["counts"]["ambiguous_multiple_rpc"], 1)
        self.assertEqual(result["counts"]["unmatched"], 1)
        self.assertEqual(result["counts"]["left_censored_magazine_streams"], 1)

    def test_conflicting_ammo_packet_is_counted_not_ordered(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_export(root, [
                (100, 10, 20, 10, self.ammo_group, audit.AMMO_FIELD, 30),
                (120, 12, 20, 10, self.ammo_group, audit.AMMO_FIELD, 29),
                (120, 12, 20, 10, self.ammo_group, audit.AMMO_FIELD, 28),
                (150, 15, 20, 10, self.ammo_group, audit.AMMO_FIELD, 27),
            ])
            result = audit.audit_export(root)
        self.assertEqual(result["counts"]["ambiguous_ammo_packets"], 1)
        self.assertEqual(result["counts"]["ammo_decreases_examined"], 0)

    def test_corpus_failure_and_empty_population_do_not_report_success(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(ValueError, "no export"):
                audit.audit_exports(root)
            bad = root / "bad"
            bad.mkdir()
            (bad / "fields.parquet").write_bytes(b"broken")
            self.assertEqual(audit.main(["--exports", str(root), "--out", str(root / "audit.json")]), 1)

    def test_conflicting_weapon_identity_cannot_corroborate(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_export(root, [
                (100, 10, 20, 10, self.ammo_group, audit.AMMO_FIELD, 30),
                (120, 12, 20, 10, self.ammo_group, audit.AMMO_FIELD, 29),
                (121, 13, 20, 0, self.rpc_group, audit.EFFECT_FIELD, 7),
            ])
            pq.write_table(pa.table({"net_guid": [10, 20, 20],
                "path": ["MagazineAmmo", "Weapon1", "Weapon2"],
                "outer_net_guid": [20, None, None]}), root / "net_guids.parquet")
            result = audit.audit_export(root)
        self.assertEqual(result["counts"]["corroborated_unique_rpc"], 0)
        self.assertEqual(result["counts"]["identity_unresolved"], 1)
        self.assertEqual(result["counts"]["conflicting_net_guid_mappings"], 1)

    def test_dynamic_weapon_guid_does_not_require_a_static_path_registration(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_export(root, [
                (100, 10, 20, 10, self.ammo_group, audit.AMMO_FIELD, 30),
                (120, 12, 20, 10, self.ammo_group, audit.AMMO_FIELD, 29),
                (121, 13, 20, 0, self.rpc_group, audit.EFFECT_FIELD, 7),
            ])
            pq.write_table(pa.table({"net_guid": [10], "path": ["MagazineAmmo"],
                                    "outer_net_guid": [20]}), root / "net_guids.parquet")
            result = audit.audit_export(root)
        self.assertEqual(result["counts"]["corroborated_unique_rpc"], 1)
        self.assertEqual(result["counts"]["identity_unresolved"], 0)


if __name__ == "__main__":
    unittest.main()
