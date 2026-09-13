using Replay.Models.Descriptors;
using Replay.Unreal.Parsing;
using Replay.Valorant.Descriptors;

namespace Replay.Valorant.Descriptors.Effects;

// EffectManagerComponent — the authoritative list of active gameplay effects
// (smokes, flashes, walls, molotovs, etc.) and the multicast RPCs that spawn
// them. This is the engine-side counterpart to ReplayEffectComponent: here the
// server replicates the live effect list, there the replay records the visual
// effects. Decoding both gives a complete picture of ability/effect usage.
//
// Handles verified against the replay manifest (build 13.01); types from the
// Valorant SDK dump (ShooterGame_classes.h, ShooterGame_struct.h).

// Property-replication descriptor. The replicated state is
// ServerActiveEffects: TArray<FActiveEffectInfo> — captured opaquely because
// FActiveEffectInfo is a deep nested struct. Individual scalar fields that the
// RepLayout flattens out (TimeStamp, Socket, AllianceFilter) are also decoded
// directly so we get usable per-effect metadata even without the full struct.
public sealed class EffectManagerComponentDescriptor
    : ExportGroupDescriptor<EffectManagerComponentDescriptor>
{
    public override string Path => "/Script/ShooterGame.EffectManagerComponent";
    public override ExportCategory Categories => ExportCategory.Effects;
    public override ExportGroupKind Kind => ExportGroupKind.Component;

    // TArray<FActiveEffectInfo> — opaque for now; contains EffectID, EffectType,
    // EffectData (float/vector/object value arrays), transform, etc.
    public ValorantRawPayload? ServerActiveEffects { get; set; }

    // Flattened inner members of FActiveEffectInfo that are useful on their own.
    public ulong EffectID { get; set; }
    public string? SourceID { get; set; }
    public bool LocalEffect { get; set; }
    public bool Transient { get; set; }
    public uint EffectType { get; set; }
    public uint WaitOnReplicationActor { get; set; }
    public string? Socket { get; set; }
    public float StartTimeStamp { get; set; }
    public byte AllianceFilter { get; set; }

    protected override void Configure()
    {
        AddProperty(x => x.ServerActiveEffects)
            .Decode(ValorantPayloadDecoders.RawPayload("TArray<FActiveEffectInfo>"));
        AddProperty(x => x.EffectID).UInt64();
        AddProperty(x => x.SourceID).FName();
        AddProperty("bLocalEffect", x => x.LocalEffect).Bool();
        AddProperty("bTransient", x => x.Transient).Bool();
        AddProperty(x => x.EffectType).ObjectNetGuid();
        AddProperty(x => x.WaitOnReplicationActor).ObjectNetGuid();
        AddProperty(x => x.Socket).FName();
        AddProperty(x => x.StartTimeStamp).Float();
        AddProperty(x => x.AllianceFilter).EnumByte();
    }
}

// The ClassNetCache dispatcher for EffectManagerComponent's multicast RPCs.
// Each RPC's parameter payload is decoded by its own parameter descriptor below.
public sealed class EffectManagerComponentClassNetCacheDescriptor
    : ClassNetCacheDescriptor<EffectManagerComponentClassNetCacheDescriptor>
{
    public override string Path => "/Script/ShooterGame.EffectManagerComponent_ClassNetCache";

    protected override void Configure()
    {
        AddFunctionHandle<MulticastPlayContinuousEffectParameters>(
            0, "MulticastPlayContinuousEffect",
            "/Script/ShooterGame.EffectManagerComponent:MulticastPlayContinuousEffect",
            ExportCategory.Effects);
        AddFunctionHandle<MulticastPlayOneShotEffectParameters>(
            1, "MulticastPlayOneShotEffect",
            "/Script/ShooterGame.EffectManagerComponent:MulticastPlayOneShotEffect",
            ExportCategory.Effects);
        AddFunctionHandle(
            2, "MulticastStopContinuousEffect",
            "/Script/ShooterGame.EffectManagerComponent:MulticastStopContinuousEffect",
            ExportCategory.Effects);
        AddFunctionHandle<MulticastUpdateContinuousEffectParameters>(
            3, "MulticastUpdateContinuousEffect",
            "/Script/ShooterGame.EffectManagerComponent:MulticastUpdateContinuousEffect",
            ExportCategory.Effects);
        // handles 4 & 5 are Replay* variants (ReplayRecordContinuousEffect,
        // ReplayRecordOneShotEffect) — these are replay-recording RPCs. Skip for
        // now; the existing ReplayEffectComponent descriptors cover that path.
    }
}

