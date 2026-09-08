//! Checkpoint-scoped field, actor and NetGUID tables.

use std::sync::Arc;

use arrow_array::builder::StringDictionaryBuilder;
use arrow_array::types::Int32Type;
use arrow_array::{
    ArrayRef, BinaryArray, BooleanArray, Float32Array, Float64Array, Int64Array, RecordBatch,
    StringArray, UInt8Array, UInt32Array, UInt64Array,
};
use arrow_schema::Schema;

use crate::ExportError;
use crate::record::{
    CheckpointActorRecord, CheckpointBlockRecord, CheckpointFieldRecord, CheckpointNetGuidRecord,
};
use crate::schema::{
    checkpoint_actors_schema_ref, checkpoint_blocks_schema_ref, checkpoint_fields_schema_ref,
    checkpoint_net_guids_schema_ref,
};
use crate::writer::{Table, TableWriter};

pub struct CheckpointFieldsTable;
pub struct CheckpointActorsTable;
pub struct CheckpointNetGuidsTable;
pub struct CheckpointBlocksTable;
pub type CheckpointFieldWriter<W> = TableWriter<CheckpointFieldsTable, W>;
pub type CheckpointActorWriter<W> = TableWriter<CheckpointActorsTable, W>;
pub type CheckpointNetGuidWriter<W> = TableWriter<CheckpointNetGuidsTable, W>;
pub type CheckpointBlockWriter<W> = TableWriter<CheckpointBlocksTable, W>;

fn identity_arrays<'a>(
    identities: impl Iterator<Item = &'a crate::record::CheckpointIdentity> + Clone,
) -> [ArrayRef; 2] {
    [
        Arc::new(UInt32Array::from_iter_values(
            identities.clone().map(|i| i.checkpoint_index),
        )),
        Arc::new(StringArray::from_iter_values(
            identities.map(|i| i.checkpoint_id.as_ref()),
        )),
    ]
}

impl Table for CheckpointBlocksTable {
    type Row = CheckpointBlockRecord;
    const DEFAULT_ROW_GROUP_SIZE: usize = 131_072;
    const DICTIONARY_COLUMNS: &'static [&'static str] = &[
        "resolved_group_path",
        "group_resolution_source",
        "function_count_source",
        "actor_archetype_path",
        "actor_archetype_outer_path",
        "actor_guid_path",
        "class_guid_path",
        "object_guid_path",
        "object_outer_path",
    ];
    fn schema() -> Arc<Schema> {
        checkpoint_blocks_schema_ref()
    }
    fn build_batch(rows: &[Self::Row]) -> Result<RecordBatch, ExportError> {
        let mut c = identity_arrays(rows.iter().map(|r| &r.checkpoint)).to_vec();
        macro_rules! values {
            ($ty:ty, $field:ident) => {
                Arc::new(<$ty>::from_iter_values(rows.iter().map(|r| r.$field))) as ArrayRef
            };
        }
        macro_rules! optional {
            ($ty:ty, $field:ident) => {
                Arc::new(<$ty>::from_iter(rows.iter().map(|r| r.$field))) as ArrayRef
            };
        }
        macro_rules! booleans {
            ($field:ident) => {
                Arc::new(BooleanArray::from_iter(rows.iter().map(|r| Some(r.$field)))) as ArrayRef
            };
        }
        c.extend([
            values!(UInt32Array, block_index),
            values!(UInt32Array, time_ms),
            values!(UInt32Array, packet_id),
            values!(UInt32Array, channel_index),
            values!(UInt32Array, actor_net_guid),
            optional!(UInt32Array, object_net_guid),
            optional!(UInt32Array, class_net_guid),
            optional!(UInt32Array, outer_net_guid),
            booleans!(has_rep_layout),
            booleans!(is_actor),
            booleans!(is_deleted),
            booleans!(is_stably_named),
            values!(UInt8Array, delete_flags),
        ]);
        c.push(Arc::new(StringArray::from_iter_values(
            rows.iter().map(|r| r.resolved_group_path.as_ref()),
        )));
        c.push(Arc::new(StringArray::from_iter_values(
            rows.iter().map(|r| r.group_resolution_source),
        )));
        c.push(booleans!(group_declared));
        c.push(booleans!(resolution_memo_hit));
        c.push(values!(UInt32Array, function_count));
        c.push(Arc::new(StringArray::from_iter_values(
            rows.iter().map(|r| r.function_count_source),
        )));
        for select in 0..6 {
            c.push(Arc::new(StringArray::from_iter(rows.iter().map(
                |r| match select {
                    0 => r.actor_archetype_path.as_deref(),
                    1 => r.actor_archetype_outer_path.as_deref(),
                    2 => r.actor_guid_path.as_deref(),
                    3 => r.class_guid_path.as_deref(),
                    4 => r.object_guid_path.as_deref(),
                    _ => r.object_outer_path.as_deref(),
                },
            ))));
        }
        c.push(values!(UInt64Array, field_row_start));
        c.push(values!(UInt32Array, field_row_count));
        RecordBatch::try_new(Self::schema(), c).map_err(|e| ExportError::Parquet(e.into()))
    }
}

