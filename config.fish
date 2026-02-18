set -x fish_greeting ""

fish_add_path ~/.bin
fish_add_path ~/anaconda3/bin/

if status is-interactive
    # Commands to run in interactive sessions can go here

    # PostgreSQL 17 aliases
    alias createdb="createdb-17"
    alias psql="psql-17"
    alias createuser="createuser-17"
end

function dotenv --description 'Load environment variables from .env file'
  set -l envfile ".env"
  if [ (count $argv) -gt 0 ]
    set envfile $argv[1]
  end

  if test -e $envfile
    for line in (cat $envfile)
      set -xg (echo $line | cut -d = -f 1) (echo $line | cut -d = -f 2-)
    end
  end
end

#
# Utils
#

set -x RESOLVE_HOME ~/devel/resolve

function copy
    if command -q pbcopy
        pbcopy $argv
    else
        xclip -selection clipboard $argv
    end
end

function ll
    ls -lah $argv
end

function dytv
    yt-dlp $argv --remux-video mp4
end

function resolve
    $RESOLVE_HOME/resolve.sh $argv
end

function encode-to-resolve
    set output $argv[2]
    if test -z "$output"
        set default_output_slices (string split / $argv[1])
        set output $default_output_slices[-1]
    end
    ffmpeg -i $argv[1] -vcodec mjpeg -q:v 2 -acodec pcm_s16be -q:a 0 -f mov $RESOLVE_HOME/mounts/resolve-home/$output
end

#
# SWIC
#

alias render-intro "node $SWIC_RENDERER_PATH/cli/render-intro.js"
alias render-intro-screenshot "node $SWIC_RENDERER_PATH/cli/render-intro-screenshot.js --output=$SWIC_RENDERER_SCREENSHOT_PATH"
alias render-worker "node $SWIC_RENDERER_PATH/cli/worker.js"

alias ri render-intro
alias ris render-intro-screenshot
alias rw render-worker

alias open-screenshot "open $SWIC_RENDERER_SCREENSHOT_PATH"
function ops
    open $SWIC_RENDERER_SCREENSHOT_PATH
    if command -q pbcopy
        pbcopy < $SWIC_RENDERER_SCREENSHOT_PATH
    else
        xclip -selection clipboard -t image/png -i $SWIC_RENDERER_SCREENSHOT_PATH
    end
end

alias upload-to-linode "node ~/devel/sxic-renderer/bin/upload-file-to-linode.js"
alias utl upload-to-linode

alias swap-swic-audio "~/devel/StarWarsIntroCreator/scripts/swap-audio.sh"
alias ssa swap-swic-audio
