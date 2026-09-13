"""Compare RPC parameter values between our Rust Parquet and the C# NDJSON export.

Validates multiset equality for key RPC functions:
  - MulticastNotifyKilledEnemy: KillerCharacter, KilledCharacter, MultikillLevel
  - MulticastNotifyDamage_Point: DamageDealt, DamageTaken, RegionalDamage, bDamageKilledTarget
  - MulticastEndRound: NewRoundNumber

Records are compared as multisets of values, not by position or time.

The C# side is CliReader's `export` of the 13.01 reference replay,
kept machine-local because it carries per-player values; docs/USAGE.md section
6 has the commands that produce it. It used to be a slimmed C# export under
valplay's pipeline/exports, which no longer holds it -- and valplay now builds
its bundles from vrfkit's own output, so that path would not be an independent
reference any more.

Usage:
    python tools/compare_rpc_params.py [--reference EVENTS] [--ours PARQUET]
"""

import argparse
import collections
import json
import os
import sys
from pathlib import Path

import pyarrow.parquet as pq

#: The rpc_received lines for the functions below, from CliReader's export of
#: replay 02d4d478, built from ValorantReplayParser 8824794 (the commit
#: vendored in third_party/vrp). The whole events.ndjson works too; other
#: lines are skipped.
DEFAULT_REFERENCE = (r"%LOCALAPPDATA%\vrfkit\csharp-reference\8824794"
                     r"\02d4d478-1dfb-4412-9a77-29ca29105a9d\rpc_params.ndjson")
#: vrfkit's export of the same replay.
DEFAULT_OURS = "out/nested/fields.parquet"

# RPC functions and the parameters to compare.
# For each function: list of (param_name, value_type) where value_type is how
# the C# JSON stores it ('int', 'float', 'bool', 'str').
# Special: 'enum_byte' means the C# stores as string but Rust stores as i64.
RPCS_TO_CHECK = {
    "MulticastNotifyKilledEnemy": [
        ("KillerCharacter", "int"),
        ("KilledCharacter", "int"),
        ("MultikillLevel", "int"),
    ],
    "MulticastNotifyDamage_Point": [
        ("DamageDealt", "float"),
        ("DamageTaken", "float"),
        ("RegionalDamage", "enum_byte"),
        ("bDamageKilledTarget", "bool"),
    ],
    "MulticastEndRound": [
        ("NewRoundNumber", "int"),
    ],
}

# Mapping from C# EAresRegionalDamage enum strings to byte values.
# Derived from the C# enum declaration and confirmed against wire data.
REGIONAL_DAMAGE_MAP = {
    "regional_damage__normal": 0,
    "regional_damage__headshot": 1,
    "regional_damage__legshot": 2,
    "regional_damage__utility": 3,
    "regional_damage__armor": 4,
    "regional_damage__invalid": 5,
}

# C# field name aliases: the C# export may use different names than the replay
# schema exports (e.g. "DamageKilledTarget" in JSON payload vs
# "bDamageKilledTarget" in the export group field name table).
CS_FIELD_ALIASES = {
    "MulticastNotifyDamage_Point": {
        "DamageKilledTarget": "bDamageKilledTarget",
    },
}


#: Decimal places float parameters are rounded to before comparison. `MATCH`
#: means equal to this precision and no further, so the verdict line states it
#: rather than leaving it buried here. (`compare_combat_report.py` uses 3 for
#: the same job; neither number was written down anywhere the reader sees.)
FLOAT_PLACES = 2


def norm(v, vtype):
    """Normalise a value for multiset comparison."""
    if v is None:
        return None
    if vtype == "int":
        return int(v)
    if vtype == "float":
        return round(float(v), FLOAT_PLACES)
    if vtype == "bool":
        return 1 if v else 0
    if vtype == "enum_byte":
        # If the value is a string (C# side), map to int via known enum table.
        if isinstance(v, str):
            return REGIONAL_DAMAGE_MAP.get(v, v)
        return int(v)
    return str(v)


def load_cs_rpc_values(path):
    """Load RPC parameter values from C# NDJSON export."""
    result = {}  # (function_name, param_name) -> Counter of values
    for func_name, params in RPCS_TO_CHECK.items():
        for pname, _ in params:
            result[(func_name, pname)] = collections.Counter()

    aliases = CS_FIELD_ALIASES

    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            if "rpc_received" not in line:
                continue
            rec = json.loads(line)
            if rec.get("type") != "rpc_received":
                continue
            func = rec.get("function_name", "")
            if func not in RPCS_TO_CHECK:
                continue
            payload = rec.get("payload", {})
            if not payload:
                continue
            func_aliases = aliases.get(func, {})
            for pname, vtype in RPCS_TO_CHECK[func]:
                # Try the canonical name first, then check aliases
                val = payload.get(pname)
                if val is None:
                    # Try reverse alias lookup
                    for cs_name, our_name in func_aliases.items():
                        if our_name == pname:
                            val = payload.get(cs_name)
                            break
                if val is not None:
                    result[(func, pname)][norm(val, vtype)] += 1

    return result


