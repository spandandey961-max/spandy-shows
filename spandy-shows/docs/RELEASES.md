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
