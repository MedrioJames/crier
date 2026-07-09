' Launch Crier completely silently (no console flash) - for the Windows
' Startup folder, so it starts automatically at login without ever hitting
' a SmartScreen prompt (it runs through the already-trusted pythonw.exe,
' not a downloaded/unsigned .exe).
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
pythonw = scriptDir & "\.venv\Scripts\pythonw.exe"

Set shell = CreateObject("WScript.Shell")
shell.Run """" & pythonw & """ -m crier", 0, False
