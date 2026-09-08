# KillData serialized observations

`tools/extract_kill_observations.py` converts the measured `KillData` array rows in one export into a versioned JSON observation stream:

Use an export generated with `--checkpoints`; the tool reads both main and
checkpoint field, declaration and reference tables.

```powershell
python tools/extract_kill_observations.py --export out/nested --out out/kill-observations.json
```

These records are serialized element updates. They are not a deduplicated kill ledger. A replay can repeat a payload, send more than one element in a parent array, or send a partial element containing only `bDidKillTriggerFinisher`. Missing fields therefore remain JSON `null`/absent and are never copied from another record.

Each observation is identified by its source table, checkpoint identity when applicable, physical `KillData` parent-row ordinal, and array element index. It retains packet/object coordinates, a parent-raw digest, exact member raw windows, and the serialized values currently measured for victim, equippable class, weapon theme, assisting players, damage type/value/region, game time, round timestamp/number, and finisher flag.

`time_ms`, `GameTimeElapsed`, and `RoundTimestamp` are separate source values. The tool does not convert one into another or claim gameplay units. Names such as `Victim` and `DamageTaken` are replay declarations; the extractor does not infer attribution, ordering, credit rules, or action semantics from them.

References keep their numeric identifier and scoped resolution status. Victim and assisting-player references are checked against the matching main or checkpoint actor table. Other references are checked against the corresponding NetGUID table; unresolved identifiers remain in the output.

The extractor fails when declarations differ from the measured group/name/checksum identities, array framing is incomplete, a nested handle is unexpected, a typed child differs from its raw window, child coordinates cross scopes, or emitted children are not physically adjacent to their parent. It records the manifest, input Parquet, and extractor SHA-256 values under `provenance`.

Output uses schema version 1 and top-level kind `vrfkit_killdata_observation_export`. Consumers should reject unsupported schema versions.

For component-local base/revision state and explicit links to character-death
events, use the [kill ledger command](KILL_LEDGER.md). It retains this original
observation stream and keeps unmatched records visible.
