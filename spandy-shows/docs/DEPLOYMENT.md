# Spandy Shows deployment

The delivered site works privately on the local machine. **No public deployment has been performed.** The build host has no working Docker/WSL access, cloud worker infrastructure or PostgreSQL service, so container isolation, Linux sanitizers and hosted persistence remain unverified.

## Frontend

`pnpm run build` produces static `dist/` assets. These can be served by FastAPI (the local default) or deployed to private static hosting, including Sites. Native compilers/debuggers cannot run inside static hosting or Cloudflare Workers. A hosted frontend requires a separately provisioned execution API and a same-origin reverse proxy for `/api`. Do not publish a disconnected frontend as a completed execution product.

## API and persistence

Run a single API instance until the queue/rate limit/job state is moved to a shared broker. Configure PostgreSQL through `DATABASE_URL`, run `migrations/001_programs.sql`, configure exact `SPANDY_ORIGINS` and `SPANDY_HOSTS`, serve HTTPS and restrict private access. Source links are readable by holders of their token; use authentication/authorization for sensitive or classroom-owned content. Back up the database and enforce 30-day retention with a scheduled cleanup in production. Supply secrets through environment injection, never to execution jobs.

## Worker boundary before public access

The development Docker configuration is not a complete security boundary. C adds SYS_PTRACE to inspect child processes. The development API's Docker socket access is a substantial orchestration privilege. Keep it local/private.

For public service, put orchestration in a separate narrowly authenticated broker on dedicated worker hosts. Run each job in a hardened gVisor or microVM boundary with a fresh filesystem and unprivileged identity; disable egress; expose no socket, API secret, database credential or host mount to job code. Compilation must use the same boundary. Verify seccomp/ptrace compatibility with real JDI/GDB and test host-file denial, no network, CPU/memory/pid/disk limits, whole-process-tree cancellation and cleanup under adversarial programs. Use bounded durable queues, global quotas, authenticated cancellation and trace validation. Monitor jobs without logging private source by default.

Only after those checks pass should native execution be exposed to others. Preserve owner/private access unless public publication is explicitly authorized. Do not select trusted-local mode for hosted execution.
