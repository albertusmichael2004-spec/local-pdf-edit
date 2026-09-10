#preproc ispp

#ifndef MyAppVersion
  #error MyAppVersion must be supplied by build_installer.ps1
#endif
#ifndef PayloadFileList
  #error PayloadFileList must be supplied by build_installer.ps1
#endif
#ifndef PayloadManifest
  #error PayloadManifest must be supplied by build_installer.ps1
#endif
#ifndef InstallerOutputDir
  #error InstallerOutputDir must be supplied by build_installer.ps1
#endif

#define MyAppName "Local PDF Workbench"
#define MyAppExeName "LocalPDFWorkbench.exe"
#define MyAppPublisher "Albertus Michael"
#define MyAppId "E6B92402-5C15-4E50-A8D3-FF805E644E0D"

[Setup]
AppId={{{#MyAppId}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppCopyright=Copyright (C) 2026 {#MyAppPublisher}
DefaultDirName={autopf}\Local PDF Workbench
DefaultGroupName=Local PDF Workbench
DisableProgramGroupPage=yes
DisableDirPage=no
UsePreviousAppDir=yes
UsePreviousGroup=yes
OutputDir={#InstallerOutputDir}
OutputBaseFilename=LocalPDFWorkbench-Setup-x64-v{#MyAppVersion}
SetupIconFile=..\..\frontend\assets\images\app.ico
WizardImageFile=wizard-logo.bmp
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallFilesDir={app}
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=commandline
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
CloseApplications=yes
RestartApplications=no
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
SetupLogging=yes
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Installer
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
VersionInfoVersion={#MyAppVersion}

[Files]
; A temporary copy lets the update code compare the prior and incoming payloads.
Source: "{#PayloadManifest}"; Flags: dontcopy noencryption
#include PayloadFileList
Source: "{#PayloadManifest}"; DestDir: "{app}"; DestName: "payload-manifest.txt"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Local PDF Workbench"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{autoprograms}\Uninstall Local PDF Workbench"; Filename: "{uninstallexe}"
Name: "{app}\Uninstall Local PDF Workbench"; Filename: "{uninstallexe}"

[Registry]
Root: HKA; Subkey: "Software\Albertus Michael\Local PDF Workbench"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Albertus Michael\Local PDF Workbench"; ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"
Root: HKA; Subkey: "Software\Albertus Michael\Local PDF Workbench"; ValueType: string; ValueName: "UninstallPath"; ValueData: "{uninstallexe}"

[UninstallDelete]
Type: files; Name: "{autodesktop}\Local PDF Workbench.lnk"
Type: files; Name: "{app}\payload-manifest.txt"
Type: files; Name: "{app}\Uninstall Local PDF Workbench.lnk"
Type: dirifempty; Name: "{app}"

[Code]
const
  ProductRegistryKey = 'Software\Albertus Michael\Local PDF Workbench';
  UninstallRegistryKey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{E6B92402-5C15-4E50-A8D3-FF805E644E0D}_is1';
  IncomingVersion = '{#MyAppVersion}';

var
  ExistingInstallPage: TInputOptionWizardPage;
  InstalledVersion: String;
  InstalledPath: String;
  InstalledUninstallPath: String;
  HasExistingInstall: Boolean;
  InstalledVersionIsNewer: Boolean;
  MaintenanceUninstallLaunched: Boolean;
  DesktopShortcutCheck: TNewCheckBox;
  LaunchApplicationCheck: TNewCheckBox;
  OldPayloadFiles: TStringList;
  NewPayloadFiles: TStringList;

function QueryInstalledValue(const ValueName: String; var Value: String): Boolean;
begin
  Result := RegQueryStringValue(HKA, ProductRegistryKey, ValueName, Value);
  if not Result then
    Result := RegQueryStringValue(HKLM64, ProductRegistryKey, ValueName, Value);
  if not Result then
    Result := RegQueryStringValue(HKCU, ProductRegistryKey, ValueName, Value);
end;

function QueryUninstallValue(const ValueName: String; var Value: String): Boolean;
begin
  Result := RegQueryStringValue(HKA, UninstallRegistryKey, ValueName, Value);
  if not Result then
    Result := RegQueryStringValue(HKLM64, UninstallRegistryKey, ValueName, Value);
  if not Result then
    Result := RegQueryStringValue(HKCU, UninstallRegistryKey, ValueName, Value);
end;

function NextVersionPart(var VersionText: String): Integer;
var
  Separator: Integer;
  Part: String;
begin
  Separator := Pos('.', VersionText);
  if Separator = 0 then
  begin
    Part := VersionText;
    VersionText := '';
  end
  else
  begin
    Part := Copy(VersionText, 1, Separator - 1);
    Delete(VersionText, 1, Separator);
  end;
  Result := StrToIntDef(Part, 0);
end;

function CompareSemanticVersions(LeftVersion, RightVersion: String): Integer;
var
  Index: Integer;
  LeftPart: Integer;
  RightPart: Integer;
begin
  Result := 0;
  for Index := 1 to 4 do
  begin
    LeftPart := NextVersionPart(LeftVersion);
    RightPart := NextVersionPart(RightVersion);
    if LeftPart < RightPart then
    begin
      Result := -1;
      Exit;
    end;
    if LeftPart > RightPart then
    begin
      Result := 1;
      Exit;
    end;
  end;
end;

procedure DetectExistingInstall;
begin
  HasExistingInstall := QueryInstalledValue('InstallPath', InstalledPath);
  if not HasExistingInstall then
    HasExistingInstall := QueryUninstallValue('InstallLocation', InstalledPath);

  if HasExistingInstall then
  begin
    if not QueryInstalledValue('Version', InstalledVersion) then
      QueryUninstallValue('DisplayVersion', InstalledVersion);
    if not QueryInstalledValue('UninstallPath', InstalledUninstallPath) then
      QueryUninstallValue('UninstallString', InstalledUninstallPath);
    if (InstalledUninstallPath = '') and (InstalledPath <> '') then
      InstalledUninstallPath := AddBackslash(InstalledPath) + 'unins000.exe';
    InstalledVersionIsNewer := CompareSemanticVersions(InstalledVersion, IncomingVersion) > 0;
  end;
end;

procedure InitializeWizard;
var
  ExistingDescription: String;
begin
  DetectExistingInstall;
  if HasExistingInstall then
  begin
    if InstalledVersionIsNewer then
      ExistingDescription := 'Version ' + InstalledVersion + ' is installed. This setup contains older version ' + IncomingVersion + '.'
    else
      ExistingDescription := 'Version ' + InstalledVersion + ' is installed in:' + #13#10 + InstalledPath;

    ExistingInstallPage := CreateInputOptionPage(
      wpWelcome,
      'Existing installation detected',
      ExistingDescription,
      'Choose what you want Setup to do:',
      True,
      False);

    if InstalledVersionIsNewer then
      ExistingInstallPage.Add('Uninstall the installed version (downgrade is disabled)')
    else if CompareSemanticVersions(InstalledVersion, IncomingVersion) < 0 then
    begin
      ExistingInstallPage.Add('Update to version ' + IncomingVersion + ' (recommended)');
      ExistingInstallPage.Add('Uninstall Local PDF Workbench');
    end
    else
    begin
      ExistingInstallPage.Add('Repair version ' + IncomingVersion + ' (recommended)');
      ExistingInstallPage.Add('Uninstall Local PDF Workbench');
    end;
    ExistingInstallPage.SelectedValueIndex := 0;
  end;

  DesktopShortcutCheck := TNewCheckBox.Create(WizardForm);
  DesktopShortcutCheck.Parent := WizardForm.FinishedPage;
  DesktopShortcutCheck.Left := WizardForm.RunList.Left;
  DesktopShortcutCheck.Top := WizardForm.RunList.Top + ScaleY(28);
  DesktopShortcutCheck.Width := WizardForm.RunList.Width;
  DesktopShortcutCheck.Caption := 'Create a desktop shortcut';
  DesktopShortcutCheck.Checked := True;

  LaunchApplicationCheck := TNewCheckBox.Create(WizardForm);
  LaunchApplicationCheck.Parent := WizardForm.FinishedPage;
  LaunchApplicationCheck.Left := WizardForm.RunList.Left;
  LaunchApplicationCheck.Top := DesktopShortcutCheck.Top + DesktopShortcutCheck.Height + ScaleY(8);
  LaunchApplicationCheck.Width := WizardForm.RunList.Width;
  LaunchApplicationCheck.Caption := 'Launch Local PDF Workbench';
  LaunchApplicationCheck.Checked := True;
end;

function ExistingPageRequestsUninstall: Boolean;
begin
  Result := False;
  if WizardSilent or not HasExistingInstall then
    Exit;
  if InstalledVersionIsNewer then
    Result := ExistingInstallPage.SelectedValueIndex = 0
  else
    Result := ExistingInstallPage.SelectedValueIndex = 1;
end;

procedure LaunchInstalledUninstaller;
var
  ResultCode: Integer;
  Uninstaller: String;
begin
  Uninstaller := RemoveQuotes(InstalledUninstallPath);
  if not FileExists(Uninstaller) then
  begin
    MsgBox('The registered uninstaller was not found:' + #13#10 + Uninstaller, mbError, MB_OK);
    Exit;
  end;

  if Exec(Uninstaller, '', InstalledPath, SW_SHOWNORMAL, ewNoWait, ResultCode) then
  begin
    MaintenanceUninstallLaunched := True;
    WizardForm.Close;
  end
  else
    MsgBox('Windows could not start the uninstaller. Error code: ' + IntToStr(ResultCode), mbError, MB_OK);
end;

function IsSafeRelativePath(const RelativePath: String): Boolean;
begin
  Result :=
    (RelativePath <> '') and
    (RelativePath[1] <> '\') and
    (RelativePath[1] <> '/') and
    (Pos(':', RelativePath) = 0) and
    (Pos('..', RelativePath) = 0);
end;

function PayloadFileNeedsUpdate(const RelativePath, ExpectedSHA256: String): Boolean;
var
  TargetPath: String;
begin
  if not IsSafeRelativePath(RelativePath) then
  begin
    Result := False;
    Exit;
  end;

  TargetPath := AddBackslash(ExpandConstant('{app}')) + RelativePath;
  if not FileExists(TargetPath) then
  begin
    Result := True;
    Exit;
  end;

  try
    Result := CompareText(GetSHA256OfFile(TargetPath), ExpectedSHA256) <> 0;
  except
    Result := True;
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  OldManifestPath: String;
  NewManifestPath: String;
begin
  Result := '';
  if HasExistingInstall and InstalledVersionIsNewer then
  begin
    Result := 'A newer version (' + InstalledVersion + ') is already installed. Downgrade to ' + IncomingVersion + ' is disabled.';
    Exit;
  end;

  OldPayloadFiles := TStringList.Create;
  NewPayloadFiles := TStringList.Create;
  OldPayloadFiles.Sorted := True;
  NewPayloadFiles.Sorted := True;

  OldManifestPath := AddBackslash(ExpandConstant('{app}')) + 'payload-manifest.txt';
  if FileExists(OldManifestPath) then
    OldPayloadFiles.LoadFromFile(OldManifestPath);

  try
    ExtractTemporaryFile('payload-manifest.txt');
    NewManifestPath := AddBackslash(ExpandConstant('{tmp}')) + 'payload-manifest.txt';
    NewPayloadFiles.LoadFromFile(NewManifestPath);
  except
    Result := 'Setup could not read the embedded payload manifest. No installed files were changed.';
  end;
end;

procedure RemoveEmptyParentDirectories(const RelativePath: String);
var
  RelativeDirectory: String;
begin
  RelativeDirectory := ExtractFileDir(RelativePath);
  while RelativeDirectory <> '' do
  begin
    RemoveDir(AddBackslash(ExpandConstant('{app}')) + RelativeDirectory);
    RelativeDirectory := ExtractFileDir(RelativeDirectory);
  end;
end;

procedure RemoveObsoletePayloadFiles;
var
  Index: Integer;
  RelativePath: String;
  TargetPath: String;
begin
  if (OldPayloadFiles = nil) or (NewPayloadFiles = nil) then
    Exit;

  for Index := 0 to OldPayloadFiles.Count - 1 do
  begin
    RelativePath := Trim(OldPayloadFiles[Index]);
    if IsSafeRelativePath(RelativePath) and (NewPayloadFiles.IndexOf(RelativePath) < 0) then
    begin
      TargetPath := AddBackslash(ExpandConstant('{app}')) + RelativePath;
      if FileExists(TargetPath) and not DeleteFile(TargetPath) then
        Log('Could not remove obsolete payload file: ' + TargetPath)
      else
        RemoveEmptyParentDirectories(RelativePath);
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    RemoveObsoletePayloadFiles;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
  if (ExistingInstallPage <> nil) and (CurPageID = ExistingInstallPage.ID) and ExistingPageRequestsUninstall then
  begin
    LaunchInstalledUninstaller;
    Result := False;
    Exit;
  end;

  if (CurPageID = wpFinished) and not WizardSilent then
  begin
    if DesktopShortcutCheck.Checked then
      CreateShellLink(
        ExpandConstant('{autodesktop}\Local PDF Workbench.lnk'),
        'Local PDF Workbench',
        ExpandConstant('{app}\{#MyAppExeName}'),
        '',
        ExpandConstant('{app}'),
        ExpandConstant('{app}\{#MyAppExeName}'),
        0,
        SW_SHOWNORMAL);

    if LaunchApplicationCheck.Checked then
      ExecAsOriginalUser(
        ExpandConstant('{app}\{#MyAppExeName}'),
        '',
        ExpandConstant('{app}'),
        SW_SHOWNORMAL,
        ewNoWait,
        ResultCode);
  end;
end;

procedure CancelButtonClick(CurPageID: Integer; var Cancel, Confirm: Boolean);
begin
  if MaintenanceUninstallLaunched then
  begin
    Cancel := True;
    Confirm := False;
  end;
end;

procedure DeinitializeSetup;
begin
  if OldPayloadFiles <> nil then
    OldPayloadFiles.Free;
  if NewPayloadFiles <> nil then
    NewPayloadFiles.Free;
end;
