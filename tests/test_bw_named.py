#!/usr/bin/env python3
"""Subprocess tests for bw-quickfiller / bw-kassellabs."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROFILE_SCRIPT = ROOT / "bin" / "bw-profile"
INSTALL_LIB = ROOT / "lib" / "bw-profiles.sh"


class BwNamedTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.config = self.home / ".config"
        self.config.mkdir()
        self.fake_bin = self.root / "bin"
        self.fake_bin.mkdir()
        self.log = self.root / "bw.jsonl"
        self._write_fake_bw()
        self.quickfiller = self.root / "bw-quickfiller"
        self.kassellabs = self.root / "bw-kassellabs"
        self.quickfiller.symlink_to(PROFILE_SCRIPT)
        self.kassellabs.symlink_to(PROFILE_SCRIPT)

    def _write_fake_bw(self) -> None:
        fake = self.fake_bin / "bw"
        fake.write_text(
            f"""#!{sys.executable}
import json
import os
from pathlib import Path
import sys

Path({str(self.log)!r}).write_text(
    json.dumps({{
        "argv": sys.argv[1:],
        "appdata": os.environ.get("BITWARDENCLI_APPDATA_DIR"),
    }})
    + "\\n"
)
"""
        )
        fake.chmod(0o755)

    def env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["HOME"] = str(self.home)
        env["XDG_CONFIG_HOME"] = str(self.config)
        env["PATH"] = f"{self.fake_bin}{os.pathsep}{env.get('PATH', '')}"
        return env

    def run_named(self, binary: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(binary), *args],
            env=self.env(),
            text=True,
            capture_output=True,
            check=False,
        )

    def last_bw(self) -> dict:
        return json.loads(self.log.read_text())

    def write_server(self, profile: str, url: str) -> Path:
        directory = self.config / f"bw-{profile}"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "server"
        path.write_text(url + "\n")
        return path

    def source_text(self) -> str:
        parts = [
            PROFILE_SCRIPT.read_text(),
            INSTALL_LIB.read_text(),
            (ROOT / "install.sh").read_text(),
        ]
        return "\n".join(parts)

    def test_tracked_files_do_not_contain_server_urls(self) -> None:
        text = self.source_text()
        self.assertNotIn("kassellabs.io", text)
        self.assertNotIn("quickfiller.org", text)

    def test_missing_server_url_fails_without_calling_bw(self) -> None:
        result = self.run_named(self.quickfiller, "status")
        self.assertEqual(result.returncode, 1)
        self.assertIn("install.sh", result.stderr)
        self.assertFalse(self.log.exists())

    def test_quickfiller_uses_dedicated_appdata_and_forwards_args(self) -> None:
        self.write_server("quickfiller", "https://example.test/vault")
        result = self.run_named(self.quickfiller, "list", "items")
        self.assertEqual(result.returncode, 0, result.stderr)
        called = self.last_bw()
        self.assertEqual(called["argv"], ["list", "items"])
        self.assertEqual(
            called["appdata"],
            str(self.config / "bw-quickfiller"),
        )

    def test_kassellabs_uses_default_bw_appdata(self) -> None:
        self.write_server("kassellabs", "https://example.test/other")
        result = self.run_named(self.kassellabs, "status")
        self.assertEqual(result.returncode, 0, result.stderr)
        called = self.last_bw()
        self.assertEqual(called["argv"], ["status"])
        self.assertIsNone(called["appdata"])

    def test_unknown_command_name_fails(self) -> None:
        other = self.root / "bw-other"
        other.symlink_to(PROFILE_SCRIPT)
        result = self.run_named(other, "status")
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.log.exists())


class BwProfileInstallTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.config = self.home / ".config"
        self.config.mkdir()
        self.fake_bin = self.root / "bin"
        self.fake_bin.mkdir()
        self.log = self.root / "bw.jsonl"
        fake = self.fake_bin / "bw"
        fake.write_text(
            f"""#!{sys.executable}
import json
import os
from pathlib import Path
import sys
Path({str(self.log)!r}).open("a").write(
    json.dumps({{"argv": sys.argv[1:], "appdata": os.environ.get("BITWARDENCLI_APPDATA_DIR")}}) + "\\n"
)
"""
        )
        fake.chmod(0o755)

    def env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["HOME"] = str(self.home)
        env["XDG_CONFIG_HOME"] = str(self.config)
        env["PATH"] = f"{self.fake_bin}{os.pathsep}{env.get('PATH', '')}"
        return env

    def configure(self, profile: str, url: str | None = None, stdin: str = "") -> subprocess.CompletedProcess[str]:
        command = f'set -euo pipefail; . "{INSTALL_LIB}" && bw_profile_configure "{profile}"'
        if url is not None:
            command += f' "{url}"'
        return subprocess.run(
            ["bash", "-c", command],
            env=self.env(),
            input=stdin,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_writes_server_file_and_points_bw_at_it(self) -> None:
        result = self.configure("quickfiller", "https://example.test/vault")
        self.assertEqual(result.returncode, 0, result.stderr)
        server = (self.config / "bw-quickfiller" / "server").read_text().strip()
        self.assertEqual(server, "https://example.test/vault")
        mode = stat.S_IMODE((self.config / "bw-quickfiller" / "server").stat().st_mode)
        self.assertEqual(mode, 0o600)
        called = json.loads(self.log.read_text().splitlines()[-1])
        self.assertEqual(called["argv"], ["config", "server", "https://example.test/vault"])
        self.assertEqual(called["appdata"], str(self.config / "bw-quickfiller"))

    def test_kassellabs_configures_default_bw_profile(self) -> None:
        result = self.configure("kassellabs", "https://example.test/other")
        self.assertEqual(result.returncode, 0, result.stderr)
        called = json.loads(self.log.read_text().splitlines()[-1])
        self.assertEqual(called["argv"], ["config", "server", "https://example.test/other"])
        self.assertIsNone(called["appdata"])

    def test_does_not_overwrite_existing_server(self) -> None:
        directory = self.config / "bw-quickfiller"
        directory.mkdir()
        (directory / "server").write_text("https://example.test/keep\n")
        result = self.configure("quickfiller", "https://example.test/new")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            (directory / "server").read_text().strip(),
            "https://example.test/keep",
        )
        self.assertFalse(self.log.exists())

    def test_prompts_when_no_url_argument(self) -> None:
        result = self.configure("quickfiller", stdin="https://example.test/prompted\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            (self.config / "bw-quickfiller" / "server").read_text().strip(),
            "https://example.test/prompted",
        )

    def test_keeps_url_when_bw_requires_logout(self) -> None:
        fake = self.fake_bin / "bw"
        fake.write_text(
            f"""#!{sys.executable}
import sys
print("Logout required before server config update.", file=sys.stderr)
raise SystemExit(1)
"""
        )
        fake.chmod(0o755)
        result = self.configure("kassellabs", "https://example.test/other")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            (self.config / "bw-kassellabs" / "server").read_text().strip(),
            "https://example.test/other",
        )

    def test_rejects_non_https_url(self) -> None:
        result = self.configure("quickfiller", "http://example.test")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.config / "bw-quickfiller" / "server").exists())


if __name__ == "__main__":
    unittest.main()
