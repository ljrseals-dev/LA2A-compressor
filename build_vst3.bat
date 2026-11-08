@echo off
setlocal EnableDelayedExpansion
REM ===== LA-2A Manual-Faithful VST3 build (Windows, Visual Studio 2022) =====
REM Usage: build_vst3.bat [install]     ("install" copies to %CommonProgramFiles%\VST3, needs admin)
REM Override SDK ref:  set VST3_SDK_TAG=<tag or branch>   (default below is UNVERIFIED - confirm it exists)
if "%VST3_SDK_TAG%"=="" set VST3_SDK_TAG=v3.7.12_build_20
set ROOT=%~dp0
cd /d "%ROOT%"

where git >nul 2>nul   || (echo [ERROR] git not found. Install Git for Windows. & exit /b 1)
where cmake >nul 2>nul || (echo [ERROR] cmake not found. Install CMake 3.19+ and add to PATH. & exit /b 1)

if not exist "external\vst3sdk\CMakeLists.txt" (
  echo Cloning Steinberg VST3 SDK %VST3_SDK_TAG% ...
  git clone --recursive --branch %VST3_SDK_TAG% https://github.com/steinbergmedia/vst3sdk.git external\vst3sdk
  if errorlevel 1 (
    echo [WARN] tag %VST3_SDK_TAG% failed; cloning default branch instead.
    rmdir /s /q external\vst3sdk 2>nul
    git clone --recursive https://github.com/steinbergmedia/vst3sdk.git external\vst3sdk || (echo [ERROR] SDK clone failed. & exit /b 1)
  )
)

cmake -S . -B build -G "Visual Studio 17 2022" -A x64 -DLA2A_BUILD_TESTS=ON || (echo [ERROR] configure failed. & exit /b 1)
cmake --build build --config Release --parallel || (echo [ERROR] build failed. & exit /b 1)

if exist "build\Release\la2a_core_test.exe" ( echo --- core test --- & "build\Release\la2a_core_test.exe" )

set VST=
for /r "build\VST3\Release" %%f in (LA2A_ManualFaithful.vst3) do set VST=%%f
if "%VST%"=="" for /d /r "build" %%d in (LA2A_ManualFaithful.vst3) do if exist "%%d" set VST=%%d
if "%VST%"=="" (echo [ERROR] .vst3 not found in build output. & exit /b 1)
echo Built: %VST%
if not exist dist mkdir dist
if exist "%VST%\" ( xcopy /e /i /y "%VST%" "dist\LA2A_ManualFaithful.vst3" >nul ) else ( copy /y "%VST%" "dist\LA2A_ManualFaithful.vst3" >nul )

if /i "%1"=="install" (
  set DEST=%CommonProgramFiles%\VST3\LA2A_ManualFaithful.vst3
  if exist "dist\LA2A_ManualFaithful.vst3\" ( xcopy /e /i /y "dist\LA2A_ManualFaithful.vst3" "!DEST!" >nul ) else ( copy /y "dist\LA2A_ManualFaithful.vst3" "!DEST!" >nul )
  echo Installed to !DEST!
)
echo Done. Output in dist\
endlocal
