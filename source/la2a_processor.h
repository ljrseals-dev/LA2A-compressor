#pragma once
#include "public.sdk/source/vst/vstaudioeffect.h"
#include "la2a_core.h"
namespace LA2A {
class Processor : public Steinberg::Vst::AudioEffect {
public:
    Processor();
    static Steinberg::FUnknown* createInstance(void*) { return static_cast<Steinberg::Vst::IAudioProcessor*>(new Processor); }
    Steinberg::tresult PLUGIN_API initialize(Steinberg::FUnknown* ctx) SMTG_OVERRIDE;
    Steinberg::tresult PLUGIN_API setBusArrangements(Steinberg::Vst::SpeakerArrangement* in, Steinberg::int32 nIn,
                                                     Steinberg::Vst::SpeakerArrangement* out, Steinberg::int32 nOut) SMTG_OVERRIDE;
    Steinberg::tresult PLUGIN_API canProcessSampleSize(Steinberg::int32 s) SMTG_OVERRIDE;
    Steinberg::tresult PLUGIN_API setupProcessing(Steinberg::Vst::ProcessSetup& s) SMTG_OVERRIDE;
    Steinberg::tresult PLUGIN_API setActive(Steinberg::TBool state) SMTG_OVERRIDE;
    Steinberg::tresult PLUGIN_API process(Steinberg::Vst::ProcessData& data) SMTG_OVERRIDE;
    Steinberg::tresult PLUGIN_API setState(Steinberg::IBStream* s) SMTG_OVERRIDE;
    Steinberg::tresult PLUGIN_API getState(Steinberg::IBStream* s) SMTG_OVERRIDE;
private:
    void apply();
    la2a::Engine engine_;
    double gain_ = 0.5, pr_ = 0.4, link_ = 0, slope_ = 0;   // normalized; slope 0 = Limit (1965 unit)
};
}
