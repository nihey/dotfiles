# CLAUDE.md — dotfiles

Personal dotfiles: a modular fish config (`fish/conf.d/*.fish`, each auto-loaded
on shell startup), plus `.gitconfig`, `.vimrc`, and `setup.sh`. See
`fish/README.md` for the fish layout and install steps.

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
