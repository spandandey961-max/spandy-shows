# Spandy Shows verification

## Desktop 1.2.0 — pointers and arrays (13 November 2026)

- Reproduced the original memory failure using an input-sized C array. The earlier observer created a GDB var object while that array's bounds/storage had not been initialized. The same program now completes; the sample sum is 12 for input 3 / 2 4 6.
- Reproduced lost links for p/q into a[1], and a 2D array's first row incorrectly referencing the containing matrix. Typed storage identities and element/field paths now retain those relationships. The sample prints 3 14 with both aliases targeting a[1].
- The complete backend/API suite passed 162 tests before the final C stepping consolidation. After that consolidation, all 55 selected C/input/trace regressions passed, including the >2,500-line program, 1,000 actual struct mutations, recursion, library calls, failures, sequential input, VLA matrices, 3D arrays, pointer-to-pointer and struct-field targets.
- Final C larger-source checks recorded 79.83 seconds for >2,500 executed source lines and 32.90 seconds for 1,000 struct mutation lines on this host, compared with 277.90 / 191.72 seconds in the earlier all-breakpoint strategy. These are local measurements, not speed guarantees. Compilation and real debugger recording take time; playback stays paused until advanced by the learner.
- All 27 frontend checks passed. TypeScript checking and production builds passed. The existing editor bundle size advisory and upstream TestClient/httpx deprecation warning remain.
- The actual Windows desktop app, using only its bundled engines with the normal compiler PATH removed, passed UI checks for exact pointer destinations, 1D mutation highlights, distinct 2D rows, 3D slices, Python/Java nested arrays, light/dark themes, phone layout, fixed playback controls and normal close. An input-sized 2×3 matrix accepted eight sequential responses in one execution and displayed all six values/output once.
- The device memory budget reported 4,096 MiB on the test host. Private memory accounting avoids adding duplicated working sets; source/trace limits and bounded inspector cropping are documented in Help and SUPPORT.md.
- The screenshot's bare C block is invalid without a main function. The compiler keeps that error and adds a targeted hint. Correct complete samples are available in Examples: Pointers into an array, Rows and columns, Inside a 3D array, Build a matrix from input.

Earlier sections below record historical revisions and their limits.


Verified locally on 11 October 2026 (Asia/Calcutta).

## Worker, Java entry point and larger-source revision

- The screenshot's Python worker failure was reproduced: anonymous `except` handlers and wildcard `match` patterns have `name=None` AST attributes. Identifier checking now checks strings before their length, preserving the identifier bound without crashing on these valid nodes.
- The exact pasted Python utility is retained in tests/fixtures/utility.py. All nine menu choices and exit completed in Run code and Visualize with standard math imports, user functions, generator expressions, match/case and exception handling. Visualize recorded 388 states. Invalid input caught by the user's ValueError handler completes normally.
- Java source filenames and launch classes now follow the declared top-level types and static main entry point. Package declarations, a public UtilityProgram, helper Box construction/methods/fields and live Scanner input completed in both modes. Debugger/input locations refer to UtilityProgram.java; compiler and runtime diagnostics use that filename. The editor header and downloaded source also use the declared filename.
- Shared source bounds are now 2,000 lines and 256 KiB of UTF-8 source for jobs, saves and shares. Schema/input/frame/diagnostic locations support that range. Each language accepted live integer input after line 1,000 in both modes and completed with the correct output.
- Separate tests actually execute 1,000 mutation statements in Python Visualize and Java/C Run code and Visualize. All completed; Visualize recorded more than 1,000 states with the final object/struct value of 1,000. Earlier Python object snapshots retain their original values.
- The targeted new regressions passed 22 checks. All 17 frontend checks and the TypeScript/production build passed. The existing Monaco bundle size advisory remains. Updated limits are documented in README.md and docs/SUPPORT.md; docs/trace.schema.json matches the runtime schema.
- A live check of all menu choices then caught a transient Windows deletion conflict while the API polled an input request. Python/C input cleanup and Java input publication/cleanup now retry brief sharing conflicts. C markers use Windows atomic replacement and retry cleanup, preventing a stale read marker from producing another prompt. These are bounded retries; permanent errors still surface.
- Nine additional input regressions passed: a forced cleanup sharing conflict, the exact Python utility with all 19 live responses in both modes, and 20 sequential reads in each language/mode. One actual execution continues across all responses.
- Final complete suite after the input sharing fix: **130 backend/API checks passed** in 377.43 seconds, with the existing upstream TestClient/httpx deprecation warning. All **17 frontend checks** and the production build passed.
- The actual windowless background server was restarted and verified healthy with Python, Java and C connected and the new 2,000-line/256-KiB source limits. The exact Python utility completed 19 live responses and 388 steps, with its first recorded state available in 0.218 seconds and total preparation/input-test time 3.765 seconds. Named/package Java UtilityProgram completed 16 steps; C with input above line 1,000 completed six steps and output Number: 42. Recorded prefixes stayed immutable. Native compilation/debugger startup still takes real time; these timings are local observations, not guarantees for arbitrary programs.

