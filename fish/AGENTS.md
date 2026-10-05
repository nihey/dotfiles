# Fish configuration

`conf.d/*.fish` modules are loaded by Fish and symlinked by `../install.sh`.
Keep command help, completions, `conf.d/cheats.fish`, and `README.md` in sync
when adding command options. Secrets belong in untracked `env.local.fish`.

`pchrome` in `conf.d/proxy.fish` launches Chrome through an SSH SOCKS tunnel
with remote DNS. Regular sessions use `~/.cache/pchrome/<host>`; `--fresh`
uses a disposable profile. `--anonymous` / `-a` and `--incognito` / `-i`
combine a disposable profile with Chrome Incognito. Remove disposable
profiles after browser exit and never fall back to a saved profile when
temporary directory creation fails. Close only tunnels started by the current
invocation and preserve the browser's exit status after cleanup.

Validate Fish syntax with `fish --no-config --no-execute` on changed modules.
Run `python3 -m unittest discover -s tests -p 'test_pchrome.py' -v` from the
repository root for launcher regression tests; they fake browser/network
commands and use temporary directories.
