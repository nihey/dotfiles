# CLAUDE.md — dotfiles

Personal dotfiles: a modular fish config (`fish/conf.d/*.fish`, each auto-loaded
on shell startup), plus `install.sh` (symlinks the fish modules into
`~/.config/fish/conf.d/` and `bin/` into `~/.local/bin/`) and `setup.sh`
(server provisioning). See `fish/README.md` for the fish layout and install
steps.

Named Bitwarden CLI wrappers (`bw-nihey`, `bw-kassellabs`, `bw-quickfiller`)
are installed by `install.sh`, which prompts for each server URL and writes
it only under `~/.config/bw-<profile>/`. `bw-nihey` is the default `bw`
profile. Never put those URLs in a tracked file.

Git cleanup commands (`gprune`, `gonly-main`) live in `fish/conf.d/git.fish` and
call `bin/git-local-cleanup`. `gprune` only deletes worktrees/branches whose
tip is an ancestor of `origin/main` (or `origin/master`). `gonly-main` is the
nuclear option: it stashes unique uncommitted work, backs unique commits up
under `refs/backup/local-reset/`, then leaves only the base branch. Never
force-push; never delete remote branches.

## Security — never commit secrets (audit every commit)

These dotfiles are pushed to GitHub. Sensitive information must **never** enter
the repository — not in a commit, not in history.

**Before every commit, audit the staged diff and refuse to commit if anything
sensitive is present.** Run `git diff --staged` and scan for:

- API keys, tokens, access/refresh tokens, personal access tokens
- Passwords, connection strings with credentials, session cookies
- Private keys and key material (`*.pem`, `*.key`, `id_rsa`/SSH keys, GPG keys)
- `.env` / `.env.*` files or any inlined environment secrets
- Internal hostnames, IPs, or work-only identifiers that should not be public

If a change needs a secret or machine-specific value, it does **not** belong in
a tracked file. Put it in `~/.config/fish/conf.d/env.local.fish` — the
machine-local layer, untracked (see `fish/README.md` § Secrets/machine-local) —
reference it through an environment variable, or use a placeholder. Never
hardcode the real value.

When in doubt, do not commit — flag it and ask.

## Commits

- Follow Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `chore:`, …).
- Never add AI attribution or `Co-Authored-By` trailers.
