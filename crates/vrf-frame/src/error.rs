//! Error types for the DemoFrame layer.

use thiserror::Error;

/// All error modes during DemoFrame iteration.
///
/// A frame error means the decompressed chunk is malformed at the framing level.
/// This is distinct from content-block errors (which live in `vrf-net`).
#[derive(Debug, Error)]
pub enum FrameError {
    /// A bit read failed (truncation or malformed primitive).
    #[error("bit-IO error during frame parsing: {0}")]
    Bit(String),

    /// A schema-reader error (net-field export or export-GUID parsing).
    #[error("schema error during frame parsing: {0}")]
    Schema(String),

    /// Packet size declared as negative.
    #[error("negative packet size: {size}")]
    NegativePacketSize { size: i32 },

    /// Packet size exceeds the protocol maximum (2 KiB).
    #[error("packet size {size} exceeds maximum {max}")]
    PacketTooLarge { size: i32, max: i32 },

    /// A frame's `timeSeconds` was finite but does not scale to a millisecond
    /// value a `u32` can hold.
    ///
    /// Separate from the non-finite case, which is not an error: the reference
    /// maps NaN and both infinities to 0 and this crate matches it. A finite
    /// value has no such mapping -- the reference keeps it in a signed `long`,
    /// while [`crate::DemoPacket::time_ms`] is a `u32`, so there is no answer
    /// to give that is not invented.
    #[error("frame time {seconds} s is outside the representable millisecond range")]
    TimeOutOfRange { seconds: f32 },

    /// The data was truncated mid-frame.
    #[error("{context}: needed {needed} bytes, only {available} available")]
    Truncated {
        context: &'static str,
        needed: usize,
        available: usize,
    },
}

// `From` rather than named adapters, so `?` performs the conversion and the 18
// call sites do not each spell out `.map_err(FrameError::bit)`. Both variants
// hold the rendered string rather than the source error: this crate's failures
// are reported, not matched on, and keeping the source types out of the public
// enum means a `vrf-bitio` or `vrf-schema` error-shape change is not a
// breaking change here.
impl From<vrf_bitio::BitError> for FrameError {
    fn from(e: vrf_bitio::BitError) -> Self {
        Self::Bit(e.to_string())
    }
}

impl From<vrf_schema::SchemaError> for FrameError {
    fn from(e: vrf_schema::SchemaError) -> Self {
        Self::Schema(e.to_string())
    }
}
