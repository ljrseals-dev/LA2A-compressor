# Claims
| Claim | Class | Source / status |
|---|---|---|
| Gain element is an electro-optical attenuator ahead of the first amplifier stage | MANUAL ARCHITECTURE | p.2-3, Fig. 2 |
| Sidechain samples the input before the attenuator (feed-forward) | MANUAL ARCHITECTURE | p.4, Fig. 2, schematic (UA manual calls it "feed-back": conflict noted) |
| No rectifier needed; EL light follows |V| | MANUAL ARCHITECTURE | p.4 (abs() in code models the physics) |
| No audio-path high-pass; no bypass | MANUAL ARCHITECTURE | p.2-3 (+/-0.1 dB 30 Hz-15 kHz; controls list) |
| Attack ~10 us; ~60 ms 50% release; 0.5-5 s full | MANUAL FIGURE | p.2 (p.4 text says 1-15 s: internal conflict) |
| Compress ~3:1; Limit horizontal; switch after serial 572 | MANUAL FIGURE | addendum 11-66 |
| R37: LF reduced in sidechain, ~10 dB more at 15 kHz at max | MANUAL FIGURE | p.7 (flat only in plugin; UNVERIFIED) |
| Cell = fast + slow exponentials in dB domain, weights 0.56/0.44, 30 ms / 2 s | HYPOTHESIS | fit to p.2 figures; UNVERIFIED |
| gamma = 2/3 gives the 3:1 compress slope | HYPOTHESIS | arithmetic only; mechanism [?] |
| K = 400*PR^2 taper, +/-20 dB gain range, 0 dBFS = +16 dBm | NOT IN MANUAL | [?] |
| Matches a real LA-2A / "faithful" / "better than hardware" | NOT CLAIMED | no measurement exists |
