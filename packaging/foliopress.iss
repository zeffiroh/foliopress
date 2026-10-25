; Inno Setup script — Windows installer for FolioPress.
; Built by packaging/build.py --installer (passes AppVersion and OutputName).

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef OutputName
  #define OutputName "FolioPress-setup"
#endif
#ifndef AppURL
  #define AppURL "https://github.com/zeffiroh"
#endif

[Setup]
AppId={{6B1E4F0C-3D7A-4C52-9E0B-F01105F0E55A}
AppName=FolioPress
AppVersion={#AppVersion}
AppVerName=FolioPress {#AppVersion}
AppPublisher=Mitali Aayat Mahnoor Sharma
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
DefaultDirName={autopf}\FolioPress
DefaultGroupName=FolioPress
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\release
OutputBaseFilename={#OutputName}
SetupIconFile=..\branding\foliopress.ico
LicenseFile=..\LICENSE
UninstallDisplayIcon={app}\FolioPress.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\FolioPress\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\FolioPress"; Filename: "{app}\FolioPress.exe"; AppUserModelID: "com.zeffiroh.foliopress"
Name: "{autodesktop}\FolioPress"; Filename: "{app}\FolioPress.exe"; Tasks: desktopicon; AppUserModelID: "com.zeffiroh.foliopress"

[Run]
Filename: "{app}\FolioPress.exe"; Description: "{cm:LaunchProgram,FolioPress}"; Flags: nowait postinstall skipifsilent
