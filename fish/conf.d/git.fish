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
