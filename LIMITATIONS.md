# Limitations (read before use)
1. **Not validated** against any real LA-2A recording or measurement. No null test exists.
2. **Release is a fit, not a measurement.** In the dB (gain-reduction) domain: 50% of the reduction recovered at ~61 ms, <1 dB after ~5 s (from 30 dB). If the manual's "50% release" means something else (e.g. cell resistance), this does not apply. HYPOTHESIS.
3. **No burst-duration memory.** Both stages attack fast, so a 50 ms burst and a 1 s burst release identically. The manual says release depends on amount of previous reduction; only depth is modeled.
4. **No -30 dB breakaway / -20 dB knee** (manual p.3, Fig. 1). The curve is a smooth 1/(1+K*L^gamma) divider.
5. **Low-frequency ripple distortion** (model artifact): ~4% at 30 Hz, ~1.8% at 100 Hz, ~0.2% at 1 kHz under heavy limiting (Python reference). Manual spec is <0.35%.
6. **Gain staging:** base gain is unity (real unit ~40 dB). Gain knob range (+/-20 dB) and the dBFS<->dBm mapping are [?] guesses.
7. **Compress mode:** gamma = 2/3 (slope ~0.34 dB/dB, ~3:1 asymptote), mechanism [?]; at the same Peak Reduction it reduces more at low levels than Limit because of K calibration.
8. **No tube, transformer or input/output impedance modeling.** Flat DC-to-Nyquist; the manual's +/-0.1 dB over 30 Hz-15 kHz is unmodeled.
9. **Slope switch:** exists only after serial 572 (addendum 11-66). The panel photo shows it, so it is live (default Limit). A genuine early (1965) unit has no switch.
10. **Stereo link** is implemented in the C++ plugin; the Python GUI processes channels independently. R37 is flat-only in the plugin.
11. **GUI:** the VST3 has no custom editor. The Python GUI is untested on a display; QSoundEffect playback relies on the OS backend resampling (pitch may be wrong if it does not).
12. **Build:** only la2a_core.h was compiled/run. The VST3 SDK glue has not been built. Default SDK tag in build_vst3.bat is unverified.
13. The panel/interior photo appears AI-generated; it is a skin only, not a hardware reference (tube count, labels and branding do not match the manual).
