# `cheats` — a printed cheatsheet of the custom commands defined by this
# dotfiles repo plus the machine-local env.local.fish layer.

function cheats --description 'Show custom shell commands from this dotfiles setup'
    set -l B (set_color --bold)
    set -l H (set_color cyan)
    set -l C (set_color green)
    set -l D (set_color brblack)
    set -l N (set_color normal)

    # Print one cheatsheet row with color *outside* the padding so widths line up.
    function __cheats_row
        set -l cmd $argv[1]
        set -l desc $argv[2]
        set -l C (set_color green)
        set -l N (set_color normal)
        printf "    %s%s%s  %s\n" $C (string pad --right --width 24 -- $cmd) $N $desc
    end

    echo ""
    echo $B"  Custom shell cheatsheet"$N
    echo $D"  Source: ~/devel/dotfiles/fish/conf.d/  +  ~/.config/fish/conf.d/env.local.fish"$N
    echo ""

    echo $H"  Project navigation"$N$D" — projects.fish"$N
    __cheats_row "p [name]"      "cd into \$DEVEL_ROOT/<project> (fzf if ambiguous, tab-completes)"
    __cheats_row "dev [project]" "run ./dev.sh in cwd, or in a resolved project"
    __cheats_row "cdr"           "cd to the git repo root"
    __cheats_row "cw [name]"     "pick projects/presets → tiled tmux of claude (name = separate session)"
    __cheats_row "cw ls"         "list tmux sessions"
    __cheats_row "cw attach [s]" "attach to an existing tmux session (picker when no name)"
    echo ""

    echo $H"  Filesystem & misc"$N$D" — utils.fish"$N
    __cheats_row "ll"            "ls -lah"
    __cheats_row "mkcd <dir>"    "mkdir -p && cd"
    __cheats_row "copy"          "system clipboard (pbcopy / xclip / wl-copy)"
    __cheats_row "dotenv [file]" "export vars from a .env file (handles quotes, comments, export)"
    __cheats_row "dytv <url>"    "yt-dlp, remuxed to mp4"
    __cheats_row "randstr [N=32]" "random alphanumeric string of length N"
    echo ""

    echo $H"  Git"$N$D" — git.fish"$N
    __cheats_row "g"             "git"
    __cheats_row "gs"            "git status -sb"
    __cheats_row "gd / gds"      "git diff  /  git diff --staged"
    __cheats_row "gco / gcb"     "git checkout  /  git checkout -b"
    __cheats_row "gco-"          "git checkout - (previous branch)"
    __cheats_row "gb"            "git branch"
    __cheats_row "gp / gpu"      "git pull  /  git push"
    __cheats_row "gl / glg"      "log --oneline -20  /  log --graph --all -30"
    __cheats_row "gaa"           "git add -A"
    __cheats_row "gcm <msg>"     "git commit -m"
    __cheats_row "gca"           "git commit --amend --no-edit"
    __cheats_row "gst / gstp"    "git stash  /  git stash pop"
    __cheats_row "gwip"          "add -A && commit -m wip --no-verify"
    echo ""

    echo $H"  PostgreSQL"$N$D" — pg.fish (interactive only, if *-17 installed)"$N
    __cheats_row "psql"          "→ psql-17"
    __cheats_row "createdb"      "→ createdb-17"
    __cheats_row "createuser"    "→ createuser-17"
    echo ""

    echo $H"  Node / nvm"$N$D" — nvm-lazy.fish"$N
    __cheats_row "node, npm"     "default nvm version on PATH, nvm.sh NOT sourced at startup"
    __cheats_row "nvm ..."       "OMF wrapper still works on demand"
    echo ""

    echo $H"  Machine-local"$N$D" — env.local.fish (not in dotfiles)"$N
    __cheats_row "ri / ris / rw" "SWIC: render-intro / -screenshot / worker"
    __cheats_row "ops"           "open + copy SWIC screenshot to clipboard"
    __cheats_row "utl"           "upload-to-linode"
    __cheats_row "ssa"           "swap-swic-audio"
    __cheats_row "resolve"       "DaVinci Resolve helper"
    __cheats_row "encode-to-resolve" "ffmpeg → Resolve mounts"
    __cheats_row "cursor"        "Cursor IDE AppImage"
    __cheats_row "sshkl / sshkassel" "Kassel Labs SSH"
    echo ""

    echo $H"  Quickfiller"$N$D" — processing-methods.fish (pre-existing)"$N
    __cheats_row "qf-dev [sub]"  "tmux dev env: start|stop|attach|status|api|frontend|worker"
    __cheats_row "pm-parse"      "run a processing-methods parser"
    __cheats_row "pm-test"       "run parser snapshots"
    __cheats_row "pm-test-update" "update parser snapshots"
    __cheats_row "pm-parsers [t]" "list parsers (payrolls | time-cards)"
    echo ""

    echo $D"  Tip: cheats | less -R    if it scrolls off."$N
    echo ""

    functions -e __cheats_row
end
