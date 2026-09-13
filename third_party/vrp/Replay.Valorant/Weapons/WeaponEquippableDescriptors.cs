using Replay.Models.Descriptors;
using Replay.Models.Unreal;
using Replay.Unreal.Parsing;
using Replay.Valorant.Descriptors;

namespace Replay.Valorant.Weapons;

// Weapon actor bodies: the AAresEquippable-derived guns and melee that players
// hold (Vandal, Phantom, Ghost, etc.). These appear in replays as undecoded
// export groups. Investigation (build 13.01) showed the weapon bodies are NOT
// empty bookkeeping — they average 130-370 payload_bits per update and carry the
// replicated COSMETIC/LOADOUT state of the weapon: which skin, skin level,
// chroma, charm, and charm level are equipped, plus the owning data asset and
// attach/scene-component bookkeeping.
//
// IMPORTANT: the per-weapon GAMEPLAY state (ammo, charge, fire mode, alt-fire)
// is NOT on the weapon body — it lives on COMPONENTS attached to the weapon
// (AmmoComponent, EquipmentChargeComponent, EquippableStateMachineComponent,
// AresEquippableDataTracker), most of which already have descriptors. The body
// is purely the cosmetic + scene-graph shell.
//
// Field layout is IDENTICAL across all weapons (every handle maps to exactly one
// checksum + name in the manifest), so a single shared base configures every
// weapon; each concrete subclass just pins its asset Path. Handles/names below
// verified against the manifest; types from the Valorant SDK dump
// (ShooterGame_classes.h, AAresEquippable : AAresItem, fields at 0xdb8-0xe58).
//
// The AttachmentDataAssets / AttachmentDataAssetIds TArray replicated elements
// appear at handles 25-50 with DUPLICATE names ("A","B","C","D") and cannot be
// resolved by export name — they are left undecoded (cleanly skipped by the
// parser). They carry per-attachment cosmetic GUIDs and are not needed for
// gameplay analysis.

public abstract class WeaponEquippableDescriptor<TDescriptor> : ExportGroupDescriptor<TDescriptor>
    where TDescriptor : WeaponEquippableDescriptor<TDescriptor>
{
    public override ExportCategory Categories => ExportCategory.Inventory;
    public override ExportGroupKind Kind => ExportGroupKind.Actor;

    // AActor / USceneComponent bookkeeping (inherited from AActor/AAttachment).
    // "216"/"215" are UE4 AttachmentReplication snapshot markers whose payload
    // width varies across replay builds (3 bits in build 13.00, wider in 13.01),
    // so they are captured as opaque raw payloads rather than a fixed-width type.
    public ValorantRawPayload? Bookkeeping216 { get; set; } // "216" — actor attachment snapshot.
    public uint AttachParent { get; set; }         // USceneComponent* the weapon is attached to.
    public ValorantRawPayload? RelativeScale3D { get; set; } // FTransform::RelativeScale3D (variable-width).
    public ValorantRawPayload? AttachComponent { get; set; } // Component-ref encoding (TODO: typed decoder).
    public uint Owner { get; set; }                // AActor* Owner (the holding character).
    public ValorantRawPayload? Bookkeeping215 { get; set; } // "215" — actor attachment snapshot.
    public uint Instigator { get; set; }           // APawn* Instigator.
    public ValorantRawPayload? InPersistentData { get; set; } // bInPersistentData (variable-width bool).

    // Cosmetic loadout (AAresEquippable fields 0xdb8-0xde8). These are
    // UEquippable*DataAsset soft/strong object references replicated as net GUIDs.
    public uint OwningPrimaryDataAsset { get; set; }  // UEquippableDataAsset* (the weapon's static data).
    public uint SkinDataAsset { get; set; }           // UEquippableSkinDataAsset*
    public uint SkinLevelDataAsset { get; set; }      // UEquippableSkinLevelDataAsset*
    public uint ChromaDataAsset { get; set; }         // UEquippableSkinChromaDataAsset*
    public uint CharmDataAsset { get; set; }          // UEquippableCharmDataAsset*
    public uint CharmLevelDataAsset { get; set; }     // UEquippableCharmLevelDataAsset*

    // Pickup throttling + cosmetic seed (fields 0xe50-0xe5c).
    public uint PreventPickupCharacter { get; set; }  // AShooterCharacter* temporarily blocked from picking this up.
    public ValorantRawPayload? CosmeticRandomSeed { get; set; } // int32 — variable width, captured raw.

    protected override void Configure()
    {
        // Structural / bookkeeping fields are captured as opaque raw payloads so
        // their variable widths across replay builds cannot misalign the stream.
        AddProperty("216", x => x.Bookkeeping216).Decode(ValorantPayloadDecoders.RawPayload("Bookkeeping216"));
        AddProperty(x => x.AttachParent).ObjectNetGuid();
        AddProperty(x => x.RelativeScale3D).Decode(ValorantPayloadDecoders.RawPayload("RelativeScale3D"));
        AddProperty(x => x.AttachComponent).Decode(ValorantPayloadDecoders.RawPayload("AttachComponent"));
        AddProperty(x => x.Owner).ObjectNetGuid();
        AddProperty("215", x => x.Bookkeeping215).Decode(ValorantPayloadDecoders.RawPayload("Bookkeeping215"));
        AddProperty(x => x.Instigator).ObjectNetGuid();
        AddProperty(x => x.InPersistentData).Decode(ValorantPayloadDecoders.RawPayload("InPersistentData"));

        // Cosmetic loadout references (stable net-GUID object pointers).
        AddProperty(x => x.OwningPrimaryDataAsset).ObjectNetGuid();
        AddProperty(x => x.SkinDataAsset).ObjectNetGuid();
        AddProperty(x => x.SkinLevelDataAsset).ObjectNetGuid();
        AddProperty(x => x.ChromaDataAsset).ObjectNetGuid();
        AddProperty(x => x.CharmDataAsset).ObjectNetGuid();
        AddProperty(x => x.CharmLevelDataAsset).ObjectNetGuid();

        // Pickup / seed.
        AddProperty(x => x.PreventPickupCharacter).ObjectNetGuid();
        AddProperty(x => x.CosmeticRandomSeed).Decode(ValorantPayloadDecoders.RawPayload("CosmeticRandomSeed"));
    }
}

