# Spandy Shows

Current source edition **1.3.0-preview.7**, prepared 23 November 2026. Publisher **Spandan**.

This edition restores syntax colors on the first editor opened, enables matching brackets and quotes, and uses four-space indentation with language-aware block indentation. The desktop draft is read once at startup to reduce typing overhead. It also includes the Java compilation cache and incremental live replay improvements. See [current release notes](docs/RELEASES.md).

The full source archive contains the React/TypeScript frontend in `src/`, Python service and C/Java tracing code in `backend/`, Electron window and installer code in `desktop/`, original assets in `public/`, and build scripts and tests. Start with the development instructions below or [desktop build instructions](docs/BUILD-DESKTOP.md). Source dependencies and upstream runtimes are installed during setup. Installed programs and personal drafts stay in the device data folder.

**See your code, step by step.**

A responsive compiler and learning workspace for real Python, Java and C execution. Run code for complete output, or Visualize for reversible trace playback. Includes Monaco, real program input, optional object/reference diagrams, examples, errors, keyboard controls, copy/download code, full-page themes, browser-local saving and server-persisted share links.

The original Spandy Shows source code and project documentation are available under the [MIT License](LICENSE). Bundled third-party components keep their own licenses and notices.

For the current preview's compiler and visualizer coverage, see [DSA compatibility](docs/COMPATIBILITY.md).

## Open the working local website

For an **extract-and-run Windows edition**, use the separate `Spandy-Shows-Portable-Windows-x64.zip` package. Extract the entire ZIP and double-click **Start Spandy Shows.exe**. It includes its own Python/dependencies, JDK and GCC/GDB, opens the default browser, and needs no runtime installation, Node.js, administrator setup or PATH changes. **Stop Spandy Shows.exe** shuts down that copy. Existing starter examples, the supplied logo, live input and visualization are included. This package targets Windows 10/11 on Intel/AMD 64-bit computers; the source ZIP still uses the setup instructions below. The portable launcher/configuration source is in `portable/` and the assembly script is `scripts/build_portable.py`.

On the computer where this project was built, the working production build is at **http://127.0.0.1:8000/** while its services are running. The production browser build is in `dist/`. To launch that build later:

```powershell
cd <path-to-spandy-shows>
.\launch.ps1 -TrustedLocal
```

Open **http://127.0.0.1:8000/**. This uses the installed project environment and the paths in `runtime.local.json`. Trusted-local mode is for your own code; it does not isolate malicious programs. It binds to loopback. No public execution deployment has been made.

For Netlify hosting, see the [Netlify setup guide](docs/NETLIFY.md). The configuration is prepared, but deployment remains pending until a suitable hosted execution backend is available. The Netlify build requires that backend's HTTPS origin so a disconnected compiler cannot be published accidentally.

For Windows desktop packaging and publishing steps, see [Windows publishing](docs/WINDOWS-PUBLISHING.md). The current packaging script can build a Store package after you reserve the app identity in Partner Center.

On the build computer, the Windows task **Spandy Shows Local Server** starts the private service at sign-in using windowless Python at normal priority, with failure retries. Its entry point is `scripts/serve_local.py --trusted-local`; startup logs are in `.runtime/server.log` and unexpected job errors in `.runtime/service.log`. This task is machine-specific and is not installed by extracting the source archive. Your computer must remain awake and signed in. Manage or disable it through Windows Task Scheduler.

## Reproducible setup on another computer

Prerequisites: CPython 3.12, Node 24 (at least 24.19), pnpm 11.25.0. Real Java requires a JDK 21 with `java` and `javac`. Real C requires GCC (C17 support) and GDB with MI support. Engines may be on PATH or specified in the ignored `runtime.local.json` file. Windows users can download the verified portable toolchains into this project:

```powershell
python scripts/fetch_toolchains.py
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
pnpm install --frozen-lockfile
pnpm run build
.\launch.ps1 -TrustedLocal
```

