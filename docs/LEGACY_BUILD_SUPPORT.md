# Build support validation, 2026-09-24

**Status: 12.01--12.09 now have verified payload transforms.** All 27 available
replays pass ReplayData validation and checkpoint-enabled export. Builds
11.06--11.11 and 12.00 remain container-only: their acquired executables have
encrypted code sections, and their payload transforms are not recovered.
The original request to support all sixteen builds, and issue #14, are not
fully resolved.

## Native transform recovery and replay results

The implementation following base commit `0d7a798` adds nine transforms and
two compatibility fixes. The containing implementation commit can be resolved
with `git log -1 --format=%H -- crates/vrf-transform/src/versions/v12_01.rs`.

Each executable was imported with Ghidra 12.1.2, using PE runtime-function
records and chained unwind entries to identify complete function boundaries.
The PRNG multiplier, reader object layout and caller argument shape located
the candidate readers. The replay reader was checked independently by
emulating its original x86-64 instructions with Unicorn, including its native
bit-copy helper. No game process was launched. The catalog records the exact
[executable SHA-256 and reader RVA](../tools/fixtures/native_transform_readers.json).
All three 256-byte S-box tables referenced by the applicable readers match
the existing tables byte for byte.

There are 79 native cases per build: the eleven upstream staging boundaries,
36 cases covering six edge seeds at six lengths, and 32 deterministic random
cases up to 512 bits. All **711 expected-byte cases** match Rust, in addition
to the unchanged 88 upstream golden vectors. Reversing one 12.09 rotation's
count makes the native test fail; restoring it passes. The capture tool
verifies executable hashes before emulation and rejects failure to return,
instruction/time exhaustion, or an incorrect reader position.

Two real-corpus failures required fixes beyond the arithmetic:

- 12.01--12.06 call the replay controller `BaseJanusController`. Recognizing
  that exact class consumes its net-player-index byte before framing. Without
  this, the first bunch and checkpoint controller bunches lose data. The new
  pipeline regression fails before the name fix and passes afterward.
- 12.01--12.05 declare `TeamEconomy` members at handles 53--55, rather than
  56--58. Their names and checksums match the later members. The exporter now
  selects by the replay's declaration, including hardcoded FName `241` for
  the IntPacked replication ID. Unknown declarations still fail. The original
  fixed-handle API remains available for compatibility.

| Build | Replays | ReplayData scored blocks | Checkpoint blocks | Main typed overlay |
|---|---:|---:|---:|---:|
| 12.01 | 3 | 1,905,287 | 72,795 | 84.6% |
| 12.02 | 3 | 2,027,973 | 77,588 | 84.2% |
| 12.03 | 3 | 1,944,438 | 74,386 | 84.2% |
| 12.04 | 3 | 2,425,410 | 86,588 | 84.7% |
| 12.05 | 3 | 1,886,622 | 69,916 | 85.0% |
| 12.06 | 3 | 1,642,411 | 58,280 | 84.9% |
| 12.07 | 3 | 1,934,113 | 77,802 | 84.8% |
| 12.08 | 3 | 1,977,496 | 69,130 | 81.2% |
| 12.09 | 3 | 2,170,389 | 74,575 | 81.4% |

Every replay reports **100%** ReplayData oracle success: 17,914,139 scored
blocks in total. All 661,060 checkpoint blocks were walked. Main and checkpoint
passes report zero malformed/framing, transform, field-stream, lost-RPC,
partial-reassembly, typed-overlay and struct-blob failures. Checkpoint
`skipped_bits` is 906 in 12.05 sample-2: six unresolved RPC blocks are retained
whole as raw payloads, rather than lost. All other checkpoint skipped-bit
counters are zero.

The main overlay decoded 23,902,871 offered rows, and the checkpoint overlay
decoded 1,919,133. The percentages above are the main overlay's decoded/offered
ratio, not semantic completeness. Unknown properties, unresolved RPC schema,
and unnamed fields remain explicitly raw, as on previously supported builds.
Independent Python decoding of the existing public-fixture evidence types
matches **410,350 values**, with no missing specification, width failure or
typed mismatch, across all 54 main/checkpoint field tables. A separate direct
bit walk of TeamEconomy matches **7,797 child values from 1,110 parent rows**,
including the 12.01--12.05 nonzero loadout values. Captured regression fixtures pin
the first two 12.01 updates and reject unknown/missing declarations.

