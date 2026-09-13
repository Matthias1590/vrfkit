namespace Replay.Valorant.Descriptors.Agents.Aggrobot;

/// <summary>
/// Gekko
/// </summary>
public sealed class AggrobotAgentDescriptor : GenericAgentDescriptor
{
    // Capital B in "AggroBot": Riot mixes casing inside Gekko's own content --
    // the sub-assets are lowercase (Ability_Aggrobot_C_ExplodeyPatch) but the
    // character directory and asset are not. Path lookup is Ordinal
    // (DescriptorCatalogIndex.cs:7, BoundExportStore.cs:5), so the lowercase
    // spelling matched nothing: Gekko's replicated character properties and his
    // MulticastNotifyKilledEnemy went unbound in every match he appeared in,
    // and the export summary reported the group as was_decoded: false.
    // Confirmed against the replays: every path they declare is "AggroBot".
    public override string Path => "/Game/Characters/AggroBot/AggroBot_PC.AggroBot_PC_C";
}
