using Replay.Models.Descriptors;
using Replay.Models.Unreal;
using Replay.Unreal.Parsing;

namespace Replay.Valorant.Descriptors.Agents.Smonk;

// Clove's ability actors. Every field type below is copied from a descriptor
// that already declares the same wire name, not inferred:
//   Owner / Instigator            GenericAgentDescriptor, MageWallDescriptor
//   ReplicatedMovement            MageWall / NeonTunnel (ByteComponents) or
//                                 DarkCover / CoveAbility (default Short)
//   every AActor/APawn property   GenericAgentDescriptor
//
// The rotator quantization is not on the wire; it is a per-class descriptor
// choice, and a wrong choice makes the strict overlay decoder read past the
// end of the payload or leave bits behind. Each class below records which of
// the two the replay's own bit widths admit -- and where they admit both, says
// so rather than claiming the wire chose.

/// <summary>
/// Clove's post-death pawn. Wire fields on release-13.01 are exactly the
/// GenericAgentDescriptor set: bReplicateMovement(1), Owner/Instigator/
/// PlayerState/Controller(16-24, IntPacked), ReplayLastTransformUpdateTimeStamp
/// (32), ReplicatedGravityDirection(48), ReplicatedMovementMode(8),
/// bCrouchHeld(1). Categories is Ability rather than Agent because
/// AgentClassNetCacheDescriptors builds a MulticastNotifyKilledEnemy cache for
/// every Agent-category path and this pawn declares no such cache.
/// </summary>
public sealed class SmonkPostDeathPawnDescriptor : GenericAgentDescriptor
{
    public override string Path => "/Game/Characters/Smonk/Smonk_PostDeath_PC.Smonk_PostDeath_PC_C";
    public override ExportCategory Categories => ExportCategory.Ability;
}

/// <summary>
/// Clove's E smoke volume. Rotation is never replicated on this class (0 of
/// 1797 payloads set any rotator flag on 02d4d478, and flipping the whole
/// 215-replay corpus to ByteComponents leaves every overlay counter identical
/// and the reference replay's fields.parquet byte-identical), so the two
/// readings consume the same bits and decode the same values. The choice is
/// unobservable here; the builder default is taken.
///
/// Do not read that as "the smoke descriptors all take the default". Of the
/// three siblings, DarkCoverAbilityDescriptor (Omen) takes Short but is itself
/// unobservable -- 0 of 7007 payloads set a rotator flag; CoveAbilityDescriptor
/// (Astra) takes Short and is contradicted by nothing in the corpus, but Astra
/// does not appear in the reference replay; and ProjectileSmokeScreenDescriptor
/// (Viper) takes Short and is WRONG -- vrfkit's apply_type_corrections.py
/// rewrites it to ByteComponents because a Short read runs off the end of 137
/// payloads. So the precedent is genuinely split, and if these classes ever do
/// replicate a rotation, that correction is the one to look at first.
/// </summary>
public sealed class SmonkNewSmokeDescriptor : ExportGroupDescriptor<SmonkNewSmokeDescriptor>
{
    public override string Path =>
        "/Game/Characters/Smonk/S0/Ability_E/MapTargetSmoke/GameObject_Smonk_NewSmoke.GameObject_Smonk_NewSmoke_C";
    public override ExportCategory Categories => ExportCategory.Ability;
    public override ExportGroupKind Kind => ExportGroupKind.Actor;

    public uint Owner { get; set; }
    public uint Instigator { get; set; }
    public FRepMovement ReplicatedMovement { get; set; }

    protected override void Configure()
    {
        AddProperty(x => x.Owner).ObjectNetGuid();
        AddProperty(x => x.Instigator).ObjectNetGuid();
        AddProperty(x => x.ReplicatedMovement).ReplicatedMovement();
    }
}

/// <summary>
/// The post-death variant of the same smoke volume. Same reasoning as
/// <see cref="SmonkNewSmokeDescriptor"/>: 0 of 408 payloads set a rotator flag.
/// </summary>
public sealed class SmonkNewSmokePdsDescriptor : ExportGroupDescriptor<SmonkNewSmokePdsDescriptor>
{
    public override string Path =>
        "/Game/Characters/Smonk/S0/Ability_E/MapTargetSmoke/GameObject_Smonk_NewSmoke_PDS.GameObject_Smonk_NewSmoke_PDS_C";
    public override ExportCategory Categories => ExportCategory.Ability;
    public override ExportGroupKind Kind => ExportGroupKind.Actor;

    public uint Owner { get; set; }
    public uint Instigator { get; set; }
    public FRepMovement ReplicatedMovement { get; set; }

    protected override void Configure()
    {
        AddProperty(x => x.Owner).ObjectNetGuid();
        AddProperty(x => x.Instigator).ObjectNetGuid();
        AddProperty(x => x.ReplicatedMovement).ReplicatedMovement();
    }
}

/// <summary>
/// Clove's Q decay projectile. ByteComponents: on 02d4d478 all 127 payloads
/// consume exactly with byte-wide rotator axes and 58 of them cannot be read
/// at all with short-wide axes (52 EOF, 6 residual).
/// </summary>
public sealed class SmonkDecayNadeDescriptor : ExportGroupDescriptor<SmonkDecayNadeDescriptor>
{
    public override string Path =>
        "/Game/Characters/Smonk/S0/Ability_Q/DebuffKnife/DecayLauncher/Projectile_Smonk_DecayNade.Projectile_Smonk_DecayNade_C";
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
/// The explosion volume the decay projectile leaves behind. Rotation is never
/// replicated (0 of 7 payloads set a rotator flag), so the quantization is
/// unobservable; the builder default is used, as for the smoke volumes. See
/// SmonkNewSmokeDescriptor for why the sibling descriptors are not the
/// tiebreaker they look like.
/// </summary>
public sealed class SmonkDecayExplosionDescriptor : ExportGroupDescriptor<SmonkDecayExplosionDescriptor>
{
    public override string Path =>
        "/Game/Characters/Smonk/S0/Ability_Q/DebuffKnife/DecayLauncher/GameObject_Smonk_Q_DecayExplosion.GameObject_Smonk_Q_DecayExplosion_C";
    public override ExportCategory Categories => ExportCategory.Ability;
    public override ExportGroupKind Kind => ExportGroupKind.Actor;

    public uint Owner { get; set; }
    public uint Instigator { get; set; }
    public FRepMovement ReplicatedMovement { get; set; }

    protected override void Configure()
    {
        AddProperty(x => x.Owner).ObjectNetGuid();
        AddProperty(x => x.Instigator).ObjectNetGuid();
        AddProperty(x => x.ReplicatedMovement).ReplicatedMovement();
    }
}