impl Table for CheckpointFieldsTable {
    type Row = CheckpointFieldRecord;
    const DEFAULT_ROW_GROUP_SIZE: usize = 131_072;
    const DICTIONARY_COLUMNS: &'static [&'static str] = &["group_path", "field_name", "value_str"];
    fn schema() -> Arc<Schema> {
        checkpoint_fields_schema_ref()
    }
    fn build_batch(rows: &[Self::Row]) -> Result<RecordBatch, ExportError> {
        let len = rows.len();
        let mut columns = identity_arrays(rows.iter().map(|r| &r.checkpoint)).to_vec();
        let fields = rows.iter().map(|r| &r.field);
        columns.extend([
            Arc::new(UInt32Array::from_iter_values(
                fields.clone().map(|r| r.time_ms),
            )) as ArrayRef,
            Arc::new(UInt32Array::from_iter_values(
                fields.clone().map(|r| r.packet_id),
            )),
            Arc::new(UInt32Array::from_iter_values(
                fields.clone().map(|r| r.channel_index),
            )),
            Arc::new(UInt32Array::from_iter_values(
                fields.clone().map(|r| r.actor_net_guid),
            )),
            Arc::new(UInt32Array::from_iter(
                fields.clone().map(|r| r.object_net_guid),
            )),
        ]);
        let mut group = StringDictionaryBuilder::<Int32Type>::with_capacity(len, 256, len * 20);
        for r in fields.clone() {
            group.append_value(&r.group_path);
        }
        columns.push(Arc::new(group.finish()));
        columns.push(Arc::new(UInt32Array::from_iter_values(
            fields.clone().map(|r| r.handle),
        )));
        let mut name = StringDictionaryBuilder::<Int32Type>::with_capacity(len, 256, len * 16);
        for r in fields.clone() {
            match &r.field_name {
                Some(v) => name.append_value(v),
                None => name.append_null(),
            }
        }
        columns.push(Arc::new(name.finish()));
        columns.extend([
            Arc::new(UInt32Array::from_iter(
                fields.clone().map(|r| r.compatible_checksum),
            )) as ArrayRef,
            Arc::new(UInt32Array::from_iter_values(
                fields.clone().map(|r| r.bit_count),
            )),
            Arc::new(BinaryArray::from_iter(
                fields.clone().map(|r| r.raw_bits.as_deref()),
            )),
            Arc::new(Int64Array::from_iter(fields.clone().map(|r| r.value_i64))),
            Arc::new(Float64Array::from_iter(fields.clone().map(|r| r.value_f64))),
            Arc::new(BooleanArray::from_iter(
                fields.clone().map(|r| r.value_bool),
            )),
        ]);
        let mut value = StringDictionaryBuilder::<Int32Type>::with_capacity(len, 2048, len * 32);
        for r in fields {
            match &r.value_str {
                Some(v) => value.append_value(v),
                None => value.append_null(),
            }
        }
        columns.push(Arc::new(value.finish()));
        RecordBatch::try_new(Self::schema(), columns).map_err(|e| ExportError::Parquet(e.into()))
    }
}

