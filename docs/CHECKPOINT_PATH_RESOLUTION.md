# Checkpoint path resolution

Checkpoint GUID entries encode a path either as a literal string or as an
integer. vrfkit resolves the integer against a checkpoint-local literal path
table. The rule is:

1. Start with an empty table for each checkpoint index.
2. Append each literal path when its GUID entry is read.
3. For an indexed entry, use `name_index` as a zero-based position in the
   literals that appeared earlier in that checkpoint.
4. Do not append indexed entries to the literal table.
5. Register the resolved path in the checkpoint GUID cache. A later entry for
   the same GUID replaces its path and outer-GUID association.

The default checkpoint readers and sink path use
`CheckpointPathMode::LiteralPathTable`. A caller that needs the historical
decimal rendering can explicitly select `CheckpointPathMode::LegacyDecimal`.
The export manifest identifies the default as
`checkpoint_path_resolution_mode = "preceding_literal_zero_based"` and reports
literal, indexed, and resolved-index counts. The CLI prints the same three
counts for every checkpoint export.

`checkpoint_guid_entries.parquet` remains the raw declaration record. Its
`path_is_string`, `literal_path`, `name_index`, `outer_net_guid`, `flags`, and
ordinal are unchanged. `checkpoint_net_guids.parquet` records the final cache,
after last-entry-per-GUID replacement and the checkpoint frame walk.
`checkpoint_blocks.parquet` records paths available to each content block.
Join all three using replay identity and `checkpoint_index`; a checkpoint ID
can repeat, and a main-stream GUID with the same number is a different scope.

## Evidence

The rule was tested on 714 replays across builds 13.01, 13.02, 13.04, and
13.05. An independent Python oracle reconstructed the final 58,509,199-row
checkpoint GUID cache from the original 58,509,199 raw entries and checked
17,251,536 checkpoint blocks. Every file matched. All manifests reported zero
frame-added or frame-exported GUIDs, which makes this raw-entry reconstruction
sufficient for that corpus.

One positive fixture checked last-entry-per-GUID replacement and
checkpoint-local references. Eight negative fixtures changed exported Parquet
or oracle input to represent a wrong base, a cache leak across checkpoints with
the same ID, insertion of a reference into the literal table, a changed raw
index, zero instead of null for an absent outer, a changed block outer path, a
forward reference, or a nonzero frame-added GUID counter. The oracle rejected
all eight. These fixtures test the independent comparison; they do not claim
that eight serializer implementations were run. The six main tables and three
raw checkpoint declaration tables stayed byte-identical across all 714
exports.

This is a measured serialization rule for the supported corpus. A matching
path does not prove a numeric export group is a particular gameplay class, and
the rule has not been matched to an authoritative current upstream serializer.
Future files with an out-of-range index fail checkpoint parsing instead of
silently falling back to decimal text. If a checkpoint frame adds or exports
GUIDs, its final cache also depends on those frame operations; the manifest
counters make that condition visible.

## Measured field expansion

The full 714-replay path-resolution experiment, compared with the
preservation-only output at `740688d`, produced:

| Observation | Increase or resolved count |
|---|---:|
| Indexed GUID path entries resolved | 14,403,610 |
| Blocks with a changed group path or resolution source | 9,441,882 |
| Physical checkpoint field rows | +6,232,453 |
| Rows with at least one typed value | +11,975,340 |
| Rows with a field name | +20,113,218 |
| Previously preserved tails split into a CNC header and raw body | 117,135 |

These are overlapping counts. Existing rows can acquire names and types
without adding a row. The physical row increase equals the increase in
indexed array-child rows; children are additional views of their parent bits.

Checkpoint fields increased from 205,866,627 to 212,099,080 rows, of which
172,491,241 have a non-null value in at least one of the four typed columns.
Main fields remain at 1,010,086,119 rows with 713,488,311 typed rows. Thus typed
presence is 70.6364% main, 81.3258% checkpoint, and 72.4914% combined. This is
neither the fraction of file bytes decoded nor the fraction of gameplay
meaning understood; an earlier semantic classification has not been
reapplied to all expanded output. These coverage figures predate the later
structured-array candidate; see [STRUCTURED_ARRAY_EXPANSION.md](STRUCTURED_ARRAY_EXPANSION.md)
for its measured physical ratios and completed 714-file comparison.

Of 198,461,491 previous raw checkpoint field rows, 198,344,356 retained the
same handle, bit count and raw bytes within the same block. The remaining
117,135 tails were independently partitioned into 2,576,970 header bits and
47,352,050 body bits; each body exactly matched the candidate output. Those
`__vrfkit_chained_cnc_h1__` bodies remain raw. The measured compatible capacity
34 is not a uniquely established declared function count or a body decoder.

For the 7,809,654 blocks with unchanged group paths and resolution sources,
all 189,991,214 field rows matched across every column, comparing valid
floating-point values by their IEEE bits. Signed zero and NaN payloads were
included in the comparator's mutation controls. All six main tables, all
three raw declaration tables and checkpoint actor output stayed byte-identical.
