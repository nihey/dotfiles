#!/usr/bin/env python3
"""Exercise pchrome without launching a browser or connecting to SSH."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROXY = ROOT / "fish" / "conf.d" / "proxy.fish"
FISH = shutil.which("fish")


@unittest.skipUnless(FISH, "fish is required")
class PchromeTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="pchrome tests ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.profile = self.root / "home" / ".cache" / "pchrome" / "example-host"
        self.profile.mkdir(parents=True)
        (self.profile / "saved-session").write_text("keep me")
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.temp_profiles = self.root / "temporary profiles"
        self.temp_profiles.mkdir()
        self.log = self.root / "browser.json"
        self.env = {
            **os.environ,
            "HOME": str(self.root / "home"),
            "XDG_CONFIG_HOME": str(self.root / "config"),
            "PATH": f"{self.bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "TMPDIR": str(self.temp_profiles),
            "PCHROME_TEST_LOG": str(self.log),
            "PCHROME_TEST_EXIT": "0",
        }
        self.write_command(
            "ss",
            'print(\'LISTEN 0 128 127.0.0.1:1080 users:(("ssh",pid=1,fd=3))\')\n',
        )
        self.write_command("ssh", 'raise SystemExit("unexpected SSH connection")\n')
        self.write_command(
            "google-chrome",
            """import json
import os
import sys
from pathlib import Path

args = sys.argv[1:]
profile = Path(next(arg.split("=", 1)[1] for arg in args
                    if arg.startswith("--user-data-dir=")))
Path(os.environ["PCHROME_TEST_LOG"]).write_text(json.dumps({
    "args": args,
    "profile": str(profile),
    "contents": sorted(path.name for path in profile.iterdir()),
}))
(profile / "browser-data").write_text("temporary browsing data")
raise SystemExit(int(os.environ["PCHROME_TEST_EXIT"]))
""",
        )

    def write_command(self, name: str, source: str) -> None:
        path = self.bin / name
        path.write_text(f"#!{sys.executable}\n{source}")
        path.chmod(0o755)

    def run_pchrome(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                FISH, "--no-config", "-c",
                'source "$argv[1]"; pchrome $argv[2..-1]; '
                'set -l result $status; '
                'if set -q __pchrome_ssh_pid[1]; echo "tunnel still tracked" >&2; end; '
                'exit $result',
                str(PROXY), *args,
            ],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

    def browser_call(self) -> dict:
        return json.loads(self.log.read_text())

    def assert_disposable(self, call: dict) -> None:
        self.assertEqual(call["contents"], [])
        self.assertEqual(Path(call["profile"]).parent, self.temp_profiles)
        self.assertFalse(Path(call["profile"]).exists())
        self.assertEqual(list(self.temp_profiles.iterdir()), [])
        self.assertEqual((self.profile / "saved-session").read_text(), "keep me")
        self.assertEqual(list(self.profile.iterdir()), [self.profile / "saved-session"])

    def test_anonymous_aliases_use_independent_profiles_and_forward_arguments(self) -> None:
        profiles = set()
        urls = ["https://example.test/a?q=two words", "https://example.test/b"]
        for flag in ("--anonymous", "-a", "--incognito", "-i"):
            with self.subTest(flag=flag):
                result = self.run_pchrome(flag, "--port", "1080", "example-host", *urls)
                self.assertEqual(result.returncode, 0, result.stderr)
                call = self.browser_call()
                self.assertIn("--incognito", call["args"])
                self.assertIn("--proxy-server=socks5://127.0.0.1:1080", call["args"])
                self.assertIn(
                    "--host-resolver-rules=MAP * ~NOTFOUND , EXCLUDE 127.0.0.1",
                    call["args"],
                )
                self.assertEqual(call["args"][-2:], urls)
                self.assert_disposable(call)
                self.assertNotIn(call["profile"], profiles)
                profiles.add(call["profile"])

    def test_regular_session_reuses_persistent_profile(self) -> None:
        result = self.run_pchrome("example-host")
        self.assertEqual(result.returncode, 0, result.stderr)
        call = self.browser_call()
        self.assertEqual(call["profile"], str(self.profile))
        self.assertEqual(call["contents"], ["saved-session"])
        self.assertNotIn("--incognito", call["args"])
        self.assertTrue((self.profile / "browser-data").exists())

    def test_fresh_stays_disposable_without_incognito(self) -> None:
        result = self.run_pchrome("--fresh", "example-host")
        self.assertEqual(result.returncode, 0, result.stderr)
        call = self.browser_call()
        self.assertNotIn("--incognito", call["args"])
        self.assert_disposable(call)

    def test_anonymous_can_be_combined_with_fresh_and_incognito(self) -> None:
        result = self.run_pchrome("--fresh", "--anonymous", "--incognito", "example-host")
        self.assertEqual(result.returncode, 0, result.stderr)
        call = self.browser_call()
        self.assertEqual(call["args"].count("--incognito"), 1)
        self.assert_disposable(call)

    def test_browser_failure_still_removes_temporary_data(self) -> None:
        self.env["PCHROME_TEST_EXIT"] = "7"
        result = self.run_pchrome("--anonymous", "example-host")
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assert_disposable(self.browser_call())

    def test_failed_profile_creation_does_not_launch_browser(self) -> None:
        self.write_command("mktemp", "raise SystemExit(1)\n")
        for flag in ("--anonymous", "--fresh"):
            with self.subTest(flag=flag):
                result = self.run_pchrome(flag, "example-host")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("could not create temporary profile", result.stderr)
                self.assertFalse(self.log.exists())

    def test_owned_tunnel_is_closed_after_browser_exit_or_profile_failure(self) -> None:
        tunnel = self.root / "tunnel"
        self.env["PCHROME_TEST_TUNNEL"] = str(tunnel)
        self.write_command(
            "ssh",
            """import os
import signal
from pathlib import Path

ready = Path(os.environ["PCHROME_TEST_TUNNEL"])
def stop(signum, frame):
    ready.unlink(missing_ok=True)
    raise SystemExit(0)
signal.signal(signal.SIGTERM, stop)
ready.write_text(str(os.getpid()))
while True:
    signal.pause()
""",
        )
        self.write_command(
            "ss",
            """import os
from pathlib import Path
if Path(os.environ["PCHROME_TEST_TUNNEL"]).exists():
    print('LISTEN 0 128 127.0.0.1:1080 users:(("ssh",pid=1,fd=3))')
""",
        )
        for fail_profile in (False, True):
            with self.subTest(fail_profile=fail_profile):
                if fail_profile:
                    self.log.unlink()
                    self.write_command("mktemp", "raise SystemExit(1)\n")
                result = self.run_pchrome("--anonymous", "example-host")
                self.assertEqual(result.returncode, 1 if fail_profile else 0, result.stderr)
                self.assertIn("opening SOCKS tunnel", result.stdout)
                self.assertNotIn("tunnel still tracked", result.stderr)
                self.assertFalse(tunnel.exists())
                if fail_profile:
                    self.assertFalse(self.log.exists())
                else:
                    self.assert_disposable(self.browser_call())


if __name__ == "__main__":
    unittest.main()