Eight previously supported builds were revalidated and re-exported, one replay
each with checkpoints. Their **104 Parquet files are byte-identical** to the
pre-change outputs. This is the full available 27-file sample for 12.01--12.09, not a
claim about every replay ever recorded on these builds.

The committed 13.01 export baseline was stale from the earlier scoped smoke
field additions. Both the pre-change `18a0c60` binary and this implementation
produce the same four differences: 116 more decoded rows, 116 fewer
not-in-table rows, `fields.parquet` growing by 133 bytes to 16,455,178, and its
SHA-256 changing to
`b186a9b50b4f73f1c3a7d8482431732af5413420ba2ca9992c314bc61cb41b93`.
The 116 values are 20 `CreatedByCharacter` GUIDs and 96 `bInPersistentData`
booleans on the previously accepted Smonk/Wushu scopes. Independent Python
IntPacked/Bool decoding matches all of them. No rows or other main tables change.
The baseline and its quoted documentation figures are refreshed for those
already-present values; the 12.01--12.09 support changes introduce no 13.01 drift.
The paired checkpoint baseline additionally gains 48 GUID and 48 Bool values
from those same scopes, all independently matched to raw bits. Its field file
shrinks by 320 bytes to 1,218,992, with SHA-256
`21ce023b9a7c3b67c0d892cc519f50b097a7e97c88d6da93d98ad78cae00806e`.
The archived pre-upstream binary reproduces both original baseline hashes;
column comparison confirms only these previously-null typed cells change.
All rows, raw bytes, names, identities and other columns are identical.

To reproduce, use the acquired binaries and the three pinned source samples
for each build. Native capture needs optional `pefile` and `unicorn` Python
packages; ordinary Rust tests use the committed vectors and need neither.

```powershell
python tools/capture_native_transforms.py --binaries '<binary-root>' --check
cargo +1.86.0 test -p vrf-transform --locked
cargo +1.86.0 build --release -p vrfkit --locked
vrfkit validate '<replay-root>/12.01/sample-1.vrf' --diagnostics
vrfkit export '<replay-root>/12.01/sample-1.vrf' --out '<exports>/12.01/sample-1' --checkpoints
python tools/validate_type_evidence.py '<exports>' tools/fixtures/public_fixture_type_evidence.json --compare-typed
```

Repeat validate/export for samples 1--3 of all nine builds. The same exports
were checked with the required-counter and reconciliation routines from
`check_decode_errors_corpus.py`, alongside the framing/loss counters.

## Replay evidence

