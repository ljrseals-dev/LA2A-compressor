#include "la2a_cids.h"
#include "la2a_processor.h"
#include "la2a_controller.h"
#include "public.sdk/source/main/pluginfactory.h"
#include "pluginterfaces/vst/ivstaudioprocessor.h"
using namespace Steinberg; using namespace Steinberg::Vst;

bool InitModule()   { return true; }
bool DeinitModule() { return true; }

BEGIN_FACTORY_DEF("ljrseals-dev", "https://github.com/ljrseals-dev/LA2A-VST3", "mailto:none@example.invalid")
    DEF_CLASS2(INLINE_UID_FROM_FUID(LA2A::kProcessorUID), PClassInfo::kManyInstances, kVstAudioEffectClass,
               "LA-2A Manual-Faithful (behavioral)", Vst::kDistributable, Vst::PlugType::kFxDynamics,
               LA2A_VERSION_STR, kVstVersionString, LA2A::Processor::createInstance)
    DEF_CLASS2(INLINE_UID_FROM_FUID(LA2A::kControllerUID), PClassInfo::kManyInstances, kVstComponentControllerClass,
               "LA-2A Manual-Faithful Controller", 0, "", LA2A_VERSION_STR, kVstVersionString, LA2A::Controller::createInstance)
END_FACTORY
