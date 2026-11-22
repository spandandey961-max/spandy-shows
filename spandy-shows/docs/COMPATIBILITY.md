# DSA compatibility in 1.3.0 Preview 2

| Area | Implemented in the preview | Remaining work |
| --- | --- | --- |
| C compilation and input | GNU C17, original-source diagnostics, legacy `void main` handling, normal conversion and EOF results, direct input calls including `fread` and `getline`, and uploaded C source and headers. | Indirect reads and allocation calls through macros, libraries or function pointers are not instrumented. Legacy graphics headers, curses, SDL and OpenGL integrations require installed platform libraries and a separate configuration. |
| C memory | GDB inspects bounded live allocations made by instrumented `malloc`, `calloc`, `realloc` and `free`. It draws aliases and offsets, labels observed freed addresses, presents bitfields and bounded flexible arrays, and labels uncertainty about union members. | General C initialization and pointer provenance are unknown. Allocator coverage and read/write events are incomplete. Deep recursion performance needs Linux and Windows benchmarks. |
| Python | The user program runs as `__main__`. Standard spawn and pickling work for guarded programs. Threads have individual recorded stacks. Deep calls use a bounded display window. More built-in collections and scalar types are displayed. Dynamic strings in the submitted namespace are recorded without highlighting unrelated editor lines. | Subprocess frames are not recorded. Dynamic source text has no separate editor view. Custom representation and property getters are excluded from inspection. Optional third-party packages require a compatible environment. The six other comprehension samples were not provided. |
| Java | JDK 21 main methods, Java 21 compact programs, uploaded Java sources and JAR classpaths, thread-aware JDI, deep stack windows and more collection and scalar inspectors. | The browser provides streams, so `System.console()` still requires a real terminal. Child JVMs or native calls are not stepped through. Large-loop, startup and Docker timing need separate benchmarks. |
| C++ | C++17 is available under the C tab in **Program options**. Preset input ends at EOF. Visualize follows the editor source and declared storage. | Live C++ stream prompts and internal STL and `new`/`delete` inspection need dedicated instrumentation. |
| Shared UI | Program arguments, preset input, **Send EOF**, bounded file uploads/downloads, PNG/JPEG output previews, heap labels and indexed memory links. | File uploads cover small projects. A multi-file editor, library management and embedded desktop windows require separate UI work. |

Run Code and Visualize show up to 64 KiB per stream on the final step. Intermediate snapshots retain up to 8 KiB per stream to keep playback data smaller. The 20,000-step, 64 MiB trace and execution-time limits still apply. Visualize follows the editor source when uploaded helpers are present. Docker jobs retain restricted networking and a read-only root with a writable job folder.

## Next validation passes

1. Compare C heap images against linked lists, trees, reallocations and flexible arrays on Windows and Linux. Profile recursion and large arrays.
2. Compare the reported Python scoping snippets directly against CPython. Verify supported packages in the intended distribution before advertising them as bundled.
3. Benchmark Java cold launch and long loops, then validate Java threads in Docker. A terminal mode and actual graphical windows need separate platform testing.
4. Run the bundled desktop package on a clean Windows computer. Verify its signature and publisher status before publishing an installer.
