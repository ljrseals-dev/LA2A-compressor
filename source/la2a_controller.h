#pragma once
#include "public.sdk/source/vst/vsteditcontroller.h"
namespace LA2A {
class Controller : public Steinberg::Vst::EditController {
public:
    static Steinberg::FUnknown* createInstance(void*) { return static_cast<Steinberg::Vst::IEditController*>(new Controller); }
    Steinberg::tresult PLUGIN_API initialize(Steinberg::FUnknown* ctx) SMTG_OVERRIDE;
    // No custom editor yet: the host shows its generic parameter UI (see README).
};
}
