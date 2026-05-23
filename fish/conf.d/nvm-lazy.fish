# Add the nvm "default" node to PATH without sourcing nvm.sh on shell startup.
# Saves ~500ms+ per interactive shell. The `nvm` function (provided by the OMF
# nvm plugin) still works on demand and will switch versions when called.

function _nvm_use_default_in_path
    set -l default_file "$HOME/.nvm/alias/default"
    test -f $default_file; or return
    set -l target (cat $default_file 2>/dev/null | string trim)
    test -n "$target"; or return

    set -l versions_dir "$HOME/.nvm/versions/node"
    test -d $versions_dir; or return

    # Try exact match first ("v22"), then highest matching minor ("v22.*")
    set -l node_version
    if test -d "$versions_dir/v$target"
        set node_version "v$target"
    else
        set node_version (ls $versions_dir 2>/dev/null | string match -r "^v$target\..*" | sort -V | tail -1)
    end
    test -n "$node_version"; or return

    fish_add_path --prepend "$versions_dir/$node_version/bin"
end

_nvm_use_default_in_path
functions -e _nvm_use_default_in_path
