#!/usr/bin/env python3
"""Subprocess tests for bin/extract-frames."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "extract-frames"


class ExtractFramesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.work = self.root / "work"
        self.work.mkdir()
        self.video = self.work / "sample clip.mp4"
        self.video.write_bytes(b"not a real video")
        self.fake_bin = self.root / "bin"
        self.fake_bin.mkdir()
        self.log = self.root / "ffmpeg.jsonl"
        self._write_fake_ffmpeg()

    def _write_fake_ffmpeg(self) -> None:
        fake = self.fake_bin / "ffmpeg"
        fake.write_text(
            f"""#!{sys.executable}
import json
import os
from pathlib import Path
import sys

with Path(os.environ["FAKE_FFMPEG_LOG"]).open("a") as log:
    log.write(json.dumps(sys.argv[1:]) + "\\n")

if os.environ.get("FAKE_FFMPEG_FAIL_TIMESTAMP") in sys.argv:
    print("simulated ffmpeg failure", file=sys.stderr)
    raise SystemExit(7)

Path(sys.argv[-1]).write_bytes(b"fake png")
"""
        )
        fake.chmod(0o755)

    def run_cli(
        self,
        *args: str,
        cwd: Path | None = None,
        env_changes: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PATH"] = f"{self.fake_bin}{os.pathsep}{env.get('PATH', '')}"
        env["FAKE_FFMPEG_LOG"] = str(self.log)
        if env_changes:
            env.update(env_changes)
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=str(cwd or self.work),
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def calls(self) -> list[list[str]]:
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_extracts_multiple_timestamps_into_current_directory(self) -> None:
        result = self.run_cli(str(self.video), "00:01", "5.500")

        self.assertEqual(result.returncode, 0, result.stderr)
        first = self.work / "sample clip-frame-001-00-01.png"
        second = self.work / "sample clip-frame-002-5.500.png"
        self.assertEqual(first.read_bytes(), b"fake png")
        self.assertEqual(second.read_bytes(), b"fake png")
        self.assertEqual(
            self.calls(),
            [
                [
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-ss",
                    "00:01",
                    "-i",
                    str(self.video),
                    "-frames:v",
                    "1",
                    str(first),
                ],
                [
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-ss",
                    "5.500",
                    "-i",
                    str(self.video),
                    "-frames:v",
                    "1",
                    str(second),
                ],
            ],
        )

    def test_creates_nested_output_with_option_on_either_side_of_timestamp(self) -> None:
        before = self.root / "before" / "frames"
        result_before = self.run_cli(
            str(self.video), "--output", str(before), "2"
        )
        self.assertEqual(result_before.returncode, 0, result_before.stderr)
        self.assertTrue((before / "sample clip-frame-001-2.png").is_file())

        after = self.root / "after" / "frames"
        result_after = self.run_cli(str(self.video), "3", "-o", str(after))
        self.assertEqual(result_after.returncode, 0, result_after.stderr)
        self.assertTrue((after / "sample clip-frame-001-3.png").is_file())

    def test_duplicate_timestamps_do_not_overwrite_each_other(self) -> None:
        result = self.run_cli(str(self.video), "10", "10")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.work / "sample clip-frame-001-10.png").is_file())
        self.assertTrue((self.work / "sample clip-frame-002-10.png").is_file())

    def test_help_prints_usage_without_calling_ffmpeg(self) -> None:
        result = self.run_cli("--help")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("extract-frames", result.stdout)
        self.assertIn("timestamp", result.stdout.lower())
        self.assertEqual(self.calls(), [])

    def test_rejects_missing_input_before_calling_ffmpeg(self) -> None:
        missing = self.work / "missing.mp4"
        result = self.run_cli(str(missing), "1")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("input video is not a file", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_rejects_missing_timestamps(self) -> None:
        result = self.run_cli(str(self.video))

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("at least one timestamp is required", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_rejects_invalid_timestamps_before_creating_output(self) -> None:
        invalid_values = ("-1", "abc", "1:60", "60:00", "1:60:00", "1:2:3:4")
        for position, value in enumerate(invalid_values):
            with self.subTest(timestamp=value):
                output = self.root / f"invalid-{position}" / "frames"
                result = self.run_cli(
                    str(self.video), value, "--output", str(output)
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(f"invalid timestamp: {value}", result.stderr)
                self.assertFalse(output.exists())
        self.assertEqual(self.calls(), [])

    def test_reports_missing_ffmpeg_without_a_traceback(self) -> None:
        result = self.run_cli(
            str(self.video),
            "1",
            env_changes={"PATH": ""},
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ffmpeg was not found on PATH", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_stops_on_ffmpeg_failure_and_keeps_completed_frames(self) -> None:
        result = self.run_cli(
            str(self.video),
            "1",
            "2",
            "3",
            env_changes={"FAKE_FFMPEG_FAIL_TIMESTAMP": "2"},
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ffmpeg failed at timestamp 2", result.stderr)
        self.assertIn("simulated ffmpeg failure", result.stderr)
        self.assertTrue((self.work / "sample clip-frame-001-1.png").is_file())
        self.assertFalse((self.work / "sample clip-frame-002-2.png").exists())
        self.assertFalse((self.work / "sample clip-frame-003-3.png").exists())
        self.assertEqual(len(self.calls()), 2)

    def test_reports_output_directory_creation_failure(self) -> None:
        output_file = self.root / "not-a-directory"
        output_file.write_text("occupied")
        result = self.run_cli(
            str(self.video), "1", "--output", str(output_file)
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cannot create output directory", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main()
