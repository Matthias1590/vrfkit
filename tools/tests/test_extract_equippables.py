"""Equippable resolver generation preserves measured path aliases."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import extract_equippables  # noqa: E402

REPO = Path(__file__).resolve().parents[2]


OLD_GUARDIAN = "/Game/Equippables/Guns/SniperRifles/Dmr/DMR.DMR_C"
NEW_GUARDIAN = "/Game/Equippables/Guns/SniperRifles/DMR/DMR.DMR_C"


class EquippableGeneratorTests(unittest.TestCase):
    def test_guardian_directory_aliases_are_exact_and_generated(self):
        definitions = [(OLD_GUARDIAN, "Guardian", "rifle")]
        namespace = {}
        exec(extract_equippables.render(definitions, "resolver.cs"), namespace)

        lookup = namespace["EQUIPPABLE_BY_PATH"]
        expected = ("Guardian", "rifle", OLD_GUARDIAN)
        self.assertEqual(lookup[OLD_GUARDIAN], expected)
        self.assertEqual(lookup[NEW_GUARDIAN], expected)
        self.assertEqual(lookup[OLD_GUARDIAN.rpartition(".")[0]], expected)
        self.assertEqual(lookup[NEW_GUARDIAN.rpartition(".")[0]], expected)
        self.assertNotIn(NEW_GUARDIAN.replace("/DMR/", "/dMR/"), lookup)


class ResolverInputTests(unittest.TestCase):
    """The default input used to be an unset environment variable."""

    def test_a_plain_run_reads_the_vendored_resolver_the_header_names(self):
        resolver = extract_equippables.find_resolver(extract_equippables.DEFAULT_CSHARP_ROOT)
        self.assertIsNotNone(resolver)
        self.assertEqual(resolver.relative_to(REPO).as_posix(), extract_equippables.SOURCE_LABEL)

    def test_an_upstream_clone_root_is_accepted_and_an_empty_root_is_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertIsNone(extract_equippables.find_resolver(root))
            upstream = root / "src" / "Replay.Valorant" / extract_equippables.RESOLVER_RELPATH
            upstream.parent.mkdir(parents=True)
            upstream.write_text("", encoding="utf-8")
            self.assertEqual(extract_equippables.find_resolver(root), upstream)


if __name__ == "__main__":
    unittest.main()
