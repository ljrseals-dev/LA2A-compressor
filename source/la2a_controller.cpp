#include "la2a_controller.h"
#include "la2a_cids.h"
#include "public.sdk/source/vst/vstparameters.h"
using namespace Steinberg; using namespace Steinberg::Vst;
namespace LA2A {
tresult PLUGIN_API Controller::initialize(FUnknown* ctx) {
    tresult r = EditController::initialize(ctx); if (r != kResultOk) return r;
    parameters.addParameter(new RangeParameter(USTRING("Gain"), kGain, USTRING("dB"), -kGainRangeDb, kGainRangeDb, 0.0));
    parameters.addParameter(new RangeParameter(USTRING("Peak Reduction"), kPeakReduction, USTRING("%"), 0.0, 100.0, 40.0));
    parameters.addParameter(STR16("Stereo Link"), nullptr, 1, 0, ParameterInfo::kCanAutomate, kStereoLink);
    auto* slope = new StringListParameter(USTRING("Limit/Compress"), kSlope);
    slope->appendString(USTRING("Limit")); slope->appendString(USTRING("Compress")); // switch exists only after serial 572 (addendum 11-66)
    parameters.addParameter(slope);
    parameters.addParameter(new RangeParameter(USTRING("Gain Reduction"), kGainReduction, USTRING("dB"), 0.0, 40.0, 0.0, 0,
                                               ParameterInfo::kIsReadOnly));
    return kResultOk;
}
}
