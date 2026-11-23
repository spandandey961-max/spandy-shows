# Spandy Shows

**See your code, step by step.**

An offline Windows desktop compiler and code execution visualizer for Python, Java and C.

## Download for Windows

### [Download Spandy Shows 1.3.0-preview.7 for Windows x64](https://github.com/spandandey961-max/spandy-shows/releases/download/v1.3.0-preview.7/Spandy-Shows-1.3.0-preview.7-Setup-Fixed-CI-Windows-x64.exe)

[View all release files and notes](https://github.com/spandandey961-max/spandy-shows/releases/tag/v1.3.0-preview.7)

For Windows 10 and 11 on Intel or AMD x64 PCs. The installer is about 671 MiB and includes Python, Java and C.

1. Download the Windows x64 installer above.
2. Open **Downloads** and double-click **Spandy-Shows-1.3.0-preview.7-Setup-Fixed-CI-Windows-x64.exe**.
3. Press the Windows key, type **Spandy Shows**, and open the app.

**Windows security notice:** This preview installer is unsigned. “Spandan” is a publisher display label, not a verified digital signature. SmartScreen may warn and Smart App Control may block it. Keep those protections enabled; do not disable them to install this preview.

## What it does

- Run Python, Java and C programs locally with interactive input.
- Visualize recorded execution with step controls and playback.
- Inspect variables, function frames, supported objects and pointer connections.
- Explore indexed 1D, 2D and 3D arrays.
- Edit with syntax highlighting, undo/redo, bracket matching and automatic indentation.
- Save, name, search and reopen programs locally.

Programs and settings are stored on your device under `%LOCALAPPDATA%\Spandy Shows`. The bundled compilers run on your PC; no cloud execution account is required. Only run code you trust. Programs run with your Windows user's permissions.

## Source code and development

- [Full source ZIP](https://github.com/spandandey961-max/spandy-shows/releases/download/v1.3.0-preview.7/Spandy-Shows-1.3.0-preview.7-Full-Source.zip)
- [Browse the source on GitHub](./spandy-shows/)
- [Windows publishing and Store preparation guide](./spandy-shows/docs/WINDOWS-PUBLISHING.md)
- [Store submission materials](./store-submission/)
- [MIT license](./LICENSE)

The interface uses React, TypeScript, CSS and Monaco Editor. FastAPI manages execution. CPython tracing, Java JDI and GDB collect execution states; Electron provides the desktop window, and SQLite stores local programs. No custom AI model is used.

## Preview 7 highlights

- Installer recovery for incomplete older installations.
- Fresh interactive input on repeated runs.
- Faster C compilation reuse and C visualization.
- Editor undo/redo and improved typing behavior.
- Updated Java compatibility and collection displays.

Visualization has recording limits and deep recursion can remain slow. Some advanced language features, graphical programs and third-party libraries are unsupported.

## Verify your download

The [preview.7 SHA-256 checksums](./Spandy-Shows-1.3.0-preview.7-SHA256SUMS.txt) match the installer and source ZIP linked above. In PowerShell, run:

```powershell
Get-FileHash .\Spandy-Shows-1.3.0-preview.7-Setup-Fixed-CI-Windows-x64.exe -Algorithm SHA256
```

The installer was built and checked by [GitHub Actions](https://github.com/spandandey961-max/spandy-shows/actions/runs/45135280941), including installation and removal checks on its Windows runner.

## Microsoft Store status

This repository includes draft listing and packaging materials. Spandy Shows is **not yet available in the Microsoft Store**. A valid Partner Center product identity, final package, privacy-policy review, certification checks and Microsoft's approval are still required. See the [Store preparation guide](./spandy-shows/docs/WINDOWS-PUBLISHING.md).
