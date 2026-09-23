//! Error types for the movement decoder.

use vrf_bitio::BitError;

/// Errors that can occur during movement RPC payload decoding.
///
/// Keep the existing variants and exhaustive shape for downstream callers.
/// Adding `#[non_exhaustive]` now would also break their exhaustive matches;
/// it cannot make removal of an existing public variant compatible.
#[derive(Debug, Clone, thiserror::Error)]
pub enum MovementError {
    /// The underlying bit reader ran out of data or was malformed.
    #[error("bit read error: {0}")]
    Bit(#[from] BitError),

    /// The movement magic byte was not 0x52.
    #[error("invalid movement magic: 0x{0:02X} (expected 0x52)")]
    InvalidMagic(u8),

    /// Movement marker sequence violated (markers must follow 1->2->3->4->5->6->7->1->2...).
    #[error("movement marker mismatch: expected {expected}, got {actual}")]
    MarkerMismatch { expected: u8, actual: u8 },

    /// The error sentinel bit in a move was set, indicating the server flagged
    /// this move as invalid.
    #[error("movement error sentinel was set")]
    ErrorSentinel,

    /// Variant-0 external character reference encountered (not yet decoded).
    #[error("variant-0 external character reference is not supported")]
    Variant0ExternalCharRef,

    /// The update count exceeded the sanity limit (256).
    #[error("update count too large: {0}")]
    TooManyUpdates(u32),

    /// A component stream ended before its mandatory u16 framing header.
    #[error("movement component header needs 16 bits, only {available_bits} remain")]
    TruncatedComponentHeader {
        /// Bits available where the u16 header was required.
        available_bits: u64,
    },

    /// A character update index exceeded the declared update count.
    /// Retained for API compatibility even though the decoder does not emit it.
    #[error("update index {index} out of range (count={count})")]
    UpdateIndexOutOfRange { index: u32, count: u32 },
}
