# Build Spandy Shows desktop from source

These steps are for a developer rebuilding the Windows app. Recipients of the installer or complete desktop ZIP do not need Python, Java, C, Node, or any cloud service installed separately.

Use Windows x64, CPython 3.12, Node and pnpm on the build machine. Start in the extracted `spandy-shows` source folder. Keep build outputs outside the source folder. The source archive includes the frontend, backend, GDB observer, Java tracers, native launcher, supplied branding, tests, installer configuration and pinned tool checksums. Downloaded upstream runtimes are included in the complete app ZIP, and are fetched separately when rebuilding from the smaller source ZIP.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
pnpm install --frozen-lockfile
pnpm run build
.\.venv\Scripts\python.exe scripts/fetch_toolchains.py
.\.venv\Scripts\python.exe scripts/fetch_desktop_tools.py
.\.venv\Scripts\python.exe scripts/build_portable.py --destination ../release/portable
.\.venv\Scripts\python.exe scripts/build_desktop.py --runtimes "../release/portable/Spandy Shows Portable/runtime" --electron desktop-tools/electron --destination "../release/desktop/Spandy Shows"
```

The app folder is now `../release/desktop/Spandy Shows`. Copy that whole folder, keeping its DLLs, resources, app files and runtime together. Its EXE opens the native window and keeps device programs under `%LOCALAPPDATA%\Spandy Shows`.

To create the installer, resolve paths and pass them directly to the pinned NSIS compiler:

```powershell
$bundle = (Resolve-Path "../release/desktop/Spandy Shows").Path
$output = [IO.Path]::GetFullPath("../release/Spandy-Shows-Setup-Windows-x64.exe")
$label = (Get-Content desktop/package.json -Raw | ConvertFrom-Json).version
$numericVersion = $label.Split('-')[0]
& desktop-tools/nsis-3.12/makensis.exe /V2 "/DBUNDLE=$bundle" "/DOUTPUT=$output" "/DVERSION=$numericVersion" "/DVERSION_LABEL=$label" desktop/installer.nsi
```

Use an empty test installation directory with `/NOINTEGRATION` for automated installation checks; normal installation creates Desktop/Start menu shortcuts. The included verification report records the tested Windows build. Runtime/tool licenses are retained by the assembly scripts. Source inspection limits, language boundaries, and unsigned packaging are described in SUPPORT.md and desktop/README-DESKTOP.txt.
