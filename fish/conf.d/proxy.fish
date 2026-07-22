# SSH SOCKS proxy + an isolated Chrome that browses through it.
#
#   pchrome <host> [url...]     tunnel to <host>, open Chrome behind it
#   pchrome --fresh <host>      throwaway profile (deleted on exit)
#   pchrome --port 1080 <host>  force the local SOCKS port
#
# The profile lives in ~/.cache/pchrome/<host> so logins survive between runs;
# --fresh gives maximum isolation instead. DNS is resolved by the remote end
# (--host-resolver-rules), so geo-DNS sees the remote IP, not yours.

complete -c pchrome -n __fish_is_first_arg -x -a '(__fish_print_hostnames)'
complete -c pchrome -s f -l fresh -d 'Throwaway profile, removed on exit'
complete -c pchrome -s p -l port -x -d 'Local SOCKS port'
complete -c pchrome -s h -l help -d 'Show usage'

function __pchrome_port_taken --description 'Is a local TCP port listening? Echoes the listener cmdline.'
    ss -ltnpH "sport = :$argv[1]" 2>/dev/null | string collect
end

function __pchrome_cleanup --on-event fish_exit
    if set -q __pchrome_ssh_pid
        for pid in $__pchrome_ssh_pid
            kill $pid 2>/dev/null
        end
        set -e __pchrome_ssh_pid
    end
end

function pchrome --description 'SSH SOCKS tunnel + isolated Chrome through it'
    argparse f/fresh p/port= h/help -- $argv
    or return 1

    if set -q _flag_help; or test (count $argv) -eq 0
        echo "usage: pchrome [--fresh] [--port N] <ssh-host> [url...]"
        echo ""
        echo "  --fresh      throwaway profile in a temp dir, removed on exit"
        echo "  --port N     local SOCKS port (default: derived from the host name)"
        echo ""
        echo "  <ssh-host> is anything ssh understands: an ~/.ssh/config alias,"
        echo "  user@host, or user@host with a -p port set in ssh config."
        test (count $argv) -eq 0; and return 1
        return 0
    end

    set -l host $argv[1]
    set -l urls $argv[2..-1]

    # Locate a Chrome/Chromium binary.
    set -l chrome
    for candidate in google-chrome google-chrome-stable chromium chromium-browser brave-browser
        if command -q $candidate
            set chrome $candidate
            break
        end
    end
    if test -z "$chrome"
        echo "pchrome: no chrome/chromium binary found" >&2
        return 1
    end

    # Pick the local SOCKS port: deterministic per host so repeat runs reuse
    # the same tunnel, then scan forward if that one is busy with something else.
    set -l port
    if set -q _flag_port
        set port $_flag_port
    else
        set -l h (printf '%s' $host | cksum | string split ' ')[1]
        set port (math 1080 + $h % 400)
    end

    set -l reused 0
    set -l ssh_pid
    for attempt in (seq 20)
        set -l listener (__pchrome_port_taken $port)
        if test -z "$listener"
            break
        else if string match -qr '"ssh"' -- $listener
            # Our own (or another) ssh tunnel is already on this port — reuse it.
            set reused 1
            break
        end
        if set -q _flag_port
            echo "pchrome: port $port is in use by something that isn't ssh" >&2
            return 1
        end
        set port (math $port + 1)
    end

    if test $reused -eq 1
        echo "pchrome: reusing existing SOCKS tunnel on 127.0.0.1:$port"
    else
        echo "pchrome: opening SOCKS tunnel $host → 127.0.0.1:$port"
        ssh -N -D 127.0.0.1:$port \
            -o ExitOnForwardFailure=yes \
            -o ServerAliveInterval=30 \
            -o ServerAliveCountMax=3 \
            $host &
        set ssh_pid $last_pid
        set -g __pchrome_ssh_pid $__pchrome_ssh_pid $ssh_pid

        # Wait for the forward to come up (or for ssh to die trying).
        set -l up 0
        for i in (seq 40)
            set -l listener (__pchrome_port_taken $port)
            if test -n "$listener"
                set up 1
                break
            end
            # A zombie still answers kill -0, so ask ps for the actual state.
            set -l state (ps -o stat= -p $ssh_pid 2>/dev/null | string trim)
            if test -z "$state"; or string match -q 'Z*' -- $state
                echo "pchrome: ssh exited before the tunnel was ready" >&2
                return 1
            end
            sleep 0.25
        end
        if test $up -eq 0
            echo "pchrome: timed out waiting for 127.0.0.1:$port" >&2
            kill $ssh_pid 2>/dev/null
            return 1
        end
    end

    # Profile directory.
    set -l profile
    set -l ephemeral 0
    if set -q _flag_fresh
        set profile (mktemp -d -t pchrome.XXXXXXXX)
        set ephemeral 1
    else
        set -l slug (string replace -a -r '[^A-Za-z0-9._-]' '_' -- $host)
        set profile "$HOME/.cache/pchrome/$slug"
        mkdir -p $profile
    end

    echo "pchrome: launching $chrome (profile: $profile)"
    $chrome \
        --user-data-dir=$profile \
        --proxy-server="socks5://127.0.0.1:$port" \
        --host-resolver-rules="MAP * ~NOTFOUND , EXCLUDE 127.0.0.1" \
        --no-first-run \
        --no-default-browser-check \
        $urls 2>/dev/null

    # Teardown: only kill the tunnel we started ourselves.
    if test -n "$ssh_pid"
        kill $ssh_pid 2>/dev/null
        if set -q __pchrome_ssh_pid
            set -g __pchrome_ssh_pid (string match -v -- $ssh_pid $__pchrome_ssh_pid)
        end
        echo "pchrome: tunnel closed"
    end
    if test $ephemeral -eq 1
        rm -rf $profile
    end
end
