# Claude Code multi-project launcher.
#
# `cw` — pick one or more projects (auto-discovered from $DEVEL_ROOT) and/or
# curated presets from a TUI, then spin each up as its own
# `claude --dangerously-skip-permissions` pane in a single tiled tmux window.
#
# Selection uses fzf --multi when available (Tab to mark several), and falls
# back to a zero-dependency numbered fish menu otherwise.

set -q DEVEL_ROOT; or set -gx DEVEL_ROOT "$HOME/devel"

# --- Curated presets -------------------------------------------------------
# One line per preset: "<name> <dir> <dir> ...". Dirs are relative to
# $DEVEL_ROOT. Edit freely — anything missing on disk is skipped at launch.
function __cw_presets --description 'Emit "name dir1 dir2 ..." lines for cw presets'
    echo "quickfiller quickfiller-strapi-api quickfiller-worker quickfiller-dashboards quickfiller-customer-bot"
    echo "kassellabs kassellabs.io kassel-admin kassel-dashboards"
    echo "autoclipper autoclipper-backend autoclipper-worker autoclipper-dashboard autoclipper-remotion"
end

function __cw_preset_names --description 'List preset names'
    for line in (__cw_presets)
        set -l parts (string split ' ' -- $line)
        echo $parts[1]
    end
end

function __cw_preset_dirs --description 'List a preset\'s project dirs' --argument-names name
    for line in (__cw_presets)
        set -l parts (string split ' ' -- $line)
        if test "$parts[1]" = "$name"
            printf '%s\n' $parts[2..-1]
            return 0
        end
    end
    return 1
end

# --- Fallback picker -------------------------------------------------------
# Numbered multi-select menu. Renders to stderr, prints chosen items (one per
# line) to stdout so it composes inside a command substitution.
function __cw_menu --description 'Numbered multi-select menu; prints chosen items'
    set -l items $argv
    for i in (seq (count $items))
        printf '%2d) %s\n' $i $items[$i] >&2
    end
    read -l -P "cw> pick (space-separated numbers/names, empty to cancel): " reply
    set -l chosen
    for tok in (string split ' ' -- $reply)
        set tok (string trim -- $tok)
        test -z "$tok"; and continue
        if string match -qr '^[0-9]+$' -- $tok
            if test $tok -ge 1; and test $tok -le (count $items)
                set -a chosen $items[$tok]
            else
                echo "cw: index $tok out of range" >&2
            end
        else
            set -l found ""
            # Prefer an exact item match (a real project dir named $tok)...
            for it in $items
                if test "$it" = "$tok"
                    set found $it
                    break
                end
            end
            # ...otherwise fall back to a bare preset label ("[preset] <tok>").
            if test -z "$found"
                for it in $items
                    if test "[preset] $tok" = "$it"
                        set found $it
                        break
                    end
                end
            end
            if test -n "$found"
                set -a chosen $found
            else
                echo "cw: no match for '$tok'" >&2
            end
        end
    end
    test (count $chosen) -gt 0; and printf '%s\n' $chosen
end

function __cw_attach --description 'Attach or switch to a tmux session' --argument-names session
    if set -q TMUX
        tmux switch-client -t "$session"
    else
        tmux attach-session -t "$session"
    end
end

# --- Main command ----------------------------------------------------------
function cw --description 'Pick projects/presets and launch claude in a tiled tmux window'
    if not type -q tmux
        echo "cw: tmux is not installed" >&2
        return 1
    end
    if not type -q claude
        echo "cw: claude CLI not found on PATH" >&2
        return 1
    end
    if not test -d "$DEVEL_ROOT"
        echo "cw: $DEVEL_ROOT does not exist" >&2
        return 1
    end

    # Build the picker list: presets first, then every project dir.
    set -l items
    for name in (__cw_preset_names)
        set -a items "[preset] $name"
    end
    for d in (ls -1 "$DEVEL_ROOT")
        test -d "$DEVEL_ROOT/$d"; and set -a items "$d"
    end

    # Select.
    set -l picks
    if type -q fzf
        set picks (printf '%s\n' $items | fzf --multi --height=60% --reverse \
            --prompt="cw> " --header="Tab to mark multiple, Enter to launch")
    else
        set picks (__cw_menu $items)
    end

    if test (count $picks) -eq 0
        echo "cw: nothing selected" >&2
        return 1
    end

    # Resolve picks -> project dirs (expand presets), tracking chosen presets.
    set -l projects
    set -l chosen_presets
    for pick in $picks
        test -z "$pick"; and continue
        if string match -qr '^\[preset\] ' -- $pick
            set -l pname (string replace '[preset] ' '' -- $pick)
            set -a chosen_presets $pname
            for pd in (__cw_preset_dirs $pname)
                set -a projects $pd
            end
        else
            set -a projects $pick
        end
    end

    # Dedupe (preserve order) and drop anything not on disk.
    set -l resolved
    for p in $projects
        test -z "$p"; and continue
        if not test -d "$DEVEL_ROOT/$p"
            echo "cw: skipping '$p' (no such dir in $DEVEL_ROOT)" >&2
            continue
        end
        contains -- $p $resolved; or set -a resolved $p
    end

    if test (count $resolved) -eq 0
        echo "cw: no valid projects to open" >&2
        return 1
    end

    # Session name: a single lone preset pick gets its own name; else "cw".
    set -l session cw
    if test (count $picks) -eq 1; and test (count $chosen_presets) -eq 1
        set session $chosen_presets[1]
    end

    # Never clobber a live session — attach to it instead of recreating.
    if tmux has-session -t "$session" 2>/dev/null
        echo "cw: session '$session' already exists — attaching to it" >&2
        __cw_attach $session
        return
    end

    set -l claude_cmd 'claude --dangerously-skip-permissions'

    # First project seeds the window; the rest split off and re-tile.
    tmux new-session -d -s "$session" -n claude -c "$DEVEL_ROOT/$resolved[1]"
    tmux send-keys -t "$session" "$claude_cmd" C-m

    for p in $resolved[2..-1]
        if not tmux split-window -t "$session" -c "$DEVEL_ROOT/$p" 2>/dev/null
            echo "cw: no room for more panes — '$p' onward were skipped (window too small)" >&2
            break
        end
        tmux select-layout -t "$session" tiled >/dev/null
        tmux send-keys -t "$session" "$claude_cmd" C-m
    end

    tmux select-layout -t "$session" tiled >/dev/null
    tmux select-pane -t "$session:claude.{top-left}" 2>/dev/null

    __cw_attach $session
end
