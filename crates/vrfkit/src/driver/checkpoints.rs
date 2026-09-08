//! The optional Checkpoint pass.
//!
//! A checkpoint is a full-state snapshot: its own guid cache, its own export
//! map, and one DemoFrame re-opening every actor alive at that instant.
//! Everything about it is independent of the live stream, so it gets its own
//! cache, reader, channel state and buffers. Sharing any of the four would let
//! the snapshot's channel opens and archetype mappings leak into the ReplayData
//! pass and corrupt it.
//!
//! Checkpoint rows go to separate tables because their packet, channel and
//! NetGUID namespaces restart inside each snapshot. Keeping that context out
//! of the main tables also leaves the default export byte-identical.

use std::io::Write;

use vrf_container::{decompress_checkpoint, parse_checkpoint_chunk};
use vrf_decode::OverlayErrorReport;
use vrf_export::{
    CheckpointActorRecord, CheckpointActorWriter, CheckpointBlockWriter, CheckpointFieldRecord,
    CheckpointFieldWriter, CheckpointIdentity, CheckpointNetGuidRecord, CheckpointNetGuidWriter,
    NetGuidRecord, PartialWriter,
};
use vrf_frame::iter_demo_frames;
use vrf_net::pipeline::ReplicationReader;
use vrf_net::stats::NetStats;
use vrf_schema::{NetGuidCache, read_checkpoint_tables};

use super::totals::SinkTotals;
use crate::error::CliError;
use crate::sink::{ChannelState, ExportSink, RecordBuffers};

/// Counters for the optional checkpoint pass. Kept together so the summary
/// cannot report one and quietly omit another.
#[derive(Debug, Default)]
pub(crate) struct CheckpointStats {
    pub chunks: u64,
    /// Sum of [`CheckpointChunk::trailing_bytes`](vrf_container::CheckpointChunk::trailing_bytes)
    /// across every chunk processed. Zero on every corpus checkpoint measured
    /// so far; printed unconditionally in the summary so a format change that
    /// starts leaving bytes after the archive is counted instead of silently
    /// dropped on the floor, same as `replay_data_trailing_bytes` in the main
    /// pass.
    pub trailing_bytes: u64,
    pub guid_entries: u64,
    pub group_records: u64,
    pub exported_fields: u64,
    /// DemoFrames walked, as `iter_demo_frames` actually counted them -- not
    /// assumed to be one per chunk.
    pub frames: u64,
    pub packets: u64,
    pub field_rows: u64,
    pub actor_rows_written: u64,
    pub net_guid_rows_written: u64,
    pub block_rows_written: u64,
    pub partial_rows: u64,
    pub partial_bits: u64,
    /// Actor rows are written to their checkpoint-scoped table. This retained
    /// counter remains explicit so a future discard path cannot be silent.
    pub actor_rows_dropped: u64,
    pub movement_rows_dropped: u64,
    /// Everything the checkpoint sinks counted.
    ///
    /// Kept separately from the ReplayData pass's totals, which the export
    /// baseline pins: mixing them would move a guarded figure by an amount that
    /// depends on a flag. Kept *at all* because the checkpoint sink is a second
    /// decode path, and a failure on it that reached no counter would be
    /// exactly the silent failure this project keeps finding.
    ///
    /// It used to be a hand-picked subset -- overlay, effect blobs, struct
    /// blobs, MultiContents -- and the ones left out were precisely the failure
    /// counters: array-decode errors, truncated RPCs and movement-decode
    /// errors. A checkpoint array that overran mid-element therefore wrote its
    /// parent raw row, lost its flattened children, and recorded nothing
    /// anywhere. Sharing [`SinkTotals`] with the main pass is what stops the
    /// two from drifting again.
    pub sink: SinkTotals,
    /// Replication/framing counters from every finalized checkpoint reader.
    pub net: NetStats,
}

pub(super) struct CheckpointWriters<W: Write + Send> {
    pub fields: CheckpointFieldWriter<W>,
    pub actors: CheckpointActorWriter<W>,
    pub net_guids: CheckpointNetGuidWriter<W>,
    pub blocks: CheckpointBlockWriter<W>,
}

impl<W: Write + Send> CheckpointWriters<W> {
    pub fn finish(self) -> Result<(), CliError> {
        self.fields.finish()?;
        self.actors.finish()?;
        self.net_guids.finish()?;
        self.blocks.finish()?;
        Ok(())
    }
}

/// Everything about the replay that the checkpoint pass needs and cannot
/// rediscover from the chunk alone.
pub(super) struct ReplayContext<'a> {
    pub branch: &'a str,
    pub flags: u32,
    pub compressed: bool,
    pub encrypted: bool,
}

