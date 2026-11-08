cmake_minimum_required(VERSION 3.19)
project(LA2A_VST3 VERSION 0.1.0 LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Steinberg VST3 SDK location (build_vst3.bat clones it to external/vst3sdk)
set(VST3_SDK_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/external/vst3sdk" CACHE PATH "Path to Steinberg vst3sdk")
if(NOT EXISTS "${VST3_SDK_ROOT}/CMakeLists.txt")
  message(FATAL_ERROR "VST3 SDK not found at ${VST3_SDK_ROOT}. Run build_vst3.bat (or git clone --recursive https://github.com/steinbergmedia/vst3sdk).")
endif()

set(SMTG_ENABLE_VST3_PLUGIN_EXAMPLES OFF CACHE BOOL "" FORCE)
set(SMTG_ENABLE_VST3_HOSTING_EXAMPLES OFF CACHE BOOL "" FORCE)
set(SMTG_ENABLE_VSTGUI_SUPPORT OFF CACHE BOOL "" FORCE)   # no custom GUI yet
set(SMTG_CREATE_PLUGIN_LINK OFF CACHE BOOL "" FORCE)      # avoid needing admin to symlink into Common Files
add_subdirectory(${VST3_SDK_ROOT} ${CMAKE_BINARY_DIR}/vst3sdk)
smtg_enable_vst3_sdk()

smtg_add_vst3plugin(LA2A_ManualFaithful
  source/la2a_entry.cpp source/la2a_processor.cpp source/la2a_processor.h
  source/la2a_controller.cpp source/la2a_controller.h source/la2a_cids.h source/la2a_core.h)
target_include_directories(LA2A_ManualFaithful PRIVATE source)
target_link_libraries(LA2A_ManualFaithful PRIVATE sdk)

option(LA2A_BUILD_TESTS "Build headless core test" OFF)
if(LA2A_BUILD_TESTS)
  add_executable(la2a_core_test tests/core_test.cpp)
  target_include_directories(la2a_core_test PRIVATE source)
endif()
