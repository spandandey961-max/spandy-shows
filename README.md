# Spandy Shows

**See your code, step by step.**

An offline Windows desktop compiler and code execution visualizer for Python, Java and C.

## Download for Windows

### [Download Spandy Shows 1.2.0 — Windows installer (.exe)](https://github.com/spandandey961-max/spandy-shows/releases/download/v1.2.0/Spandy-Shows-1.2.0-Setup-Windows-x64.exe)

For Windows 10 and 11 on Intel or AMD x64 PCs. The download is about 636 MiB and includes Python, Java and C.

1. Click **Download Spandy Shows 1.2.0** above.
2. Open **Downloads** and double-click **Spandy-Shows-1.2.0-Setup-Windows-x64.exe**. Follow the setup prompts if Windows allows the installer to open.
3. Press the **Windows key**, type **Spandy Shows** and open the app. Choose an example and select **Visualize** to step through it.

**If Windows says “Smart App Control blocked an app”**  
Version 1.2.0 is unsigned. On a PC showing this message, close the notice and leave Smart App Control enabled. Windows has no per-app approval for this block. Use the releases page to check for a future signed version. [Microsoft’s explanation](https://support.microsoft.com/en-gb/windows/security/threat-malware-protection/smart-app-control-frequently-asked-questions) · [Spandy Shows releases](https://github.com/spandandey961-max/spandy-shows/releases)

## What it does

- Run real Python, Java and C programs, with input requested when execution reaches a read.
- Visualize recorded execution using previous/next, play/pause, a timeline and playback speed controls.
- Inspect variables, function frames, supported objects and pointer connections.
- Explore indexed 1D arrays, 2D rows and columns, and 3D slices.
- Edit code with syntax highlighting; copy, open and export source files.
- Save, name, rename, search and reopen programs locally.
- Use dark or light themes in a normal desktop window.

## Local storage

Programs and settings are stored on your device under `%LOCALAPPDATA%\Spandy Shows`, separately from the installation. Updates preserve that local library. The app runs the bundled compilers on your PC; no cloud execution account is required.

Only run code you trust. The local desktop edition executes programs with your user account's access.

## Source code and development

The [full source ZIP](./Spandy-Shows-1.2.0-source.zip) contains the implementation, tests, examples and rebuild documentation. Extract it and see `README.md`, `docs/ARCHITECTURE.md` and `docs/BUILD-DESKTOP.md` inside.

The interface uses React, TypeScript, CSS and Monaco Editor. FastAPI manages execution. CPython tracing hooks, Java JDI and GDB collect execution states; Electron supplies the desktop window, SQLite stores local programs, and NSIS builds the Windows installer. No custom AI model is needed to execute or visualize programs.

Valid program syntax and available dependencies are required. Standard libraries are supported, but arbitrary third-party packages and graphical libraries are not all bundled. Visualization uses bounded inspection and resource limits; see app Help and `docs/SUPPORT.md` in the source ZIP.

## Verify your download

SHA-256 for `Spandy-Shows-1.2.0-Setup-Windows-x64.exe`:

```text
bb3a0acc7be77cf280f361bc667b3b14e60e7546d24aee28c40538a2f0dc4fe4
```

[Release checksums and verification record](./Spandy-Shows-1.2.0-Checksums.json)

The interaction model was inspired by [Python Tutor](https://pythontutor.com/). Spandy Shows has its own interface, branding and execution integration.
