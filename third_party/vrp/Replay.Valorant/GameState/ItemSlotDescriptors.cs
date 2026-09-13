using Replay.Models.Descriptors;
using Replay.Unreal.Parsing;
using Replay.Valorant.Descriptors;

namespace Replay.Valorant.GameState;

// Inventory slot descriptors. UItemSlot holds a single item; UMultiItemSlot
// holds an array. These appear as nested structs within AresInventory's
// replicated ItemSlots blob, but they also show up as their own export groups.
// Handles verified against the replay manifest (build 13.01); types from the
// Valorant SDK dump.

// UItemSlot : UObject — a single-item slot. Only `Contents` (the item) is
// replicated.
public sealed class ItemSlotDescriptor : ExportGroupDescriptor<ItemSlotDescriptor>
{
    public override string Path => "/Script/ShooterGame.ItemSlot";
    public override ExportCategory Categories => ExportCategory.Inventory;
    public override ExportGroupKind Kind => ExportGroupKind.Component;

    // The item held in this slot (AAresItem*).
    public uint Contents { get; set; }

    protected override void Configure()
    {
        AddProperty(x => x.Contents).ObjectNetGuid();
    }
}

// UMultiItemSlot : UItemSlot — a slot that can hold multiple items. The two
// `MultiContents` handles reflect UE4 FastArray replication (the array plus its
// replication metadata). Captured as a single opaque payload for safety.
public sealed class MultiItemSlotDescriptor : ExportGroupDescriptor<MultiItemSlotDescriptor>
{
    public override string Path => "/Script/ShooterGame.MultiItemSlot";
    public override ExportCategory Categories => ExportCategory.Inventory;
    public override ExportGroupKind Kind => ExportGroupKind.Component;

    // TArray<AAresItem*> — the FastArray payload. Decoded opaquely for now; the
    // two handles (1 = array, 2 = metadata) are folded into one capture.
    public ValorantRawPayload? MultiContents { get; set; }

    protected override void Configure()
    {
        AddProperty(x => x.MultiContents)
            .Decode(ValorantPayloadDecoders.RawPayload("TArray<AAresItem*>"));
    }
}