impl Table for CheckpointActorsTable {
    type Row = CheckpointActorRecord;
    const DEFAULT_ROW_GROUP_SIZE: usize = 131_072;
    const DICTIONARY_COLUMNS: &'static [&'static str] = &["class_path", "archetype_path"];
    fn schema() -> Arc<Schema> {
        checkpoint_actors_schema_ref()
    }
    fn initial_capacity(_: usize) -> usize {
        4096
    }
    fn build_batch(rows: &[Self::Row]) -> Result<RecordBatch, ExportError> {
        let len = rows.len();
        let mut c = identity_arrays(rows.iter().map(|r| &r.checkpoint)).to_vec();
        let actors = rows.iter().map(|r| &r.actor);
        c.extend([
            Arc::new(UInt32Array::from_iter_values(
                actors.clone().map(|r| r.time_ms),
            )) as ArrayRef,
            Arc::new(UInt32Array::from_iter_values(
                actors.clone().map(|r| r.packet_id),
            )),
            Arc::new(UInt32Array::from_iter_values(
                actors.clone().map(|r| r.channel_index),
            )),
            Arc::new(UInt32Array::from_iter_values(
                actors.clone().map(|r| r.actor_net_guid),
            )),
            Arc::new(StringArray::from_iter_values(
                actors.clone().map(|r| r.event),
            )),
        ]);
        for select in [0, 1] {
            let mut b = StringDictionaryBuilder::<Int32Type>::with_capacity(len, 128, len * 30);
            for r in actors.clone() {
                let v = if select == 0 {
                    &r.class_path
                } else {
                    &r.archetype_path
                };
                match v {
                    Some(v) => b.append_value(v),
                    None => b.append_null(),
                }
            }
            c.push(Arc::new(b.finish()));
        }
        c.extend([
            Arc::new(Float32Array::from_iter(actors.clone().map(|r| r.spawn_x))) as ArrayRef,
            Arc::new(Float32Array::from_iter(actors.clone().map(|r| r.spawn_y))),
            Arc::new(Float32Array::from_iter(actors.clone().map(|r| r.spawn_z))),
            Arc::new(Float32Array::from_iter(
                actors.clone().map(|r| r.spawn_pitch),
            )),
            Arc::new(Float32Array::from_iter(actors.clone().map(|r| r.spawn_yaw))),
            Arc::new(Float32Array::from_iter(actors.map(|r| r.spawn_roll))),
        ]);
        RecordBatch::try_new(Self::schema(), c).map_err(|e| ExportError::Parquet(e.into()))
    }
}

