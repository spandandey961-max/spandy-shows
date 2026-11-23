# Spandy Shows 1.3.0-preview.7

C compiler and visualizer performance update, 23 November 2026.

- Rebuild the precompiled desktop C helper from the shipped source. On Windows, reuse compiled C binaries after verifying the compiler, flags, source, active headers and uploaded files. Launch a fresh process for each run.
- Capture debugger state directly at each user-source stop and send differences from the previous state. Reconstruct full snapshots for existing replay controls.
- Reuse C symbol lookups, read newly appended input events and output, and publish the first eight recorded states promptly.
- Keep a newly arrived input prompt visible when the previous answer finishes submitting.

# Spandy Shows 1.3.0-preview.6

Editor and performance update, 23 November 2026. Publisher Spandan.

- Register the Python, Java and C/C++ grammars before creating the editor model. This fixes the first opened language displaying plain text after asynchronous grammar registration.
- Retain the existing dark and light syntax palettes for keywords, strings, comments and numbers.
- Enable automatic bracket and quote pairs, paired-delimiter overtyping and deletion, bracket matching, four-space indentation, and language-aware Enter and paste indentation. Python block headers indent after a colon. C and Java brace blocks indent on Enter.
- Read the desktop draft once at startup, removing repeated local storage reads and JSON parsing from the typing path.
- Keep Monaco's live typing buffer authoritative while React updates the surrounding UI. Only loading another document replaces the editor model, preventing a delayed text update from resetting the cursor or overwriting newer keystrokes.
- Include the previous local Java compilation cache, fresh per-run input sessions, incremental replay requests, and append-only Python/C live replay changes.
- Keep ordinary compiler diagnostics available after Run or Visualize. Editor token colors and indentation follow the language grammar. Semantic errors are checked by the actual compiler or interpreter during execution.

The source ZIP contains the complete app code, pinned dependency lockfiles, branding, tests and build instructions. Downloaded third-party runtime binaries and personal device data are excluded. The source package is a developer build input. The existing recording limits and compiler/library compatibility boundaries still apply.

# Spandy Shows 1.2.0

Windows desktop update, 13 November 2026.

- C pointers preserve aliases to individual array cells, nested rows and struct fields. A matrix, its first row and scalar storage keep distinct typed identities even when their addresses overlap.
- C arrays with dimensions read from input are not inspected before their declarations have executed. This fixes the reproduced 768 MiB debugger failure.
- Arrays use indexed cells, 2D rows/columns and labelled 3D slices. Nested Java arrays and Python lists use the same display; shared rows and cycles retain their reference identity. Clicking a reference focuses its destination.
- One bounded GDB Python observation replaces many per-element debugger requests. Inspection stays bounded while the real program uses its complete arrays.
- Local memory accounting uses private memory rather than adding duplicated working sets. Its default budget is one quarter of device RAM, bounded to 512–4,096 MiB. Java heaps use a portion of that budget. Container execution retains its 768 MiB cap.
- Source: 10,000 lines / 1 MiB. Visualize: 20,000 states / 64 MiB / 300 active seconds. Run: 60 active seconds. Compiler, workspace and UI help limits agree with the supervisor.
- Missing `main` in a C snippet produces an actionable diagnostic. Valid C still needs a function entry point.

Install the updated Windows x64 installer over the existing Spandy Shows installation, or extract the updated desktop ZIP to a new folder. Named programs stay in the separate device library. This build remains Windows 10/11 Intel/AMD x64; macOS/Linux/ARM editions are not included.

The app reports real compiler/runtime failures. Programs with invalid memory access, missing dependencies, nontermination, or unsupported libraries can still fail. Large memory views explicitly mark cropped observations; this is separate from the full program's execution. See SUPPORT.md for current boundaries.
