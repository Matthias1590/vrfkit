//! The fixed-width reads shared by every chunk parser, and the one thing they
//! all add over `vrf_bitio`: a [`ContainerError::Truncated`] that names which
//! field ran out and how many bytes were left.
//!
//! `header`, `info`, `event` and `checkpoint` each carried a byte-identical
//! copy of these three. They are here once instead.
//!
//! `oodle`'s same-named helpers are deliberately NOT part of this module. They
//! map a bit-reader failure to [`ContainerError::BitIo`], not to `Truncated`:
//! an archive header that will not read is a corrupt archive, not a payload
//! that ended early, and the two are reported apart on purpose. They look like
//! duplicates of these and are not.

use vrf_bitio::BitReader;

use crate::error::ContainerError;

/// Bytes still available to the reader, for the `available` field of
/// [`ContainerError::Truncated`].
fn bytes_left(reader: &BitReader<'_>) -> usize {
    (reader.bits_remaining() / 8) as usize
}

pub(crate) fn read_u32(
    reader: &mut BitReader<'_>,
    context: &'static str,
) -> Result<u32, ContainerError> {
    reader.read_u32().map_err(|_| ContainerError::Truncated {
        context,
        needed: 4,
        available: bytes_left(reader),
    })
}

pub(crate) fn read_i32(
    reader: &mut BitReader<'_>,
    context: &'static str,
) -> Result<i32, ContainerError> {
    reader.read_i32().map_err(|_| ContainerError::Truncated {
        context,
        needed: 4,
        available: bytes_left(reader),
    })
}

/// `max_bytes` is a parameter rather than [`crate::limits::MAX_FSTRING_BYTES`]
/// because `info` reads one string under a much tighter bound
/// (`MAX_FRIENDLY_NAME_BYTES`); the other three pass the general limit.
pub(crate) fn read_fstring(
    reader: &mut BitReader<'_>,
    context: &'static str,
    max_bytes: i64,
) -> Result<String, ContainerError> {
    reader
        .read_fstring(max_bytes)
        .map_err(|source| ContainerError::FString { context, source })
}
