//! Event chunk parser.
//!
//! An Event chunk carries one entry from the server's own labelled game
//! timeline: a round start, a character death, a spike plant. It is the only
//! place in the file where the server names what happened -- everything else
//! has to be reconstructed from replicated properties and RPCs.
//!
//! # Wire layout
//!
//! | Offset | Type | Field |
//! |--------|------|-------|
//! | 0 | FString | Id |
//! | ... | FString | Group |
//! | ... | FString | Metadata |
//! | ... | u32 | Time1 |
//! | ... | u32 | Time2 |
//! | ... | i32 | SizeInBytes |
//! | ... | [u8; SizeInBytes] | payload |
//!
//! Measured over 527 replays from releases 13.01, 13.02 and 13.04 (109,126
//! Event chunks): every chunk is consumed exactly by this layout with no bytes
//! left over, and Time1 always equals Time2. Checkpoint chunks open with the
//! same six fields, so the framing is not Event-specific; this module parses
//! Event chunks only.
//!
//! # Structural payload view
//!
//! The `SizeInBytes` payload has an observable shape:
//!
//! ```text
//! [u32 group tag][N x u32 words][FString "EReplayEventGroup::<Name>"][f32 seconds]
//! ```
//!
//! but it is not self-describing. `N` varies by group (0 for SpikePlanted, 1
//! for RoundStart, 2 for CharacterDeath) and no count precedes the words, so a
//! forward read cannot tell where they end. For the seven known groups, a
//! fixed `N`, tag and public enum-name FString consumed all 109,126 payloads
//! exactly across the three measured builds. That remains corpus evidence, not
//! a self-describing format guarantee. [`parse_event_payload`] therefore
//! requires the caller to supply an already-established `N`; the guarded
//! [`parse_known_event_payload`] additionally requires the measured tag and
//! name. The original payload is still handed to the caller byte for byte, and
//! `trailing_bytes` reports anything the outer chunk layout does not account
//! for rather than dropping it silently.

use vrf_bitio::BitReader;

use crate::error::ContainerError;
use crate::limits::MAX_FSTRING_BYTES;

/// A parsed Event chunk: the six header fields plus its raw payload.
///
/// `payload` borrows the chunk bytes; nothing is copied.
#[derive(Debug, Clone)]
pub struct EventChunk<'a> {
    /// Server-assigned event id, `<replay-guid>_<32 hex digits>` in every
    /// corpus file. Emitted as the wire gives it; no structure is assumed.
    pub id: String,
    /// Event group, e.g. `characterDeath`, `roundStarted`, `spikePlanted`.
    pub group: String,
    /// Free-form metadata string. Frequently empty; empty is what the wire
    /// says, not a missing value.
    pub metadata: String,
    /// First timestamp in milliseconds.
    pub time1: u32,
    /// Second timestamp in milliseconds. Equal to `time1` in every corpus file,
    /// but both are reported because the format keeps them separate.
    pub time2: u32,
    /// Declared payload size. Validated non-negative and within the chunk.
    pub size_in_bytes: i32,
    /// The payload bytes, exactly `size_in_bytes` of them.
    pub payload: &'a [u8],
    /// Bytes after the payload that this layout does not account for. Zero for
    /// all 109,126 corpus chunks; reported so a format change is counted
    /// rather than discarded in silence.
    pub trailing_bytes: usize,
}

/// The values whose wire types are structural once a group's word count is
/// known.
///
/// The `words` remain deliberately unnamed: only a subset of Event groups has
/// evidence for what each word means. `name` and `seconds` are likewise named
/// after their wire types rather than assigned game semantics.
#[derive(Debug, Clone, PartialEq)]
pub struct EventPayload {
    /// Leading group tag.
    pub tag: u32,
    /// The caller-established number of group-dependent words.
    pub words: Vec<u32>,
    /// FString following the group-dependent words.
    pub name: String,
    /// Trailing single-precision seconds value.
    pub seconds: f32,
}

