using Replay.Models.Descriptors;
using Replay.Unreal.Parsing;

namespace Replay.Valorant.GameState;

// UPurchasedItemComponent : UActorComponent — records who bought an item and
// whether the purchase belongs to the current buy-round session. This is the
// per-purchase economy record. Handles verified against the replay manifest
// (build 13.01); types from the Valorant SDK dump.
public sealed class PurchasedItemComponentDescriptor
    : ExportGroupDescriptor<PurchasedItemComponentDescriptor>
{
    public override string Path => "/Script/ShooterGame.PurchasedItemComponent";
    public override ExportCategory Categories => ExportCategory.Economy | ExportCategory.Inventory;
    public override ExportGroupKind Kind => ExportGroupKind.Component;

    // The purchasable equippable that was bought (UAresPurchasableEquippable*).
    public uint Purchaseable { get; set; }

    // True if this purchase was made in the current buy-window session.
    public bool IsCurrentSessionPurchase { get; set; }

    // The player who made the purchase (AShooterPlayerState*).
    public uint PurchasingPlayerState { get; set; }

    // Where the purchase came from — EPurchaseSource / TransactionSource enum.
    // Field added in a later patch than the SDK dump; typed as a byte enum but
    // type is MEDIUM-confidence. Fall back to RawPayload if a future build breaks.
    public byte PurchasableTransactionSource { get; set; }

    protected override void Configure()
    {
        AddProperty(x => x.Purchaseable).ObjectNetGuid();
        AddProperty("bIsCurrentSessionPurchase", x => x.IsCurrentSessionPurchase).Bool();
        AddProperty(x => x.PurchasingPlayerState).ObjectNetGuid();
        AddProperty(x => x.PurchasableTransactionSource).EnumByte();
    }
}
