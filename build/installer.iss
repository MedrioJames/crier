; Inno Setup script for Crier.  Compile with the Inno Setup Compiler (iscc):
;   iscc build\installer.iss
; Expects PyInstaller output in dist\Crier\  (run pyinstaller build\crier.spec first).

#define MyAppName "Crier"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "MedrioJames"
#define MyAppExeName "Crier.exe"
#define MyAppURL "https://github.com/MedrioJames/crier"

[Setup]
AppId={{B7F6B3C2-CR13-4E7A-9E21-CRIER0000001}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputBaseFilename=Crier-Setup-{#MyAppVersion}
OutputDir=..\dist
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
SetupIconFile=..\crier\resources\crier.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"
Name: "startup"; Description: "Start Crier when I log in"; GroupDescription: "Startup:"

[Files]
Source: "..\dist\Crier\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startup

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Crier"; Flags: nowait postinstall skipifsilent