## Visualizer preparation and manual playback revision

- The user's C pattern produced the complete five-row output and 205 real debugger snapshots, including completion. It passed three repeated backend runs and three browser visualizations. Run code and Visualize produced identical output.
- Direct profiling reduced full C preparation from 37.251 seconds to 7.366â€“7.961 seconds (about five times faster). The first genuine snapshot was recorded in 0.645â€“1.094 seconds. Under simultaneous test load, the browser enabled the first paused view in 1.941 seconds; compilation/debugger startup still takes real time.
- Visualize publishes real recorded prefixes without advancing the cursor. The browser stayed at step 1 after all 205 states were prepared. In a second run, manually selecting step 2 during preparation kept step 2 selected after completion. Output stayed blank at those early states rather than revealing future pattern rows.
- Play/Pause and all navigation buttons retain their existing design. Twenty Next clicks had zero button drift at the default viewport. Play advanced during preparation (step 2 of 34 while the recording process was still running); new checkpoints do not restart the playback clock. First/last, Play/Pause, timeline, variable changes and the full five-row result were verified. The laptop view at 1366Ã—768 retained the fixed bottom controls and both panels; the viewport override was reset afterwards.
- The Java Scanner example opened paused at step 1 with the first read pending in the background. The inline character field appeared only at selected step 7/line 11. After submitting a, the cursor stayed at step 7; selecting the second read showed its integer field at step 9/line 13. After 4, completion preserved step 9 of 48 and did not show future pattern output. The same actual process and immutable-prefix behavior is covered by API tests.
- Limits now allow 10,000 snapshots and 32 MiB traces. Visualize has a separate 180-second preparation budget; Run code retains 25 seconds. Python, Java and C loops with more than 600 actual snapshots all completed. Nontermination, genuine runtime errors, input bounds, cancellation and output/memory bounds remain tested.
- A full-suite run caught a transient Windows file sharing conflict during checkpoint replacement. Atomic publishers now retry brief reader conflicts. The final full suite passed **86 backend/API tests and 13 frontend tests**. TypeScript checking and production build passed; the existing Monaco size advisory remains.
- Evidence: Spandy-Shows-paused-first-step.png and Spandy-Shows-complete-pattern-laptop.png in the parent outputs directory. Earlier sections below document prior revisions; their historical test counts and limits describe those revisions.

## Execution and interactive input

- **77 backend/API checks passed:** the existing 56 regression checks plus 21 live-input integration checks. CPython 3.12.14, Temurin JDK 21.0.12.1/JDI, WinLibs GCC 16.2.0/GDB 18.1. The only test warning is the upstream TestClient/httpx deprecation.
- Python, Java and C each passed two sequential real reads in both Run code and Visualize. The menu/prompt output exists before input is submitted; the same worker PID survives both responses. Previously recorded trace states remain unchanged. No source-prefix replay or substitute values are used.
- The user's clean Java Scanner pattern program passed all four choices a/b/c/d with n=4. It waits for a character at line 11, then an integer at line 13; n, i, j/k values are observed in the real trace. Invalid text at the second read produces the real InputMismatchException and no pattern output.
- Integer failures produce actual CPython ValueError, JVM InputMismatchException or C input_invalid diagnostics. Text and decimal reads passed in all three languages. Type hints do not change the language's conversion rules.
- C multi-conversion scanf stays inside its original read across two responses. A buffered newline consumed by getchar does not create another input request; 12 is followed by character code 10. The existing C input checks cover palindrome values, partial/failed reads and other stdin readers.
- Input waits do not spend the active execution budget. Waiting cancellation kills the job, stale/duplicate responses return 409, cumulative input is bounded, and idle expiry preserves the printed prompt.
- The existing regression suite covers compilation, standalone Run mode, loops above the visualization step cap, tracing/recursion, immutable/shared/cyclic objects, native errors, schema boundaries, queues/cancellation, save/share persistence and limits.
- Eleven frontend checks passed: seven existing reader/inspector checks plus four checks for truthful preceding-line attribution, recursive scope labels, variables leaving scope and mutation of an object whose reference remains unchanged. All 27 bundled examples were previously verified; tests/example-results.json records those results.
- TypeScript and production build passed. The Monaco bundle remains about 782 KB gzipped; the build succeeds with a size advisory.

## Browser checks

The running production app was checked in the in-app browser.

