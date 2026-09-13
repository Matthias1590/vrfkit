using Replay.Models.Descriptors;
using Replay.Models.Unreal;
using Replay.Unreal.Parsing;

namespace Replay.Valorant.Descriptors.Agents.Aggrobot;

// Gekko's ability actors. Paths use the mixed casing Riot ships and the
// replays declare: directory "AggroBot" with a capital B, asset names
// "Aggrobot" with a lowercase b. See AggrobotAgentDescriptor for the incident
// that made that distinction load-bearing.

/// <summary>
/// Gekko's Wingman pawn. Wire fields are the GenericAgentDescriptor set plus a
/// ReplicatedMovement, which the shared base does not declare -- so this one
/// spells the fields out rather than inheriting them. Every (name, type) pair
/// below is copied from an existing descriptor: the AActor/APawn properties
/// from GenericAgentDescriptor, ReplicatedMovement from
/// DarkCoverAbilityDescriptor.
///
/// ShortComponents, and here the wire settles it: all 6 payloads on 02d4d478
/// consume exactly with short-wide rotator axes and 4 run off the end with
/// byte-wide ones. This is the only class in the set that reads as Short with
/// the discriminator live.
///
/// bAIControlled, "Started Planting" and SeekingActive are on the wire (1 bit
/// each) but no existing descriptor declares them, so they are deliberately
/// left undeclared rather than guessed.
/// </summary>
public sealed class AggrobotSeekerNadePawnDescriptor : ExportGroupDescriptor<AggrobotSeekerNadePawnDescriptor>
{
    public override string Path =>
        "/Game/Characters/AggroBot/S0/Ability_Q/Pawn_Aggrobot_SeekerNade.Pawn_Aggrobot_SeekerNade_C";
    public override ExportCategory Categories => ExportCategory.Ability;
    public override ExportGroupKind Kind => ExportGroupKind.Actor;

    public bool ReplicateMovement { get; set; }
    public uint Owner { get; set; }
    public uint Instigator { get; set; }
    public uint Controller { get; set; }
    public float ReplayLastTransformUpdateTimeStamp { get; set; }
    public FVector ReplicatedGravityDirection { get; set; }
    public uint ReplicatedMovementMode { get; set; }
    public FRepMovement ReplicatedMovement { get; set; }

    protected override void Configure()
    {
        AddProperty("bReplicateMovement", x => x.ReplicateMovement).Bool();
        AddProperty(x => x.Owner).ObjectNetGuid();
        AddProperty(x => x.Instigator).ObjectNetGuid();
        AddProperty(x => x.Controller).ObjectNetGuid();
        AddProperty(x => x.ReplayLastTransformUpdateTimeStamp).Ignore();
        AddProperty(x => x.ReplicatedGravityDirection).FVectorNetQuantizeNormal();
        AddProperty(x => x.ReplicatedMovementMode).Byte();
        AddProperty(x => x.ReplicatedMovement).ReplicatedMovement();
    }
}

/// <summary>
/// Gekko's Mosh Pit pawn. Wire fields are a subset of the
/// GenericAgentDescriptor set, with no ReplicatedMovement.
/// </summary>
public sealed class AggrobotRollyPollyPawnDescriptor : GenericAgentDescriptor
{
    public override string Path =>
        "/Game/Characters/AggroBot/S0/Ability_X/Pawn_Aggrobot_RollyPolly.Pawn_Aggrobot_RollyPolly_C";
    public override ExportCategory Categories => ExportCategory.Ability;
}

/// <summary>
/// Dizzy's power wave. ByteComponents: 342 of 342 exact, 211 short-wide
/// failures (204 EOF, 7 residual).
/// </summary>
public sealed class AggrobotDiscTurretPowerWaveDescriptor
    : ExportGroupDescriptor<AggrobotDiscTurretPowerWaveDescriptor>
{
    public override string Path =>
        "/Game/Characters/AggroBot/S0/Ability_E/Projectile_E_Aggrobot_DiscTurret_PowerWave.Projectile_E_Aggrobot_DiscTurret_PowerWave_C";
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
/// Dizzy's orb spawner. ByteComponents: 172 of 172 exact, 86 short-wide
/// failures (81 EOF, 5 residual).
/// </summary>
public sealed class AggrobotOrbSpawnerDescriptor : ExportGroupDescriptor<AggrobotOrbSpawnerDescriptor>
{
    public override string Path =>
        "/Game/Characters/AggroBot/S0/Ability_E/Projectile_E_Aggrobot_OrbSpawner.Projectile_E_Aggrobot_OrbSpawner_C";
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
/// Thrash's rocket. ByteComponents: 32 of 32 exact, 6 short-wide EOF failures.
/// </summary>
public sealed class AggrobotZamboniRocketDescriptor : ExportGroupDescriptor<AggrobotZamboniRocketDescriptor>
{
    public override string Path =>
        "/Game/Characters/AggroBot/S0/Ability_E/Projectile_Aggrobot_Zamboni_Rocket.Projectile_Aggrobot_Zamboni_Rocket_C";
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
/// Mosh Pit's explodey patch projectile. ByteComponents: 23 of 23 exact,
/// 9 short-wide residual failures.
/// </summary>
public sealed class AggrobotExplodeyPatchDescriptor : ExportGroupDescriptor<AggrobotExplodeyPatchDescriptor>
{
    public override string Path =>
        "/Game/Characters/AggroBot/S0/Ability_4/Projectile_Aggrobot_C_ExplodeyPatch.Projectile_Aggrobot_C_ExplodeyPatch_C";
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
