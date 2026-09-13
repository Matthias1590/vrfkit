using Replay.Models.Descriptors;
using Replay.Models.Unreal;
using Replay.Unreal.Parsing;

namespace Replay.Valorant.Descriptors.Agents.Hunter;

// Sova's ability actors. Field types are copied from descriptors that already
// declare the same wire names (GenericAgentDescriptor for the pawn properties,
// MageWall/NeonTunnel for the ByteComponents ReplicatedMovement).

/// <summary>
/// Sova's recon drone. Wire fields on release-13.01 are exactly the
/// GenericAgentDescriptor set. Categories is Ability rather than Agent so that
/// AgentClassNetCacheDescriptors does not fabricate a
/// MulticastNotifyKilledEnemy cache for a class that has none.
/// </summary>
public sealed class HunterDronePawnDescriptor : GenericAgentDescriptor
{
    public override string Path =>
        "/Game/Characters/Hunter/S0/Ability_E/Drone/Pawn_Hunter_E_Drone.Pawn_Hunter_E_Drone_C";
    public override ExportCategory Categories => ExportCategory.Ability;
}

/// <summary>
/// Sova's recon bolt. ByteComponents: all 486 payloads on 02d4d478 consume
/// exactly with byte-wide rotator axes; 225 fail with short-wide axes
/// (222 EOF, 3 residual).
/// </summary>
public sealed class HunterRevealBoltDescriptor : ExportGroupDescriptor<HunterRevealBoltDescriptor>
{
    public override string Path =>
        "/Game/Characters/Hunter/S0/Ability_Q/Projectile_Hunter_Q_RevealBolt.Projectile_Hunter_Q_RevealBolt_C";
    public override ExportCategory Categories => ExportCategory.Ability;
    public override ExportGroupKind Kind => ExportGroupKind.Actor;

    public FRepMovement ReplicatedMovement { get; set; }
    public uint Owner { get; set; }
    public uint Instigator { get; set; }

    protected override void Configure()
    {
        AddProperty(x => x.ReplicatedMovement)
            .ReplicatedMovement(ERotatorQuantization.ByteComponents);
        AddProperty(x => x.Owner).ObjectNetGuid();
        AddProperty(x => x.Instigator).ObjectNetGuid();
    }
}

/// <summary>
/// Sova's shock bolt. ByteComponents: 377 of 377 exact, 263 short-wide
/// failures (261 EOF, 2 residual).
/// </summary>
public sealed class HunterExplosiveBoltDescriptor : ExportGroupDescriptor<HunterExplosiveBoltDescriptor>
{
    public override string Path =>
        "/Game/Characters/Hunter/S0/Ability_4/Projectile_Hunter_4_ExplosiveBolt.Projectile_Hunter_4_ExplosiveBolt_C";
    public override ExportCategory Categories => ExportCategory.Ability;
    public override ExportGroupKind Kind => ExportGroupKind.Actor;

    public FRepMovement ReplicatedMovement { get; set; }
    public uint Owner { get; set; }
    public uint Instigator { get; set; }

    protected override void Configure()
    {
        AddProperty(x => x.ReplicatedMovement)
            .ReplicatedMovement(ERotatorQuantization.ByteComponents);
        AddProperty(x => x.Owner).ObjectNetGuid();
        AddProperty(x => x.Instigator).ObjectNetGuid();
    }
}
