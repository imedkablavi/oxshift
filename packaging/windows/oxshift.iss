#ifndef AppVersion
#define AppVersion "0.3.0-alpha.1"
#endif

[Setup]
AppId={{A2A61762-CE73-4A09-9344-7DA7F2DB31D5}
AppName=OxShift
AppVersion={#AppVersion}
AppPublisher=OxShift
DefaultDirName={autopf}\OxShift
DefaultGroupName=OxShift
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
OutputDir=..\..\release
OutputBaseFilename=OxShift-Setup-{#AppVersion}-windows-x86_64
UninstallDisplayName=OxShift
PrivilegesRequired=lowest

[Files]
Source: "..\..\dist\OxShift\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\..\scripts\windows\setup_virtual_mic.ps1"; DestDir: "{app}\tools"; Flags: ignoreversion
Source: "..\..\docs\WINDOWS_VIRTUAL_MIC.md"; DestDir: "{app}\docs"; Flags: ignoreversion

[Icons]
Name: "{group}\OxShift"; Filename: "{app}\OxShift.exe"
Name: "{autodesktop}\OxShift"; Filename: "{app}\OxShift.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Run]
Filename: "{app}\OxShift.exe"; Description: "Launch OxShift"; Flags: nowait postinstall skipifsilent
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File \"{app}\tools\setup_virtual_mic.ps1\""; Description: "Check Windows virtual microphone setup"; Flags: postinstall skipifsilent shellexec