/// Decode one Checkpoint chunk and write its field rows.
///
/// `error_report` is the *shared* one: a decode error is a decode error
/// wherever it happened, and the breakdown the summary prints is the only place
/// a checkpoint-only failure would ever be seen.
pub(super) fn process_chunk<W: Write + Send, P: Write + Send>(
    payload: &[u8],
    ctx: &ReplayContext<'_>,
    writers: &mut CheckpointWriters<W>,
    stats: &mut CheckpointStats,
    error_report: &mut OverlayErrorReport,
    partial_writer: &mut PartialWriter<P>,
) -> Result<(), CliError> {
    let cp = parse_checkpoint_chunk(payload)?;
    stats.trailing_bytes += cp.trailing_bytes as u64;
    let plain = decompress_checkpoint(cp.archive, ctx.compressed, ctx.encrypted)?;

    let mut cache = NetGuidCache::new();
    let tables = read_checkpoint_tables(&plain, &mut cache)
        .map_err(|e| CliError::Usage(format!("checkpoint {}: {e}", cp.id)))?;
    let checkpoint_index = u32::try_from(stats.chunks)
        .map_err(|_| CliError::Usage("too many checkpoint chunks to index".to_owned()))?;
    let checkpoint = CheckpointIdentity {
        checkpoint_index,
        checkpoint_id: cp.id.clone().into(),
    };

    let frame = &plain[tables.frame_offset..];
    let mut reader = ReplicationReader::new(ctx.branch)
        .map_err(|e| CliError::Usage(format!("unsupported branch: {e}")))?;
    let mut channels = ChannelState::new();
    let mut buffers = RecordBuffers::default();
    let mut packet_count = 0u64;
    let mut block_count = 0u32;
    let mut packet_error = None;
    let (_, frame_count) = iter_demo_frames(frame, ctx.flags, &mut cache, |pkt, packet_cache| {
        if packet_error.is_some() {
            return;
        }
        {
            let mut sink = ExportSink::new(packet_cache, &mut channels, &mut buffers);
            sink.enable_measured_array_routes(ctx.branch);
            sink.enable_checkpoint_block_context(checkpoint.clone(), stats.field_rows, block_count);
            sink.time_ms = pkt.time_ms;
            sink.packet_id = packet_count as u32;
            reader.process_packet(pkt.data, packet_count as i32, &mut sink);
            // Same aggregation the ReplayData pass uses, so the two cannot
            // diverge on which counters they bother to read. See `totals`.
            stats.sink.absorb(&mut sink.stats, error_report);
        }
        let result = (|| -> Result<(), CliError> {
            let packet_blocks = buffers.checkpoint_blocks.len() as u32;
            stats.block_rows_written += u64::from(packet_blocks);
            writers
                .blocks
                .push_batch(buffers.checkpoint_blocks.drain(..))?;
            block_count += packet_blocks;
            stats.field_rows += buffers.fields.len() as u64;
            writers
                .fields
                .push_batch(buffers.fields.drain(..).map(|field| CheckpointFieldRecord {
                    checkpoint: checkpoint.clone(),
                    field,
                }))?;
            stats.actor_rows_written += buffers.actors.len() as u64;
            writers
                .actors
                .push_batch(buffers.actors.drain(..).map(|actor| CheckpointActorRecord {
                    checkpoint: checkpoint.clone(),
                    actor,
                }))?;
            stats.movement_rows_dropped += buffers.movement.len() as u64;
            buffers.movement.clear();
            for mut record in buffers.partials.drain(..) {
                stats.partial_rows += 1;
                stats.partial_bits += record.bit_count;
                record.source = "checkpoint";
                record.checkpoint_id = Some(cp.id.clone());
                partial_writer.push(record)?;
            }
            Ok(())
        })();
        if let Err(error) = result {
            packet_error = Some(error);
        }
        packet_count += 1;
    })?;
    if let Some(error) = packet_error {
        return Err(error);
    }
    {
        let mut sink = ExportSink::new(&mut cache, &mut channels, &mut buffers);
        sink.enable_measured_array_routes(ctx.branch);
        sink.enable_checkpoint_block_context(checkpoint.clone(), stats.field_rows, block_count);
        reader.finish_with_sink(&mut sink);
    }
    stats.block_rows_written += buffers.checkpoint_blocks.len() as u64;
    writers
        .blocks
        .push_batch(buffers.checkpoint_blocks.drain(..))?;
    for mut record in buffers.partials.drain(..) {
        stats.partial_rows += 1;
        stats.partial_bits += record.bit_count;
        record.source = "checkpoint";
        record.checkpoint_id = Some(cp.id.clone());
        partial_writer.push(record)?;
    }
    let mut chunk_net = reader.stats().clone();
    stats.net.absorb(&mut chunk_net);

    let mut guid_entries = cache.net_guid_entries();
    guid_entries.sort_unstable_by_key(|entry| entry.net_guid);
    stats.net_guid_rows_written += guid_entries.len() as u64;
    writers
        .net_guids
        .push_batch(
            guid_entries
                .into_iter()
                .map(|entry| CheckpointNetGuidRecord {
                    checkpoint: checkpoint.clone(),
                    net_guid: NetGuidRecord {
                        net_guid: entry.net_guid,
                        path: entry.path.to_owned(),
                        outer_net_guid: entry.outer_net_guid,
                    },
                }),
        )?;

    stats.chunks += 1;
    stats.guid_entries += u64::from(tables.guid_count);
    stats.group_records += u64::from(tables.group_count);
    stats.exported_fields += u64::from(tables.exported_fields);
    // The actual DemoFrame count `iter_demo_frames` walked, not an assumed
    // one-per-chunk. `tools/check_export_baseline.py`'s `cp_frames`/`cp_chunks`
    // pin used to be a tautology -- always equal, because this line always
    // added exactly 1 -- which could not have caught a build whose checkpoint
    // carries more than one DemoFrame.
    stats.frames += u64::from(frame_count);
    stats.packets += packet_count;
    Ok(())
}