// One concrete subclass per weapon asset path. Each is a single-line override
// of Path; the layout + decoding all live in the shared base.

// --- Sidearms ---
public sealed class BasePistolWeaponDescriptor : WeaponEquippableDescriptor<BasePistolWeaponDescriptor>
{
    public override string Path => "/Game/Equippables/Guns/Sidearms/BasePistol/BasePistol.BasePistol_C";
}

public sealed class LugerPistolWeaponDescriptor : WeaponEquippableDescriptor<LugerPistolWeaponDescriptor>
{
    // Ghost.
    public override string Path => "/Game/Equippables/Guns/Sidearms/Luger/LugerPistol.LugerPistol_C";
}

public sealed class CompactPistolWeaponDescriptor : WeaponEquippableDescriptor<CompactPistolWeaponDescriptor>
{
    // Frenzy.
    public override string Path => "/Game/Equippables/Guns/Sidearms/Compact/CompactPistol.CompactPistol_C";
}

public sealed class RevolverPistolWeaponDescriptor : WeaponEquippableDescriptor<RevolverPistolWeaponDescriptor>
{
    // Sheriff.
    public override string Path => "/Game/Equippables/Guns/Sidearms/Revolver/RevolverPistol.RevolverPistol_C";
}

public sealed class SawedOffShotgunWeaponDescriptor : WeaponEquippableDescriptor<SawedOffShotgunWeaponDescriptor>
{
    // Shorty (sidearms/slim bucket).
    public override string Path => "/Game/Equippables/Guns/Sidearms/Slim/SawedOffShotgun.SawedOffShotgun_C";
}

// --- Rifles ---
public sealed class AssaultRifleAkWeaponDescriptor : WeaponEquippableDescriptor<AssaultRifleAkWeaponDescriptor>
{
    // Vandal.
    public override string Path => "/Game/Equippables/Guns/Rifles/AK/AssaultRifle_AK.AssaultRifle_AK_C";
}

public sealed class AssaultRifleAcrWeaponDescriptor : WeaponEquippableDescriptor<AssaultRifleAcrWeaponDescriptor>
{
    // Phantom.
    public override string Path => "/Game/Equippables/Guns/Rifles/Carbine/AssaultRifle_ACR.AssaultRifle_ACR_C";
}

public sealed class AssaultRifleBurstWeaponDescriptor : WeaponEquippableDescriptor<AssaultRifleBurstWeaponDescriptor>
{
    // Bulldog.
    public override string Path => "/Game/Equippables/Guns/Rifles/Burst/AssaultRifle_Burst.AssaultRifle_Burst_C";
}

