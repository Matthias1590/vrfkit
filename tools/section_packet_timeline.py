"""Packet-resolved companion view for an accepted strict section timeline."""
from __future__ import annotations
import collections, copy

REMOVED_STRICT_REASONS={"same_time_tie","prior_tie_censor","lifecycle_unresolved","prior_lifecycle_unresolved","actor_channel_instance_changed"}

def traces(rows):
 actors,channels=collections.defaultdict(list),collections.defaultdict(list)
 for ordinal,row in rows:
  if row.get("event") in ("open","close"):
   item=(ordinal,dict(row));actors[row["actor_net_guid"]].append(item);channels[row["channel_index"]].append(item)
 return actors,channels

def active_at_packet(history,coordinate):
 """Resolve main-packet state; events in the observation packet are unordered."""
 last=None;active=None;reason=None
 for ordinal,row in history:
  packet=row.get("packet_id")
  if packet is None:return None,"missing_packet_clock"
  if last is not None and packet<=last:return None,"packet_clock_duplicate_or_regression"
  last=packet
  if packet==coordinate["packet_id"]:reason="same_packet_boundary"
  if row["event"]=="open":
   if active is not None:return None,"reopen_without_close"
   active={**row,"physical_row_ordinal":ordinal}
  elif row["event"]=="close":
   if active is None:return None,"close_without_open"
   if any(active[k]!=row[k] for k in ("actor_net_guid","channel_index")):return None,"close_identity_mismatch"
   active=None
 # Full-trace validity above is deliberate; now replay only the strict prefix.
 if reason:return None,reason
 active=None
 for ordinal,row in history:
  if row["packet_id"]>=coordinate["packet_id"]:break
  if row["event"]=="open":active={**row,"physical_row_ordinal":ordinal}
  else:active=None
 if active is None:return None,"no_active_actor"
 if any(active[k]!=coordinate[k] for k in ("actor_net_guid","channel_index")):return None,"active_identity_mismatch"
 return active,"active"

def packet_lifetime(actors,channels,coordinate):
 actor,a_status=active_at_packet(actors.get(coordinate["actor_net_guid"],[]),coordinate)
 channel,c_status=active_at_packet(channels.get(coordinate["channel_index"],[]),coordinate)
 matched=actor is not None and channel is not None and actor==channel
 return {"status":"active" if matched else "unresolved","actor_status":a_status,"channel_status":c_status,"actor_open":actor,"channel_open":channel}

def _arithmetic_counts(nodes,key):
 out={f"{key}_arithmetic_true":0,f"{key}_arithmetic_false":0,f"{key}_arithmetic_unknown":0,f"{key}_eligible_arithmetic_true":0,f"{key}_eligible_arithmetic_false":0,f"{key}_eligible_arithmetic_unknown":0}
 for node in nodes:
  value=node["route_arithmetic"]["matches"];suffix="true" if value is True else "false" if value is False else "unknown";out[f"{key}_arithmetic_{suffix}"]+=1
  if node[key]["eligible"] and value is True:out[f"{key}_eligible_arithmetic_true"]+=1
  if node[key]["eligible"] and value is False:out[f"{key}_eligible_arithmetic_false"]+=1
  if node[key]["eligible"] and value is None:out[f"{key}_eligible_arithmetic_unknown"]+=1
 return out

def build(strict,actor_rows,population="main"):
 """Retain strict data and add packet-only comparison evidence."""
 if population!="main":raise ValueError("packet timeline requires main population")
 result=copy.deepcopy(strict);actors,channels=traces(actor_rows);nodes=result["nodes"]
 packet_counts=collections.Counter();time_groups=collections.defaultdict(list)
 for n in nodes:
  c=n["origin"]["coordinate"];k=n["state_key"];packet_counts[(k["actor_net_guid"],k["object_net_guid"],k["changed_component_ref"],c["packet_id"])]+=1
  time_groups[(k["actor_net_guid"],k["object_net_guid"],k["changed_component_ref"],c["time_ms"])].append(c["packet_id"])
 by_id={tuple(n["node_id"]):n for n in nodes}
 for node in nodes:
  c=node["origin"]["coordinate"];k=node["state_key"];life=packet_lifetime(actors,channels,c);prior=by_id.get(tuple(node["previous_node_id"])) if node["previous_node_id"] else None
  removed=sorted(x for x in node["continuity"]["reasons"] if x in REMOVED_STRICT_REASONS);reasons=[x for x in node["continuity"]["reasons"] if x not in REMOVED_STRICT_REASONS]
  tied=packet_counts[(k["actor_net_guid"],k["object_net_guid"],k["changed_component_ref"],c["packet_id"])]>1
  if tied:reasons.append("same_packet_tie")
  if prior and prior.get("packet_view",{}).get("same_packet_tie"):reasons.append("prior_packet_tie_censor")
  if life["status"]!="active":reasons.append("packet_lifecycle_unresolved")
  if prior:
   plife=prior["packet_view"]["actor_lifecycle"]
   if plife["status"]!="active":reasons.append("prior_packet_lifecycle_unresolved")
   elif life["status"]=="active" and plife!=life:reasons.append("packet_actor_channel_instance_changed")
   pc=prior["origin"]["coordinate"]
   if c["packet_id"]<=pc["packet_id"]:reasons.append("nonincreasing_packet")
  reasons=sorted(set(reasons))
  packets=time_groups[(k["actor_net_guid"],k["object_net_guid"],k["changed_component_ref"],c["time_ms"])];group={"group_size":len(packets),"same_packet":len(set(packets))<len(packets),"packets":sorted(packets)}
  node["packet_view"]={"eligible":not reasons,"reasons":reasons,"removed_strict_reasons":removed,"scope":"main_packet_ordered_observation_comparison_only","game_life":"unproved","component_life":"unproved","same_packet_tie":tied,"actor_lifecycle":life,"actor_channel_lifecycle":life,"predecessor_lifecycle":prior["packet_view"]["actor_channel_lifecycle"] if prior else None,"same_time_group":group,"predecessor_same_time_group":prior["packet_view"]["same_time_group"] if prior else None,"strict_previous_node_id":node["previous_node_id"],"arithmetic_matches":node["route_arithmetic"]["matches"]}
 strict_counts={"eligible":sum(n["continuity"]["eligible"] for n in nodes),"ineligible":sum(not n["continuity"]["eligible"] for n in nodes)}
 packet_summary={"eligible":sum(n["packet_view"]["eligible"] for n in nodes),"ineligible":sum(not n["packet_view"]["eligible"] for n in nodes),"resolved_from_strict_ineligible":sum(n["packet_view"]["eligible"] and not n["continuity"]["eligible"] for n in nodes)}
 packet_summary.update(_arithmetic_counts(nodes,"packet_view"));strict_counts.update(_arithmetic_counts(nodes,"continuity"))
 result["strict_counts_retained"]={**result["counts"],**strict_counts};result["packet_counts"]=packet_summary;result["schema_version"]=2;result["kind"]="vrfkit_section_packet_timeline"
 return result
