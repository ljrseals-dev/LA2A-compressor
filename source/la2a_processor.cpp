#include "la2a_processor.h"
#include "la2a_cids.h"
#include "base/source/fstreamer.h"
#include "pluginterfaces/vst/ivstparameterchanges.h"
#include "pluginterfaces/vst/vstspeaker.h"
using namespace Steinberg; using namespace Steinberg::Vst;
namespace LA2A {

Processor::Processor() { setControllerClass(kControllerUID); }

tresult PLUGIN_API Processor::initialize(FUnknown* ctx) {
    tresult r = AudioEffect::initialize(ctx); if (r != kResultOk) return r;
    addAudioInput(STR16("Input"), SpeakerArr::kStereo);
    addAudioOutput(STR16("Output"), SpeakerArr::kStereo);
    return kResultOk;
}
tresult PLUGIN_API Processor::setBusArrangements(SpeakerArrangement* in, int32 nIn, SpeakerArrangement* out, int32 nOut) {
    if (nIn == 1 && nOut == 1 && in[0] == out[0] && (in[0] == SpeakerArr::kMono || in[0] == SpeakerArr::kStereo)) {
        removeAudioBusses(); addAudioInput(STR16("Input"), in[0]); addAudioOutput(STR16("Output"), out[0]); return kResultTrue;
    }
    return kResultFalse;
}
tresult PLUGIN_API Processor::canProcessSampleSize(int32 s) { return s == kSample32 ? kResultTrue : kResultFalse; }
tresult PLUGIN_API Processor::setupProcessing(ProcessSetup& s) { engine_.prepare(s.sampleRate); apply(); return AudioEffect::setupProcessing(s); }
tresult PLUGIN_API Processor::setActive(TBool state) { if (state) { engine_.reset(); } return AudioEffect::setActive(state); }

void Processor::apply() {
    engine_.setParams(-kGainRangeDb + 2.0 * kGainRangeDb * gain_, pr_, slope_ > 0.5, link_ > 0.5);
}

tresult PLUGIN_API Processor::process(ProcessData& data) {
    if (data.inputParameterChanges) {
        const int32 n = data.inputParameterChanges->getParameterCount();
        for (int32 i = 0; i < n; ++i) {
            IParamValueQueue* q = data.inputParameterChanges->getParameterData(i); if (!q) continue;
            const int32 pts = q->getPointCount(); if (pts <= 0) continue;
            int32 off = 0; ParamValue v = 0;
            if (q->getPoint(pts - 1, off, v) != kResultTrue) continue;
            switch (q->getParameterId()) {
                case kGain: gain_ = v; break; case kPeakReduction: pr_ = v; break;
                case kStereoLink: link_ = v; break; case kSlope: slope_ = v; break; default: break;
            }
        }
        apply();
    }
    if (data.numSamples <= 0 || data.numInputs < 1 || data.numOutputs < 1) return kResultOk;
    AudioBusBuffers& in = data.inputs[0]; AudioBusBuffers& out = data.outputs[0];
    const int32 nch = std::min<int32>(in.numChannels, out.numChannels);
    engine_.process(in.channelBuffers32, out.channelBuffers32, data.numSamples, nch);
    out.silenceFlags = 0;
    if (data.outputParameterChanges) {          // read-only GR meter for the host (normalized 0..40 dB)
        int32 idx = 0;
        if (IParamValueQueue* q = data.outputParameterChanges->addParameterData(kGainReduction, idx)) {
            int32 pi = 0; q->addPoint(0, std::min(1.0, engine_.grDb() / 40.0), pi);
        }
    }
    return kResultOk;
}
tresult PLUGIN_API Processor::setState(IBStream* s) {
    IBStreamer st(s, kLittleEndian); double g, p, l, sl;
    if (!st.readDouble(g) || !st.readDouble(p) || !st.readDouble(l) || !st.readDouble(sl)) return kResultFalse;
    gain_ = g; pr_ = p; link_ = l; slope_ = sl; apply(); return kResultOk;
}
tresult PLUGIN_API Processor::getState(IBStream* s) {
    IBStreamer st(s, kLittleEndian);
    st.writeDouble(gain_); st.writeDouble(pr_); st.writeDouble(link_); st.writeDouble(slope_); return kResultOk;
}
}