On Linux/macOS:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
pnpm install --frozen-lockfile
pnpm run build
sh launch.sh --trusted-local
```

Portable Windows toolchains are not included in the source archive; the setup script downloads the locked release assets and checks their recorded SHA-256 hashes. They remain project-local and do not change system PATH.

For development, run FastAPI on port 8000 and `pnpm dev` in a separate terminal. Vite proxies `/api` to FastAPI. The built application is served by FastAPI when `dist/` exists.

## Docker Compose development isolation

Docker Engine or Docker Desktop is required. This path was packaged but could not be run on the build computer, which has no Docker runtime. It is **not a public production security boundary**.

1. Copy `.env.example` to `.env`, set a local database password and `SPANDY_JOB_HOST_ROOT` to an absolute existing directory on the Docker host.
2. `docker compose --profile build build worker-image`
3. `docker compose up --build api postgres`
4. Open http://127.0.0.1:8000/.

The API uses PostgreSQL; each compilation/execution job runs in a fresh container with no network, an unprivileged UID, read-only root, restricted capabilities, and CPU/memory/process/file/wall/output limits. C adds SYS_PTRACE for GDB. AddressSanitizer and UBSan are enabled for container C jobs; leak checking is disabled under ptrace. Windows trusted-local C tracing has no sanitizer coverage.

The Compose API accesses the Docker socket to create per-job containers. This is a powerful orchestration privilege and is intended only for private local development. Do not expose this Compose service on a public network. Production requires a separate authenticated worker broker and hardened sandbox/microVM infrastructure. See [deployment instructions](docs/DEPLOYMENT.md).

## Program input

Run and input submission are locked immediately while a request is in flight, so repeated clicks or Enter events cannot start a second job or submit the same response twice. Distinctive Java, C and Python declarations are detected before execution; for example, pasting a Java class while Python is selected switches to the Java compiler without altering the source. Selecting the matching language tab also retains that pasted source.

The **Java utility — one choice** example is a corrected version of the supplied nine-operation menu: it prints its menu once, performs the selected operation, closes Scanner and finishes. Open `/?example=utility-once&language=java`, or download `public/examples/java-utility-once.java` and save it as `Main.java`. Its original outer `do…while (choice != 0)` repeated the menu intentionally; normal program loops remain unchanged in the compiler. Each new Run click starts a fresh execution, while input continues the current process.

Select **Visualize** or **Run code** without entering input in advance. Output appears as the program runs. **Program input** appears below Output only when the real runtime needs another response, with the source line and an integer, number, character or text hint. Enter one response, then press **Enter** or **Continue**. The same process resumes until its next input read. The Java pattern example prints its menu, waits at `next().charAt(0)`, then prints the terms prompt and waits at `nextInt()`. Invalid integer input raises the actual JVM `InputMismatchException`; CPython conversions raise their actual exceptions. No substitute values are generated.

While Visualize waits, you can replay the recorded prefix with the arrows or timeline. **Go to input line** returns to the current read and enables the input field. Earlier snapshots remain immutable. Each step has a source highlight, explanation, variable values and an old → new list when values change. Completion keeps the full output; rewind to inspect the recorded execution. Submitted input is displayed in blue, separately from the runtime's cumulative stdout. Run code keeps the same interactive input flow without recording a trace.

C `scanf`/`fscanf`/`vscanf`/`vfscanf`, `getchar`/`fgetc`/`getc` and `fgets` stdin calls use the actual libc readers on a blocking pipe. Multiple conversions can wait for further responses inside the same original scanf call. Buffered input, including the newline left by scanf, retains normal C semantics. Invalid/failed reads stop before unread destinations are used; direct destinations remain labeled **awaiting input** until the real read succeeds. C programs intentionally handling failed reads or EOF, indirect/custom readers, Python unbounded `stdin.read()` and raw Java `System.in` EOF workflows are outside this interface. Type labels are hints derived from the read statement; runtime conversion rules are authoritative (for example, Java `next().charAt(0)` takes the first character of a token).

The API preserves backward compatibility: jobs default to pre-supplied `stdin`; browser jobs use `interactive: true`. Saved/shared input is a transcript for reference and is never silently fed to a new interactive run. Total input is bounded to 4 KB and 128 responses. Waiting suspends the active execution timer, with a three-minute idle limit per response.

## Scope and limits

**Run code** executes to completion without recording intermediate snapshots. Long loops are not subject to the visualizer's 20,000-step cap. Both modes support the installed standard libraries. Python supports imports, builtins, user functions/classes, generators and async functions; generator/async suspension and resumption are labeled in playback. Java uses the declared public class name for the source file and discovers the class containing static main; package declarations and helper classes in the same source file work in both modes. C links libm for math calls. Third-party Python packages, external Java JARs and extra native libraries require installation/configuration; the app does not include every package ever published. See [language support](docs/SUPPORT.md). Native Run code uses real GCC/javac output and does not inspect frames or objects. **Visualize** records states for variable inspection, source highlighting and playback. Visualize publishes its first real state as soon as the debugger reaches user code. It stays paused on that state while the remaining trace is prepared; only your playback controls advance the display. Output is the selected step’s output, with live prompts shown at actual reads. All resource and supported-program boundaries still apply.

The workspace fits the viewport, with playback controls anchored at the bottom. They remain visible before execution and in compiler mode, disabled until a replayable visualization is available. Stepping, code highlighting, input, errors and variable changes never move the bar. On laptops the editor fills its panel and the wider output panel scrolls independently. On phones and tablets the stacked code and output scroll above the same persistent controls, with no panel-switching tabs.

Output has a simple heading and preserves every printed row within the scrolling execution details. Whitespace is preserved. Wide banners scale to fit the available width, down to an 8px monospaced font; unusually wide lines retain horizontal scrolling rather than corrupting their layout. Objects & memory starts closed. Its header button appears only when the current state contains actual relevant object records; programs without objects have no empty memory panel. Java's unused empty startup argument array is hidden in the presentation, while the raw trace stays unchanged and explicitly used arguments/user arrays remain visible. Variables remain visible during visualization.

Use **Copy code** to copy the full editor source, or the download button to save the language's source file. **Ctrl / Command + Enter** runs from the editor; **Ctrl / Command + Shift + Enter** visualizes. Outside typing fields, **Left / Right** steps, **Home / End** or **Ctrl / Command + Left / Right** jumps to first/last, and **Space** plays or pauses. Theme switching covers the entire page, editor, diagrams, inputs and dialogs. The supplied gold Spandy Shows logo is preserved in `public/spandy-shows-icon.png` for the header, favicon and touch icon; the supplied full wordmark is `public/spandy-shows-logo.png` and is referenced in social metadata.

See [language support](docs/SUPPORT.md) for the exact constructs, timing convention and known limitations. Java uses `public class Main` and `public static void main(String[] args)`. C has debugger-visible local values whose initialization status is unknown unless separately instrumented. Pointers connect to displayed symbols, fields, rows and individual array elements; arbitrary pointers are not dereferenced. Dynamic allocation/freed/out-of-bounds state is not inferred.

10,000 source lines, 1 MiB UTF-8 source, 4 KB input, 20,000 snapshots in Visualize, 60 seconds of active work for Run code and 300 seconds for Visualize preparation, including compilation, three minutes of idle waiting per response, a local memory budget based on 25% of device RAM (512–4,096 MiB by default; Docker remains 768 MiB), 8 KB output per stream, 64 MiB trace, 256 MiB workspace files, 50 frames, 80 objects, 6 traversal levels and 40 items per collection. Run code returns a single completion or termination observation. Two workers run concurrently with eight queued/running/waiting jobs total. Job traces expire after an hour; the in-memory store has 128 entries. Job/save/share writes are limited to 20 per minute per client; input responses have a separate 120-per-minute limit. Local limits are monitoring controls; Docker additionally enforces cgroups and process/file limits.

## Save and share

“Save locally” stores up to 30 programs in this browser on this device. “Share” persists source, language, input, title and selected step in the service and creates an unguessable URL. Anyone with the URL can read the source. Retention is 30 days; expired rows are removed on the next save. A recipient re-executes the program to obtain a new real trace. Localhost links work only on the computer serving them. Basic use needs no account. Server APIs also support saving programs via `POST /api/programs`. Local service persistence uses SQLite when `DATABASE_URL` is absent.

## Verify

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m tests.verify_examples
node --experimental-strip-types --test tests/*.test.ts tests/*.test.mjs
pnpm run build
```

