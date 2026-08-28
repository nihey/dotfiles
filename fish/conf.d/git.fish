# Common git aliases.

alias g  'git'
alias gs 'git status --short --branch'
alias gd 'git diff'
alias gds 'git diff --staged'
alias gco 'git checkout'
alias gcb 'git checkout -b'
alias gb  'git branch'
alias gp  'git pull'
alias gpu 'git push'
alias gl  'git log --oneline --decorate -20'
alias glg 'git log --oneline --decorate --graph --all -30'
alias gaa 'git add -A'
alias gcm 'git commit -m'
alias gca 'git commit --amend --no-edit'
alias gst 'git stash'
alias gstp 'git stash pop'

function gco- --description 'git checkout previous branch'
    git checkout -
end

function gwip --description 'Quick WIP commit (no verify)'
    git add -A
    git commit -m "wip" --no-verify
end

function __git_local_cleanup_bin --description 'Resolve git-local-cleanup executable'
    if command -q git-local-cleanup
        echo git-local-cleanup
        return 0
    end
    set -l here (dirname (realpath (status --current-filename)))
    set -l candidate "$here/../../bin/git-local-cleanup"
    if test -x $candidate
        echo $candidate
        return 0
    end
    echo "git-local-cleanup not found; run ~/devel/dotfiles/install.sh" >&2
    return 1
end

function __git_enter_main_repo --description 'cd to the main git checkout if this is a linked worktree'
    git rev-parse --is-inside-work-tree >/dev/null 2>&1
    or begin
        echo "not a git repository" >&2
        return 1
    end
    set -l common (git rev-parse --git-common-dir)
    set -l main_repo (realpath "$common/..")
    set -l toplevel (realpath (git rev-parse --show-toplevel))
    if test "$toplevel" != "$main_repo"
        echo "moving to main repo: $main_repo"
        cd $main_repo
    end
end

function gprune --description 'Prune merged git worktrees/branches; checkout main if HEAD is merged'
    __git_enter_main_repo; or return
    set -l bin (__git_local_cleanup_bin); or return
    $bin prune $argv
end

function gonly-main --description 'Stash unique WIP, delete other local branches/worktrees, leave only main'
    __git_enter_main_repo; or return
    set -l bin (__git_local_cleanup_bin); or return
    $bin only-main $argv
end
