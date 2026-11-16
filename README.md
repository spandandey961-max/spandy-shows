# Spandy Shows

**See your code, step by step.**

An offline Windows desktop compiler and code execution visualizer for Python, Java and C.

## Download for Windows

### [Download Spandy Shows 1.2.0 — Windows installer (.exe)](https://github.com/spandandey961-max/spandy-shows/releases/download/v1.2.0/Spandy-Shows-1.2.0-Setup-Windows-x64.exe)

[Download the Windows sharing ZIP](https://github.com/spandandey961-max/spandy-shows/releases/download/v1.2.0/Spandy-Shows-1.2.0-Windows-Share.zip) · [Download the full source code ZIP](./Spandy-Shows-1.2.0-source.zip) · [All releases](https://github.com/spandandey961-max/spandy-shows/releases)

The installer download is approximately 636 MiB. It includes the required Python, Java and C runtimes. You do not need to install those separately.

1. Download the EXE above on a Windows PC.
2. Double-click it and follow the installation steps.
3. Open **Spandy Shows** from the desktop or Start menu.

For the sharing ZIP, extract it first and run the installer inside. A browser may ask where to save a download. Downloading does not automatically install or launch the app.

**Supported:** Windows 10/11 on Intel/AMD x64. This release is not an Android, macOS, Linux or Windows ARM build. The installer is unsigned, so Windows may display a publisher warning.

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