Native tests skip only when their engine is unavailable. The recorded [verification report](VERIFICATION.md) distinguishes passing local checks from unverified deployment infrastructure. No hardcoded or guessed execution traces are used.

## Project guide

- `src/`: React/TypeScript interface, editor, responsive output and optional SVG diagram.
- `backend/`: FastAPI, schema validation, job supervisor, CPython tracer, Java JDI tracer and GDB/MI adapter.
- `tests/`: state/identity tests, API integration checks and verified language examples.
- `migrations/`: persistence schema.
- [Architecture](docs/ARCHITECTURE.md), [trace format](docs/TRACE.md), [support](docs/SUPPORT.md), [deployment](docs/DEPLOYMENT.md).

The interaction model was studied from [Python Tutor](https://pythontutor.com/index.html). Spandy Shows has its own interface and branding. Tracers follow the official [CPython tracing hooks](https://docs.python.org/3.12/library/sys.html#sys.settrace), [Java Debug Interface](https://docs.oracle.com/en/java/javase/21/docs/api/jdk.jdi/com/sun/jdi/package-summary.html), and [GDB/MI](https://sourceware.org/gdb/current/onlinedocs/gdb.html/GDB_002fMI.html).
# Spandy Shows desktop edition

The Windows desktop release opens in its own native window, includes the supplied logo, creates desktop and Start menu shortcuts, and keeps named programs in a permanent local SQLite library. Closing the window shuts down the app's own compiler service and workers. Python, Java, C, real input, visualization, diagrams, playback and the corrected editor cursor are retained.

Use `Spandy-Shows-Setup-Windows-x64.exe` for a normal per-user installation, or extract `Spandy-Shows-Desktop-Windows-x64.zip` and transfer its whole **Spandy Shows** folder. Open **Spandy Shows.exe**. First launch of the copyable edition registers this location's shortcuts. Both releases include every required runtime; no cloud or separate compiler installation is needed. They target Windows 10/11 Intel/AMD x64 and are unsigned.

Named programs, theme, draft and window settings are stored in `%LOCALAPPDATA%\Spandy Shows`, independently of the app files. My programs supports search, rename, reopening and deletion. Native File → Open reads source files and exported `.spandy.json` files; Share exports a program file for manual transfer. Desktop source and installer configuration are in `desktop/`; assembly scripts are in `scripts/build_desktop.py` and `scripts/brand_windows.py`. See `desktop/README-DESKTOP.txt` for user instructions and retained limits.


Desktop 1.2.0 adds indexed 1D arrays, 2D rows/columns and 3D slices; pointer aliases follow exact displayed elements. Runtime-sized C arrays are inspected only after their declaration. See [release notes](docs/RELEASES.md).

Developers can rebuild the complete offline app and installer using [desktop build instructions](docs/BUILD-DESKTOP.md).
