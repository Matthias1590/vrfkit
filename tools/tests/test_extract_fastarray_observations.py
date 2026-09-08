"""Wire boundaries and preserved failure evidence for numeric FastArray updates."""
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

import pyarrow as pa
import pyarrow.parquet as pq

from tools import extract_fastarray_observations as fast


def packed(value):
    out = bytearray()
    while True:
        next_value = value >> 7
        out.append(((value & 127) << 1) | bool(next_value))
        if not next_value:
            return bytes(out)
        value = next_value


def payload(deleted=(), changed=(), keys=(8, 5)):
    body = bytearray(struct.pack("<iiii", *keys, len(deleted), len(changed)))
    for ident in deleted:
        body += struct.pack("<i", ident)
    for ident, fields in changed:
        body += struct.pack("<i", ident)
        for handle, raw in fields:
            body += packed(handle + 1) + packed(len(raw) * 8) + raw
        body += b"\0"
    # Shift the byte-aligned body to insert its single leading support bit.
    return (1 | (int.from_bytes(body, "little") << 1)).to_bytes(len(body) + 1, "little"), len(body) * 8 + 1


class FastArrayTests(unittest.TestCase):
    def test_changed_fields_and_deleted_ids_exact_raw_offsets(self):
        raw, count = payload([1, -3], [(5, [(0, b"\x96\xab"), (18, b""), (130, b"\xfe")])])
        result = fast.decode(raw, count)
        self.assertEqual(result["deleted_item_ids"], [1, -3])
        self.assertEqual((result["array_replication_key"], result["base_replication_key"]), (8, 5))
        self.assertEqual(result["consumed_bits"], count)
        item = result["changed_items"][0]
        self.assertEqual(item["item_id"], 5)
        self.assertEqual([f["handle"] for f in item["fields"]], [0, 18, 130])
        decoded = [(int.from_bytes(raw, "little") >> f["bit_offset"]) & ((1 << f["bit_count"]) - 1) for f in item["fields"]]
        self.assertEqual(decoded, [0xab96, 0, 254])
        self.assertEqual([f["bit_count"] for f in item["fields"]], [16, 0, 8])

    def test_deletion_only_and_signed_keys(self):
        raw, count = payload([1, 3], keys=(-1, -2))
        result = fast.decode(raw, count)
        self.assertEqual(result["array_replication_key"], -1)
        self.assertEqual(result["deleted_item_ids"], [1, 3])
        self.assertEqual(result["changed_items"], [])

    def test_each_truncation_is_rejected(self):
        raw, count = payload([1], [(3, [(2, b"\x81\x12")])])
        for width in range(count):
            with self.subTest(width=width), self.assertRaises(fast.WireError):
                fast.decode(raw[:(width + 7) // 8], width)

    def test_suffix_and_count_mutations_are_rejected(self):
        raw, count = payload([1, 3])
        with self.assertRaisesRegex(fast.WireError, "unconsumed_suffix"):
            fast.decode(raw, count + 1)
        bits = int.from_bytes(raw, "little")
        # Replace NumDeletes (bits 65..96) with -1 or an impossible positive.
        for value, reason in [(0xffffffff, "negative_count"), (0x7fffffff, "count_bounds")]:
            altered = ((bits & ~(0xffffffff << 65)) | (value << 65)).to_bytes(len(raw), "little")
            with self.assertRaisesRegex(fast.WireError, reason):
                fast.decode(altered, count)

    def test_unreal_packed_overflow_and_termination(self):
        self.assertEqual(fast.Bits(bytes.fromhex("ffffffff1e"), 40).packed(), 0xffffffff)
        self.assertEqual(fast.Bits(bytes.fromhex("171e"), 16).packed(), 1931)
        for raw, reason in [("ffffffff20", "packed_overflow"), ("0101010101", "packed_unterminated")]:
            with self.assertRaisesRegex(fast.WireError, reason):
                fast.Bits(bytes.fromhex(raw), 40).packed()

    def test_unknown_support_mode_and_bad_window(self):
        raw, count = payload()
        with self.assertRaisesRegex(fast.WireError, "unsupported_support_bit"):
            fast.decode(bytes([raw[0] & 254]) + raw[1:], count)
        for bad, size in [(None, count), (raw[:-1], count), (raw, -1)]:
            with self.assertRaises(fast.WireError):
                fast.decode(bad, size)

    def test_identity_and_unvalidated_context_stay_raw(self):
        raw, count = payload([1, 3])
        row = {"group_path": fast.GROUP, "field_name": "_cnc_h1", "handle": 1,
               "raw_bits": raw, "bit_count": count}
        for population, build, handle, reason in [
            ("fields", "future", 1, "unvalidated_build"),
            ("checkpoint_fields", "++Ares-Core+release-13.05", 1, "unvalidated_checkpoint_route"),
            ("fields", "++Ares-Core+release-13.05", 2, "route_identity")]:
            record = fast.observation(dict(row, handle=handle), 27, population, build)
            self.assertEqual(record["status"], reason)
            self.assertEqual(record["raw_bits_hex"], raw.hex())
            self.assertEqual(record["physical_row_ordinal"], 27)
            self.assertIsNone(record["structure"])

    def make_export(self, root, malformed=False):
        source = root / "export"
        source.mkdir()
        (source / "manifest.json").write_text(json.dumps({"replay_build": "++Ares-Core+release-13.05"}))
        raw, count = payload([1, 3])
        row = {name: 0 for name in fast.COLUMNS}
        row.update(group_path=fast.GROUP, field_name="_cnc_h1", handle=1,
                   raw_bits=raw, bit_count=count + int(malformed))
        unrelated = dict(row, group_path="unrelated")
        table = pa.Table.from_pylist([unrelated, row])
        pq.write_table(table, source / "fields.parquet")
        cp = table.slice(0, 0).append_column("checkpoint_index", pa.array([], type=pa.int64())).append_column("checkpoint_id", pa.array([], type=pa.int64()))
        pq.write_table(cp, source / "checkpoint_fields.parquet")
        return source

    def test_cli_artifact_receipts_and_physical_ordinal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = self.make_export(root); out = root / "result"
            receipt = fast.extract(source, out)
            self.assertEqual(receipt["counts"]["structural_exact"], 1)
            self.assertEqual(receipt["counts"]["rejected"], 0)
            self.assertEqual(receipt["input_sha256_before"], receipt["input_sha256_after"])
            self.assertEqual(receipt["observations_sha256"], fast.sha(out / "observations.ndjson"))
            record = json.loads((out / "observations.ndjson").read_text())
            self.assertEqual(record["physical_row_ordinal"], 1)
            self.assertEqual(record["structure"]["deleted_item_ids"], [1, 3])
            with self.assertRaisesRegex(ValueError, "already exists"):
                fast.extract(source, out)
            with self.assertRaisesRegex(ValueError, "outside"):
                fast.extract(source, source / "forbidden")

    def test_cli_rejections_retained_and_nonzero_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = self.make_export(root, malformed=True); out = root / "result"
            with patch.object(fast.sys, "argv", ["extract", "--export-dir", str(source), "--out-dir", str(out)]):
                self.assertEqual(fast.main(), 1)
            receipt = json.loads((out / "receipt.json").read_text())
            self.assertEqual(receipt["counts"]["rejected"], 1)
            record = json.loads((out / "observations.ndjson").read_text())
            self.assertEqual(record["status"], "unconsumed_suffix")
            self.assertIsNotNone(record["raw_bits_hex"])

    def test_changed_input_does_not_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = self.make_export(root); out = root / "result"
            original = fast.selected_rows
            def alter(path, checkpoint):
                yield from original(path, checkpoint)
                if checkpoint:
                    with (source / "manifest.json").open("a") as handle:
                        handle.write(" ")
            with patch.object(fast, "selected_rows", alter), self.assertRaisesRegex(ValueError, "changed during read"):
                fast.extract(source, out)
            self.assertFalse(out.exists())
            self.assertEqual(list(root.glob(".fastarray-*")), [])


if __name__ == "__main__":
    unittest.main()
