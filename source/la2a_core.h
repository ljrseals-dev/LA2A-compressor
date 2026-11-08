// LA-2A manual-faithful behavioral core (C++ port of docs/reference_model_python.py).
// NOT hardware-equivalent. Source of truth: Teletronix LA-2A manual (3-66 + 11-66 addendum).
// Every unmeasured number is UNVERIFIED; [?] = not in the manual.
#pragma once
#include <algorithm>
#include <cmath>

namespace la2a {

// EL panel + CdS cell. Both stages attack fast (manual p.2: ~10 us); release = fast stage + slow tail.
// Illumination = 0.5*fast + 0.5*slow (HYPOTHESIS). Release constants are UNVERIFIED and, in GAIN terms,
// do NOT yet meet the manual's ~60 ms / 0.5-5 s (see README "Known failures").
struct T4Cell {
    double fa = 0, fr = 0, sa = 0, sr = 0, f = 0, s = 0;
    static double coef(double t, double fs) { return std::exp(-1.0 / (std::max(t, 1.0 / fs) * fs)); }
    void prepare(double fs, double attack = 10e-6, double fastRel = 0.015, double slowRel = 2.5) {
        // At 48 kHz one sample = 20.8 us, so the 10 us attack is clamped to one sample (effective ~40-60 us).
        fa = sa = coef(attack, fs); fr = coef(fastRel, fs); sr = coef(slowRel, fs); reset();
    }
    void reset() { f = s = 0; }
    double step(double light) {
        double k = light > f ? fa : fr;  f = k * f + (1 - k) * light;
        k = light > s ? sa : sr;         s = k * s + (1 - k) * light;
        if (f < 1e-18) f = 0; if (s < 1e-18) s = 0;   // flush denormals
        return 0.5 * f + 0.5 * s;
    }
};

class Engine {
public:
    static constexpr int kMaxCh = 2;
    void prepare(double fs) {
        sr_ = fs; for (auto& c : cell_) c.prepare(fs);
        smooth_ = 1.0 - std::exp(-1.0 / (0.010 * fs));
        gain_ = gainT_; pr_ = prT_; grDb_ = 0;
    }
    void reset() { for (auto& c : cell_) c.reset(); grDb_ = 0; }
    // gainDb: [?] range chosen by the plugin (+/-20 dB); pr 0..1; compress=false -> limit (1965 default)
    void setParams(double gainDb, double pr, bool compress, bool link) {
        gainT_ = std::pow(10.0, gainDb / 20.0); prT_ = pr; compress_ = compress; link_ = link;
    }
    double grDb() const { return grDb_; }

    void process(const float* const* in, float* const* out, int n, int nch) {
        nch = std::min(nch, kMaxCh);
        const double gamma = compress_ ? 2.0 / 3.0 : 1.0;      // slope 1-gamma = 1/3 -> 3:1 (addendum); mechanism [?]
        for (int i = 0; i < n; ++i) {
            gain_ += smooth_ * (gainT_ - gain_); pr_ += smooth_ * (prT_ - pr_);
            const double K = 400.0 * pr_ * pr_ + 1e-9;           // quadratic taper is a guess [?]
            double v[kMaxCh], light[kMaxCh], L[kMaxCh]; double worst = 0;
            for (int c = 0; c < nch; ++c) { v[c] = in[c][i]; light[c] = std::fabs(v[c]); } // EL responds to |V| (physics, p.4)
            if (link_ && nch > 1) {                              // terminals 6/7: shared control (p.5-6)
                const double l = std::max(light[0], light[1]);
                const double Ls = cell_[0].step(l); L[0] = L[1] = Ls;
            } else for (int c = 0; c < nch; ++c) L[c] = cell_[c].step(light[c]);
            for (int c = 0; c < nch; ++c) {
                // Smooth 1/(1+K*L^gamma); does NOT model the -30 dB breakaway / -20 dB knee (p.3). [HYPOTHESIS]
                const double att = 1.0 / (1.0 + K * (compress_ ? std::pow(L[c], gamma) : L[c]));
                // Gain applied post-attenuation (makeup style); manual says "input level" (p.3). [?]
                out[c][i] = static_cast<float>(v[c] * att * gain_);
                worst = std::max(worst, -20.0 * std::log10(att));
            }
            grDb_ = worst;
        }
    }
private:
    double sr_ = 48000, smooth_ = 0.001, gain_ = 1, gainT_ = 1, pr_ = 0.4, prT_ = 0.4, grDb_ = 0;
    bool compress_ = false, link_ = false; T4Cell cell_[kMaxCh];
};

} // namespace la2a
