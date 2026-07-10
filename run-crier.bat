@echo off
rem Launch Crier without an installer. Runs through pythonw.exe (already
rem trusted by Windows), so it doesn't hit the SmartScreen unknown-publisher
rem block that an unsigned downloaded .exe does. The venv lives under
rem %LOCALAPPDATA% rather than this repo folder, which is a synced Google
rem Drive Desktop mount - keeping Python's own imports (and native DLLs
rem like onnxruntime's) off that mount avoids the sync client adding
rem latency to every file access during startup.
start "" /D "%~dp0" "%LOCALAPPDATA%\Crier\venv\Scripts\pythonw.exe" -m crier
