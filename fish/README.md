# fish config

Modular fish config. Each file in `conf.d/` is auto-loaded by fish on shell
startup — there is no central `config.fish` here. The real machine's
`~/.config/fish/config.fish` is kept minimal (only heavy third-party inits
like conda / gcloud) and lives outside this repo.

## Layout

- `conf.d/00-greeting.fish` — empty greeting.
- `conf.d/utils.fish` — `ll`, `copy`, `mkcd`, `dytv`, `randstr`, `dotenv`.
- `conf.d/git.fish` — common git aliases (`gs`, `gd`, `gco`, `gca`, `gl`, ...),
  plus `gprune` (delete already-merged local worktrees/branches and return to
  main/master) and `gonly-main` (stash unique WIP, delete every other local
  branch and worktree, leave only main/master). Both wrap
  `bin/git-local-cleanup`. `gonly-main` asks you to type `only-main` unless
  you pass `--yes`; unique commits are saved under
  `refs/backup/local-reset/<timestamp>/` before the branch is deleted.
- `conf.d/projects.fish` — `p <name>` jumps to `$DEVEL_ROOT/<project>` (fzf
  fallback when ambiguous), `dev [project]` runs `./dev.sh`, `cdr` cd's to
  the git repo root.
- `conf.d/proxy.fish` — `pchrome <ssh-host>` opens an SSH SOCKS tunnel and
  launches a separate Chrome profile that browses through it (remote DNS, so
  sites see the remote IP). Tunnel is torn down when Chrome exits; `--fresh`
  uses a throwaway profile, `--port N` forces the local port.
- `conf.d/nvm-lazy.fish` — adds the nvm "default" node to `PATH` without
  sourcing `nvm.sh` on startup. The OMF `nvm` function still works on demand.
- `conf.d/cheats.fish` — `cheats` prints a colored cheatsheet of every
  command defined here plus the machine-local layer.
- `conf.d/pg.fish` — interactive-only `psql` / `createdb` / `createuser`
  shadows pointing at the `-17` binaries when present.
- `conf.d/anaconda.fish` — adds `~/anaconda3/bin` to `PATH` if it exists.
- `../bin/extract-frames` — portable `ffmpeg` wrapper that extracts one PNG
  frame per requested timestamp.
- `../bin/video-resolutions` — portable `ffprobe` wrapper that lists video
  dimensions and optionally sorts by resolution.

## Extract video frames

`extract-frames` accepts a video followed by one or more timestamps. Without
an output option it writes lossless PNG files into the current directory:

```sh
extract-frames video.mp4 00:01 00:05.500 01:20
```

Use `-o` or `--output` to select a directory. Missing directories are created:

```sh
extract-frames video.mp4 10 25.5 --output ./selected-frames
```

Output names include the video stem, timestamp position, and timestamp, such
as `video-frame-001-00-01.png`. The command requires `python3` and `ffmpeg` on
`PATH`.

## List video resolutions

`video-resolutions` recursively lists supported videos and the dimensions of
their first video stream. The directory defaults to the current directory:

```sh
video-resolutions
video-resolutions ~/Videos
```

Use `--no-recursive` to inspect only the selected directory:

```sh
video-resolutions ~/Videos --no-recursive
```

Results are ordered alphabetically by default. To sort by resolution instead,
use `--sort-resolution`; resolution sorting uses total pixel area and lists the
largest videos first by default. Add `--ascending` for smallest-first order:

```sh
video-resolutions ~/Videos --sort-resolution
video-resolutions ~/Videos --sort-resolution --ascending
```

Supported extensions are matched case-insensitively: `.3gp`, `.avi`, `.flv`,
`.m2ts`, `.m4v`, `.mkv`, `.mov`, `.mp4`, `.mpeg`, `.mpg`, `.mts`, `.ts`,
`.webm`, and `.wmv`. Unprobeable files produce warnings while valid results
remain in the output, but any warning makes the command exit nonzero. The
command requires `python3` and `ffprobe` on `PATH`.

## Install

Run the installer from the repo root:

```sh
./install.sh
```

It symlinks each module into `~/.config/fish/conf.d/` and each `bin/`
executable into `~/.local/bin/`. Safe to re-run: `env.local.fish` is never
touched, and existing regular files are skipped (only symlinks are replaced).
Or do it manually:

```fish
for f in ~/devel/dotfiles/fish/conf.d/*.fish
    ln -sfv $f ~/.config/fish/conf.d/(basename $f)
end
```

## Secrets / machine-local

Anything secret or machine-specific (API keys, local paths, work-only aliases)
lives in `~/.config/fish/conf.d/env.local.fish` on each machine and is **not**
tracked here. Fish auto-loads it the same way.
