; Inno Setup script for Realmweave.
; Produces build\RealmweaveSetup.exe from the exported client + frozen server.
; Build:  iscc packaging\realmweave.iss   (run from the repo root)

#define AppName "Realmweave"
#define AppVersion "0.1.0"
#define AppPublisher "James Wilson"
#define AppURL "https://github.com/sagejw-svg/realmweave"

[Setup]
AppId={{B7A5E8C0-1E2D-4A6F-9C3B-REALMWEAVE01}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
OutputDir=..\build
OutputBaseFilename=RealmweaveSetup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
LicenseFile=..\LICENSE

[Files]
; These are produced by the build steps in docs/PACKAGING.md (or CI).
Source: "..\build\RealmweaveClient.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\build\RealmweaveServer.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "Launch-Realmweave.bat";         DestDir: "{app}"; Flags: ignoreversion
Source: "..\backend\config.json";        DestDir: "{app}"; Flags: onlyifdoesntexist
Source: "..\README.md";                  DestDir: "{app}"; Flags: ignoreversion isreadme

[Icons]
Name: "{group}\{#AppName}";           Filename: "{app}\Launch-Realmweave.bat"; WorkingDir: "{app}"; IconFilename: "{app}\RealmweaveClient.exe"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}";     Filename: "{app}\Launch-Realmweave.bat"; WorkingDir: "{app}"; IconFilename: "{app}\RealmweaveClient.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Run]
Filename: "{app}\Launch-Realmweave.bat"; Description: "Launch {#AppName}"; Flags: postinstall nowait skipifsilent shellexec
