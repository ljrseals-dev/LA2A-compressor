#pragma once
#include "pluginterfaces/base/funknown.h"
#include "pluginterfaces/vst/vsttypes.h"
namespace LA2A {
static const Steinberg::FUID kProcessorUID (0xf1763ccd, 0xe53f04da, 0xac520c5a, 0xba24ec4f);
static const Steinberg::FUID kControllerUID(0xecfdca0e, 0xea936534, 0x75b61942, 0xd68d4808);
enum ParamIds : Steinberg::Vst::ParamID { kGain = 100, kPeakReduction = 101, kStereoLink = 102, kSlope = 103, kGainReduction = 104 };
constexpr double kGainRangeDb = 20.0;   // [?] not from the manual
#define LA2A_VERSION_STR "0.1.0"
}
