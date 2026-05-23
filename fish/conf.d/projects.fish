# Project navigation and dev launchers.
# Assumes projects live under $DEVEL_ROOT (defaults to ~/devel).

set -q DEVEL_ROOT; or set -gx DEVEL_ROOT "$HOME/devel"

function p --description 'cd into a project under $DEVEL_ROOT (fzf if ambiguous)'
    if not test -d "$DEVEL_ROOT"
        echo "p: $DEVEL_ROOT does not exist" >&2
        return 1
    end

    set -l query
    if test (count $argv) -gt 0
        set query $argv[1]
    end

    # No arg: full fzf picker
    if test -z "$query"
        if not type -q fzf
            echo "p: install fzf or pass a project name" >&2
            return 1
        end
        set -l pick (ls -1 "$DEVEL_ROOT" | fzf --height=40% --reverse --prompt="project> ")
        test -n "$pick"; and cd "$DEVEL_ROOT/$pick"
        return
    end

    # Exact match wins
    if test -d "$DEVEL_ROOT/$query"
        cd "$DEVEL_ROOT/$query"
        return
    end

    # Single substring match: jump directly
    set -l matches (ls -1 "$DEVEL_ROOT" | string match -i -r ".*$query.*")
    set -l n (count $matches)
    if test $n -eq 1
        cd "$DEVEL_ROOT/$matches[1]"
        return
    else if test $n -eq 0
        echo "p: no project matching '$query' in $DEVEL_ROOT" >&2
        return 1
    end

    # Multiple matches: fzf-filter on them
    if not type -q fzf
        echo "p: multiple matches for '$query', install fzf or refine:" >&2
        printf '  %s\n' $matches >&2
        return 1
    end
    set -l pick (printf '%s\n' $matches | fzf --height=40% --reverse --query="$query" --prompt="project> ")
    test -n "$pick"; and cd "$DEVEL_ROOT/$pick"
end

complete -c p -x -a "(ls -1 $DEVEL_ROOT 2>/dev/null)"

function cdr --description 'cd to the git repo root'
    set -l root (git rev-parse --show-toplevel 2>/dev/null)
    if test -z "$root"
        echo "cdr: not inside a git repo" >&2
        return 1
    end
    cd "$root"
end

function dev --description 'Run ./dev.sh in cwd or in a project'
    set -l target
    if test (count $argv) -eq 0
        set target (pwd)
    else
        # Resolve via p's lookup logic
        if test -d "$DEVEL_ROOT/$argv[1]"
            set target "$DEVEL_ROOT/$argv[1]"
        else
            set -l matches (ls -1 "$DEVEL_ROOT" | string match -i -r ".*$argv[1].*")
            if test (count $matches) -eq 1
                set target "$DEVEL_ROOT/$matches[1]"
            else
                echo "dev: cannot resolve project '$argv[1]'" >&2
                return 1
            end
        end
    end

    if not test -x "$target/dev.sh"
        if test -f "$target/dev.sh"
            echo "dev: $target/dev.sh is not executable" >&2
        else
            echo "dev: $target/dev.sh not found" >&2
        end
        return 1
    end

    pushd "$target" >/dev/null
    ./dev.sh
    popd >/dev/null
end

complete -c dev -x -a "(ls -1 $DEVEL_ROOT 2>/dev/null)"
