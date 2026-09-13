using Replay.Models.Descriptors;
using Replay.Models.Unreal;
using Replay.Unreal.Parsing;
using Replay.Valorant.Descriptors;

namespace Replay.Valorant.GameState;

public sealed class MulticastResetForRespawnParameters : ExportGroupDescriptor<MulticastResetForRespawnParameters>
{
    public override string Path => "/Script/ShooterGame.AresGameStateBase:MulticastResetForRespawn";
    public override ExportCategory Categories => ExportCategory.GameState;
    public override ExportGroupKind Kind => ExportGroupKind.ClassNetCache;
    public override FieldStreamGrammar Grammar => FieldStreamGrammar.FunctionParameters;

    public ValorantRawPayload? ShooterCharacter { get; set; } // TODO: Implement this object-reference encoding.

    // The spawn transform is replicated as separate named components, not as
    // one FTransform. The replay's net field export declares four handles for
    // this function -- ShooterCharacter, 249, Translation, Scale3D -- so a
    // single `SpawnTransform` property matched nothing and the whole transform
    // stayed undecoded on both parsers.
    //
    // MulticastAddSmokeScreenPointParameters.cs:21-22 already declares these
    // exact two names as FVector, and both functions send both at 192 bits
    // (3 x double) on every replay measured. Handle 249 is left unnamed: the
    // wire supplies no name for it and guessing one would be invention.
    public FVector Translation { get; set; }
    public FVector Scale3D { get; set; }

    protected override void Configure()
    {
        AddProperty(x => x.ShooterCharacter, ExportCategory.GameState)
            .Decode(ValorantPayloadDecoders.RawPayload("ShooterCharacter"));
        AddProperty(x => x.Translation, ExportCategory.GameState).FVector();
        AddProperty(x => x.Scale3D, ExportCategory.GameState).FVector();
    }
}