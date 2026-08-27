@echo off
echo Building Ember...

echo [1/3] Building injector...
cd src\injector
cl /EHsc /Fe:..\..\build\ember_injector.exe ember_injector.cpp
cd ..\..

echo [2/3] Building payload...
cd src\payload
cl /LD /EHsc payload.cpp /Fe:..\..\build\payload.dll
cd ..\..

echo [3/3] Done!
pause