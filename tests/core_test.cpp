// Headless check of la2a_core.h (no SDK needed): g++ -std=c++17 -O2 -I source tests/core_test.cpp -o core_test
#include "la2a_core.h"
#include <cstdio>
#include <vector>
int main() {
    const double fs = 48000; la2a::Engine e; e.setParams(0, 0.5, false, false); e.prepare(fs);
    std::vector<float> x(int(fs * 9)), y(x.size());
    for (int i = 0; i < int(fs); ++i) x[i] = float(0.316 * std::sin(2 * M_PI * 1000.0 * i / fs));
    const float* in[1] = {x.data()}; float* out[1] = {y.data()}; e.process(in, out, int(fs), 1);
    std::printf("GR at end of 1 s burst: %.1f dB (python reference ~30 dB)\n", e.grDb());
    const float* in2[1] = {x.data() + int(fs)}; float* out2[1] = {y.data() + int(fs)}; e.process(in2, out2, int(fs * 8), 1);
    std::printf("GR 8 s after burst: %.1f dB (python: ~0.2 dB; <1 dB near 5 s)\n", e.grDb());
    // flat response at PR=0
    for (double f : {30.0, 1000.0, 15000.0}) {
        la2a::Engine u; u.setParams(0, 0.0, false, false); u.prepare(fs);
        std::vector<float> a(24000), b(24000); for (int i = 0; i < 24000; ++i) a[i] = float(0.03 * std::sin(2 * M_PI * f * i / fs));
        const float* i1[1] = {a.data()}; float* o1[1] = {b.data()}; u.process(i1, o1, 24000, 1);
        double sa = 0, sb = 0; for (int i = 12000; i < 24000; ++i) { sa += a[i] * a[i]; sb += b[i] * b[i]; }
        std::printf("flat %6.0f Hz: %.3f dB\n", f, 10 * std::log10(sb / sa));
    }
}