The 48 samples are from
[`Matthias1590/unsupported-replays`](https://github.com/Matthias1590/unsupported-replays/tree/c5ba8419b96afa8e88e7afb3e594cf4cce9c75fe):
three per build, 11.06--11.11 and 12.00--12.09. The downloaded `.replay` files
were renamed `.vrf` without changing their bytes. The repository's SHA-256
manifest identifies the source payloads.

Before the fix, `inspect` failed on all 36 samples through 12.05. The first
four builds ran past the end of the header, while larger headers from 11.10
onward reached an invalid level-name count. All twelve samples from
12.06--12.09 already passed inspection but were rejected for missing payload
transforms.

The legacy header places UE4Version directly after the replay branch string:
the next three little-endian u32 values are 522, 1009 and 77. The current
reader instead interpreted 522 as the length of a VALORANT extension. The
extension's length and bytes first appear in the 12.06 samples. Reading it
only outside the twelve measured legacy branches restores the correct
package-version, level-name, game-specific-data and recording-parameter
boundaries. Malformed modern headers are not retried with the legacy layout.

After the fix, all 48 samples pass inspection and the container corpus smoke
test. That smoke test also decompresses the first ReplayData chunk and checks
known Event layouts; it does not decode replication payloads. Synthetic
regressions cover every legacy branch, the 12.06 boundary, zero/nonzero
extensions and rejection of missing modern extensions. The legacy regression
was run against the original reader and failed on the same misplaced length.

## Earlier identity-transform probe

A temporary identity-transform probe was run on `sample-1` from every build.
All sixteen validations failed, with framing oracle rates of only
0.711762%--3.804203%. The experimental registrations were removed. Neither
plaintext passthrough nor merely accepting the branch is a decoding fix.

The upstream parser at
[`2b66c65`](https://github.com/michel-giehl/ValorantReplayParser/tree/2b66c65a7b116154e18ebb84d9f6795f2b080233/src/Replay.Encoding/PayloadEncryption/VersionedTransforms)
has transforms only for the eight previously supported builds.
The additional nine transforms above were recovered from the acquired
game executables listed below. The upstream maintainer describes
locating the transformed reader through `UActorChannel::ReadContentBlockHeader`
in [issue #2](https://github.com/michel-giehl/ValorantReplayParser/issues/2).

Each new transform must come with independent expected-byte vectors, followed
by validation and checkpoint-enabled export of all three available samples
for its build. Frame success alone is not evidence that typed values agree
with the wire.

## Binary analysis feasibility check

The analysis path was exercised on the installed 13.06 executable, without
launching the game or modifying its files. Its SHA-256 is
`8f033b34913a2e16fb6630fe67ac758baf3612e08315b8b74241ed7f5eb537a2`.
Ghidra 12.1.2 headless import and targeted decompilation located a seeded bit
reader at RVA `0x04534320` (VA `0x144534320` at image base `0x140000000`).
Its seed addend `0xe974593c`, initialization offset `0x3c`, PRNG multiplier
`0x2545f4914f6cdd1d` and transform operations match the 13.06 implementation.

For an independent check, Unicorn emulated that original x86-64 function
and its native bit-copy helper directly from the PE image. The Windows x64
arguments were a reader pointer, output pointer and bit count. In this
executable the reader's source pointer, total bits, current bit position and
seed are at offsets `0x98`, `0xa8`, `0xb0` and `0xb8`. Each case reset the
reader and input bytes, used bit position zero, and set the seed to
`bit_count ^ actor_net_guid`. Emulation required return to the caller within
the instruction/time limit before comparing output bytes.

All eleven 13.06 cases from
[`golden_vectors.rs`](../crates/vrf-transform/tests/data/golden_vectors.rs)
matched: 0, 1, 7, 8, 31, 32, 63, 64, 65, 287 and 288 bits. This verifies a
practical way to obtain an independent native-code oracle; it does not add
support for any legacy build. Addresses, reader layouts and algorithms must
be recovered and checked for each executable, not assumed to carry over.

The manifest-link archive
[`Morilli/riot-manifests` at `573d6e7`](https://github.com/Morilli/riot-manifests/tree/573d6e78edc51395a03513800230eab3dbadbf92/VALORANT/na)
contains 29 patch entries covering all sixteen missing builds. These are
links to Riot manifests, not archived game executables. Acquisition was
initially blocked in the measured environment. A browser check of the CDN
hostname's HTTP root displayed an SK Broadband school-network notice stating
that firewall policy blocks the page. DNS resolves several Riot hostnames to
that warning server, whose expired, mismatched certificate caused the HTTPS
failures. The earlier TLS error is therefore evidence of the local network
block, not evidence that Riot's own CDN certificate is invalid or that the
archived files have disappeared.

After the user requested a retry, DNS resolved to Riot's CloudFront endpoint
and certificate-verified HTTPS downloads succeeded. All sixteen executables
below were acquired from the latest recorded patch for each replay branch.
Only `ShooterGame/Binaries/Win64/VALORANT-Win64-Shipping.exe` was selected;
the installed game was not replaced or launched. Every downloaded file:

- Passed `ManifestDownloader --verify-only` against its RMAN chunk hashes.
- Contained its expected `++Ares-Core+release-<build>` branch label.
- Had a valid Windows Authenticode signature from `Riot Games, Inc.`.
- Was recorded with its SHA-256, manifest ID/hash, source URL and archive
  commit in the local acquisition catalog.

| Replay build | Acquired patch | Executable bytes |
|---|---|---:|
| 11.06 | 11.06.00.3836880 | 201,181,352 |
| 11.07 | 11.07.00.3855133 | 201,408,608 |
| 11.08 | 11.08.00.3918089 | 202,602,752 |
| 11.09 | 11.09.00.3920876 | 203,230,824 |
| 11.10 | 11.10.00.4002057 | 202,949,848 |
| 11.11 | 11.11.00.4091853 | 208,825,552 |
| 12.00 | 12.00.00.4183428 | 208,267,728 |
| 12.01 | 12.01.00.4211771 | 208,325,576 |
| 12.02 | 12.02.00.4226954 | 210,556,856 |
| 12.03 | 12.03.00.4322591 | 210,990,720 |
| 12.04 | 12.04.00.4354757 | 212,279,904 |
| 12.05 | 12.05.00.4440267 | 213,755,024 |
| 12.06 | 12.06.00.4440219 | 214,659,936 |
| 12.07 | 12.07.00.4488404 | 214,767,368 |
| 12.08 | 12.08.00.4578383 | 214,750,840 |
| 12.09 | 12.09.00.4704114 | 184,074,872 |

The selected manifest file sizes sum to **3,312,627,760 bytes** (3.313 GB,
3.085 GiB). The sixteen RMAN files add 148,679,917 bytes. Summing the compressed
chunks referenced by those executables gives 1,688,334,507 bytes, or
**1,837,014,424 bytes** including manifests for the nominal download payload;
HTTP/TLS overhead and retries are not measured by that figure. Generated
metadata and future Ghidra databases need additional space.

Executable acquisition is complete. The seven 11.06--12.00 executables have
high-entropy encrypted `.text` data, no plaintext PRNG-multiplier references,
a NOP entry point and an imported `stub.dll!packman`. The separately acquired
11.06 `stub.dll` is itself packed/virtualized: its exported `packman` address
has no on-disk code, and its entry point enters the protected stub section.
These files do not yet provide a callable native reader for the oracle.

This matches the mechanism described in the first-hand
[Packman analysis](https://hypercall.net/posts/Packman/): the loader prepares
and decrypts code at runtime. The public
[ValorantUnpacker](https://github.com/nitrog0d/ValorantUnpacker) implementation
was also inspected; it reads a running game through an injected DLL, rather
than supplying an offline decryption algorithm. It was not executed.

Completing these seven builds still requires their correctly decrypted reader
code, a matching executable memory dump, or recovery of the protected loader's
offline decryption. No verified source of those matching dumps or usable
offline unpacker was found in this investigation. Merely downloading each
protected executable again does not resolve that dependency. The installed
game and Vanguard configuration were left unchanged, and these seven branches
continue to fail closed for payload decoding.

## Regression scope and commands

Eight previously supported builds were checked before and after this change:
12.10, 12.11, 13.00, 13.01, 13.02, 13.04, 13.05 and 13.06, one replay each.
All validations and checkpoint-enabled exports passed. All 104 Parquet files
(13 per replay) were byte-identical between the two binaries.

The baseline binary was built from `18a0c607ff85cbd7cc785210dbc9add1d6e6e166`.
To repeat the legacy container checks, set `VRFKIT_CORPUS_DIR` to one build's
directory and require that it exists:

```powershell
$env:VRFKIT_CORPUS_DIR = '<replay-root>/11.06'
$env:VRFKIT_REQUIRE_CORPUS = '1'
cargo +1.86.0 test -p vrf-container --test corpus parse_all_vrf_files --locked -- --exact --nocapture
vrfkit inspect '<replay-root>/11.06/sample-1.vrf' --redact-identifiers
vrfkit validate '<replay-root>/11.06/sample-1.vrf' # expected: unsupported branch
```

Repeat for every affected directory. For the supported-build comparison, run
both binaries on the same replay with `validate` and
`export <replay> --out <separate-directory> --checkpoints`, then compare the
SHA-256 of each output Parquet file. Replay bytes and local export bundles are
not committed.