/// Return the corpus-established group-dependent word count for an Event
/// group.
///
/// An unknown group returns `None`, not zero: zero is a measured layout for the
/// spike groups, while `None` means no structural claim can yet be made.
#[must_use]
pub const fn known_event_word_count(group: &str) -> Option<usize> {
    match group.as_bytes() {
        b"characterDeath" => Some(2),
        b"characterUltimateUsed" | b"roundStarted" | b"switchTeams" => Some(1),
        b"spikePlanted" | b"spikeDefused" | b"spikeExploded" => Some(0),
        _ => None,
    }
}

/// Return the public enum-name FString measured for a known Event group.
///
/// Requiring this exact constant before exposing the FString prevents a future
/// format change from turning an arbitrary payload string into a newly
/// searchable column. The original bytes remain available in `raw_payload`.
#[must_use]
pub const fn known_event_payload_name(group: &str) -> Option<&'static str> {
    match group.as_bytes() {
        b"characterDeath" => Some("EReplayEventGroup::CharacterDeath"),
        b"characterUltimateUsed" => Some("EReplayEventGroup::CharacterUltimateUsed"),
        b"roundStarted" => Some("EReplayEventGroup::RoundStart"),
        b"switchTeams" => Some("EReplayEventGroup::SwitchTeams"),
        b"spikePlanted" => Some("EReplayEventGroup::SpikePlanted"),
        b"spikeDefused" => Some("EReplayEventGroup::SpikeDefused"),
        b"spikeExploded" => Some("EReplayEventGroup::SpikeExploded"),
        _ => None,
    }
}

/// Return the group tag measured across the supported corpus for a known
/// Event group.
///
/// Each mapping was constant over 109,126 Event payloads spanning releases
/// 13.01, 13.02 and 13.04. Keeping it beside the arity and enum-name guards
/// makes a future enum reorder fail closed instead of publishing a stale tag.
#[must_use]
pub const fn known_event_payload_tag(group: &str) -> Option<u32> {
    match group.as_bytes() {
        b"characterDeath" => Some(8),
        b"characterUltimateUsed" => Some(11),
        b"roundStarted" => Some(2),
        b"switchTeams" => Some(3),
        b"spikePlanted" => Some(4),
        b"spikeDefused" => Some(5),
        b"spikeExploded" => Some(6),
        _ => None,
    }
}

/// Whether the inner payload's seconds value agrees with the Event chunk's
/// integer millisecond time.
///
/// Across 109,126 payloads from releases 13.01, 13.02 and 13.04, the maximum
/// absolute difference was 0.999878 ms. A 1.001 ms bound allows exactly the
/// observed integer-quantisation interval plus float noise, while rejecting a
/// stale offset or a non-finite value.
pub const EVENT_PAYLOAD_TIME_TOLERANCE_MS: f64 = 1.001;

#[must_use]
pub fn event_payload_seconds_matches_time(time_ms: u32, seconds: f32) -> bool {
    seconds.is_finite()
        && (f64::from(seconds) * 1000.0 - f64::from(time_ms)).abs()
            <= EVENT_PAYLOAD_TIME_TOLERANCE_MS
}

/// Parse an Event chunk's inner payload using an established word count.
///
/// Returns `None` if the count would run past the payload, any primitive is
/// malformed, or the proposed layout leaves bytes behind. This is a guarded
/// structural overlay: callers must retain the original payload, and a future
/// build changing a group's arity cannot yield plausible values read from the
/// following FString.
#[must_use]
pub fn parse_event_payload(payload: &[u8], word_count: usize) -> Option<EventPayload> {
    // tag + words + FString length + trailing f32. Checking the fixed minimum
    // before allocating also bounds `word_count` by the input size.
    let fixed_bytes = 12usize.checked_add(word_count.checked_mul(4)?)?;
    if fixed_bytes > payload.len() {
        return None;
    }

    let mut reader = BitReader::new(payload);
    let tag = reader.read_u32().ok()?;
    let mut words = Vec::with_capacity(word_count);
    for _ in 0..word_count {
        words.push(reader.read_u32().ok()?);
    }
    let name = reader.read_fstring(MAX_FSTRING_BYTES).ok()?;
    let seconds = reader.read_f32().ok()?;
    if !reader.at_end() {
        return None;
    }

    Some(EventPayload {
        tag,
        words,
        name,
        seconds,
    })
}

