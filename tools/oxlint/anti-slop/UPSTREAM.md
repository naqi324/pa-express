# Anti-slop source record

Installed on 2026-09-25 from the local `install-anti-slop` skill's
`assets/anti-slop` bundle.

- Source repository: [dmmulroy/anti-slop](https://github.com/dmmulroy/anti-slop),
  skill path `skills/install-anti-slop/SKILL.md`, per the local skills lock.
- Skill folder Git tree hash: `89044d21c75a367eac1ddbaf208e650b1a7d5820`.
  This matches the lock's `skillFolderHash`.
- Bundle Git tree hash (`assets/anti-slop`):
  `a7831feb0c097943ac813ddcb1367e26eef52da5`. The copied files had this same
  tree hash before this record was added.
- Source commit: unknown. The installed skill has no Git metadata. Do not treat
  the upstream HEAD or the Oxlint package version as the identity of these rules.

The initial installation commit is the pristine base for later updates.

## Installation

- Installed path: `tools/oxlint/anti-slop/`.
- Enabled entry point: `index.ts`, with all generic rules at `"error"`, plus
  native `oxc/no-accumulating-spread`.
- Not enabled: `effect/index.ts`. This project has no direct Effect dependency.
- `oxlint` and `@oxlint/plugins` are pinned together at 1.85.0.
- The plugin directory and local agent tooling directories are excluded from lint.

Intentional deviations: none. This file is the only addition to the bundle.

Keep `vendor/eslint-stylistic/LICENSE` and its `UPSTREAM.md`. They hold that
component's license, source revision, and adaptation notes.
