# Add anaconda binaries to PATH if anaconda is installed at the standard
# location. Heavy `conda` init (for `conda activate`) is intentionally left
# to ~/.config/fish/config.fish on machines that need it.

if test -d ~/anaconda3/bin
    fish_add_path ~/anaconda3/bin
end
