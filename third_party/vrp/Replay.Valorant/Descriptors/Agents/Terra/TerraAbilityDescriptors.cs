using Replay.Models.Descriptors;
using Replay.Models.Unreal;
using Replay.Unreal.Parsing;

namespace Replay.Valorant.Descriptors.Agents.Terra;

/// <summary>
/// Chamber's Trademark-style slow grenade projectile. ByteComponents:
/// 76 of 76 exact, 27 short-wide EOF failures.
/// </summary>
public sealed class TerraTimeSlowGrenadeDescriptor : ExportGroupDescriptor<TerraTimeSlowGrenadeDescriptor>
{
    public override string Path =>
        "/Game/Characters/Terra/S0/Ability_4/Projectile_Terra_C_TimeSlowGrenade.Projectile_Terra_C_TimeSlowGrenade_C";
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
/// The slow field the grenade leaves behind. ByteComponents, and unlike the
/// other stationary volumes in this change the discriminator IS live here:
/// all 7 payloads set a rotator flag, 7 of 7 consume exactly with byte-wide
/// axes and all 7 run off the end with short-wide axes.
/// </summary>
public sealed class TerraTimeSlowExplosionDescriptor : ExportGroupDescriptor<TerraTimeSlowExplosionDescriptor>
{
    public override string Path =>
        "/Game/Characters/Terra/S0/Ability_4/GameObject_Terra_C_TimeSlowGrenade_Explosion.GameObject_Terra_C_TimeSlowGrenade_Explosion_C";
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
