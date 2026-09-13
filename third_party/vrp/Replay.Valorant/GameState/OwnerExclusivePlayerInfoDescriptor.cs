using Replay.Models.Descriptors;
using Replay.Unreal.Parsing;
using Replay.Valorant.Descriptors;

namespace Replay.Valorant.GameState;

// AOwnerExclusivePlayerInfo : AInfo — per-player private state that only the
// owning client receives. This carries economy (per-round money, loadout value),
// rewards, AFK status, and the player's round-by-round info. Very high value for
// economy and per-round analysis. Handles verified against the replay manifest
// (build 13.01); types from the Valorant SDK dump (ShooterGame_classes.h).
//
// NOTE: flattened inner handles (the repeated `Rewards` entries 19-27, and the
// RoundInfos inner fields 40-44) reflect UE RepLayout expansion of
// TArray<FAresTrackedReward> and TArray<FAresPlayerRoundInfo>. The arrays
// themselves are captured opaquely; selected scalar fields are decoded directly.
public sealed class OwnerExclusivePlayerInfoDescriptor
    : ExportGroupDescriptor<OwnerExclusivePlayerInfoDescriptor>
{
    public override string Path => "/Script/ShooterGame.OwnerExclusivePlayerInfo";
    public override ExportCategory Categories => ExportCategory.GameState | ExportCategory.Economy;
    public override ExportGroupKind Kind => ExportGroupKind.Actor;

    public int A { get; set; }   // "216"
    public int B { get; set; }   // "215"

    // The owning actor (usually the player controller).
    public uint Owner { get; set; }
    // The player's controller (AController*).
    public uint AresController { get; set; }
    // Current death streak count.
    public int NumDeathStreak { get; set; }

    // TArray<FAresTrackedReward> — captured opaquely (the inner Reward ints
    // 19-27 are the flattened members and are not individually declared here).
    public ValorantRawPayload? TrackedRewards { get; set; }
    public string? RewardName { get; set; }
    // FText — no native decoder, capture opaquely.
    public ValorantRawPayload? LocalizedRewardName { get; set; }
    public int InstancesOfReward { get; set; }
    // EAresRewardGrantStrategy (byte enum).
    public byte RewardGrantStrategy { get; set; }
    // ERewardSource (byte enum).
    public byte Source { get; set; }

    // Money held at the end of the round, before rewards are granted.
    public int EndOfRoundBeforeRewardsMoney { get; set; }
    // True once the player's loadout is locked in for the round.
    public bool LoadoutFinalized { get; set; }
    // The combat-report component for this player (UCombatReportComponent*).
    public uint CombatReportComponent { get; set; }

    // TArray<FAresPlayerRoundInfo> — per-round economy summary. The scalar
    // members (RoundNumber/StartOfRoundMoney/etc.) are decoded directly below
    // because they are the analytically useful part; the array wrapper is opaque.
    public ValorantRawPayload? RoundInfos { get; set; }
    public int RoundNumber { get; set; }
    public int StartOfRoundMoney { get; set; }
    public int StartOfRoundLoadoutValue { get; set; }
    public int EndOfRoundMoney { get; set; }
    public int EndOfRoundLoadoutValue { get; set; }

    // Opaque — TArray<FObfuscatedPlayerInformation>, no public layout.
    public ValorantRawPayload? AllPlayersObfuscatedPlayerInformation { get; set; }
    // FUniqueNetIdRepl — opaque (the parser already captures this pattern in
    // BombPlayerStateDescriptor).
    public ValorantRawPayload? SubjectUniqueId { get; set; }
    public bool IsAfk { get; set; }
    // EConnectionStatus (byte enum).
    public byte ConnectionStatus { get; set; }

    protected override void Configure()
    {
        AddProperty("216", x => x.A).Int32();
        AddProperty("215", x => x.B).Int32();
        AddProperty(x => x.Owner).ObjectNetGuid();
        AddProperty(x => x.AresController).ObjectNetGuid();
        AddProperty(x => x.NumDeathStreak).Int32();
        AddProperty(x => x.TrackedRewards)
            .Decode(ValorantPayloadDecoders.RawPayload("TArray<FAresTrackedReward>"));
        AddProperty(x => x.RewardName).FName();
        AddProperty(x => x.LocalizedRewardName)
            .Decode(ValorantPayloadDecoders.RawPayload("FText"));
        AddProperty(x => x.InstancesOfReward).Int32();
        AddProperty(x => x.RewardGrantStrategy).EnumByte();
        AddProperty(x => x.Source).EnumByte();
        AddProperty(x => x.EndOfRoundBeforeRewardsMoney).Int32();
        AddProperty("bLoadoutFinalized", x => x.LoadoutFinalized).Bool();
        AddProperty(x => x.CombatReportComponent).ObjectNetGuid();
        AddProperty(x => x.RoundInfos)
            .Decode(ValorantPayloadDecoders.RawPayload("TArray<FAresPlayerRoundInfo>"));
        AddProperty(x => x.RoundNumber).Int32();
        AddProperty(x => x.StartOfRoundMoney).Int32();
        AddProperty(x => x.StartOfRoundLoadoutValue).Int32();
        AddProperty(x => x.EndOfRoundMoney).Int32();
        AddProperty(x => x.EndOfRoundLoadoutValue).Int32();
        AddProperty(x => x.AllPlayersObfuscatedPlayerInformation)
            .Decode(ValorantPayloadDecoders.RawPayload("TArray<FObfuscatedPlayerInformation>"));
        AddProperty(x => x.SubjectUniqueId)
            .Decode(ValorantPayloadDecoders.RawPayload("FUniqueNetIdRepl"));
        AddProperty("bIsAfk", x => x.IsAfk).Bool();
        AddProperty(x => x.ConnectionStatus).EnumByte();
    }
}
