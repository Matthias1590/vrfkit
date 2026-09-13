using Replay.Models.Descriptors;
using Replay.Models.Unreal;
using Replay.Unreal.Parsing;

namespace Replay.Valorant.Descriptors.Agents.Wraith;

// Omen's projectiles. DarkCoverAbilityDescriptor already covers the smoke
// ZONE these projectiles land into; these two are the projectiles themselves,
// and unlike the zone their rotation IS replicated, which is what makes the
// quantization observable.

/// <summary>
/// Omen's Dark Cover projectile. ByteComponents: 410 of 410 exact, 247
/// short-wide failures (202 EOF, 45 residual).
/// </summary>
public sealed class WraithSmokeProjectileDescriptor : ExportGroupDescriptor<WraithSmokeProjectileDescriptor>
{
    public override string Path =>
        "/Game/Characters/Wraith/S0/Ability_4/Projectile_Wraith_4_Smoke.Projectile_Wraith_4_Smoke_C";
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
/// Omen's Paranoia missile. ByteComponents: 154 of 154 exact, 70 short-wide
/// failures (56 EOF, 14 residual).
/// </summary>
public sealed class WraithNearsightMissileDescriptor : ExportGroupDescriptor<WraithNearsightMissileDescriptor>
{
    public override string Path =>
        "/Game/Characters/Wraith/S0/Ability_Q/Projectile_Wraith_Q_NearsightMissile.Projectile_Wraith_Q_NearsightMissile_C";
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
