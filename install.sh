#!/usr/bin/env bash
# Symlink the fish modules into ~/.config/fish/conf.d/.
#
# Safe to re-run. Never touches env.local.fish (the untracked machine-local
# layer holding secrets/env vars) and never overwrites a regular file — only
# symlinks are replaced.
set -euo pipefail

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FISH_CONF_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/fish/conf.d"

mkdir -p "$FISH_CONF_DIR"

for src in "$DOTFILES_DIR"/fish/conf.d/*.fish; do
    name="$(basename "$src")"
    dest="$FISH_CONF_DIR/$name"

    if [ "$name" = "env.local.fish" ]; then
        continue
    fi

    if [ -e "$dest" ] && [ ! -L "$dest" ]; then
        echo "skip: $dest exists and is not a symlink — leaving it alone"
        continue
    fi

    ln -sfv "$src" "$dest"
done
