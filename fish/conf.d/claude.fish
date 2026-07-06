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

# --- Interactive checkbox picker -------------------------------------------
# A zero-dependency multi-select TUI: move with up/down or j/k, toggle the
# highlighted row with space, `a` toggles all, enter launches, q cancels.
# Renders to stderr (with a scrolling viewport + alt screen), prints the
# chosen items to stdout so it composes inside a command substitution.
function __cw_pick --description 'Interactive checkbox multi-select; prints chosen items'
    set -l items $argv
    set -l n (count $items)
    test $n -eq 0; and return 1

    # Parallel 0/1 selection array (built with -a so indexing stays in range).
    set -l sel
    for i in (seq $n)
        set -a sel 0
    end
    set -l cursor 1
    set -l top 1

    # Viewport height: terminal rows minus title/help/footer chrome.
    set -l rows $LINES
    test -z "$rows"; and set rows (tput lines 2>/dev/null)
    test -z "$rows"; and set rows 40
    set -l view (math "$rows - 4")
    test $view -lt 1; and set view 1
    test $view -gt $n; and set view $n

    # Put the terminal in raw, no-echo mode so we read single keypresses
    # ourselves. fish's `read` would otherwise run its full line editor
    # (prompt, highlighting, arrow keys as edit commands). Restored below.
    set -l stty_saved (stty -g 2>/dev/null)
    stty -icanon -echo -isig min 1 time 0 2>/dev/null

    printf '\e[?1049h\e[2J\e[H\e[?25l' >&2   # alt screen, clear, hide cursor
    set -l cancelled 0

    while true
        # Keep the cursor inside the visible window.
        if test $cursor -lt $top
            set top $cursor
        else if test $cursor -gt (math "$top + $view - 1")
            set top (math "$cursor - $view + 1")
        end

        set -l selcount 0
        for i in (seq $n)
            test "$sel[$i]" = 1; and set selcount (math "$selcount + 1")
        end

        set -l last (math "$top + $view - 1")
        test $last -gt $n; and set last $n

        printf '\e[H' >&2
        printf '\e[1m  cw — select projects\e[0m  \e[2m(%d selected)\e[0m\e[K\n' $selcount >&2
        printf '  \e[2mup/dn or j/k move · space toggle · a all · enter launch · q cancel\e[0m\e[K\n' >&2
        for i in (seq $top $last)
            set -l box '[ ]'
            test "$sel[$i]" = 1; and set box '[x]'
            if test $i -eq $cursor
                printf '\e[7m> %s %s\e[0m\e[K\n' $box $items[$i] >&2
            else
                printf '  %s %s\e[K\n' $box $items[$i] >&2
            end
        end
        if test $n -gt $view
            printf '  \e[2m[%d-%d/%d]\e[0m\e[K\n' $top $last $n >&2
        else
            printf '\e[K\n' >&2
        end
        printf '\e[0J' >&2

        # Read one raw byte and switch on its decimal code. `od` appends a
        # trailing blank line, so take the first element.
        set -l code (dd bs=1 count=1 2>/dev/null | od -An -tu1 | string trim)
        set code $code[1]
        test -z "$code"; and break   # EOF -> confirm

        switch $code
            case 32   # space -> toggle current row
                if test "$sel[$cursor]" = 1
                    set sel[$cursor] 0
                else
                    set sel[$cursor] 1
                end
            case 106   # j -> down
                set cursor (math "$cursor + 1"); test $cursor -gt $n; and set cursor 1
            case 107   # k -> up
                set cursor (math "$cursor - 1"); test $cursor -lt 1; and set cursor $n
            case 97   # a -> toggle all
                set -l allsel 1
                for i in (seq $n)
                    test "$sel[$i]" = 1; or set allsel 0
                end
                for i in (seq $n)
                    if test $allsel -eq 1
                        set sel[$i] 0
                    else
                        set sel[$i] 1
                    end
                end
            case 113 81   # q / Q -> cancel
                set cancelled 1
                break
            case 3   # Ctrl-C -> cancel
                set cancelled 1
                break
            case 10 13   # Enter -> launch
                break
            case 27   # ESC -> possibly an arrow key: consume '[' then A/B
                set -l b1 (dd bs=1 count=1 2>/dev/null | od -An -tu1 | string trim)
                if test "$b1[1]" = 91
                    set -l b2 (dd bs=1 count=1 2>/dev/null | od -An -tu1 | string trim)
                    switch "$b2[1]"
                        case 65   # up
                            set cursor (math "$cursor - 1"); test $cursor -lt 1; and set cursor $n
                        case 66   # down
                            set cursor (math "$cursor + 1"); test $cursor -gt $n; and set cursor 1
                    end
                end
        end
    end

    printf '\e[?25h\e[?1049l' >&2   # show cursor, leave alt screen
    test -n "$stty_saved"; and stty $stty_saved 2>/dev/null

    test $cancelled -eq 1; and return 130

    for i in (seq $n)
        test "$sel[$i]" = 1; and echo $items[$i]
    end
    return 0
end

function __cw_attach --description 'Attach or switch to a tmux session' --argument-names session
    if set -q TMUX
        tmux switch-client -t "$session"
    else
        tmux attach-session -t "$session"
    end
end

# --- Main command ----------------------------------------------------------
# Usage:
#   cw                launch picker; session is "cw" (or the lone preset's name)
#   cw <name>         same, but as a separate session called <name>
#   cw ls             list tmux sessions
#   cw attach [name]  attach to an existing session (picker when no name)
function cw --description 'Pick projects/presets and launch claude in a tiled tmux window'
    if not type -q tmux
        echo "cw: tmux is not installed" >&2
        return 1
    end

    set -l session_arg ""
    switch "$argv[1]"
        case ls list
            tmux list-sessions 2>/dev/null
            or echo "cw: no tmux sessions running" >&2
            return
        case attach a
            set -l sessions (tmux list-sessions -F '#{session_name}' 2>/dev/null)
            if test (count $sessions) -eq 0
                echo "cw: no tmux sessions to attach to" >&2
                return 1
            end
            set -l target "$argv[2]"
            if test -z "$target"
                if test (count $sessions) -eq 1
                    set target $sessions[1]
                else if type -q fzf
                    set target (printf '%s\n' $sessions | fzf --height=40% --reverse \
                        --prompt="cw attach> " --header="Enter to attach")
                else
                    set -l picked (__cw_menu $sessions)
                    test (count $picked) -gt 0; and set target $picked[1]
                end
            end
            if test -z "$target"
                echo "cw: nothing selected" >&2
                return 1
            end
            if not tmux has-session -t "$target" 2>/dev/null
                echo "cw: no session named '$target'" >&2
                return 1
            end
            __cw_attach $target
            return
        case '*'
            set session_arg "$argv[1]"
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

    # Select. Prefer fzf; else an interactive checkbox picker on a real
    # terminal; else a plain numbered menu (non-interactive / piped stdin).
    set -l picks
    if type -q fzf
        set picks (printf '%s\n' $items | fzf --multi --height=60% --reverse \
            --bind space:toggle --marker='x ' \
            --prompt="cw> " --header="space/tab: toggle · enter: launch")
    else if isatty stdin
        set picks (__cw_pick $items)
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

    # Session name: explicit arg wins; else a single lone preset pick gets
    # its own name; else "cw".
    set -l session cw
    if test -n "$session_arg"
        set session $session_arg
    else if test (count $picks) -eq 1; and test (count $chosen_presets) -eq 1
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
