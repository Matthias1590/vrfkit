import json
import sys
import tempfile
import unittest
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).parents[1]))
import extract_player_effects as effects


class PlayerEffectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def export(self, fields, players=None):
        if players is None:
            players = [{"character_net_guid": 20, "subject": "target",
                        "possessed_character": 412}]
        (self.root / "manifest.json").write_text(json.dumps({"players": players}),
                                                 encoding="utf-8")
        schema = pa.schema([(name, pa.string() if name in ("group_path", "field_name", "value_str")
                             else pa.float64() if name == "value_f64"
                             else pa.bool_() if name == "value_bool" else pa.int64())
                            for name in effects.COLUMNS])
        pq.write_table(pa.Table.from_pylist(fields, schema=schema), self.root / "fields.parquet")
        pq.write_table(pa.table({"net_guid": [99],
                                "path": ["FXC_Wraith_Q_NearsightMissile_Nearsight_C"]}),
                       self.root / "net_guids.parquet")
        before = (self.root / "fields.parquet").read_bytes()
        result = effects.build(self.root)
        self.assertEqual(before, (self.root / "fields.parquet").read_bytes())
        return result

    @staticmethod
    def row(actor, name, value=None, packet=1, rpc=False):
        return {"time_ms": packet * 100, "packet_id": packet,
                "channel_index": 4, "actor_net_guid": actor, "object_net_guid": actor + 1,
                "group_path": effects.EFFECT_GROUP if rpc else effects.BLIND_GROUP,
                "field_name": name, "value_i64": value}

    def blind(self, actor, effect_id=1, packet=1):
        return [self.row(actor, "ActiveBlinds[0].EffectID", effect_id, packet),
                self.row(actor, "ActiveBlinds[0].CausingActor", 100, packet),
                self.row(actor, "ActiveBlinds", packet=packet)]

    def test_possessed_devices_keep_evidence_without_player_hits(self):
        for device in (412, 798, 1170, 1534, 1884):
            with self.subTest(device=device):
                doc = self.export(self.blind(device) + self.blind(20, 2, 2)
                                  + self.blind(device, 3, 3))
                self.assertEqual(doc["totals"]["player_blind_update"], 1)
                self.assertEqual(doc["totals"]["unconfirmed_target_observations"], 2)
                self.assertEqual([r["values"]["CausingActor"] for r in doc["records"]], [100] * 3)
                self.assertEqual(doc["records"][1]["target_subject"], "target")

    def test_device_only_flash_is_preserved_with_zero_player_observations(self):
        doc = self.export(self.blind(412))
        self.assertEqual(len(doc["records"]), 1)
        self.assertEqual(doc["totals"]["player_blind_update"], 0)
        self.assertEqual(doc["records"][0]["values"]["CausingActor"], 100)

    def test_nearsight_start_and_stop_use_body_identity(self):
        fields = []
        for actor in (412, 20):
            for rpc in ("MulticastPlayContinuousEffect", "MulticastStopContinuousEffect"):
                fields.append(self.row(actor, rpc + ".EffectID", 1, rpc=True))
                if rpc.startswith("MulticastPlay"):
                    fields.append(self.row(actor, rpc + ".EffectContainer", 99, rpc=True))
        doc = self.export(fields)
        self.assertEqual(doc["totals"]["player_continuous_start"], 1)
        self.assertEqual(doc["totals"]["player_continuous_stop"], 1)
        self.assertEqual(len(doc["records"]), 4)
        self.assertEqual(doc["records"][0]["effect_container_path"],
                         "FXC_Wraith_Q_NearsightMissile_Nearsight_C")

    def test_same_packet_invocations_and_array_items_do_not_merge(self):
        fields = [self.row(20, "MulticastPlayContinuousEffect.EffectID", n, rpc=True)
                  for n in (1, 2)]
        fields += [self.row(20, f"ActiveBlinds[{n}].EffectID", n + 3) for n in (0, 1)]
        doc = self.export(fields)
        self.assertEqual([r["values"]["EffectID"] for r in doc["records"]], [1, 2, 3, 4])
        self.assertEqual(doc["totals"]["same_packet_parameter_restarts"], 1)

    def test_missing_and_conflicting_identities_are_not_players(self):
        for players in ([], [{"character_net_guid": 20, "subject": "a"},
                             {"character_net_guid": 20, "subject": "b"}]):
            doc = self.export(self.blind(20), players)
            self.assertEqual(doc["totals"]["player_blind_update"], 0)
            self.assertIsNone(doc["records"][0]["target_subject"])

    def test_untyped_member_stays_missing_and_wrong_group_is_ignored(self):
        fields = [self.row(20, "ActiveBlinds[0].InitialDuration")]
        wrong = self.row(20, "ActiveBlinds[0].EffectID", 1)
        wrong["group_path"] = "/unrelated"
        doc = self.export(fields + [wrong])
        self.assertIsNone(doc["records"][0]["values"]["InitialDuration"])
        self.assertNotIn("EffectID", doc["records"][0]["values"])
        self.assertEqual(doc["totals"]["untyped_members"], 1)


if __name__ == "__main__":
    unittest.main()