// Parameter payload for MulticastPlayContinuousEffect — spawns a lasting effect
// (smoke, wall, etc.). Decodes the analytically useful fields (container, owner,
// timing, alliance) and captures the value arrays opaquely.
internal sealed class MulticastPlayContinuousEffectParameters
    : ExportGroupDescriptor<MulticastPlayContinuousEffectParameters>
{
    public override string Path =>
        "/Script/ShooterGame.EffectManagerComponent:MulticastPlayContinuousEffect";
    public override ExportCategory Categories => ExportCategory.Effects;
    public override ExportGroupKind Kind => ExportGroupKind.ClassNetCache;
    public override FieldStreamGrammar Grammar => FieldStreamGrammar.FunctionParameters;

    public uint EffectContainer { get; set; }
    public uint WaitOnReplicationActor { get; set; }
    public ValorantRawPayload? FloatValues { get; set; }
    public ValorantRawPayload? ObjectValues { get; set; }
    public ValorantRawPayload? Transform { get; set; }
    public string? AttachSocket { get; set; }
    public ulong EffectID { get; set; }
    public string? SourceID { get; set; }
    public bool LocalEffect { get; set; }
    public bool Transient { get; set; }
    public uint ClientControllerThatTriggered { get; set; }
    public float StartMovementTime { get; set; }
    public byte AllianceFilter { get; set; }

    protected override void Configure()
    {
        AddProperty(x => x.EffectContainer).ObjectNetGuid();
        AddProperty(x => x.WaitOnReplicationActor).ObjectNetGuid();
        AddProperty(x => x.FloatValues)
            .Decode(ValorantPayloadDecoders.RawPayload("TArray<FEffectDataFloat>"));
        AddProperty(x => x.ObjectValues)
            .Decode(ValorantPayloadDecoders.RawPayload("TArray<FEffectDataObject>"));
        AddProperty(x => x.Transform).Decode(ValorantPayloadDecoders.RawPayload("FTransform"));
        AddProperty(x => x.AttachSocket).FName();
        AddProperty(x => x.EffectID).UInt64();
        AddProperty(x => x.SourceID).FName();
        AddProperty("bLocalEffect", x => x.LocalEffect).Bool();
        AddProperty("bTransient", x => x.Transient).Bool();
        AddProperty(x => x.ClientControllerThatTriggered).ObjectNetGuid();
        AddProperty(x => x.StartMovementTime).Float();
        AddProperty(x => x.AllianceFilter).EnumByte();
    }
}

// Parameter payload for MulticastPlayOneShotEffect — spawns a one-shot effect
// (flash, concussion, etc.).
internal sealed class MulticastPlayOneShotEffectParameters
    : ExportGroupDescriptor<MulticastPlayOneShotEffectParameters>
{
    public override string Path =>
        "/Script/ShooterGame.EffectManagerComponent:MulticastPlayOneShotEffect";
    public override ExportCategory Categories => ExportCategory.Effects;
    public override ExportGroupKind Kind => ExportGroupKind.ClassNetCache;
    public override FieldStreamGrammar Grammar => FieldStreamGrammar.FunctionParameters;

    public uint EffectContainer { get; set; }
    public uint WaitOnReplicationActor { get; set; }
    public ValorantRawPayload? FloatValues { get; set; }
    public ValorantRawPayload? ObjectValues { get; set; }
    public ValorantRawPayload? Transform { get; set; }
    public string? AttachSocket { get; set; }
    public uint ClientControllerThatTriggered { get; set; }
    public float StartMovementTime { get; set; }
    public byte AllianceFilter { get; set; }

    protected override void Configure()
    {
        AddProperty(x => x.EffectContainer).ObjectNetGuid();
        AddProperty(x => x.WaitOnReplicationActor).ObjectNetGuid();
        AddProperty(x => x.FloatValues)
            .Decode(ValorantPayloadDecoders.RawPayload("TArray<FEffectDataFloat>"));
        AddProperty(x => x.ObjectValues)
            .Decode(ValorantPayloadDecoders.RawPayload("TArray<FEffectDataObject>"));
        AddProperty(x => x.Transform).Decode(ValorantPayloadDecoders.RawPayload("FTransform"));
        AddProperty(x => x.AttachSocket).FName();
        AddProperty(x => x.ClientControllerThatTriggered).ObjectNetGuid();
        AddProperty(x => x.StartMovementTime).Float();
        AddProperty(x => x.AllianceFilter).EnumByte();
    }
}

// Parameter payload for MulticastUpdateContinuousEffect — updates a live
// effect's float values (e.g. a shrinking smoke timer).
internal sealed class MulticastUpdateContinuousEffectParameters
    : ExportGroupDescriptor<MulticastUpdateContinuousEffectParameters>
{
    public override string Path =>
        "/Script/ShooterGame.EffectManagerComponent:MulticastUpdateContinuousEffect";
    public override ExportCategory Categories => ExportCategory.Effects;
    public override ExportGroupKind Kind => ExportGroupKind.ClassNetCache;
    public override FieldStreamGrammar Grammar => FieldStreamGrammar.FunctionParameters;

    public ulong EffectID { get; set; }
    public string? SourceID { get; set; }
    public bool LocalEffect { get; set; }
    public bool Transient { get; set; }
    public uint WaitOnReplicationActor { get; set; }
    public ValorantRawPayload? FloatValues { get; set; }

    protected override void Configure()
    {
        AddProperty(x => x.EffectID).UInt64();
        AddProperty(x => x.SourceID).FName();
        AddProperty("bLocalEffect", x => x.LocalEffect).Bool();
        AddProperty("bTransient", x => x.Transient).Bool();
        AddProperty(x => x.WaitOnReplicationActor).ObjectNetGuid();
        AddProperty(x => x.FloatValues)
            .Decode(ValorantPayloadDecoders.RawPayload("TArray<FEffectDataFloat>"));
    }
}
