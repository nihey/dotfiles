#!/usr/bin/env python3
"""Subprocess tests for bin/video-resolutions."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "video-resolutions"
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
        self.dimensions: dict[str, list[int]] = {}
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
width, height = dimensions[str(Path(sys.argv[-1]).resolve())]
print(json.dumps({{"streams": [{{"width": width, "height": height}}]}}))
"""
        )
        fake.chmod(0o755)

    def create_video(
        self,
        relative_path: str,
        dimensions: tuple[int, int] = (1920, 1080),
    ) -> Path:
        video = self.work / relative_path
        video.parent.mkdir(parents=True, exist_ok=True)
        video.write_bytes(b"not a real video")
        self.dimensions[str(video.resolve())] = list(dimensions)
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


if __name__ == "__main__":
    unittest.main()