- No input field appears before execution reaches a real read. Your Java menu appears first; the inline character field appears at line 11, then the integer field at line 13. Enter and Continue submit a single response. No popup or pre-run input collection is used.
- Replay is available while waiting: First step shows the recorded entry frame; Go to input line returns to the live read. Completion preserves the output and all 48 recorded steps for a,4.
- Step 10 shows n created as 4 after line 13. Step 17 highlights line 17 and explains the observed i change from 1 to 2 after line 16. The variable table shows ch, n and i, with a change marker. Arrow keys and first/last/previous/next controls work.
- Invalid abc at the second read displays java.util.InputMismatchException, the Main.java:13 runtime location, retained prompts and submitted input, without pattern rows.
- Output retains its plain heading and whitespace. Input echo is blue and separate from raw runtime stdout. Step explanations have their own visualization section; they do not replace Output. Execution details now scroll within the upper workspace to keep playback visible.
- The restored visualizer was checked at 390px phone width with the stacked code/output/explanation/variables/playback layout. Resizing keeps the current input/code line visible in the wrapped editor. Inline input was checked in both full-page light and dark themes. Current dark mode, responsive layout, logo, copy/download controls and optional memory disclosure are preserved. Previous phase verification also exercised 320px phone and 768px tablet widths, full light/dark surfaces and large banners.
- Copy code matched the entire Java source. Ctrl/Command + Enter ran the Python compiler; Ctrl/Command + Shift + Enter produced its 17-step visualization. The C palindrome paused at scanf line 6, accepted 121 and printed Palindrome, with no empty memory section.
- Memory remains optional and is offered only when actual relevant object records exist. Your scalar Java pattern program has no empty memory section. The previous phase verified shared-list reference arrows and filtering of unused JVM startup arrays.

## Fixed playback and viewport layout

The subsequent layout-only revision passed TypeScript checking and a fresh production build. Execution engines and their limits were unchanged; the backend suite was not rerun for this CSS/layout revision.

- Twenty consecutive mouse clicks advanced the Java example from step 1 to step 21. The playback bar and Next button had **zero horizontal or vertical drift**, despite output, explanation and variable rows changing. Switching between Play and Pause also produced zero bar movement. Previous and first/last controls retain their existing design and 44px button targets.
- Playback stays mounted before execution, while compiling, at both live input reads and after completion. Controls are disabled when there is no replayable visualization, including standalone compiler mode.
- Laptop sizes 1280Ã—720, 1366Ã—768 and 1440Ã—900 were checked with the existing 110% browser zoom (effective CSS viewports approximately 1164Ã—655, 1242Ã—698 and 1309Ã—818). Document height matched viewport height; the editor fills the area between its header and run buttons, and output is about 56% of the two-panel width. Only editor/execution content scrolls.
- 768Ã—1024 tablet and 390Ã—844 phone layouts keep the stacked content in a scrolling upper region. Scrolling from code to variables and clicking Previous/Next did not move the playback bar. The Java example's second inline input at line 13 remained entirely above the controls and accepted 4 with Enter.
- All five 44px playback targets fit at 320Ã—568, including its approximately 291px CSS width at 110% zoom. Short phones use compact header spacing and omit the redundant footer, preserving room for upper content.
- Output keeps every row and whitespace in the scrolling details; it never pushes the controls below the viewport. Optional memory diagrams, errors and input occupy that same bounded area.

Saved evidence in the parent outputs directory: Spandy-Shows-fixed-playback.png and Spandy-Shows-fixed-playback-mobile.png. Earlier phase evidence: Spandy-Shows-input-choice.png, Spandy-Shows-input-terms.png, Spandy-Shows-step-replay.png, Spandy-Shows-variable-changes.png, Spandy-Shows-interactive-mobile.png, Spandy-Shows-invalid-integer.png, Spandy-Shows-mobile-input.png, Spandy-Shows-mobile-input-light.png and Spandy-Shows-restored-visualizer.png.

This is targeted verification, not formal accessibility certification or testing on every physical device/browser.

## Scope and deployment

The preview is private loopback trusted-local execution with SQLite. It runs actual code in supervised processes with bounds; it does not isolate untrusted programs. No public deployment was made.

## Supplied logo and single-choice execution â€” 11 October 2026

