using Replay.Models.Descriptors;
using Replay.Models.Unreal;
using Replay.Unreal.Parsing;

namespace Replay.Valorant.GameState;

// Dropped/pickupable weapons on the ground. These are actors (inherit from
// AProjectile / AAresDroppedEquippable), so they carry ReplicatedMovement and
// the anonymous 215/216 bookkeeping fields. Handles verified against the replay
// manifest (build 13.01); types from the Valorant SDK dump
// (EquippablePickupProjectile_classes.h, AresDroppedEquippable).

// AAresDroppedEquippable projected as a physics projectile while in flight,
// then becomes a ground pickup. Tracks the weapon it carries + who dropped it.
public sealed class EquippablePickupProjectileDescriptor
    : ExportGroupDescriptor<EquippablePickupProjectileDescriptor>
{
    public override string Path =>
        "/Game/Weapons/WeaponPickups/EquippablePickupProjectile.EquippablePickupProjectile_C";
    public override ExportCategory Categories => ExportCategory.Inventory;
    public override ExportGroupKind Kind => ExportGroupKind.Actor;

    public int A { get; set; }   // "216"
    public FRepMovement ReplicatedMovement { get; set; }
    public int B { get; set; }   // "215"
    // The weapon this projectile is carrying (AAresEquippable*).
    public uint MyEquippable { get; set; }

    protected override void Configure()
    {
        AddProperty("216", x => x.A).Int32();
        AddProperty(x => x.ReplicatedMovement)
            .ReplicatedMovement(ERotatorQuantization.ByteComponents);
        AddProperty("215", x => x.B).Int32();
        AddProperty(x => x.MyEquippable).ObjectNetGuid();
    }
}

// The resting ground pickup variant. Carries the weapon + the last owner.
public sealed class EquippableGroundPickupDescriptor
    : ExportGroupDescriptor<EquippableGroundPickupDescriptor>
{
    public override string Path =>
        "/Game/Weapons/WeaponPickups/EquippableGroundPickup.EquippableGroundPickup_C";
    public override ExportCategory Categories => ExportCategory.Inventory;
    public override ExportGroupKind Kind => ExportGroupKind.Actor;

    public int A { get; set; }   // "216"
    public int B { get; set; }   // "215"
    // The weapon on the ground (AAresEquippable*).
    public uint MyEquippable { get; set; }
    // The last player who held this weapon (AShooterCharacter*).
    public uint LastOwner { get; set; }

    protected override void Configure()
    {
        AddProperty("216", x => x.A).Int32();
        AddProperty("215", x => x.B).Int32();
        AddProperty(x => x.MyEquippable).ObjectNetGuid();
        AddProperty(x => x.LastOwner).ObjectNetGuid();
    }
}
