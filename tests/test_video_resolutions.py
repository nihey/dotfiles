#!/usr/bin/env python3
"""Subprocess tests for bin/video-resolutions."""

from __future__ import annotations

import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "video-resolutions"
SCRIPT_LOADER = importlib.machinery.SourceFileLoader("video_resolutions", str(SCRIPT))
SCRIPT_SPEC = importlib.util.spec_from_loader(SCRIPT_LOADER.name, SCRIPT_LOADER)
if SCRIPT_SPEC is None or SCRIPT_SPEC.loader is None:
    raise RuntimeError(f"could not load {SCRIPT}")
VIDEO_RESOLUTIONS = importlib.util.module_from_spec(SCRIPT_SPEC)
sys.modules[SCRIPT_SPEC.name] = VIDEO_RESOLUTIONS
SCRIPT_SPEC.loader.exec_module(VIDEO_RESOLUTIONS)
FFPROBE_ARGS = [
    "-v",
    "error",
    "-select_streams",
    "v:0",
    "-show_entries",
    "stream=width,height",
    "-of",
    "json",
]
VIDEO_EXTENSIONS = (
    ".3gp",
    ".avi",
    ".flv",
    ".m2ts",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".mts",
    ".ts",
    ".webm",
    ".wmv",
)


class VideoResolutionsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.work = self.root / "work"
        self.work.mkdir()
        self.fake_bin = self.root / "bin"
        self.fake_bin.mkdir()
        self.log = self.root / "ffprobe.jsonl"
        self.dimensions: dict[str, list[object] | str] = {}
        self._write_fake_ffprobe()

    def _write_fake_ffprobe(self) -> None:
        fake = self.fake_bin / "ffprobe"
        fake.write_text(
            f"""#!{sys.executable}
import json
import os
from pathlib import Path
import sys

with Path(os.environ["FAKE_FFPROBE_LOG"]).open("a") as log:
    log.write(json.dumps(sys.argv[1:]) + "\\n")

dimensions = json.loads(os.environ["FAKE_FFPROBE_DIMENSIONS"])
probe_result = dimensions[str(Path(sys.argv[-1]).resolve())]
if probe_result == "fail":
    print("simulated probe failure", file=sys.stderr)
    raise SystemExit(7)
if probe_result == "invalid-bytes":
    sys.stderr.buffer.write(b"\\xffsimulated invalid bytes\\n")
    raise SystemExit(7)
if probe_result == "malformed":
    print("not json")
    raise SystemExit(0)
if probe_result == "empty":
    print(json.dumps({{"streams": []}}))
    raise SystemExit(0)
width, height = probe_result
print(json.dumps({{"streams": [{{"width": width, "height": height}}]}}))
"""
        )
        fake.chmod(0o755)

    def create_video(
        self,
        relative_path: str,
        dimensions: tuple[object, object] | str = (1920, 1080),
    ) -> Path:
        video = self.work / relative_path
        video.parent.mkdir(parents=True, exist_ok=True)
        video.write_bytes(b"not a real video")
        self.dimensions[str(video.resolve())] = (
            dimensions if isinstance(dimensions, str) else list(dimensions)
        )
        return video

    def run_cli(
        self, *args: str, cwd: Path | None = None
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PATH"] = f"{self.fake_bin}{os.pathsep}{env.get('PATH', '')}"
        env["FAKE_FFPROBE_LOG"] = str(self.log)
        env["FAKE_FFPROBE_DIMENSIONS"] = json.dumps(self.dimensions)
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

    def assert_probed(self, *videos: str) -> None:
        self.assertEqual(
            self.calls(),
            [FFPROBE_ARGS + [video] for video in videos],
        )

    def test_recursively_lists_supported_videos_in_aligned_path_order(self) -> None:
        apple = self.create_video("apple.mov", (3840, 2160))
        target = self.root / "linked-source.bin"
        target.write_bytes(b"not a real video")
        linked = self.work / "Linked clip.WEBM"
        linked.symlink_to(target)
        self.dimensions[str(target.resolve())] = [1280, 720]
        zebra = self.create_video("nested/Zebra.MP4", (640, 360))
        unicode_video = self.create_video("vídeos espaço/Árvore.MkV", (1920, 1080))
        (self.work / "notes.txt").write_text("ignore me")

        result = self.run_cli(str(self.work))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout,
            "Resolution  File\n"
            "----------  ----\n"
            "3840x2160   apple.mov\n"
            "1280x720    Linked clip.WEBM\n"
            "640x360     nested/Zebra.MP4\n"
            "1920x1080   vídeos espaço/Árvore.MkV\n",
        )
        self.assert_probed(str(apple), str(linked), str(zebra), str(unicode_video))

    def test_defaults_to_scanning_current_directory(self) -> None:
        self.create_video("current.mp4", (720, 480))

        result = self.run_cli(cwd=self.work)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout,
            "Resolution  File\n"
            "----------  ----\n"
            "720x480     current.mp4\n",
        )
        self.assert_probed("current.mp4")

    def test_no_recursive_only_lists_immediate_videos(self) -> None:
        self.create_video("immediate.mp4", (640, 480))
        self.create_video("nested/hidden.mkv", (1920, 1080))
        (self.work / "unrelated.txt").write_text("ignore me")

        result = self.run_cli("--no-recursive", cwd=self.work)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout,
            "Resolution  File\n"
            "----------  ----\n"
            "640x480     immediate.mp4\n",
        )
        self.assert_probed("immediate.mp4")

    def test_recognizes_exact_case_insensitive_extension_allowlist(self) -> None:
        supported: list[Path] = []
        for position, extension in enumerate(VIDEO_EXTENSIONS, start=1):
            mixed_case = extension.upper() if position % 2 else extension
            supported.append(
                self.create_video(f"clip-{position:02d}{mixed_case}", (320, 240))
            )
        self.create_video("not-video.mp42", (320, 240))
        self.create_video("not-video.ogv", (320, 240))
        self.create_video("not-video", (320, 240))

        result = self.run_cli(str(self.work))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_probed(*(str(video) for video in supported))
        output_files = [line.split(maxsplit=1)[1] for line in result.stdout.splitlines()[2:]]
        self.assertEqual(output_files, [video.name for video in supported])

    def test_empty_directory_prints_message_without_probing(self) -> None:
        result = self.run_cli(str(self.work))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "No videos found.\n")
        self.assertEqual(self.calls(), [])

    def test_help_describes_sort_option_without_probing(self) -> None:
        result = self.run_cli("--help")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("video-resolutions", result.stdout)
        self.assertIn("--sort-resolution", result.stdout)
        self.assertEqual(self.calls(), [])

    def test_sorts_by_resolution_descending_with_paths_breaking_ties(self) -> None:
        self.create_video("z-wide.mp4", (1920, 1080))
        self.create_video("a-wide.mp4", (1920, 1080))
        self.create_video("portrait.mp4", (1080, 1920))
        self.create_video("small.mp4", (1280, 720))

        result = self.run_cli("--sort-resolution", cwd=self.work)

        self.assertEqual(result.returncode, 0, result.stderr)
        rows = [line.split(maxsplit=1) for line in result.stdout.splitlines()[2:]]
        self.assertEqual(
            rows,
            [
                ["1920x1080", "a-wide.mp4"],
                ["1920x1080", "z-wide.mp4"],
                ["1080x1920", "portrait.mp4"],
                ["1280x720", "small.mp4"],
            ],
        )

    def test_sorts_by_resolution_ascending_with_paths_breaking_ties(self) -> None:
        self.create_video("z-wide.mp4", (1920, 1080))
        self.create_video("a-wide.mp4", (1920, 1080))
        self.create_video("portrait.mp4", (1080, 1920))
        self.create_video("small.mp4", (1280, 720))

        result = self.run_cli("--sort-resolution", "--ascending", cwd=self.work)

        self.assertEqual(result.returncode, 0, result.stderr)
        rows = [line.split(maxsplit=1) for line in result.stdout.splitlines()[2:]]
        self.assertEqual(
            rows,
            [
                ["1280x720", "small.mp4"],
                ["1080x1920", "portrait.mp4"],
                ["1920x1080", "a-wide.mp4"],
                ["1920x1080", "z-wide.mp4"],
            ],
        )

    def test_rejects_paths_that_are_not_directories_without_probing(self) -> None:
        regular_file = self.root / "regular-file"
        regular_file.write_text("not a directory")

        for invalid_path in (self.root / "missing", regular_file):
            with self.subTest(path=invalid_path):
                result = self.run_cli(str(invalid_path))

                self.assertNotEqual(result.returncode, 0)
                self.assertIn("path is not a directory", result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertEqual(self.calls(), [])

    def test_reports_recursive_traversal_errors_without_probing(self) -> None:
        blocked = self.work / "blocked"
        scan_error = PermissionError(13, "Permission denied", str(blocked))

        def failing_walk(
            directory: Path,
            *,
            onerror: object,
            followlinks: bool,
        ) -> list[object]:
            self.assertEqual(directory, self.work)
            self.assertFalse(followlinks)
            assert callable(onerror)
            onerror(scan_error)
            return []

        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            mock.patch("os.walk", side_effect=failing_walk),
            mock.patch.object(sys, "argv", [str(SCRIPT), str(self.work)]),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            returncode = VIDEO_RESOLUTIONS.main()

        self.assertNotEqual(returncode, 0)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("could not scan directory", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())
        self.assertEqual(self.calls(), [])

    def test_rejects_ascending_without_resolution_sorting(self) -> None:
        result = self.run_cli("--ascending", cwd=self.work)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--ascending requires --sort-resolution", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_reports_missing_ffprobe_without_a_traceback(self) -> None:
        self.create_video("candidate.mp4")

        env = os.environ.copy()
        env["PATH"] = ""
        env["FAKE_FFPROBE_LOG"] = str(self.log)
        env["FAKE_FFPROBE_DIMENSIONS"] = json.dumps(self.dimensions)
        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(self.work)],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ffprobe was not found on PATH", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_warns_for_bad_probes_and_prints_only_valid_rows(self) -> None:
        failures: dict[str, tuple[object, object] | str] = {
            "command-failure.mp4": "fail",
            "empty-streams.mp4": "empty",
            "malformed-json.mp4": "malformed",
            "string-width.mp4": ("1920", 1080),
            "zero-width.mp4": (0, 1080),
        }
        for relative_path, probe_result in failures.items():
            self.create_video(relative_path, probe_result)
        self.create_video("aaa-small-valid.mp4", (640, 360))
        self.create_video("valid.mp4", (1920, 1080))

        result = self.run_cli("--sort-resolution", str(self.work))

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(
            result.stdout,
            "Resolution  File\n"
            "----------  ----\n"
            "1920x1080   valid.mp4\n"
            "640x360     aaa-small-valid.mp4\n",
        )
        for relative_path in failures:
            self.assertIn(
                f"video-resolutions: warning: {relative_path}:", result.stderr
            )
        self.assertIn("simulated probe failure", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_failed_only_candidate_prints_no_table(self) -> None:
        self.create_video("nested/broken.mp4", "fail")

        result = self.run_cli(str(self.work))

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn(
            "video-resolutions: warning: nested/broken.mp4:", result.stderr
        )
        self.assertNotIn("Traceback", result.stderr)

    def test_invalid_probe_bytes_warn_and_do_not_stop_valid_results(self) -> None:
        invalid = self.create_video("a-invalid.mp4", "invalid-bytes")
        valid = self.create_video("z-valid.mp4", (1280, 720))

        result = self.run_cli(str(self.work))

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(
            result.stdout,
            "Resolution  File\n"
            "----------  ----\n"
            "1280x720    z-valid.mp4\n",
        )
        self.assertIn(
            "video-resolutions: warning: a-invalid.mp4:", result.stderr
        )
        self.assertNotIn("Traceback", result.stderr)
        self.assert_probed(str(invalid), str(valid))


if __name__ == "__main__":
    unittest.main()
