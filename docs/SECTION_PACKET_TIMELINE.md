# Packet-ordered section observations

`tools/extract_section_packet_timeline.py` adds a packet-order view to the
serialized section timeline described in [SECTION_TIMELINE.md](SECTION_TIMELINE.md).
It reads an export directly and includes the strict timeline in its output.
The packet view is an additional observation-order policy, not a measurement
of effective player HP or proof of game/component lifetime.

```sh
python tools/extract_section_packet_timeline.py --export /path/to/export --out /path/to/packet-timeline.json
```

The strict node values, source rows, predecessors, epochs, lifecycle evidence,
continuity decisions, barriers, warnings and original counts are retained.
Each node adds `packet_view`; separate summaries expose strict and packet
eligibility and arithmetic outcomes. `packet_provenance` records the consumed
inputs and all transitive implementation helpers before and after extraction.

## What the additional ordering resolves

Main-stream field records and actor lifecycle records use the same packet
counter. Distinct, increasing packets can order observations that share one
millisecond timestamp. Both endpoints must resolve to the same complete actor
and channel open record. Same-packet boundaries remain unordered.

The resolver validates the entire relevant actor and channel lifecycle traces.
Duplicate or regressing packet clocks, unmatched closes, reopens without a
close, channel ownership conflicts and unresolved endpoints prevent a link.
Section observations sharing a packet remain ambiguous even when their
millisecond timestamps differ; a tied predecessor also prevents a link.
Dormancy is not interpreted as destruction.

Checkpoint packet IDs have a separate counter and can overlap main IDs. This
view uses main observations and main actor events only. It does not splice
checkpoint records into the main packet sequence.

Other strict barriers remain in force, including actor/object and scope
changes, resets on incoming edges, malformed or ambiguous observations, and
missing or changed opaque tokens. Packet order does not supply missing state
updates or give opaque tokens a gameplay meaning.

## Arithmetic is separate from eligibility

The output retains the strict route arithmetic, including disagreements.
Both summaries report true, false and unknown outcomes with explicit zeros,
including those among eligible comparisons. An ordered pair can still fail
the tested arithmetic hypothesis. Values are never rounded or corrected to
force a match.

In particular, the accepted strict corpus contains thirteen eligible
OverhealDecay comparisons whose recorded result is zero while one-step f32
subtraction leaves a small positive residual. A packet view must retain those
raw values and disagreements. It does not establish a clamp or rounding rule.

Validated over 714 retained exports on builds 13.01, 13.02, 13.04 and
13.05. An independent interval-index reader agrees with every public packet
view field and complete node identity. All strict values, source references,
predecessors, epochs, barriers, warnings and eligibility decisions are retained.

| Measurement | Count |
|---|---:|
| Original strict section states | 4,153,928 |
| Strict eligible comparisons | 1,874,166 |
| Packet eligible comparisons | 1,892,315 |
| Newly eligible comparisons | 18,149 |
| Previously eligible comparisons lost in the packet view | 0 |
| Packet-ineligible states | 2,261,613 |
| Packet-eligible arithmetic matches | 1,892,300 |
| Packet-eligible arithmetic disagreements | 15 |
| Packet-eligible arithmetic unknown | 0 |

The original 1,635 barriers and 46 scalar-relation warnings remain separate.
The fifteen eligible disagreements include the thirteen strict-view cases
described above and two newly ordered comparisons. Both new cases end at zero
one packet after their predecessor in the same millisecond. Their one-step f32
subtraction residuals are 9.5367431640625e-07 and 2.09808349609375e-05. This is a
descriptive pattern, not evidence for a clamp, rounding location or game mechanic.

These are section-observation counts. They are not a new percentage of replay
data whose gameplay meaning has been established.
