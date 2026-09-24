//! `BombGameState.TeamEconomy` -- team loadout value per round.

use vrf_bitio::BitReader;

use super::framing::{
    MAX_FIELDS_PER_ELEMENT, ensure_consumed, ensure_member_consumed, member_name, read_array_count,
    read_element_index, read_field_header,
};
use super::{Result, StructBlobError};

/// A single team economy update.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TeamEconomyUpdate {
    /// Zero-based team index (0 = first team, 1 = second team).
    pub index: u32,
    /// The actor replication ID for this team (only present on initial spawn).
    pub replication_id: Option<u32>,
    /// Total loadout value for the team this round.
    pub loadout_value: Option<i32>,
    /// Average loadout value per player for the team this round.
    pub average_loadout_value: Option<i32>,
}

/// Decode a `BombGameState.TeamEconomy` blob.
///
/// # Wire layout
///
/// Standard UE RepLayout dynamic-array framing (see module docs).
/// Field handles: 56=ReplicationId(IntPacked), 57=LoadoutValue(Int32),
/// 58=AverageLoadoutValue(Int32).
///
/// This compatibility entry point retains the 12.06--13.01 handle layout.
/// Replay parsers should use [`decode_team_economy_declared`] to follow the
/// enclosing group's declaration, including the older 53..=55 layout.
///
/// # Arguments
///
/// * `reader` - A `BitReader` positioned at the start of the blob, with
///   `len_bits()` equal to the declared bit count.
pub fn decode_team_economy(reader: &mut BitReader<'_>) -> Result<Vec<TeamEconomyUpdate>> {
    decode_members(reader, |handle| match handle {
        56 => Ok("241"),
        57 => Ok("LoadoutValue"),
        58 => Ok("AverageLoadoutValue"),
        _ => Err(StructBlobError::UnsupportedHandle {
            handle,
            context: "TeamEconomy",
        }),
    })
}

/// Decode TeamEconomy using the replay's enclosing-group handle declarations.
///
/// The replication ID is declared as hardcoded FName index `241`; it retains
/// its existing IntPacked interpretation. Loadout members are named Int32s.
/// Unknown or missing declarations are errors, never a numeric-handle fallback.
pub fn decode_team_economy_declared(
    reader: &mut BitReader<'_>,
    declared: &[Option<&str>],
) -> Result<Vec<TeamEconomyUpdate>> {
    decode_members(reader, |handle| {
        member_name(declared, handle, "TeamEconomy")
    })
}

fn decode_members<'a>(
    reader: &mut BitReader<'_>,
    mut name_for: impl FnMut(u32) -> Result<&'a str>,
) -> Result<Vec<TeamEconomyUpdate>> {
    let count = read_array_count(reader)?;
    let mut results = Vec::new();

    while let Some(index) = read_element_index(reader, count)? {
        let mut replication_id: Option<u32> = None;
        let mut loadout_value: Option<i32> = None;
        let mut average_loadout_value: Option<i32> = None;

        for field_idx in 0..=MAX_FIELDS_PER_ELEMENT {
            let Some((handle, bit_count)) = read_field_header(reader)? else {
                break;
            };
            if field_idx == MAX_FIELDS_PER_ELEMENT {
                return Err(StructBlobError::TooManyFields {
                    context: "TeamEconomy",
                });
            }

            let mut sub = reader.sub_reader(u64::from(bit_count))?;
            let member = match name_for(handle)? {
                "241" => {
                    replication_id = Some(sub.read_int_packed()?);
                    "ReplicationId"
                }
                "LoadoutValue" => {
                    loadout_value = Some(sub.read_i32()?);
                    "LoadoutValue"
                }
                "AverageLoadoutValue" => {
                    average_loadout_value = Some(sub.read_i32()?);
                    "AverageLoadoutValue"
                }
                name => {
                    return Err(StructBlobError::UnsupportedMember {
                        name: name.to_owned(),
                        handle,
                        context: "TeamEconomy",
                    });
                }
            };
            // Two Int32s and one IntPacked, all self-delimiting or fixed, so
            // each owes its whole window. See `ensure_member_consumed`.
            ensure_member_consumed(&sub, member, handle, bit_count, "TeamEconomy")?;
        }

        results.push(TeamEconomyUpdate {
            index,
            replication_id,
            loadout_value,
            average_loadout_value,
        });
    }

    ensure_consumed(reader)?;
    Ok(results)
}

#[cfg(test)]
mod tests {
    use super::*;

    // 12.01 sample-1, first TeamEconomy update. No player identifiers.
    const INITIAL: [u8; 36] = [
        4, 2, 108, 16, 124, 110, 64, 0, 0, 0, 0, 112, 64, 0, 0, 0, 0, 0, 4, 108, 16, 128, 110, 64,
        0, 0, 0, 0, 112, 64, 0, 0, 0, 0, 0, 0,
    ];

    #[test]
    fn legacy_economy_uses_declared_handles_and_preserves_values() {
        let mut names = [None; 59];
        names[53] = Some("241");
        names[54] = Some("LoadoutValue");
        names[55] = Some("AverageLoadoutValue");
        let rows = decode_team_economy_declared(&mut BitReader::new(&INITIAL), &names).unwrap();
        assert_eq!(
            rows,
            vec![
                TeamEconomyUpdate {
                    index: 0,
                    replication_id: Some(62),
                    loadout_value: Some(0),
                    average_loadout_value: Some(0)
                },
                TeamEconomyUpdate {
                    index: 1,
                    replication_id: Some(64),
                    loadout_value: Some(0),
                    average_loadout_value: Some(0)
                },
            ]
        );
        // Next captured update: independently read little-endian Int32 values.
        let update = [
            4, 2, 110, 64, 48, 17, 0, 0, 112, 64, 112, 3, 0, 0, 0, 4, 110, 64, 248, 17, 0, 0, 112,
            64, 152, 3, 0, 0, 0, 0,
        ];
        let rows = decode_team_economy_declared(&mut BitReader::new(&update), &names).unwrap();
        assert_eq!(rows[0].replication_id, None);
        assert_eq!(rows[0].loadout_value, Some(4400));
        assert_eq!(rows[0].average_loadout_value, Some(880));
        assert_eq!(rows[1].loadout_value, Some(4600));
        assert_eq!(rows[1].average_loadout_value, Some(920));
        // Renaming a declared member must fail rather than use its old handle.
        names[54] = Some("UnrecognizedMember");
        assert!(matches!(
            decode_team_economy_declared(&mut BitReader::new(&INITIAL), &names),
            Err(StructBlobError::UnsupportedMember { handle: 54, .. })
        ));
        assert!(matches!(
            decode_team_economy_declared(&mut BitReader::new(&INITIAL), &[]),
            Err(StructBlobError::UndeclaredHandle { handle: 53, .. })
        ));
    }
}