// --- SMGs ---
public sealed class SubMachineGunMp5WeaponDescriptor : WeaponEquippableDescriptor<SubMachineGunMp5WeaponDescriptor>
{
    // MP5 / Ksub.
    public override string Path => "/Game/Equippables/Guns/SubMachineGuns/MP5/SubMachineGun_MP5.SubMachineGun_MP5_C";
}

// --- Shotguns ---
public sealed class AutomaticShotgunWeaponDescriptor : WeaponEquippableDescriptor<AutomaticShotgunWeaponDescriptor>
{
    // Bucky.
    public override string Path => "/Game/Equippables/Guns/Shotguns/AutoShotgun/AutomaticShotgun.AutomaticShotgun_C";
}

public sealed class PumpShotgunWeaponDescriptor : WeaponEquippableDescriptor<PumpShotgunWeaponDescriptor>
{
    // Judge.
    public override string Path => "/Game/Equippables/Guns/Shotguns/PumpShotgun/PumpShotgun.PumpShotgun_C";
}

// --- Snipers ---
public sealed class BoltSniperWeaponDescriptor : WeaponEquippableDescriptor<BoltSniperWeaponDescriptor>
{
    // Marshal.
    public override string Path => "/Game/Equippables/Guns/SniperRifles/Boltsniper/BoltSniper.BoltSniper_C";
}

public sealed class DmrWeaponDescriptor : WeaponEquippableDescriptor<DmrWeaponDescriptor>
{
    // Outlaw.
    public override string Path => "/Game/Equippables/Guns/SniperRifles/Dmr/DMR.DMR_C";
}

public sealed class DoubleSniperWeaponDescriptor : WeaponEquippableDescriptor<DoubleSniperWeaponDescriptor>
{
    // Operator.
    public override string Path => "/Game/Equippables/Guns/SniperRifles/Doublesniper/DS_Gun.DS_Gun_C";
}

public sealed class LeverSniperRifleWeaponDescriptor : WeaponEquippableDescriptor<LeverSniperRifleWeaponDescriptor>
{
    public override string Path => "/Game/Equippables/Guns/SniperRifles/Leversniper/LeverSniperRifle.LeverSniperRifle_C";
}

// --- Heavy ---
public sealed class HeavyMachineGunWeaponDescriptor : WeaponEquippableDescriptor<HeavyMachineGunWeaponDescriptor>
{
    public override string Path => "/Game/Equippables/Guns/HvyMachineGuns/HMG/HeavyMachineGun.HeavyMachineGun_C";
}

public sealed class LightMachineGunWeaponDescriptor : WeaponEquippableDescriptor<LightMachineGunWeaponDescriptor>
{
    // Ares / Odin.
    public override string Path => "/Game/Equippables/Guns/HvyMachineGuns/LMG/LightMachineGun.LightMachineGun_C";
}

// --- Melee ---
public sealed class MeleeWeaponDescriptor : WeaponEquippableDescriptor<MeleeWeaponDescriptor>
{
    public override string Path => "/Game/Equippables/Melee/Ability_Melee_Base.Ability_Melee_Base_C";
}

internal static class WeaponEquippableDescriptors
{
    public static IEnumerable<ExportGroupDescriptor> CreateDescriptors()
    {
        yield return new BasePistolWeaponDescriptor();
        yield return new LugerPistolWeaponDescriptor();
        yield return new CompactPistolWeaponDescriptor();
        yield return new RevolverPistolWeaponDescriptor();
        yield return new SawedOffShotgunWeaponDescriptor();
        yield return new AssaultRifleAkWeaponDescriptor();
        yield return new AssaultRifleAcrWeaponDescriptor();
        yield return new AssaultRifleBurstWeaponDescriptor();
        yield return new SubMachineGunMp5WeaponDescriptor();
        yield return new AutomaticShotgunWeaponDescriptor();
        yield return new PumpShotgunWeaponDescriptor();
        yield return new BoltSniperWeaponDescriptor();
        yield return new DmrWeaponDescriptor();
        yield return new DoubleSniperWeaponDescriptor();
        yield return new LeverSniperRifleWeaponDescriptor();
        yield return new HeavyMachineGunWeaponDescriptor();
        yield return new LightMachineGunWeaponDescriptor();
        yield return new MeleeWeaponDescriptor();
    }
}
