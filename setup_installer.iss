#define AppName "ACs Generator"
#define AppVersion "1.0"
#define AppPublisher "ODS Metering Systems"
#define AppExeName "Ac_app.exe"
#define SourceDir "dist\Ac_app"

[Setup]
AppId={{B3F2A1C4-9D7E-4F8B-A123-56789ABCDEF0}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={userappdata}\{#AppName}
DefaultGroupName={#AppName}
OutputDir=installer
OutputBaseFilename=Setup_ACsGenerator_v{#AppVersion}
SetupIconFile=logo\logo icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Área de Trabalho"; GroupDescription: "Ícones adicionais:"; Flags: unchecked

[Files]
; Aplicativo compilado (todos os arquivos da pasta dist\Ac_app)
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Templates Excel (ficam em templates\ dentro da pasta do exe para o app encontrá-los)
Source: "templates\TemplateAC_ORIGEM.xlsx";             DestDir: "{app}\templates"; Flags: ignoreversion
Source: "templates\TemplateAC_PRIO.xlsx";               DestDir: "{app}\templates"; Flags: ignoreversion
Source: "templates\TemplateAC_YINSON.xlsx";             DestDir: "{app}\templates"; Flags: ignoreversion
Source: "templates\TemplateAC_YINSON - ATLANTA.xlsx";   DestDir: "{app}\templates"; Flags: ignoreversion
Source: "templates\TemplateAC_PO_ORIGEM.xlsx";          DestDir: "{app}\templates"; Flags: ignoreversion
Source: "templates\TemplateAC_PO_PRIO.xlsx";            DestDir: "{app}\templates"; Flags: ignoreversion
Source: "templates\TemplateAC_PO_YINSON.xlsx";          DestDir: "{app}\templates"; Flags: ignoreversion
Source: "templates\TemplateAC_PO_YINSON - ATLANTA.xlsx"; DestDir: "{app}\templates"; Flags: ignoreversion
Source: "templates\Template_Linearizacao.xlsx";         DestDir: "{app}\templates"; Flags: ignoreversion
Source: "templates\template_importacao_instrumentos.xlsx"; DestDir: "{app}\templates"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}";           Filename: "{app}\{#AppExeName}"
Name: "{group}\Desinstalar {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}";     Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Abrir {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Remove o banco de dados criado pelo app ao desinstalar
Type: files; Name: "{app}\instrumentos.db"
