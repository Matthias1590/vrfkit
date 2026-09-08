//! Checkpoint-scoped field, actor and NetGUID tables.

use std::sync::Arc;

use arrow_array::builder::StringDictionaryBuilder;
use arrow_array::types::Int32Type;
use arrow_array::{
    ArrayRef, BinaryArray, BooleanArray, Float32Array, Float64Array, Int64Array, RecordBatch,
    StringArray, UInt32Array,
};
use arrow_schema::Schema;

use crate::ExportError;
use crate::record::{CheckpointActorRecord, CheckpointFieldRecord, CheckpointNetGuidRecord};
use crate::schema::{
    checkpoint_actors_schema_ref, checkpoint_fields_schema_ref, checkpoint_net_guids_schema_ref,
};
use crate::writer::{Table, TableWriter};

pub struct CheckpointFieldsTable;
pub struct CheckpointActorsTable;
pub struct CheckpointNetGuidsTable;
pub type CheckpointFieldWriter<W> = TableWriter<CheckpointFieldsTable, W>;
pub type CheckpointActorWriter<W> = TableWriter<CheckpointActorsTable, W>;
pub type CheckpointNetGuidWriter<W> = TableWriter<CheckpointNetGuidsTable, W>;

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
    }
}
