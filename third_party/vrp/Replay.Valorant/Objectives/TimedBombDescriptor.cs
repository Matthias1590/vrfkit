using Replay.Models.Descriptors;
using Replay.Unreal.Parsing;

namespace Replay.Valorant.Objectives;

// The spike / bomb. Decoded from /Game/GameModes/Bomb/TimedBomb.TimedBomb_C.
// Field handles verified against the replay manifest (build 13.01); property
// semantics cross-referenced against APlantedBomb_C in the Valorant SDK dump.
// This is the single most valuable undecoded group for objective analysis:
// plant site, defuse progress, who is defusing, time-to-explode.
public sealed class TimedBombDescriptor : ExportGroupDescriptor<TimedBombDescriptor>
{
    public override string Path => "/Game/GameModes/Bomb/TimedBomb.TimedBomb_C";
    public override ExportCategory Categories => ExportCategory.GameState;
    public override ExportGroupKind Kind => ExportGroupKind.Actor;

    // Anonymous RepLayout bookkeeping fields present on every actor.
    public int A { get; set; }   // "216"
    public int B { get; set; }   // "215"

    // Time (seconds) until the spike detonates while planted.
    public float TimeRemainingToExplode { get; set; }

    // Which site (A/B) the spike was planted at — BombSiteEnum.
    public byte PlantedAtSite { get; set; }

    // True once a defuse has completed.
    public bool BombHasBeenDefused { get; set; }

    // Current defusing state — BombDefusingState enum (idle / defusing / complete).
    public byte BombDefuseState { get; set; }

    // The character currently defusing the spike (ObjectNetGuid -> ShooterCharacter).
    public uint CurrentDefuser { get; set; }

    // Defuse progress in the 0..1 range (or seconds, depending on build).
    public float DefuseProgress { get; set; }

    // Index of the defuse "section" currently being processed (defuse is staged).
    public int CurrentDefuseSection { get; set; }

    // True once the bomb actor has finished initialising.
    public bool BombInitializeComplete { get; set; }

    protected override void Configure()
    {
        AddProperty("216", x => x.A).Int32();
        AddProperty("215", x => x.B).Int32();
        AddProperty(x => x.TimeRemainingToExplode).Float();
        AddProperty(x => x.PlantedAtSite).EnumByte();
        AddProperty(x => x.BombHasBeenDefused).Bool();
        AddProperty(x => x.BombDefuseState).EnumByte();
        AddProperty(x => x.CurrentDefuser).ObjectNetGuid();
        AddProperty(x => x.DefuseProgress).Float();
        AddProperty(x => x.CurrentDefuseSection).Int32();
        AddProperty(x => x.BombInitializeComplete).Bool();
    }
}
