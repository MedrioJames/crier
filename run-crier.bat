@echo off
rem Launch Crier without an installer. Runs through pythonw.exe (already
rem trusted by Windows), so it doesn't hit the SmartScreen unknown-publisher
rem block that an unsigned downloaded .exe does.
start "" "%~dp0.venv\Scripts\pythonw.exe" -m crier
