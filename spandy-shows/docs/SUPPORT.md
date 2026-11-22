# Spandy Shows supported programs

See your code, step by step. The [Preview 2 compatibility notes](COMPATIBILITY.md) describe the current coverage and verification gaps.

## Python

The app runs submitted code with CPython, including standard-library imports, recursion, generators, async functions, user classes, exceptions and standard input. The submitted file becomes the real `__main__` module. Programs can import uploaded helper modules. Windows multiprocessing supports the standard main guard.

Visualize records the editor source across user threads and identifies dynamic code executed in the submitted namespace. Generator yields and async suspension/resumption preserve frame identity. Collection and stack views are bounded. The visualizer observes supported library objects without invoking user representations or getters. Install compatible third-party packages in the worker environment and configure their module path in trusted-local mode. Missing packages produce Python's `ModuleNotFoundError`. Graphical output can be sent back as a generated image file.

## Java

Java runs on JDK 21. The service derives the filename from the top-level public class and supports package declarations, traditional and Java 21 preview main methods, uploaded source files and uploaded JARs. Standard JDK packages such as `java.util`, `java.math` and `java.time` work in both execution modes.

Visualize uses JDI to observe user threads, captured locals, arrays, shared references, supported standard collections and return values where available. The trace follows the editor source inside the debugged JVM. `System.exit` reports the exit result. Browser input uses streams. `System.console()` needs a terminal. Off-screen drawings can be returned as PNG or JPEG files.

## C

The app uses GNU C17 and builds with debug symbols. Standard headers and libm are available. Upload small C source and header files through Program options. The visualizer observes declared storage, runtime-sized arrays, structs, bitfields and supported heap allocations. It derives flexible array bounds from tracked allocation sizes when available. Union members share storage and the active member is unknown.

Pointers matching displayed declarations, fields or indexed cells link to that destination. The debugger uses allocation records from instrumented direct calls to observe bounded heap memory and flag freed and one-past addresses. It leaves other addresses as addresses. Before a declaration executes, its value is shown as unknown. Observed bytes after declaration may still be uninitialized, and address matches do not prove pointer provenance. C return events come from changes in the debugger stack. Platform-specific libraries such as legacy graphics libraries require a compatible toolchain and library setup.

Direct calls such as `scanf`, `fgets`, `fread` and `getchar` read from the real C input stream. They return the usual C results when a conversion fails or reaches EOF. Check return values before using the destination. The visualizer may keep a destination marked **awaiting input** when it cannot prove a complete read. Indirect or custom readers can require input supplied before the run.

## C++

Choose C++17 in Program options under the C tab. G++ compiles the editor source and small uploaded helper files. Supply input before running. Preset input ends at EOF. Visualize shows editor lines and declared storage. Live stream prompts and inspection of STL internals and `new` allocations need separate instrumentation.

## All languages

Program input appears below Output at an actual blocked read. Enter submits a response. **Send EOF** ends input for that run, and submitting an empty response sends a newline. Preset input runs before the first prompt. Programs can receive up to 512 interactive responses and 64 KiB of interactive input. **Program options** accepts one argument per line and up to eight small files. Open input and output paths under `files/`. The output files from the last completed run can be downloaded before the next run. Each direction allows up to 256 KiB in total. Run code displays up to 64 KiB per output stream. Visualize retains up to 8 KiB per stream in intermediate snapshots. The final step displays up to 64 KiB.

Programs accept up to 10,000 source lines and 1 MiB of UTF-8 source, including saved/shared programs. Source, input and debugger locations above line 1,000 are retained. Source length and recorded execution length are separate: Visualize still has a 20,000-snapshot, 64 MiB trace and 300-second active preparation limit. Run code has a 60-second active budget; time awaiting input is excluded.

No accounts are required. Run code executes without the 20,000-snapshot limit and shows final output. Visualize produces a bounded trace; stepping backward/forward replays snapshots without side effects. Editing source or language stops execution/playback and invalidates the displayed trace. Submitting a runtime response continues the current execution. Step explanations compare actual recorded values; highlighted before-line snapshots show what executes next. Phone/tablet layouts show code, input and output together in a stacked page. Objects & memory is initially collapsed and only offered when relevant actual records exist. Java's unused empty startup argument array is omitted from the display, without changing raw API traces; explicitly used arguments and user arrays remain visible. Python Run code may inspect final objects; Java and C object inspection requires Visualize.

Keyboard: Enter in Program input continues the waiting execution, Ctrl/Command + Enter runs from the editor, Ctrl/Command + Shift + Enter visualizes. Arrows step, Space plays/pauses, Home/End and Ctrl/Command + Left/Right jump to first/last; replay shortcuts leave editor typing and form fields alone. Dialogs use native focus trapping, buttons have labels/focus rings and reduced-motion preferences disable animation. Copy code copies the entire source. Themes cover all page surfaces and the editor. Output keeps its whitespace and expands vertically; banners scale down to 8px, with horizontal scrolling only for unusually wide content. The diagram is educational, not an exact physical memory layout.

Array presentation uses indexed cells for 1D arrays, rows and columns for 2D arrays, and labelled slices for 3D arrays, including nested Java arrays and Python lists. Shared rows and cycles retain their reference identities. C observes up to 1,024 cells per snapshot, in addition to the existing depth/object/collection bounds; execution uses the complete arrays. The bundled GDB Python observer reads only the bounded visible storage, without creating an unbounded var-object tree.