/// Parse the structural payload for a measured Event group.
///
/// The arity, stable tag and FString constant must all match. Unknown groups
/// and changed layouts return `None`, leaving the caller to preserve only the
/// raw payload and report the mismatch.
#[must_use]
pub fn parse_known_event_payload(group: &str, payload: &[u8]) -> Option<EventPayload> {
    let word_count = known_event_word_count(group)?;
    let expected_name = known_event_payload_name(group)?;
    let expected_tag = known_event_payload_tag(group)?;
    let parsed = parse_event_payload(payload, word_count)?;
    (parsed.name == expected_name && parsed.tag == expected_tag).then_some(parsed)
}

/// Parse an Event chunk payload.
///
/// `payload` is the region `data[chunk.data_offset .. + chunk.size_in_bytes]`
/// from a [`RawChunk`](crate::RawChunk) of type [`ChunkType::Event`](crate::ChunkType::Event).
///
/// # Errors
///
/// Returns [`ContainerError::Truncated`] if any field runs past the end of the
/// chunk, and [`ContainerError::InvalidEventPayloadSize`] if `SizeInBytes` is
/// negative.
pub fn parse_event_chunk(payload: &[u8]) -> Result<EventChunk<'_>, ContainerError> {
    let mut reader = BitReader::new(payload);

    let id = read_fstring(&mut reader, "event id")?;
    let group = read_fstring(&mut reader, "event group")?;
    let metadata = read_fstring(&mut reader, "event metadata")?;
    let time1 = read_u32(&mut reader, "event time1")?;
    let time2 = read_u32(&mut reader, "event time2")?;
    let size_in_bytes = read_i32(&mut reader, "event payload size")?;

    if size_in_bytes < 0 {
        return Err(ContainerError::InvalidEventPayloadSize {
            size: size_in_bytes,
        });
    }
    let size = size_in_bytes as usize;

    // Every read above is byte-granular, so the reader sits on a byte boundary.
    let header_end = (reader.position() / 8) as usize;
    if header_end > payload.len() || payload.len() - header_end < size {
        return Err(ContainerError::Truncated {
            context: "event payload",
            needed: size,
            available: payload.len().saturating_sub(header_end),
        });
    }

    Ok(EventChunk {
        id,
        group,
        metadata,
        time1,
        time2,
        size_in_bytes,
        payload: &payload[header_end..header_end + size],
        trailing_bytes: payload.len() - header_end - size,
    })
}

// --- Helpers ------------------------------------------------------------------

fn read_u32(reader: &mut BitReader<'_>, context: &'static str) -> Result<u32, ContainerError> {
    reader.read_u32().map_err(|_| ContainerError::Truncated {
        context,
        needed: 4,
        available: (reader.bits_remaining() / 8) as usize,
    })
}

fn read_i32(reader: &mut BitReader<'_>, context: &'static str) -> Result<i32, ContainerError> {
    reader.read_i32().map_err(|_| ContainerError::Truncated {
        context,
        needed: 4,
        available: (reader.bits_remaining() / 8) as usize,
    })
}

fn read_fstring(
    reader: &mut BitReader<'_>,
    context: &'static str,
) -> Result<String, ContainerError> {
    reader
        .read_fstring(MAX_FSTRING_BYTES)
        .map_err(|source| ContainerError::FString { context, source })
}
