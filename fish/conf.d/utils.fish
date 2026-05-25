# Generic shell utilities — safe to share across machines.

function copy --description 'Copy stdin/args to the system clipboard'
    if command -q pbcopy
        pbcopy $argv
    else if command -q xclip
        xclip -selection clipboard $argv
    else if command -q wl-copy
        wl-copy $argv
    else
        echo "copy: no clipboard utility found (pbcopy/xclip/wl-copy)" >&2
        return 1
    end
end

function ll --description 'ls -lah'
    ls -lah $argv
end

function mkcd --description 'mkdir -p && cd into it'
    if test (count $argv) -eq 0
        echo "usage: mkcd <dir>"
        return 1
    end
    mkdir -p $argv[1]; and cd $argv[1]
end

function dytv --description 'yt-dlp remuxed to mp4'
    yt-dlp $argv --remux-video mp4
end

function randstr --description 'Random alphanumeric string (default length 32)'
    set -l length 32
    if test (count $argv) -gt 0
        set length $argv[1]
    end
    cat /dev/urandom | tr -dc 'a-zA-Z0-9-_' | head -c $length
    echo
end

function dotenv --description 'Export vars from a .env file into the current shell'
    set -l envfile ".env"
    if test (count $argv) -gt 0
        set envfile $argv[1]
    end

    if not test -e $envfile
        echo "dotenv: $envfile not found" >&2
        return 1
    end

    # Handles: KEY=value, KEY="value", KEY='value', comments, blank lines, `export` prefix, `=` inside values.
    while read -l line
        set line (string trim -- $line)
        # skip blanks and comments
        test -z "$line"; and continue
        string match -qr '^#' -- $line; and continue
        # strip leading `export `
        set line (string replace -r '^export[[:space:]]+' '' -- $line)
        # must look like KEY=...
        string match -qr '^[A-Za-z_][A-Za-z0-9_]*=' -- $line; or continue
        set -l key (string replace -r '=.*' '' -- $line)
        set -l val (string replace -r '^[^=]+=' '' -- $line)
        # strip matched surrounding quotes
        set val (string replace -r '^"(.*)"$' '$1' -- $val)
        set val (string replace -r "^'(.*)'\$" '$1' -- $val)
        set -gx $key $val
    end < $envfile
end
