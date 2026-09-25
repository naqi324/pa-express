# Prior Auth Express

Prior authorization app. Vite + plain TypeScript, pnpm, Oxlint.

## Commands

- `pnpm check` — lint and typecheck. Run before every commit.
- `pnpm build` — typecheck, then production build.

## Rules

- Use pnpm. Do not add npm or yarn lockfiles.
- Keep source in `src/`.
- Oxlint runs the vendored anti-slop rules in `tools/oxlint/anti-slop/`. Fix findings in the code. Do not suppress rules or lower their severity.
- To update anti-slop, use the `install-anti-slop` update procedure. Keep the provenance in `tools/oxlint/anti-slop/UPSTREAM.md`.
- Never commit real patient data (PHI). Use synthetic data for fixtures and demos.
