using Replay.Models.Descriptors;
using Replay.Unreal.Parsing;

namespace Replay.Valorant.GameState;

// Small single/double-field component descriptors. Grouped together because each
// is too small to justify its own file. Handles verified against the replay
// manifest (build 13.01); types from the Valorant SDK dump (ShooterGame_classes.h).

// UAbilityTrackingDelegateComponent : UActorComponent — binds a delegate to its
// tracking component. Single replicated property.
public sealed class AbilityTrackingDelegateComponentDescriptor
    : ExportGroupDescriptor<AbilityTrackingDelegateComponentDescriptor>
{
    public override string Path => "/Script/ShooterGame.AbilityTrackingDelegateComponent";
    public override ExportCategory Categories => ExportCategory.Ability;
    public override ExportGroupKind Kind => ExportGroupKind.Component;

    public uint AbilityTrackingComponent { get; set; }

    protected override void Configure()
    {
        AddProperty(x => x.AbilityTrackingComponent).ObjectNetGuid();
    }
}

// UAutoEquipTransitionContext : UStateTransitionContext — drives weapon equip
// transitions. Two byte enums.
public sealed class AutoEquipTransitionContextDescriptor
    : ExportGroupDescriptor<AutoEquipTransitionContextDescriptor>
{
    public override string Path => "/Script/ShooterGame.AutoEquipTransitionContext";
    public override ExportCategory Categories => ExportCategory.Inventory;
    public override ExportGroupKind Kind => ExportGroupKind.Component;

    // EEquipSpeed (byte enum).
    public byte AutoEquipSpeed { get; set; }
    // EEquipSource (byte enum).
    public byte EquipSource { get; set; }

    protected override void Configure()
    {
        AddProperty(x => x.AutoEquipSpeed).EnumByte();
        AddProperty(x => x.EquipSource).EnumByte();
    }
}

// UAresEquippableDataTracker : UActorComponent — tracks the original buyer's
// team for a weapon. NOTE: the SDK member is `OriginalBuyer` (a player-state
// pointer), but the replay exposes a later property `OriginalBuyerTeam` which is
// a small team enum (EAresTeamRole). Typed as byte enum; fall back to RawPayload
// if decoding fails on a future patch.
public sealed class AresEquippableDataTrackerDescriptor
    : ExportGroupDescriptor<AresEquippableDataTrackerDescriptor>
{
    public override string Path => "/Script/ShooterGame.AresEquippableDataTracker";
    public override ExportCategory Categories => ExportCategory.Inventory | ExportCategory.Economy;
    public override ExportGroupKind Kind => ExportGroupKind.Component;

    public byte OriginalBuyerTeam { get; set; }

    protected override void Configure()
    {
        AddProperty(x => x.OriginalBuyerTeam).EnumByte();
    }
}
