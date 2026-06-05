[Setup]
AppName=StockManager
AppVersion=1.0
AppPublisher=Ton Nom
DefaultDirName={autopf}\StockManager
DefaultGroupName=StockManager
OutputDir=.\installer_output
OutputBaseFilename=StockManager_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Files]
Source: "dist\StockManager.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "staticfiles\*"; DestDir: "{app}\staticfiles"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "media\*"; DestDir: "{app}\media"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist

[Icons]
Name: "{group}\StockManager"; Filename: "{app}\StockManager.exe"
Name: "{commondesktop}\StockManager"; Filename: "{app}\StockManager.exe"

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "StockManager"; ValueData: "{app}\StockManager.exe"; Flags: uninsdeletevalue

[Run]
Filename: "{app}\StockManager.exe"; Description: "Lancer StockManager maintenant"; Flags: nowait postinstall skipifsilent