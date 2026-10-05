# Anonymous pchrome sessions

`pchrome --anonymous <ssh-host> [url...]` opens Chrome Incognito through the
existing SSH SOCKS tunnel. `-a`, `--incognito`, and `-i` select the same mode.
Each invocation uses a new temporary user-data directory and removes it
after the browser process exits, including when the browser reports failure.
The persistent per-host profile is never read or changed by this mode.

Using only the existing `--fresh` option gives a clean regular browser;
adding Incognito to the persistent profile would still share that profile's
settings. Incognito with a disposable profile provides both private browsing
and isolation from saved sessions. `--fresh` keeps its existing behavior and
may be combined with the new flags. Proxy, remote DNS, port selection, URL
forwarding, and tunnel ownership remain the same.

If temporary profile creation fails, do not launch Chrome with a missing
user-data directory; report failure and close any tunnel started by this
invocation. Return the browser exit status after cleanup. Anonymous means
local Incognito browsing through the selected SSH host, not network anonymity.

Document the flags in command help, completions, the cheatsheet, and Fish
documentation. Use subprocess tests with fake Chrome and network commands to
verify isolation, argument forwarding, cleanup, and failure behavior without
opening a browser or connecting to an SSH server.
