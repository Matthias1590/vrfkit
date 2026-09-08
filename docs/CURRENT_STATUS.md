# Current status

Status at vrfkit `14e58e52e8f412927c6bde1909abd89e38f5d2b6`, validated
2026-09-09. Start with [DATA.md](DATA.md) for the current exported schema and
[USAGE.md](USAGE.md) for commands and validation procedures.

## Current measured field inventory

The accepted 714-replay inventory reports:

| Table | Physical rows | Rows with a typed value |
|---|---:|---:|
| Main `fields` | 1,020,577,224 | 726,993,845 |
| `checkpoint_fields` | 285,420,158 | 220,648,387 |
| Combined | 1,305,997,382 | 947,642,232 |

The combined typed-value presence is 72.5608%. This counts physical rows with
at least one non-null typed value column. It is not semantic coverage, gameplay
accuracy, or a percentage of known field meanings. Earlier percentages in
phase documents are dated measurements of earlier parser states and remain
historical.

The current untyped-row inventory includes named properties and whole RPC payloads
without an accepted type, anonymous or checksum-unresolved fields, structured
or nested raw parents whose synthesized children may be only partly
understood, and decoded movement rows whose input bytes are not duplicated in
`raw_bits`. These categories need separate evidence and denominators; they
must not be collapsed into one
semantic backlog percentage.

Across the two field tables, the inventory contains 36,839 table/group/field/
checksum/build catalog keys. It records 187,106,485 untyped rows with preserved
raw payloads, 3,075,937 zero-bit markers, and zero preserved rows with a wrong
raw length. The 168,172,728 nonempty untyped rows without duplicated `raw_bits`
are all on the decoded movement route. These are transport and catalog counts,
not counts of distinct gameplay facts or meanings.

The measured starting point for follow-up work is
[CURRENT_RAW_BACKLOG.md](CURRENT_RAW_BACKLOG.md). Its ranked populations are an
investigation inventory, not a completed semantic partition or a claim that
each catalog key is one distinct field meaning.

## Completed evidence phases

The main completed phases are recorded in
[TRANSPORT_PRESERVATION.md](TRANSPORT_PRESERVATION.md),
[PARTIAL_HEADER_CORRECTION.md](PARTIAL_HEADER_CORRECTION.md),
[CHECKPOINT_SCHEMA_PRESERVATION.md](CHECKPOINT_SCHEMA_PRESERVATION.md),
[CHECKPOINT_PATH_RESOLUTION.md](CHECKPOINT_PATH_RESOLUTION.md),
[STRUCTURED_ARRAY_EXPANSION.md](STRUCTURED_ARRAY_EXPANSION.md),
[NESTED_ARRAY_REFERENCES.md](NESTED_ARRAY_REFERENCES.md),
[TEXT_HISTORY_EXPANSION.md](TEXT_HISTORY_EXPANSION.md),
[REFERENCE_VALUE_EXPANSION.md](REFERENCE_VALUE_EXPANSION.md),
[TARGETING_AND_HEAL_VALUES.md](TARGETING_AND_HEAL_VALUES.md),
[HEALING_OBSERVATIONS.md](HEALING_OBSERVATIONS.md),
[KILL_OBSERVATIONS.md](KILL_OBSERVATIONS.md),
[KILL_LEDGER.md](KILL_LEDGER.md),
[SECTION_OBSERVATIONS.md](SECTION_OBSERVATIONS.md),
[SECTION_TIMELINE.md](SECTION_TIMELINE.md), and
[SECTION_PACKET_TIMELINE.md](SECTION_PACKET_TIMELINE.md). Each document states
its own evidence boundary; derived section and kill views do not prove game HP,
healing attribution, damage attribution, causality, or player credit.

The parser acceptance commit for the physical field counts was `fc50bfe`.
Later derived-view commits through `14e58e5` do not change those counts. The
dated validation at `14e58e5` passed 692 Rust tests and 786 Python tests. Test
counts describe that validation run and are not a permanent compatibility
guarantee.
