import contextlib,copy,io,os,sys,tempfile,unittest
from pathlib import Path
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import section_timeline as strict_tool
import section_packet_timeline as tool
import extract_section_packet_timeline as cli

def obs(i,time,packet,value=80.0,ref=9):return {"route":"MulticastNotifyHeal","identity":{"time_ms":time,"packet_id":packet,"channel_index":1,"actor_net_guid":1,"object_net_guid":2},"source_rows":[{"physical_row_ordinal":i}],"schema_errors":[],"ambiguity_reasons":[],"raw_lifecycle_tokens":{},"section_state":{"status":"validated_array","sections":[{"index":0,"changed_component_ref":ref,"changed_component_path":None,"life_result":value,"delta_life":5.0,"alive_after_change":True}],"relation":{"matches":True}}}
def event(i,time,packet,kind="open",actor=1,channel=1):return (i,{"time_ms":time,"packet_id":packet,"channel_index":channel,"actor_net_guid":actor,"event":kind,"class_path":"x"})
def run(observations,events=None):
 events=events or [event(0,0,0)];raw={"observations":observations};strict=strict_tool.build(raw,events);return strict,tool.build(strict,events)
class PacketTests(unittest.TestCase):
 def test_distinct_increasing_packets_resolve_same_ms(self):
  strict,result=run([obs(1,10,1,75),obs(2,10,2,80)]);n=result["nodes"][-1];self.assertFalse(strict["nodes"][-1]["continuity"]["eligible"]);self.assertTrue(n["packet_view"]["eligible"]);self.assertEqual(result["packet_counts"]["resolved_from_strict_ineligible"],1)
 def test_same_packet_states_remain_unresolved(self):
  _,r=run([obs(1,10,2,75),obs(2,11,2,80)]);self.assertTrue(all("same_packet_tie" in n["packet_view"]["reasons"] for n in r["nodes"]))
 def test_prior_packet_tie_censors_next(self):
  _,r=run([obs(1,10,2),obs(2,10,2),obs(3,11,3)]);self.assertIn("prior_packet_tie_censor",r["nodes"][-1]["packet_view"]["reasons"])
 def test_same_packet_actor_boundary_unresolved(self):
  _,r=run([obs(1,10,2)], [event(0,0,0),event(2,10,2,"close")]);self.assertEqual(r["nodes"][0]["packet_view"]["actor_lifecycle"]["actor_status"],"same_packet_boundary")
 def test_lifecycle_same_ms_different_packet_resolves(self):
  _,r=run([obs(2,10,2)],[event(0,10,1)]);self.assertEqual(r["nodes"][0]["packet_view"]["actor_lifecycle"]["status"],"active")
 def test_future_trace_reopen_defect_rejected_globally(self):
  _,r=run([obs(1,1,1)],[event(0,0,0),event(5,5,5)]);self.assertEqual(r["nodes"][0]["packet_view"]["actor_lifecycle"]["actor_status"],"reopen_without_close")
 def test_packet_endpoint_open_identity_changes(self):
  _,r=run([obs(1,1,1),obs(4,4,4)],[event(0,0,0),event(2,2,2,"close"),event(3,3,3)]);self.assertIn("packet_actor_channel_instance_changed",r["nodes"][-1]["packet_view"]["reasons"])
 def test_checkpoint_population_rejected(self):
  strict=strict_tool.build({"observations":[obs(1,1,1)]},[event(0,0,0)])
  with self.assertRaises(ValueError):tool.build(strict,[event(0,0,0)],population="checkpoint")
 def test_strict_output_projection_is_exact(self):
  strict,r=run([obs(1,1,1),obs(2,2,2)]);projected=copy.deepcopy(r);projected.pop("packet_counts");projected.pop("strict_counts_retained");projected["schema_version"]=strict.get("schema_version");projected["kind"]=strict.get("kind")
  if projected["schema_version"] is None:projected.pop("schema_version")
  if projected["kind"] is None:projected.pop("kind")
  for node in projected["nodes"]:node.pop("packet_view")
  self.assertEqual(projected,strict)
 def test_channel_takeover_rejected(self):
  _,r=run([obs(3,10,3)],[event(0,0,0),event(1,1,1,actor=4)]);self.assertEqual(r["nodes"][0]["packet_view"]["actor_lifecycle"]["channel_status"],"reopen_without_close")
 def test_packet_regression_and_duplicate_rejected(self):
  for rows in ([event(0,0,2),event(1,1,1,"close")],[event(0,0,1),event(1,1,1,"close")]):
   with self.subTest(rows=rows):self.assertEqual(tool.active_at_packet(rows,{"packet_id":3,"actor_net_guid":1,"channel_index":1})[1],"packet_clock_duplicate_or_regression")
 def test_close_owner_conflict_rejected(self):
  rows=[event(0,0,0),event(1,1,1,"close",actor=4)];self.assertEqual(tool.active_at_packet(rows,{"packet_id":2,"actor_net_guid":1,"channel_index":1})[1],"close_identity_mismatch")
 def test_other_strict_barriers_persist(self):
  strict,r=run([obs(1,1,1),obs(2,2,2)]);strict["nodes"][1]["continuity"]["reasons"]=["opaque_token_gap"];strict["nodes"][1]["continuity"]["eligible"]=False;r=tool.build(strict,[event(0,0,0)]);self.assertIn("opaque_token_gap",r["nodes"][1]["packet_view"]["reasons"])
 def test_input_strict_object_unchanged(self):
  events=[event(0,0,0)];strict=strict_tool.build({"observations":[obs(1,1,1),obs(2,2,2)]},events);before=copy.deepcopy(strict);tool.build(strict,events);self.assertEqual(strict,before)
 def test_zero_inclusive_counters_present(self):
  _,r=run([obs(1,1,1,75),obs(2,2,2,80)]);self.assertEqual(r["packet_counts"]["packet_view_eligible_arithmetic_true"],1);self.assertIn("packet_view_eligible_arithmetic_false",r["packet_counts"]);self.assertEqual(r["packet_counts"]["packet_view_eligible_arithmetic_false"],0);self.assertIn("continuity_eligible_arithmetic_unknown",r["strict_counts_retained"])
 def test_arithmetic_false_counter_moves(self):
  _,r=run([obs(1,1,1,75),obs(2,2,2,81)]);self.assertEqual(r["packet_counts"]["packet_view_arithmetic_false"],1);self.assertEqual(r["packet_counts"]["packet_view_eligible_arithmetic_false"],1)
 def test_game_and_component_life_unproved(self):
  _,r=run([obs(1,1,1)]);p=r["nodes"][0]["packet_view"];self.assertEqual((p["game_life"],p["component_life"]),("unproved","unproved"))
 def test_cli_helpers_include_transitive_sources(self):
  names={p.name for p in cli.helpers()};self.assertTrue({"extract_section_packet_timeline.py","section_packet_timeline.py","extract_section_timeline.py","section_timeline.py","extract_section_observations.py","atomic_io.py"}<=names)
 def test_cli_rejects_export_file_and_hardlink_alias(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);export=root/"export";export.mkdir();source=export/"fields.parquet";source.write_bytes(b"x");alias=root/"alias";os.link(source,alias)
   for out in (source,alias):
    with contextlib.redirect_stderr(io.StringIO()) as err:self.assertEqual(cli.main(["--export",str(export),"--out",str(out)]),1)
    self.assertIn("aliases",err.getvalue())
 def test_atomic_failure_preserves_destination(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);export=root/"export";export.mkdir();out=root/"out.json";out.write_text("old")
   with mock.patch.object(cli,"extract",return_value={"counts":{"nodes":0},"packet_counts":{"eligible":0,"resolved_from_strict_ineligible":0}}),mock.patch.object(cli,"atomic_write_text",side_effect=OSError("boom")),contextlib.redirect_stderr(io.StringIO()):self.assertEqual(cli.main(["--export",str(export),"--out",str(out)]),1)
   self.assertEqual(out.read_text(),"old")
if __name__=="__main__":unittest.main()
