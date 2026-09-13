using Replay.Models.Descriptors;

namespace Replay.Valorant.Descriptors.Agents.Aggrobot;

public static class AggrobotDescriptors
{
    public static List<ExportGroupDescriptor> CreateDescriptors()
    {
        return
        [
            new AggrobotAgentDescriptor(),
            new AggrobotSeekerNadePawnDescriptor(),
            new AggrobotRollyPollyPawnDescriptor(),
            new AggrobotDiscTurretPowerWaveDescriptor(),
            new AggrobotOrbSpawnerDescriptor(),
            new AggrobotZamboniRocketDescriptor(),
            new AggrobotExplodeyPatchDescriptor(),
        ];
    }
}