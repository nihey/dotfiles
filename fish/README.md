# fish config

Modular fish config. Each file in `conf.d/` is auto-loaded by fish on shell
startup — there is no central `config.fish` here. The real machine's
`~/.config/fish/config.fish` is kept minimal (only heavy third-party inits
like conda / gcloud) and lives outside this repo.

## Layout

- `conf.d/00-greeting.fish` — empty greeting.
- `conf.d/utils.fish` — `ll`, `copy`, `mkcd`, `dytv`, `randstr`, `dotenv`.
- `conf.d/git.fish` — common git aliases (`gs`, `gd`, `gco`, `gca`, `gl`, ...).
- `conf.d/projects.fish` — `p <name>` jumps to `$DEVEL_ROOT/<project>` (fzf
  fallback when ambiguous), `dev [project]` runs `./dev.sh`, `cdr` cd's to
  the git repo root.
- `conf.d/nvm-lazy.fish` — adds the nvm "default" node to `PATH` without
  sourcing `nvm.sh` on startup. The OMF `nvm` function still works on demand.
- `conf.d/cheats.fish` — `cheats` prints a colored cheatsheet of every
  command defined here plus the machine-local layer.
- `conf.d/pg.fish` — interactive-only `psql` / `createdb` / `createuser`
  shadows pointing at the `-17` binaries when present.
- `conf.d/anaconda.fish` — adds `~/anaconda3/bin` to `PATH` if it exists.

## Install

Run the installer from the repo root:

```sh
./install.sh
```

It symlinks each module into `~/.config/fish/conf.d/`. Safe to re-run:
`env.local.fish` is never touched, and existing regular files are skipped
(only symlinks are replaced). Or do it manually:

```fish
for f in ~/devel/dotfiles/fish/conf.d/*.fish
    ln -sfv $f ~/.config/fish/conf.d/(basename $f)
end
```

## Secrets / machine-local

Anything secret or machine-specific (API keys, local paths, work-only aliases)
lives in `~/.config/fish/conf.d/env.local.fish` on each machine and is **not**
tracked here. Fish auto-loads it the same way.