impl Table for CheckpointNetGuidsTable {
    type Row = CheckpointNetGuidRecord;
    const DEFAULT_ROW_GROUP_SIZE: usize = 131_072;
    const DICTIONARY_COLUMNS: &'static [&'static str] = &["path"];
    fn schema() -> Arc<Schema> {
        checkpoint_net_guids_schema_ref()
    }
    fn initial_capacity(_: usize) -> usize {
        4096
    }
    fn build_batch(rows: &[Self::Row]) -> Result<RecordBatch, ExportError> {
        let mut c = identity_arrays(rows.iter().map(|r| &r.checkpoint)).to_vec();
        let records = rows.iter().map(|r| &r.net_guid);
        c.push(Arc::new(UInt32Array::from_iter_values(
            records.clone().map(|r| r.net_guid),
        )));
        let mut path =
            StringDictionaryBuilder::<Int32Type>::with_capacity(rows.len(), 1024, rows.len() * 40);
        for r in records.clone() {
            path.append_value(&r.path);
        }
        c.push(Arc::new(path.finish()));
        c.push(Arc::new(UInt32Array::from_iter(
            records.map(|r| r.outer_net_guid),
        )));
        RecordBatch::try_new(Self::schema(), c).map_err(|e| ExportError::Parquet(e.into()))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::record::{ActorRecord, CheckpointIdentity, FieldRecord, NetGuidRecord};
    use crate::schema::fields_schema;
    use smallvec::smallvec;

    fn identities() -> [CheckpointIdentity; 2] {
        [
            CheckpointIdentity {
                checkpoint_index: 3,
                checkpoint_id: Arc::from("same"),
            },
            CheckpointIdentity {
                checkpoint_index: 4,
                checkpoint_id: Arc::from("same"),
            },
        ]
    }

    #[test]
    fn duplicate_wire_ids_remain_distinct_and_payload_values_are_unchanged() {
        let [a, b] = identities();
        let field = |checkpoint| CheckpointFieldRecord {
            checkpoint,
            field: FieldRecord {
                time_ms: 7,
                packet_id: 0,
                channel_index: 2,
                actor_net_guid: 9,
                object_net_guid: Some(10),
                group_path: Arc::from("group"),
                handle: 11,
                field_name: Some(Arc::from("field")),
                compatible_checksum: Some(12),
                bit_count: 5,
                raw_bits: Some(smallvec![0x15]),
                value_i64: Some(42),
                value_f64: None,
                value_bool: None,
                value_str: None,
            },
        };
        let batch =
            CheckpointFieldsTable::build_batch(&[field(a.clone()), field(b.clone())]).unwrap();
        assert_eq!(
            batch
                .column(0)
                .as_any()
                .downcast_ref::<UInt32Array>()
                .unwrap()
                .values(),
            &[3, 4]
        );
        assert_eq!(
            batch
                .column(1)
                .as_any()
                .downcast_ref::<StringArray>()
                .unwrap()
                .value(0),
            "same"
        );
        assert_eq!(
            batch
                .column(12)
                .as_any()
                .downcast_ref::<BinaryArray>()
                .unwrap()
                .value(1),
            &[0x15]
        );
        assert_eq!(
            batch
                .column(13)
                .as_any()
                .downcast_ref::<Int64Array>()
                .unwrap()
                .value(0),
            42
        );
        assert_eq!(
            fields_schema().fields()[0].name(),
            "time_ms",
            "main schema must not acquire checkpoint identity"
        );

        let actor = |checkpoint| CheckpointActorRecord {
            checkpoint,
            actor: ActorRecord {
                time_ms: 7,
                packet_id: 0,
                channel_index: 2,
                actor_net_guid: 9,
                event: "open",
                class_path: Some("class".into()),
                archetype_path: None,
                spawn_x: Some(1.0),
                spawn_y: None,
                spawn_z: None,
                spawn_pitch: None,
                spawn_yaw: None,
                spawn_roll: None,
            },
        };
        let actors =
            CheckpointActorsTable::build_batch(&[actor(a.clone()), actor(b.clone())]).unwrap();
        assert_eq!(
            actors
                .column(0)
                .as_any()
                .downcast_ref::<UInt32Array>()
                .unwrap()
                .values(),
            &[3, 4]
        );
        assert_eq!(
            actors
                .column(3)
                .as_any()
                .downcast_ref::<UInt32Array>()
                .unwrap()
                .values(),
            &[0, 0]
        );

        let guid = |checkpoint| CheckpointNetGuidRecord {
            checkpoint,
            net_guid: NetGuidRecord {
                net_guid: 9,
                path: "path".into(),
                outer_net_guid: Some(1),
            },
        };
        let guids = CheckpointNetGuidsTable::build_batch(&[guid(a), guid(b)]).unwrap();
        assert_eq!(
            guids
                .column(0)
                .as_any()
                .downcast_ref::<UInt32Array>()
                .unwrap()
                .values(),
            &[3, 4]
        );
        assert_eq!(
            guids
                .column(2)
                .as_any()
                .downcast_ref::<UInt32Array>()
                .unwrap()
                .values(),
            &[9, 9]
        );

        let [a, b] = identities();
        let block = |checkpoint| CheckpointBlockRecord {
            checkpoint,
            block_index: 0,
            time_ms: 7,
            packet_id: 0,
            channel_index: 2,
            actor_net_guid: 9,
            object_net_guid: Some(0),
            class_net_guid: Some(0),
            outer_net_guid: Some(9),
            has_rep_layout: true,
            is_actor: false,
            is_deleted: false,
            is_stably_named: false,
            delete_flags: 0,
            resolved_group_path: Arc::from("group"),
            group_resolution_source: "replay_declared_group",
            group_declared: true,
            resolution_memo_hit: false,
            function_count: 0,
            function_count_source: "rep_layout_not_applicable",
            actor_archetype_path: None,
            actor_archetype_outer_path: None,
            actor_guid_path: None,
            class_guid_path: None,
            object_guid_path: Some("object".into()),
            object_outer_path: None,
            field_row_start: 12,
            field_row_count: 2,
        };
        let blocks = CheckpointBlocksTable::build_batch(&[block(a), block(b)]).unwrap();
        assert_eq!(
            blocks
                .column(0)
                .as_any()
                .downcast_ref::<UInt32Array>()
                .unwrap()
                .values(),
            &[3, 4]
        );
        assert_eq!(
            blocks
                .column(8)
                .as_any()
                .downcast_ref::<UInt32Array>()
                .unwrap()
                .values(),
            &[0, 0]
        );
        assert_eq!(
            blocks
                .column(27)
                .as_any()
                .downcast_ref::<UInt64Array>()
                .unwrap()
                .values(),
            &[12, 12]
        );
    }
}
