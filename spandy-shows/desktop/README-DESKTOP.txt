SPANDY SHOWS — See your code, step by step.
Desktop edition 1.2.0 — Windows 10/11, Intel/AMD x64

COPYABLE APP
Copy this entire Spandy Shows folder to another compatible Windows computer.
Open Spandy Shows.exe. Keep app, resources, runtime, DLLs and the EXE together.
The first launch creates desktop and Start menu shortcuts for this location.
After moving the folder, open the EXE once to refresh those shortcuts.

INSTALLER
Alternatively transfer Spandy-Shows-Setup-Windows-x64.exe and double-click it.
It installs for the current Windows user and creates both shortcuts. No separate
Python, Java, C, Node or browser installation is needed. The app runs offline.

WINDOW AND PROGRAMS
Spandy Shows opens in its own native window. Close X stops its private backend
and running code. Minimize, maximize and the remembered window bounds work normally.
Multiple launches bring the existing window forward instead of starting duplicates.

Save names a program. Saving it again updates that program. My programs opens,
searches, renames and deletes your local saved programs. They have no expiry.
Your current draft and theme are restored next time the app opens.
File > Open loads code and exported .spandy.json program files. Share exports
a program file you can transfer yourself. Export code saves a normal source file.

DATA
Programs, settings, draft/browser storage and logs stay in:
  %LOCALAPPDATA%\Spandy Shows
My programs > Device folder opens this location. Programs are in programs.sqlite3.
These device saves are separate from the app folder, so reinstalling or copying
the app does not erase them. They do not travel when you copy just the app folder;
use Share to export programs you want to transfer. Old browser saves remain in
that browser; export their code and open it in the desktop app.

The app uses the included Python, Java and C engines. Run, Visualize, real input,
variable changes, explanations, objects/memory, playback controls, dark mode,
copying code, examples and the corrected typing cursor are preserved. Java input
and tracing helpers and the C input helper are precompiled; user code is compiled
for each new run.
Compilation and recording still take time. Current language/resource limits apply.
This is for your own trusted code. A desktop window does not isolate that code.
Graphics.h/desktop GUI programs, third-party libraries and multiple source files
remain outside the existing single-file compiler support.

The installer and app are unsigned. Follow the device's normal software policy.
Do not disable Windows protection. This is a Windows x64 build, not a Mac/ARM build.
License notices and editable source are included. See THIRD-PARTY-NOTICES.txt,
LICENSE, LICENSES.chromium.html, runtime licenses and app/desktop/.

VERSION 1.2.0
Arrays display as indexed cells, 2D rows and columns, and labelled 3D slices.
Pointers can follow displayed array elements and struct fields. Input-sized C
arrays no longer exhaust debugger memory before their declaration executes.
The local execution budget adapts to device RAM. Code supports up to 10,000
lines/1 MiB; Visualize records up to 20,000 steps/64 MiB. Existing language and
inspection bounds still apply; compiler errors and invalid programs are reported.
