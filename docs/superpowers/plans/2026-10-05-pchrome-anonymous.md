# Anonymous pchrome Implementation Plan

> Execute inline in this session; keep the change focused on the existing
> Fish launcher and its documentation.

**Goal:** Launch disposable Incognito sessions using `pchrome --anonymous`.

**Architecture:** Extend `fish/conf.d/proxy.fish` argument parsing and use
its existing temporary-profile cleanup path. Keep SSH and DNS configuration
unchanged. Validate behavior using fake external commands in subprocess tests.

**Tech Stack:** Fish and Python standard-library unittest.

- [x] Add `tests/test_pchrome.py` to exercise anonymous aliases, independent
  temporary profiles, saved-profile preservation, proxy/URL arguments, normal
  and fresh modes, and profile/browser failure cleanup.
- [x] Run `python3 -m unittest discover -s tests -p 'test_pchrome.py' -v`;
  confirm new anonymous behavior is unsupported before implementation.
- [x] In `fish/conf.d/proxy.fish`, accept `a/anonymous` and `i/incognito`,
  add `--incognito` to browser arguments, and select a temporary profile for
  either flag. Reject failed temporary directory creation, clean up owned
  tunnels, and preserve the browser exit code across teardown.
- [x] Document flags in help, completions, `fish/conf.d/cheats.fish`,
  `fish/README.md`, and `fish/AGENTS.md`.
- [x] Run the focused tests, Fish syntax checks, the full Python suite, and
  `git diff --check`. Review the diff and leave changes ready for review.

Verification: all 67 Python tests passed, including 7 pchrome tests. Fish
syntax checks, `fish_indent --check fish/conf.d/proxy.fish`, command help,
anonymous/incognito completions, and `git diff --check` passed. Browser and
SSH behavior was tested with fake commands, without a live GUI or connection.
