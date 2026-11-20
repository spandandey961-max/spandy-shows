# Spandy Shows implementation plan

See your code, step by step.

## Environment and architecture

The starting workspace is empty. Windows has Node 24.19.0 and bundled CPython 3.12.14. Its old MinGW binaries fail with a Windows DLL relocation error. No Java or Docker command is installed; WSL access is unavailable. Use project-local dependencies and portable toolchains for verification if downloads succeed. Do not alter system PATH or install system services.

React 19.3, TypeScript, Vite, and Monaco form the browser workspace. FastAPI owns validation, bounded asynchronous jobs, persistence, cancellation, and schema verification. Separate processes perform real CPython/sys.settrace, JVM/JDI, and GCC/GDB-MI tracing. The frontend renders one immutable recorded snapshot, never re-executing when stepping backward. PostgreSQL is the Compose persistence service; SQLite is an explicitly documented local fallback. A bounded in-process scheduler avoids needing Redis for this small single-instance version. Production scaling requires an external queue.

Native trusted-local execution is available only through explicit opt-in on loopback. Default execution uses per-job containers with network disabled, resource limits, unprivileged identities, and ephemeral workspaces. Containers are a development isolation layer, not a sufficient public security boundary. Public deployment requires an independently verified gVisor/microVM boundary. Sites hosting can serve the frontend but cannot execute the native workers; do not deploy a disconnected frontend as a completed product.

## Ordered work

1. Inspect workspace, engines, upstream functionality, and registry versions; record scope and shared schema.
2. Build Python serialization and tracer; hand-check states and run adapter tests.
3. Connect FastAPI and React for complete Python execution and replay; build the responsive accessible workspace.
4. Add Java compilation/JDI with stable identities and compiler diagnostics; run real engine tests.
5. Add C compilation/GDB-MI with bounded symbol inspection; run real engine tests.
6. Complete container limits, cancellation, rate limits, validated results, API persistence and shares.
7. Verify language examples, errors, stale traces, keyboard interaction, responsive layouts, and limits.
8. Package source, locked dependencies, Docker Compose, migrations, setup scripts, architecture and deployment documentation. Report unavailable infrastructure precisely.

## Experience

A compact editorial application shell, warm paper surfaces, ink code panel, burnt-orange action accent, blue reference arrows and fine grid diagram canvas. No marketing page. Useful initial example. Memory frames at left and stable object cards at right; explicit before-line convention; event-derived explanation; separate synchronized output; bottom playback bar. Small screens switch between code and memory panels. Brand, page title, metadata, help and documentation use Spandy Shows consistently.
