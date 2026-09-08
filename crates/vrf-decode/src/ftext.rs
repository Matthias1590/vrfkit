//! Strict structural decoder for the measured FText histories used by overlays.
//!
//! It preserves wire identifiers and argument trees; it makes no localization
//! or gameplay-meaning inference.
use core::fmt::{self, Write};
use thiserror::Error;
use vrf_bitio::{BitError, BitReader};

const MAX_STRING_BYTES: u64 = 64 * 1024;
const MAX_DEPTH: u16 = 16;
const MAX_NODES: u16 = 256;
const MAX_FORMAT_ARGUMENTS: i32 = 128;

/// A complete measured FText history tree.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum FTextTree {
    /// History 11 string-table form.
    StringTable {
        flags: u32,
        table: FTextName,
        key: String,
    },
    /// History 3 format form. Arguments retain their wire order and duplicates.
    Format {
        flags: u32,
        source: Box<FTextTree>,
        arguments: Vec<FTextArgument>,
    },
    /// Observed history-255, zero-flags, zero-length empty form.
    Empty { flags: u32 },
}
/// Inline FName from a string-table history.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FTextName {
    pub name: String,
    pub number: i32,
}
/// One ordered format argument.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FTextArgument {
    pub name: String,
    pub tag: u8,
    pub value: FTextArgumentValue,
}
/// Explicitly measured argument forms.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum FTextArgumentValue {
    U64Bits(u64),
    Text(Box<FTextTree>),
}
/// Full-tree FText decoding failure.
#[derive(Debug, Error, Clone, PartialEq, Eq)]
pub enum FTextTreeError {
    #[error(transparent)]
    BitIo(#[from] BitError),
    #[error("unsupported FText history discriminator {discriminator}")]
    UnsupportedHistory { discriminator: u8 },
    #[error("unsupported FText name form")]
    UnsupportedNameForm,
    #[error("FText FName suffix must be nonnegative, got {number}")]
    NegativeNameSuffix { number: i32 },
    #[error("FText format argument count must be in 0..={max}, got {actual}")]
    InvalidArgumentCount { max: i32, actual: i32 },
    #[error("unsupported FText format argument tag {tag}")]
    UnsupportedArgumentTag { tag: u8 },
    #[error("empty FText history must have zero flags and zero length")]
    InvalidEmptyForm,
    #[error("FText string exceeds {max_bytes} byte cap: {bytes} bytes")]
    StringTooLong { bytes: u64, max_bytes: u64 },
    #[error("FText string is missing its NUL terminator")]
    MissingStringTerminator,
    #[error("FText nesting exceeds depth limit {limit}")]
    DepthLimit { limit: u16 },
    #[error("FText node count exceeds limit {limit}")]
    NodeLimit { limit: u16 },
    #[error("FText payload has {remaining} unconsumed bits")]
    TrailingBits { remaining: u64 },
}

/// Decode an exact bit window containing only measured FText histories 11, 3,
/// and the observed 255 empty form. Raw u64 argument bits remain unsigned.
pub fn decode_ftext_tree(data: &[u8], bit_count: u32) -> Result<FTextTree, FTextTreeError> {
    let mut r = BitReader::with_bit_len(data, u64::from(bit_count))?;
    let mut nodes = 0;
    let value = decode_tree(&mut r, 0, &mut nodes)?;
    if r.bits_remaining() != 0 {
        return Err(FTextTreeError::TrailingBits {
            remaining: r.bits_remaining(),
        });
    }
    Ok(value)
}
impl FTextTree {
    /// JSON for additive `value_str`; it retains flags, history and wire values.
    #[must_use]
    pub fn to_json(&self) -> String {
        let mut s = String::new();
        self.write_json(&mut s).expect("String write");
        s
    }
    fn write_json(&self, s: &mut String) -> fmt::Result {
        match self {
            Self::StringTable { flags, table, key } => {
                write!(
                    s,
                    r#"{{"flags":{flags},"history":11,"kind":"string_table","table":{{"name":"#
                )?;
                json_string(s, &table.name)?;
                write!(s, r#","number":{}}},"key":"#, table.number)?;
                json_string(s, key)?;
                s.push('}');
                Ok(())
            }
            Self::Format {
                flags,
                source,
                arguments,
            } => {
                write!(
                    s,
                    r#"{{"flags":{flags},"history":3,"kind":"format","source":"#
                )?;
                source.write_json(s)?;
                s.push_str(r#","arguments":["#);
                for (i, a) in arguments.iter().enumerate() {
                    if i > 0 {
                        s.push(',');
                    }
                    s.push_str(r#"{"name":"#);
                    json_string(s, &a.name)?;
                    write!(s, r#","tag":{},"value":"#, a.tag)?;
                    match &a.value {
                        FTextArgumentValue::U64Bits(v) => write!(s, r#"{{"bits_u64":"{v}"}}"#)?,
                        FTextArgumentValue::Text(v) => v.write_json(s)?,
                    };
                    s.push('}');
                }
                s.push_str("]}");
                Ok(())
            }
            Self::Empty { flags } => {
                write!(s, r#"{{"flags":{flags},"history":255,"kind":"empty"}}"#)
            }
        }
    }
}
fn decode_tree(
    r: &mut BitReader<'_>,
    depth: u16,
    nodes: &mut u16,
) -> Result<FTextTree, FTextTreeError> {
    if depth >= MAX_DEPTH {
        return Err(FTextTreeError::DepthLimit { limit: MAX_DEPTH });
    }
    *nodes = nodes
        .checked_add(1)
        .ok_or(FTextTreeError::NodeLimit { limit: MAX_NODES })?;
    if *nodes > MAX_NODES {
        return Err(FTextTreeError::NodeLimit { limit: MAX_NODES });
    }
    let flags = r.read_bits(32)? as u32;
    let history = r.read_bits(8)? as u8;
    match history {
        11 => {
            if r.read_bit()? {
                return Err(FTextTreeError::UnsupportedNameForm);
            };
            let name = read_string(r)?;
            let number = r.read_i32()?;
            if number < 0 {
                return Err(FTextTreeError::NegativeNameSuffix { number });
            };
            let key = read_string(r)?;
            Ok(FTextTree::StringTable {
                flags,
                table: FTextName { name, number },
                key,
            })
        }
        3 => {
            let source = Box::new(decode_tree(r, depth + 1, nodes)?);
            let actual = r.read_i32()?;
            if !(0..=MAX_FORMAT_ARGUMENTS).contains(&actual) {
                return Err(FTextTreeError::InvalidArgumentCount {
                    max: MAX_FORMAT_ARGUMENTS,
                    actual,
                });
            };
            let mut arguments = Vec::with_capacity(actual as usize);
            for _ in 0..actual {
                *nodes = nodes
                    .checked_add(1)
                    .ok_or(FTextTreeError::NodeLimit { limit: MAX_NODES })?;
                if *nodes > MAX_NODES {
                    return Err(FTextTreeError::NodeLimit { limit: MAX_NODES });
                }
                let name = read_string(r)?;
                let tag = r.read_bits(8)? as u8;
                let value = match tag {
                    0 => FTextArgumentValue::U64Bits(r.read_u64()?),
                    4 => FTextArgumentValue::Text(Box::new(decode_tree(r, depth + 1, nodes)?)),
                    _ => return Err(FTextTreeError::UnsupportedArgumentTag { tag }),
                };
                arguments.push(FTextArgument { name, tag, value });
            }
            Ok(FTextTree::Format {
                flags,
                source,
                arguments,
            })
        }
        255 => {
            if flags != 0 || r.read_i32()? != 0 {
                Err(FTextTreeError::InvalidEmptyForm)
            } else {
                Ok(FTextTree::Empty { flags })
            }
        }
        _ => Err(FTextTreeError::UnsupportedHistory {
            discriminator: history,
        }),
    }
}
fn read_string(r: &mut BitReader<'_>) -> Result<String, FTextTreeError> {
    let length = r.read_i32()?;
    if length == 0 {
        return Ok(String::new());
    };
    let units = u64::from(length.unsigned_abs());
    let bytes = units.saturating_mul(if length < 0 { 2 } else { 1 });
    if bytes > MAX_STRING_BYTES {
        return Err(FTextTreeError::StringTooLong {
            bytes,
            max_bytes: MAX_STRING_BYTES,
        });
    };
    if length > 0 {
        let mut v = Vec::with_capacity(units as usize);
        for _ in 0..units {
            v.push(r.read_bits(8)? as u8)
        }
        if v.last() != Some(&0) {
            return Err(FTextTreeError::MissingStringTerminator);
        };
        v.pop();
        String::from_utf8(v).map_err(|_| {
            BitError::InvalidString {
                position: r.position(),
            }
            .into()
        })
    } else {
        let mut v = Vec::with_capacity(units as usize);
        for _ in 0..units {
            v.push(r.read_bits(16)? as u16)
        }
        if v.last() != Some(&0) {
            return Err(FTextTreeError::MissingStringTerminator);
        };
        v.pop();
        String::from_utf16(&v).map_err(|_| {
            BitError::InvalidString {
                position: r.position(),
            }
            .into()
        })
    }
}
fn json_string(s: &mut String, value: &str) -> fmt::Result {
    s.push('"');
    for c in value.chars() {
        match c {
            '"' => s.push_str("\\\""),
            '\\' => s.push_str("\\\\"),
            '\n' => s.push_str("\\n"),
            '\r' => s.push_str("\\r"),
            '\t' => s.push_str("\\t"),
            c if c <= '\u{1f}' => write!(s, "\\u{:04x}", c as u32)?,
            c => s.push(c),
        }
    }
    s.push('"');
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    struct Bits(Vec<bool>);
    impl Bits {
        fn new() -> Self {
            Self(Vec::new())
        }
        fn bits(&mut self, value: u64, width: u32) {
            for bit in 0..width {
                self.0.push(value & (1 << bit) != 0);
            }
        }
        fn i32(&mut self, value: i32) {
            self.bits(value as u32 as u64, 32);
        }
        fn string(&mut self, value: &str) {
            self.i32((value.len() + 1) as i32);
            for byte in value.bytes() {
                self.bits(u64::from(byte), 8);
            }
            self.bits(0, 8);
        }
        fn table(&mut self, flags: u32, name: &str, number: i32, key: &str) {
            self.bits(u64::from(flags), 32);
            self.bits(11, 8);
            self.bits(0, 1);
            self.string(name);
            self.i32(number);
            self.string(key);
        }
        fn empty(&mut self) {
            self.bits(0, 32);
            self.bits(255, 8);
            self.i32(0);
        }
        fn finish(self) -> (Vec<u8>, u32) {
            let len = self.0.len() as u32;
            let mut out = vec![0; self.0.len().div_ceil(8)];
            for (i, bit) in self.0.into_iter().enumerate() {
                if bit {
                    out[i / 8] |= 1 << (i % 8)
                }
            }
            (out, len)
        }
    }

    #[test]
    fn string_table_preserves_suffix_and_escapes_json() {
        let mut bits = Bits::new();
        bits.table(7, "Table\\Name", 2, "line\n\"key");
        let (raw, count) = bits.finish();
        let tree = decode_ftext_tree(&raw, count).unwrap();
        assert_eq!(
            tree.to_json(),
            r#"{"flags":7,"history":11,"kind":"string_table","table":{"name":"Table\\Name","number":2},"key":"line\n\"key"}"#
        );
    }

    #[test]
    fn format_keeps_duplicate_names_and_unsigned_bits() {
        let mut bits = Bits::new();
        bits.bits(9, 32);
        bits.bits(3, 8);
        bits.table(0, "T", 0, "Source");
        bits.i32(2);
        bits.string("same");
        bits.bits(0, 8);
        bits.bits(u64::MAX, 64);
        bits.string("same");
        bits.bits(4, 8);
        bits.empty();
        let (raw, count) = bits.finish();
        let json = decode_ftext_tree(&raw, count).unwrap().to_json();
        assert!(json.contains(r#""bits_u64":"18446744073709551615""#));
        assert_eq!(json.matches(r#""name":"same""#).count(), 2);
    }

    #[test]
    fn format_accepts_zero_one_and_two_arguments() {
        for count in 0..=2 {
            let mut bits = Bits::new();
            bits.bits(0, 32);
            bits.bits(3, 8);
            bits.empty();
            bits.i32(count);
            for index in 0..count {
                bits.string("arg");
                bits.bits(0, 8);
                bits.bits(index as u64, 64);
            }
            let (raw, width) = bits.finish();
            let FTextTree::Format { arguments, .. } = decode_ftext_tree(&raw, width).unwrap()
            else {
                panic!("format history");
            };
            assert_eq!(arguments.len(), count as usize);
        }
    }

    #[test]
    fn rejects_bad_terminator_count_tag_flags_and_residual() {
        let mut terminator = Bits::new();
        terminator.bits(0, 32);
        terminator.bits(11, 8);
        terminator.bits(0, 1);
        terminator.i32(2);
        terminator.bits(u64::from(b'A'), 8);
        terminator.bits(u64::from(b'X'), 8);
        let (raw, count) = terminator.finish();
        assert!(matches!(
            decode_ftext_tree(&raw, count),
            Err(FTextTreeError::MissingStringTerminator)
        ));
        let mut count_bits = Bits::new();
        count_bits.bits(0, 32);
        count_bits.bits(3, 8);
        count_bits.empty();
        count_bits.i32(-1);
        let (raw, count) = count_bits.finish();
        assert!(matches!(
            decode_ftext_tree(&raw, count),
            Err(FTextTreeError::InvalidArgumentCount { .. })
        ));
        let mut too_wide = Bits::new();
        too_wide.bits(0, 32);
        too_wide.bits(3, 8);
        too_wide.empty();
        too_wide.i32(129);
        let (raw, count) = too_wide.finish();
        assert!(matches!(
            decode_ftext_tree(&raw, count),
            Err(FTextTreeError::InvalidArgumentCount { .. })
        ));
        let mut tag_bits = Bits::new();
        tag_bits.bits(0, 32);
        tag_bits.bits(3, 8);
        tag_bits.empty();
        tag_bits.i32(2);
        tag_bits.string("first");
        tag_bits.bits(0, 8);
        tag_bits.bits(1, 64);
        tag_bits.string("second");
        tag_bits.bits(99, 8);
        let (raw, count) = tag_bits.finish();
        assert!(matches!(
            decode_ftext_tree(&raw, count),
            Err(FTextTreeError::UnsupportedArgumentTag { tag: 99 })
        ));
        let mut empty = Bits::new();
        empty.bits(1, 32);
        empty.bits(255, 8);
        empty.i32(0);
        let (raw, count) = empty.finish();
        assert!(matches!(
            decode_ftext_tree(&raw, count),
            Err(FTextTreeError::InvalidEmptyForm)
        ));
        let mut residual = Bits::new();
        residual.empty();
        residual.bits(1, 1);
        let (raw, count) = residual.finish();
        assert!(matches!(
            decode_ftext_tree(&raw, count),
            Err(FTextTreeError::TrailingBits { .. })
        ));
    }

    #[test]
    fn unicode_strings_are_strict_and_byte_bounded() {
        let mut valid = Bits::new();
        valid.bits(0, 32);
        valid.bits(11, 8);
        valid.bits(0, 1);
        valid.i32(-3);
        for unit in [0xd83d, 0xde00, 0] {
            valid.bits(unit, 16);
        }
        valid.i32(0);
        valid.string("Key");
        let (raw, count) = valid.finish();
        let FTextTree::StringTable { table, .. } = decode_ftext_tree(&raw, count).unwrap() else {
            panic!("string table");
        };
        assert_eq!(table.name, "\u{1f600}");

        for (length, units, width) in [(2, vec![0xff, 0], 8), (-2, vec![0xd800, 0], 16)] {
            let mut invalid = Bits::new();
            invalid.bits(0, 32);
            invalid.bits(11, 8);
            invalid.bits(0, 1);
            invalid.i32(length);
            for unit in units {
                invalid.bits(unit, width);
            }
            let (raw, count) = invalid.finish();
            assert!(matches!(
                decode_ftext_tree(&raw, count),
                Err(FTextTreeError::BitIo(BitError::InvalidString { .. }))
            ));
        }
        for length in [65_537, -32_769, i32::MIN] {
            let mut invalid = Bits::new();
            invalid.bits(0, 32);
            invalid.bits(11, 8);
            invalid.bits(0, 1);
            invalid.i32(length);
            let (raw, count) = invalid.finish();
            assert!(matches!(
                decode_ftext_tree(&raw, count),
                Err(FTextTreeError::StringTooLong { .. })
            ));
        }
    }

    #[test]
    fn depth_and_total_node_budgets_reject_otherwise_complete_trees() {
        for levels in [MAX_DEPTH - 1, MAX_DEPTH] {
            let mut nested = Bits::new();
            for _ in 0..levels {
                nested.bits(0, 32);
                nested.bits(3, 8);
            }
            nested.empty();
            for _ in 0..levels {
                nested.i32(0);
            }
            let (raw, count) = nested.finish();
            if levels < MAX_DEPTH {
                assert!(decode_ftext_tree(&raw, count).is_ok());
            } else {
                assert!(matches!(
                    decode_ftext_tree(&raw, count),
                    Err(FTextTreeError::DepthLimit { .. })
                ));
            }
        }
        // Root + source + (one argument and one text per entry): the final
        // argument crosses the global budget while its local count is valid.
        for arguments in [127, 128] {
            let mut wide = Bits::new();
            wide.bits(0, 32);
            wide.bits(3, 8);
            wide.empty();
            wide.i32(arguments);
            for _ in 0..arguments {
                wide.string("arg");
                wide.bits(4, 8);
                wide.empty();
            }
            let (raw, count) = wide.finish();
            if arguments == 127 {
                assert!(decode_ftext_tree(&raw, count).is_ok());
            } else {
                assert!(matches!(
                    decode_ftext_tree(&raw, count),
                    Err(FTextTreeError::NodeLimit { .. })
                ));
            }
        }
    }
}
