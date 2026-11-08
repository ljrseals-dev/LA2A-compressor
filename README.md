# LA-2A Manual-Faithful (behavioral) VST3

C++17 VST3 built on the Steinberg VST3 SDK. A **behavioral model** of the Teletronix LA-2A architecture from the
original manual (3-66 + 11-66 addendum): T4 shunt attenuator ahead of the gain stage, pre-attenuator (feed-forward)
sidechain, no audio-path high-pass, no bypass. Limit/Compress defaults to Limit; the switch itself exists only after serial 572 (addendum 11-66), which the panel photo shows.

## Build (Windows, VS 2022, Git, CMake 3.19+)
    build_vst3.bat            :: clones the SDK to external\vst3sdk, builds, copies to dist\
    build_vst3.bat install    :: also copies to %CommonProgramFiles%\VST3 (admin)
    publish_github.bat        :: creates/pushes ljrseals-dev/LA2A-VST3 (private) via gh, else git push

## Parameters
Gain (+/-20 dB, [?] range), Peak Reduction, Stereo Link (shared control, manual p.5-6), Limit/Compress, Gain Reduction (read-only).

## Status
See LIMITATIONS.md (what is wrong/unverified) and CLAIMS.md (every claim classified). Headline: behavioral model only, unvalidated against real hardware; SDK glue not yet built; release timing is a dB-domain fit.

## Layout
`source/` plugin + `la2a_core.h` DSP; `tests/core_test.cpp` headless check; `gui/` Python/PyQt6 front end + Python reference model; `docs/` panel image.
