# Spandy Shows on Netlify

Netlify hosts the built website. A separately hosted, isolated execution backend runs the existing Python, Java and C engines, live input sessions and step recording. This repository's FastAPI/process workers are not Netlify Functions. No Netlify site or public backend has been provisioned yet.

## Deployment configuration

Import the `spandy-shows` source directory as the repository root, or set that directory as the base directory if the repository includes the parent output folder. Netlify reads `netlify.toml`: Node 24, pnpm 11.25.0, build command `pnpm run build:netlify`, publish directory `dist`.

Set `SPANDY_API_ORIGIN` in Netlify's build environment to the actual HTTPS backend origin, for example `https://execution.your-domain.com`. This is a public routing address, not a credential. Do not include `/api`, passwords, tokens or trailing query parameters. The build fails if this is missing or points to localhost, preventing accidental deployment of a compiler with no backend configured.

The build generates `public/_redirects`, copied into `dist` by Vite. `/api/*` proxies to that backend's `/api/:splat`; the SPA fallback comes last. Job submission, polling, trace retrieval, input response and cancellation keep their existing relative paths. Each HTTP operation remains short while compilation, recording and input waits continue in the backend process.

## Backend configuration

Provision and verify the execution infrastructure described in [DEPLOYMENT.md](DEPLOYMENT.md) before public access. Do not expose the local trusted execution mode or the development Docker socket configuration. Preserve a job on the same backend instance until the queue and state are migrated to shared infrastructure; default round-robin multi-instance hosting will lose active sessions.

Configure backend `SPANDY_ORIGINS` to the exact Netlify production origin and any explicitly approved deploy-preview origins. Configure `SPANDY_HOSTS` to the backend hostname. Keep HTTPS enabled and configure PostgreSQL for share persistence. Origins are currently exact strings, so a wildcard deploy-preview domain will not enable previews; add a specific origin or keep preview execution disabled. The site address is required to finish this configuration after site creation.

## Verification before release

Check `/api/health` from the Netlify site and verify all three runtime availability flags. Then test both Run code and Visualize, each language's sequential input, invalid input, the full C pattern, playback without automatic cursor movement, cancellation and share retrieval after a server restart. Confirm backend isolation and per-client limits before allowing public submissions. The existing proxy uses asynchronous jobs, avoiding a long HTTP request for an entire execution.

Netlify documentation: [Create deploys](https://docs.netlify.com/deploy/create-deploys/), [Rewrites and proxies](https://docs.netlify.com/manage/routing/redirects/rewrites-proxies/), [Functions overview](https://docs.netlify.com/build/functions/overview/).
