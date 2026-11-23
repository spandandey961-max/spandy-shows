Unicode true
!include "MUI2.nsh"
!include "FileFunc.nsh"
!include "x64.nsh"
Name "Spandy Shows"
OutFile "${OUTPUT}"
!ifndef SPANDY_DEFAULT_PATH
 !define SPANDY_DEFAULT_PATH "$LOCALAPPDATA\Programs\Spandy Shows"
!endif
InstallDir "${SPANDY_DEFAULT_PATH}"
InstallDirRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\SpandyShows" "InstallLocation"
RequestExecutionLevel user
SetCompressor zlib
!ifndef VERSION
 !define VERSION "1.3.0"
!endif
!ifndef VERSION_LABEL
 !define VERSION_LABEL "${VERSION}"
!endif
VIProductVersion "${VERSION}.0"
VIAddVersionKey "CompanyName" "Spandan"
VIAddVersionKey "ProductName" "Spandy Shows"
VIAddVersionKey "FileDescription" "Spandy Shows Setup"
VIAddVersionKey "FileVersion" "${VERSION_LABEL}"
VIAddVersionKey "LegalCopyright" "Bundled components retain their upstream licenses."
!define MUI_ICON "${BUNDLE}\Spandy Shows.ico"
!define MUI_UNICON "${BUNDLE}\Spandy Shows.ico"
!define MUI_ABORTWARNING
!define MUI_FINISHPAGE_RUN "$INSTDIR\Spandy Shows.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Open Spandy Shows"
!define MUI_DIRECTORYPAGE_TEXT_TOP "Choose where to install Spandy Shows. Select an empty folder or the folder of a completed Spandy Shows installation."
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"
Var NoIntegration
Function .onInit
 ${IfNot} ${RunningX64}
  MessageBox MB_ICONSTOP "This edition requires 64-bit Windows on an Intel or AMD computer."
  Abort
 ${EndIf}
 ${GetParameters} $0
 ${GetOptions} $0 "/NOINTEGRATION" $NoIntegration
 IfErrors +2 0
 StrCpy $NoIntegration "1"
 SetShellVarContext current
 ; An interrupted install can leave files without a valid marker.
 ; A sibling folder lets setup complete without taking ownership of that folder.
 StrCmp "$INSTDIR" "${SPANDY_DEFAULT_PATH}" 0 init_done
 Call CheckInstallDirectory
 StrCmp $0 "1" init_done
 StrCpy $2 "1"
 find_clean_folder:
 StrCpy $INSTDIR "${SPANDY_DEFAULT_PATH} ($2)"
 Call CheckInstallDirectory
 StrCmp $0 "1" init_done
 IntOp $2 $2 + 1
 IntCmp $2 100 init_done find_clean_folder init_done
 init_done:
FunctionEnd
Function CheckInstallDirectory
 IfFileExists "$INSTDIR\*" 0 available
 ReadINIStr $1 "$INSTDIR\spandy-install.ini" "App" "Id"
 StrCmp $1 "SpandyShows.Desktop" 0 occupied
 ReadINIStr $1 "$INSTDIR\spandy-install.ini" "App" "Directory"
 StrCmp $1 "$INSTDIR" available
 occupied:
 StrCpy $0 "0"
 Return
 available:
 StrCpy $0 "1"
FunctionEnd
Function .onVerifyInstDir
 ${GetFileName} "$INSTDIR" $0
 StrCmp $0 "" invalid_dir
 StrCmp "$INSTDIR" "$WINDIR" invalid_dir
 StrCmp "$INSTDIR" "$DESKTOP" invalid_dir
 StrCmp "$INSTDIR" "$PROFILE" invalid_dir
 StrCmp "$INSTDIR" "$LOCALAPPDATA" invalid_dir
 StrCmp "$INSTDIR" "$APPDATA" invalid_dir
 StrCmp "$INSTDIR" "$PROGRAMFILES64" invalid_dir
 Call CheckInstallDirectory
 StrCmp $0 "1" 0 invalid_dir
 Return
 invalid_dir:
 Abort
FunctionEnd
Section "Spandy Shows" MainSection
 Call .onVerifyInstDir
 IfFileExists "$INSTDIR\Spandy Shows.exe" 0 write_files
 ClearErrors
 FileOpen $0 "$INSTDIR\Spandy Shows.exe" a
 IfErrors running_app
 FileClose $0
 Goto write_files
 running_app:
 MessageBox MB_ICONSTOP "Close Spandy Shows before updating. If it is already closed, check that you can write to the installation folder." /SD IDOK
 SetErrorLevel 1
 Abort
 write_files:
 SetOutPath "$INSTDIR"
 File /r "${BUNDLE}\*"
 WriteINIStr "$INSTDIR\spandy-install.ini" "App" "Id" "SpandyShows.Desktop"
 WriteINIStr "$INSTDIR\spandy-install.ini" "App" "Directory" "$INSTDIR"
 WriteUninstaller "$INSTDIR\Uninstall Spandy Shows.exe"
 StrCmp $NoIntegration "1" skip_integration
 CreateShortcut "$DESKTOP\Spandy Shows.lnk" "$INSTDIR\Spandy Shows.exe" "" "$INSTDIR\Spandy Shows.ico" 0
 CreateShortcut "$SMPROGRAMS\Spandy Shows.lnk" "$INSTDIR\Spandy Shows.exe" "" "$INSTDIR\Spandy Shows.ico" 0
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\SpandyShows" "DisplayName" "Spandy Shows"
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\SpandyShows" "DisplayVersion" "${VERSION_LABEL}"
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\SpandyShows" "Publisher" "Spandan"
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\SpandyShows" "InstallLocation" "$INSTDIR"
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\SpandyShows" "DisplayIcon" "$INSTDIR\Spandy Shows.exe"
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\SpandyShows" "UninstallString" '$\"$INSTDIR\Uninstall Spandy Shows.exe$\"'
 WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\SpandyShows" "NoModify" 1
 WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\SpandyShows" "NoRepair" 1
 skip_integration:
SectionEnd
Section "Uninstall"
 SetShellVarContext current
 ReadINIStr $0 "$INSTDIR\spandy-install.ini" "App" "Id"
 StrCmp $0 "SpandyShows.Desktop" 0 unsafe_uninstall
 ReadINIStr $0 "$INSTDIR\spandy-install.ini" "App" "Directory"
 StrCmp $0 "$INSTDIR" 0 unsafe_uninstall
 ReadRegStr $0 HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\SpandyShows" "InstallLocation"
 StrCmp $0 "$INSTDIR" 0 remove_app
 Delete "$DESKTOP\Spandy Shows.lnk"
 Delete "$SMPROGRAMS\Spandy Shows.lnk"
 DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\SpandyShows"
 remove_app:
 RMDir /r "$INSTDIR"
 ; Device data is deliberately retained so uninstalling cannot erase programs.
 Goto done_uninstall
 unsafe_uninstall:
 MessageBox MB_ICONSTOP "The installed app folder could not be verified. No files were removed."
 Abort
 done_uninstall:
SectionEnd
