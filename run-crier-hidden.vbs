' Launch Crier completely silently (no console flash) - for the Windows
' Startup folder, so it starts automatically at login without ever hitting
' a SmartScreen prompt (it runs through the already-trusted pythonw.exe,
' not a downloaded/unsigned .exe).
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

Set shell = CreateObject("WScript.Shell")
' The venv lives under %LOCALAPPDATA%, not this repo folder (a synced
' Google Drive Desktop mount) - keeps Python's own imports off that mount
' so the sync client doesn't add latency to every file access at startup.
pythonw = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Crier\venv\Scripts\pythonw.exe"
shell.CurrentDirectory = scriptDir
shell.Run """" & pythonw & """ -m crier", 0, False