- The two supplied PNGs are copied unchanged: the gold symbol appears in the header, favicon and touch icon; the full wordmark is referenced in social metadata. Existing HTML branding and tagline remain accessible.
- The supplied Java menu intentionally repeats inside `doâ€¦while (choice != 0)`. `public/examples/java-utility-once.java` removes that outer menu loop and its now-invalid error-path break, preserving all nine calculation methods and their internal loops. The new **Java utility â€” one choice** example is reachable at `/?example=utility-once&language=java` without replacing existing starter examples or rewriting arbitrary user programs.
- **25 targeted backend checks passed** in 47.46 seconds: all nine single-choice operations and Exit, real Run/Visualize interactive factorial and string reversal, invalid menu input, the original repeating menu, Python/Java/C two-read flows and runtime validation. A worker PID remains unchanged between reads; repeated old input IDs receive 409. The corrected program completes with one menu and one result; the original menu correctly continues in the same process until Exit.
- **23 frontend checks passed**, including Java pasted while Python/C is selected, conservative language detection, comments/literals, source filenames, input, replay, inspector and explanations. TypeScript and the production build passed. Immediate in-flight locks cover Run and input submission. A browser-discovered second click hitting the replacement Stop button is ignored; keyboard repeat on Stop is also suppressed.
- In the real production browser, double-clicking Run and Continue completed factorial for choice 5/value 5 with one menu and one `Factorial of 5 = 120`. Double-clicking Visualize remained active, started paused at step 1, requested integer input at `hasNextInt`, and completed a 46-step trace with the same single result. The gold header image loaded successfully. Java pasted into the Python editor automatically selected Java, retained the source, displayed `UtilityProgram.java`, and printed `Runs once` successfully.
- Evidence: `../Spandy-Shows-one-execution.png`. These are targeted checks for this revision; the earlier complete backend verification is not being claimed as a new full-suite run.

Docker/Compose, PostgreSQL migration and deployment instructions are supplied but remain unverified on this computer. Native visualization has source-line granularity and a 10,000-snapshot cap. C general initialization, allocation/freed lifetime and arbitrary pointer validity remain unknown and labeled. Indirect/custom stdin readers and intentional EOF/failed-read control flow are outside the guarded input interface. Java/C Run code does not inspect memory; use Visualize. See docs/SUPPORT.md for scope and limits.

## Library compatibility revision â€” 11 October 2026

- Final complete backend suite: **99 passed** in 259.06 seconds. Frontend input, inspector, playback, step explanation and Netlify routing checks: **16 passed**. TypeScript checking and the production build passed.
- Python standard imports, builtins, functions/classes, dataclasses, slot storage, generator expressions, yield/from, async/await and normal sys.exit(0) were exercised. Generator/async frames retain identity across suspension and resumption; explanations distinguish yields from completed returns. Missing dependencies produce real ModuleNotFoundError diagnostics.
- Both Run code and Visualize executed Python math, json, collections, dataclasses, decimal, functools, random and statistics; Java util/streams, BigInteger, LocalDate and Runtime queries; C stdio, stdlib, string, ctype, math and malloc/free. Java Box methods/fields declared alongside Main appeared in the recorded user-source trace. C links libm.
- The actual windowless background server accepted live integer input at line 3 for a Python custom function using import math and a generator expression. The immutable prefix was preserved; 153 produced `Number: True 9.0` in a completed 23-step trace. Workers now use normal python.exe streams with CREATE_NO_WINDOW even when the service uses pythonw.exe.
- An initial full test run overlapping the production build had two input failures. Both passed in isolation; the subsequent complete run without that build passed all 99 tests. This does not guarantee timing under arbitrary device load.
- Standard-library implementation lines and native object internals remain outside source playback. External packages/JARs/native libraries are not automatically installed. Multiple source files, GUI integration and full multi-thread/heap inspection are not supplied. Current exact boundaries are in docs/SUPPORT.md.

## Portable Windows edition â€” 11 October 2026

- Includes CPython and backend dependencies, the JDK, GCC/GDB, the built website, source, and windowless Start/Stop launchers. No installer, system PATH change, or startup task is required.
- `tests/verify_portable.py` passed at the original location and again after moving the complete folder. Tests used only Windows System32 on PATH and invalid PYTHONHOME/PYTHONPATH; Python import paths stayed inside the bundle.
- Real Run and Visualize checks passed for Python imports/functions/classes, Java Scanner/custom methods/named entry classes, and C scanf/math. Live input, one-menu factorial output, repeated Start reusing one server, and Stop cancelling a worker waiting for input all passed.
- A GCC specs override corrects its optional manifest filename handling in folders containing spaces. Compiler binaries remain unchanged. The original local server was preserved.
- Testing covered relocation on this computer, not a second physical computer or a clean Windows VM. The unsigned package targets Windows 10/11 Intel/AMD x64 and preserves the existing compiler limits.

## Editor cursor alignment â€” 12 October 2026

- Reproduced the offset by delaying IBM Plex Mono in a fresh browser: after the web font loaded, Monaco retained fallback measurements and the caret was 41.63px behind the rendered end of a long line.
- The editor now requests its font and refreshes Monaco font measurements when it loads or fails. Font listeners and scheduled work are removed when the editor unmounts.
- The same delayed-font browser check now reports 0.63px of fractional rounding. Typing, spaces, backspace, left/right arrows, and edits before/after a semicolon passed with less than 2px of drift. Both themes and a 390px phone viewport passed. TypeScript and the production build passed.
- This is a focused editor correction; compiler behavior and execution were not changed. Evidence: `../Spandy-Shows-cursor-fixed.png`.