def load_rust_rpc_values(path):
    """Load RPC parameter values from Rust Parquet export."""
    result = {}  # (function_name, param_name) -> Counter of values
    for func_name, params in RPCS_TO_CHECK.items():
        for pname, _ in params:
            result[(func_name, pname)] = collections.Counter()

    t = pq.read_table(str(path))
    fn_col = t.column("field_name").to_pylist()
    vi_col = t.column("value_i64").to_pylist()
    vf_col = t.column("value_f64").to_pylist()
    vb_col = t.column("value_bool").to_pylist()
    vs_col = t.column("value_str").to_pylist()

    for i, field_name in enumerate(fn_col):
        if not field_name or "." not in field_name:
            continue
        dot = field_name.index(".")
        func = field_name[:dot]
        param = field_name[dot + 1:]
        if func not in RPCS_TO_CHECK:
            continue

        # Find the matching param entry
        for pname, vtype in RPCS_TO_CHECK[func]:
            if param != pname:
                continue
            # Get the value from the appropriate column
            if vtype in ("int", "enum_byte"):
                val = vi_col[i]
            elif vtype == "float":
                val = vf_col[i]
            elif vtype == "bool":
                val = vb_col[i]
            else:
                val = vs_col[i]
            if val is not None:
                result[(func, pname)][norm(val, vtype)] += 1
            break

    return result


def compare(cs, rust, rpcs=None):
    """`(printable rows, everything matched, how many were compared)`.

    Split out of `main` so the verdict can be asserted on -- it could not be
    before, which is the same shape `compare_combat_report.py` had.

    Emptiness is tested BEFORE equality. Two empty Counters satisfy
    `cs_vals == rust_vals`, so the `both empty` arm sat below it and could
    never be reached: every parameter of a replay carrying none of these RPCs
    reported `MATCH`. The third return value is what stops that reading as a
    result -- `all_match` stays True for an empty pair, because per parameter
    that is not a disagreement; it is simply not a comparison.
    """
    rows, all_match, checked = [], True, 0
    for func_name, params in (rpcs or RPCS_TO_CHECK).items():
        for pname, _vtype in params:
            key = (func_name, pname)
            cs_vals = cs.get(key, collections.Counter())
            rust_vals = rust.get(key, collections.Counter())

            cs_total = sum(cs_vals.values())
            rust_total = sum(rust_vals.values())

            if not cs_vals and not rust_vals:
                verdict = "both empty -- nothing compared"
            elif cs_vals == rust_vals:
                verdict = "MATCH"
                checked += 1
            else:
                extra_rust = sum((rust_vals - cs_vals).values())
                extra_cs = sum((cs_vals - rust_vals).values())
                verdict = f"DIFFER (+{extra_rust} rust / +{extra_cs} C#)"
                all_match = False
                checked += 1

            rows.append(f"{func_name:<35} {pname:<25} {cs_total:>5} "
                        f"{rust_total:>5}  {verdict}")
    return rows, all_match, checked


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reference", default=DEFAULT_REFERENCE,
                        help="C# export events.ndjson, or its rpc_received lines "
                             "(default: %(default)s)")
    parser.add_argument("--ours", default=DEFAULT_OURS,
                        help="vrfkit fields.parquet of the same replay "
                             "(default: %(default)s)")
    return parser.parse_args(argv)


def main(cs=None, rust=None, rpcs=None, argv=None):
    """Exit 0 only if every parameter matches and every one was there.

    A run in which any parameter carried nothing on either side exits 2: that
    parameter was not compared, and a run that compared nothing at all used to
    print `ALL RPC PARAMETER VALUES MATCH`. Every parameter is present in the
    reference replay.
    """
    if cs is None or rust is None:
        args = parse_args(argv)
        reference = Path(os.path.expandvars(args.reference))
        if cs is None and not reference.is_file():
            print(f"C# reference not found at {reference}; produce it with the "
                  f"commands in docs/USAGE.md section 6, or pass --reference",
                  file=sys.stderr)
            return 2
        if rust is None and not Path(args.ours).is_file():
            print(f"vrfkit fields.parquet not found at {args.ours}; export the "
                  f"same replay, or pass --ours", file=sys.stderr)
            return 2
        print(f"C# source: {reference}")
        print(f"Rust source: {args.ours}")
        print()
        cs = load_cs_rpc_values(reference) if cs is None else cs
        rust = load_rust_rpc_values(args.ours) if rust is None else rust

    checked_rpcs = rpcs or RPCS_TO_CHECK
    rows, all_match, checked = compare(cs, rust, checked_rpcs)

    print(f"{'Function':<35} {'Param':<25} {'C#':>5} {'Rust':>5}  Verdict")
    print("-" * 100)
    for row in rows:
        print(row)

    print()
    total = sum(len(params) for params in checked_rpcs.values())
    if all_match and checked < total:
        print(f"INCOMPLETE: {total - checked} of the {total} RPC parameters "
              f"carry no value on either side, so they were not compared. This "
              f"is not agreement -- check the parquet path and the reference.")
        return 2
    if all_match:
        print(f"ALL {checked} RPC PARAMETER VALUES MATCH "
              f"(floats to {FLOAT_PLACES} decimal places)")
    else:
        print("SOME VALUES DIFFER -- see above")

    # Print sample values for verification
    print()
    print("=== Sample values (first 5 per function) ===")
    for func_name, params in checked_rpcs.items():
        pname0, _vtype0 = params[0]
        key = (func_name, pname0)
        cs_sample = list(cs.get(key, collections.Counter()).most_common(5))
        rust_sample = list(rust.get(key, collections.Counter()).most_common(5))
        print(f"\n{func_name}.{pname0}:")
        print(f"  C#:   {cs_sample}")
        print(f"  Rust: {rust_sample}")

    return 0 if all_match else 1


if __name__ == "__main__":
    raise SystemExit(main(argv=sys.argv[1:]))
