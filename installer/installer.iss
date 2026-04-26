; Inno Setup script for Syroce KBS Agent
; Build with: iscc installer\installer.iss
; Output:    installer\Output\SyroceKBSAgent_Setup.exe

#define AppName       "Syroce KBS Agent"
#define AppVersion    "1.0.0"
#define AppPublisher  "Syroce"
#define AppURL        "https://syroce.example/kbs"
#define AppExeName    "SyroceKBSAgent.exe"
#define ServiceName   "SyroceKBSAgent"

[Setup]
AppId={{6D4F2A7E-1B9C-4F1A-9C8E-A1B2C3D4E5F6}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
OutputBaseFilename=SyroceKBSAgent_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon";  Description: "Masaustu kisayolu olustur"; GroupDescription: "Ek gorevler:"; Flags: unchecked
Name: "autostarttray"; Description: "Oturum aciliminda tepside baslat"; GroupDescription: "Ek gorevler:"; Flags: unchecked

[Files]
Source: "..\dist\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md";          DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}";        Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Registry]
; Optional tray autostart per user
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "SyroceKBSAgent"; ValueData: """{app}\{#AppExeName}"""; Flags: uninsdeletevalue; Tasks: autostarttray

[Run]
; Register the Windows service (admin required)
Filename: "{app}\{#AppExeName}"; Parameters: "--installer"; Flags: runhidden waituntilterminated; StatusMsg: "Hizmet kaydediliyor..."
; Set start type = Automatic (Delayed Start) — task acceptance criterion.
; This avoids competing with logon-time apps and lets the system settle
; (network, DPAPI subsystem) before the agent comes up.
Filename: "{sys}\sc.exe"; Parameters: "config {#ServiceName} start= delayed-auto"; Flags: runhidden waituntilterminated; StatusMsg: "Servis baslatma tipi ayarlaniyor..."
Filename: "{sys}\sc.exe"; Parameters: "description {#ServiceName} ""Syroce KBS Agent — otomatik EGM/Jandarma KBS gonderici"""; Flags: runhidden waituntilterminated
; Start the service
Filename: "{sys}\sc.exe"; Parameters: "start {#ServiceName}"; Flags: runhidden waituntilterminated; StatusMsg: "Hizmet baslatiliyor..."

[UninstallRun]
Filename: "{sys}\sc.exe"; Parameters: "stop {#ServiceName}";   Flags: runhidden waituntilterminated; RunOnceId: "StopSvc"
Filename: "{sys}\sc.exe"; Parameters: "delete {#ServiceName}"; Flags: runhidden waituntilterminated; RunOnceId: "DelSvc"

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
end;
