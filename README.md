# LA-2A Manual-Faithful (behavioral) VST3

C++17 VST3 built on the Steinberg VST3 SDK. A **behavioral model** of the Teletronix LA-2A architecture from the
original manual (3-66 + 11-66 addendum): T4 shunt attenuator ahead of the gain stage, pre-attenuator (feed-forward)
sidechain, no audio-path high-pass, no bypass. 1965 configuration: Limit/Compress defaults to Limit (the switch exists only after serial 572).

## Build (Windows, VS 2022, Git, CMake 3.19+)
    build_vst3.bat            :: clones the SDK to external\vst3sdk, builds, copies to dist\
    build_vst3.bat install    :: also copies to %CommonProgramFiles%\VST3 (admin)
    publish_github.bat        :: creates/pushes ljrseals-dev/LA2A-VST3 (private) via gh, else git push

## Parameters
Gain (+/-20 dB, [?] range), Peak Reduction, Stereo Link (shared control, manual p.5-6), Limit/Compress, Gain Reduction (read-only).

## Known failures / unverified (read before trusting it)
- **Release timing:** illumination falls to 50% in ~57 ms, but *gain* release takes seconds -- does not meet the manual's ~60 ms / 0.5-5 s. UNVERIFIED.
- **Gain staging:** base gain is unity (real unit ~40 dB); heavy reduction makes the output very quiet.
- No -30 dB breakaway / -20 dB knee; compress mode is ~2.6:1 at best, mechanism [?]; no transformer/tube response modeled (flat).
- No custom GUI: the host shows generic parameters. `docs/la2a_panel_1965.png` is the planned skin (needs VSTGUI work).
- **Untested:** the sandbox had no SDK/network. Only `source/la2a_core.h` was compiled and run (matches the Python reference: ~30 dB GR after a 1 s burst). The SDK glue (CMake, processor, controller, factory) has NOT been built; expect to fix compile errors. The default SDK tag in `build_vst3.bat` is unverified.
- Not validated against any real LA-2A recording.
- License: choose one deliberately. The VST3 SDK is GPLv3/proprietary dual-licensed on 3.7.x (reported MIT from 3.8; verify).
