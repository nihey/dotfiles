# Video Resolutions CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a portable `video-resolutions` command that discovers videos, displays first-stream dimensions, and optionally sorts results by pixel area.

**Architecture:** A standard-library Python executable in `bin/` discovers files by a fixed extension allowlist and invokes one `ffprobe` JSON query per candidate. Subprocess tests supply a deterministic fake `ffprobe`, exercising the public command, table output, ordering, and failure behavior without real media.

**Tech Stack:** Python 3 standard library, `unittest`, `ffprobe`, existing dotfiles installer and Fish documentation.

---

## File Structure

- Create `bin/video-resolutions`: Own CLI parsing, video discovery, probing,
  sorting, table formatting, and user-facing errors.
- Create `tests/test_video_resolutions.py`: Exercise the executable as a
  subprocess with temporary directory trees and a fake `ffprobe`.
- Modify `fish/README.md`: Document recursion, resolution sorting, supported
  extensions, and partial failures.
- Modify `fish/conf.d/cheats.fish`: Add the portable command to `cheats`.

### Task 1: Video Discovery, Probing, and Table Output

**Files:**
- Create: `tests/test_video_resolutions.py`
- Create: `bin/video-resolutions`

- [ ] **Step 1: Write failing discovery and output tests**

Create `tests/test_video_resolutions.py`:

```python
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
EXTENSIONS = (
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
        self.work = self.root / "videos"
        self.work.mkdir()
        self.fake_bin = self.root / "bin"
        self.fake_bin.mkdir()
        self.log = self.root / "ffprobe.jsonl"
        self.probe_data: dict[str, list[object] | str] = {}
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

path = Path(sys.argv[-1])
value = json.loads(os.environ["FAKE_FFPROBE_DATA"]).get(path.name, [640, 480])
if value == "fail":
    print("simulated probe failure", file=sys.stderr)
    raise SystemExit(7)
if value == "malformed":
    print("{{not-json")
elif value == "empty":
    print(json.dumps({{"streams": []}}))
else:
    print(json.dumps({{"streams": [{{"width": value[0], "height": value[1]}}]}}))
"""
        )
        fake.chmod(0o755)

    def add_video(
        self,
        relative: str,
        probe_result: list[object] | str,
    ) -> Path:
        path = self.work / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fake video")
        self.probe_data[path.name] = probe_result
        return path

    def run_cli(
        self,
        *args: str,
        cwd: Path | None = None,
        env_changes: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PATH"] = f"{self.fake_bin}{os.pathsep}{env.get('PATH', '')}"
        env["FAKE_FFPROBE_LOG"] = str(self.log)
        env["FAKE_FFPROBE_DATA"] = json.dumps(self.probe_data)
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

    @staticmethod
    def result_files(stdout: str) -> list[str]:
        lines = stdout.splitlines()
        if not lines or lines == ["No videos found."]:
            return []
        return [line.split(maxsplit=1)[1] for line in lines[2:]]

    @staticmethod
    def result_resolutions(stdout: str) -> list[str]:
        lines = stdout.splitlines()
        if not lines or lines == ["No videos found."]:
            return []
        return [line.split(maxsplit=1)[0] for line in lines[2:]]

    def test_recursively_lists_videos_alphabetically_in_an_aligned_table(self) -> None:
        nested = self.add_video("nested/Á video.MoV", [1920, 1080])
        top = self.add_video("Z clip.MP4", [1280, 720])
        (self.work / "notes.txt").write_text("not a video")

        result = self.run_cli(str(self.work))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.splitlines(),
            [
                "Resolution  File",
                "----------  ----",
                "1920x1080   nested/Á video.MoV",
                "1280x720    Z clip.MP4",
            ],
        )
        expected_prefix = [
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "json",
        ]
        self.assertEqual(
            self.calls(),
            [expected_prefix + [str(nested)], expected_prefix + [str(top)]],
        )

    def test_defaults_to_current_directory(self) -> None:
        self.add_video("current.webm", [854, 480])

        result = self.run_cli(cwd=self.work)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.result_files(result.stdout), ["current.webm"])
        self.assertEqual(self.result_resolutions(result.stdout), ["854x480"])

    def test_no_recursive_excludes_nested_and_unrelated_files(self) -> None:
        self.add_video("top.mov", [1280, 720])
        self.add_video("nested/hidden.mp4", [1920, 1080])
        (self.work / "fake.mp4.txt").write_text("not a video")

        result = self.run_cli(str(self.work), "--no-recursive")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.result_files(result.stdout), ["top.mov"])
        self.assertEqual(len(self.calls()), 1)

    def test_supports_documented_extensions_case_insensitively(self) -> None:
        for position, extension in enumerate(EXTENSIONS):
            self.add_video(
                f"video-{position:02d}{extension.upper()}",
                [640 + position, 480],
            )

        result = self.run_cli(str(self.work), "--no-recursive")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.result_files(result.stdout)), len(EXTENSIONS))
        self.assertEqual(len(self.calls()), len(EXTENSIONS))

    def test_empty_directory_reports_no_videos(self) -> None:
        empty = self.root / "empty"
        empty.mkdir()

        result = self.run_cli(str(empty))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "No videos found.\n")
        self.assertEqual(self.calls(), [])

    def test_help_prints_usage_without_probing(self) -> None:
        result = self.run_cli("--help")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("video-resolutions", result.stdout)
        self.assertIn("--sort-resolution", result.stdout)
        self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests and verify the RED state**

Run:

```bash
python3 -m unittest tests.test_video_resolutions -v
```

Expected: 6 tests FAIL because `bin/video-resolutions` does not exist.

- [ ] **Step 3: Implement discovery, probing, and table output**

Create `bin/video-resolutions`:

```python
#!/usr/bin/env python3
"""List video files and their first video stream's resolution."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


VIDEO_EXTENSIONS = frozenset(
    {
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
    }
)


@dataclass(frozen=True)
class VideoInfo:
    relative_path: str
    width: int
    height: int

    @property
    def resolution(self) -> str:
        return f"{self.width}x{self.height}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="video-resolutions",
        description="List video files and their resolutions.",
    )
    parser.add_argument(
        "directory",
        nargs="?",
        type=Path,
        default=Path("."),
        help="directory to scan (default: current directory)",
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="scan only the selected directory",
    )
    parser.add_argument(
        "--sort-resolution",
        action="store_true",
        help="sort by pixel area, largest first",
    )
    return parser


def discover_videos(directory: Path, recursive: bool) -> list[Path]:
    iterator = directory.rglob("*") if recursive else directory.iterdir()
    candidates = (
        path
        for path in iterator
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
    )
    return sorted(
        candidates,
        key=lambda path: (
            str(path.relative_to(directory)).casefold(),
            str(path.relative_to(directory)),
        ),
    )


def probe_video(ffprobe: str, path: Path, directory: Path) -> VideoInfo:
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "json",
            str(path),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    data = json.loads(result.stdout)
    stream = data["streams"][0]
    return VideoInfo(
        relative_path=str(path.relative_to(directory)),
        width=stream["width"],
        height=stream["height"],
    )


def print_table(videos: list[VideoInfo]) -> None:
    resolution_width = max(
        len("Resolution"),
        *(len(video.resolution) for video in videos),
    )
    print(f"{'Resolution':<{resolution_width}}  File")
    print(f"{'-' * resolution_width}  ----")
    for video in videos:
        print(f"{video.resolution:<{resolution_width}}  {video.relative_path}")


def main() -> int:
    args = build_parser().parse_args()
    directory = args.directory.expanduser().resolve()
    ffprobe = shutil.which("ffprobe")
    candidates = discover_videos(directory, recursive=not args.no_recursive)
    if not candidates:
        print("No videos found.")
        return 0
    videos = [probe_video(ffprobe, path, directory) for path in candidates]
    print_table(videos)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Make it executable:

```bash
chmod +x bin/video-resolutions
```

- [ ] **Step 4: Run focused tests and verify the GREEN state**

Run:

```bash
python3 -m unittest tests.test_video_resolutions -v
```

Expected: 6 tests PASS. The table assertion proves alignment and relative
paths; the fake log proves that only supported candidates are probed with the
specified first-stream query.

- [ ] **Step 5: Commit the discovery slice**

Audit the staged diff for secrets, then commit:

```bash
git add bin/video-resolutions tests/test_video_resolutions.py
git diff --staged --check
git diff --staged
git commit -m "feat: add video resolution listing command"
```

### Task 2: Resolution Sorting

**Files:**
- Modify: `tests/test_video_resolutions.py`
- Modify: `bin/video-resolutions`

- [ ] **Step 1: Add failing descending and ascending sorting tests**

Add these methods to `VideoResolutionsTest` before its `if __name__` block:

```python
    def test_sorts_resolution_descending_with_deterministic_ties(self) -> None:
        self.add_video("z-wide.mp4", [1920, 1080])
        self.add_video("a-wide.mp4", [1920, 1080])
        self.add_video("portrait.mp4", [1080, 1920])
        self.add_video("small.mp4", [1280, 720])

        result = self.run_cli(str(self.work), "--sort-resolution")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.result_files(result.stdout),
            ["a-wide.mp4", "z-wide.mp4", "portrait.mp4", "small.mp4"],
        )
        self.assertEqual(
            self.result_resolutions(result.stdout),
            ["1920x1080", "1920x1080", "1080x1920", "1280x720"],
        )

    def test_sorts_resolution_ascending(self) -> None:
        self.add_video("z-wide.mp4", [1920, 1080])
        self.add_video("a-wide.mp4", [1920, 1080])
        self.add_video("portrait.mp4", [1080, 1920])
        self.add_video("small.mp4", [1280, 720])

        result = self.run_cli(
            str(self.work), "--sort-resolution", "--ascending"
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.result_files(result.stdout),
            ["small.mp4", "portrait.mp4", "a-wide.mp4", "z-wide.mp4"],
        )
        self.assertEqual(
            self.result_resolutions(result.stdout),
            ["1280x720", "1080x1920", "1920x1080", "1920x1080"],
        )
```

- [ ] **Step 2: Run focused tests and verify the RED state**

Run:

```bash
python3 -m unittest tests.test_video_resolutions -v
```

Expected: the original 6 tests pass; the descending test FAILS because output
remains path-sorted, and the ascending test FAILS because `--ascending` is not
recognized.

- [ ] **Step 3: Add sorting arguments and deterministic sort keys**

In `build_parser()`, insert after the `--sort-resolution` argument:

```python
    parser.add_argument(
        "--ascending",
        action="store_true",
        help="sort resolution from smallest to largest",
    )
```

Add this function immediately before `print_table()`:

```python
def sort_by_resolution(
    videos: list[VideoInfo],
    ascending: bool,
) -> list[VideoInfo]:
    if ascending:
        return sorted(
            videos,
            key=lambda video: (
                video.width * video.height,
                video.width,
                video.height,
                video.relative_path.casefold(),
                video.relative_path,
            ),
        )
    return sorted(
        videos,
        key=lambda video: (
            -(video.width * video.height),
            -video.width,
            -video.height,
            video.relative_path.casefold(),
            video.relative_path,
        ),
    )
```

Replace the final two lines before `return 0` in `main()`:

```python
    videos = [probe_video(ffprobe, path, directory) for path in candidates]
    if args.sort_resolution:
        videos = sort_by_resolution(videos, ascending=args.ascending)
    print_table(videos)
    return 0
```

- [ ] **Step 4: Run focused tests and verify the GREEN state**

Run:

```bash
python3 -m unittest tests.test_video_resolutions -v
```

Expected: 8 tests PASS, including area ordering, width/height tie breaking,
and path ordering for identical resolutions.

- [ ] **Step 5: Commit sorting behavior**

Audit the staged diff for secrets, then commit:

```bash
git add bin/video-resolutions tests/test_video_resolutions.py
git diff --staged --check
git diff --staged
git commit -m "feat: sort videos by resolution"
```

### Task 3: Validation and Partial Probe Failures

**Files:**
- Modify: `tests/test_video_resolutions.py`
- Modify: `bin/video-resolutions`

- [ ] **Step 1: Add failing validation and partial-result tests**

Add these methods to `VideoResolutionsTest` before its `if __name__` block:

```python
    def test_rejects_missing_or_non_directory_paths(self) -> None:
        missing = self.root / "missing"
        regular_file = self.root / "file.txt"
        regular_file.write_text("not a directory")

        for path in (missing, regular_file):
            with self.subTest(path=path):
                result = self.run_cli(str(path))
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("path is not a directory", result.stderr)
                self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_rejects_ascending_without_resolution_sort(self) -> None:
        result = self.run_cli(str(self.work), "--ascending")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--ascending requires --sort-resolution", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_reports_missing_ffprobe_without_a_traceback(self) -> None:
        self.add_video("clip.mp4", [1920, 1080])

        result = self.run_cli(
            str(self.work),
            env_changes={"PATH": ""},
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ffprobe was not found on PATH", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_keeps_valid_results_and_warns_for_every_probe_problem(self) -> None:
        self.add_video("valid.mp4", [1920, 1080])
        self.add_video("command-failure.mp4", "fail")
        self.add_video("missing-stream.mp4", "empty")
        self.add_video("malformed.mp4", "malformed")
        self.add_video("zero-width.mp4", [0, 1080])
        self.add_video("string-width.mp4", ["1920", 1080])

        result = self.run_cli(str(self.work))

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.result_files(result.stdout), ["valid.mp4"])
        self.assertEqual(self.result_resolutions(result.stdout), ["1920x1080"])
        for name in (
            "command-failure.mp4",
            "missing-stream.mp4",
            "malformed.mp4",
            "zero-width.mp4",
            "string-width.mp4",
        ):
            self.assertIn(f"warning: {name}:", result.stderr)
        self.assertIn("simulated probe failure", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_prints_no_table_when_all_candidates_fail(self) -> None:
        self.add_video("broken.mp4", "fail")

        result = self.run_cli(str(self.work))

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("warning: broken.mp4:", result.stderr)
```

- [ ] **Step 2: Run focused tests and verify the RED state**

Run:

```bash
python3 -m unittest tests.test_video_resolutions -v
```

Expected: the 8 existing tests remain green and the 5 new tests FAIL because
the initial implementation does not preflight inputs or isolate probe errors.

- [ ] **Step 3: Implement final validation and warning behavior**

Replace `bin/video-resolutions` with this complete implementation:

```python
#!/usr/bin/env python3
"""List video files and their first video stream's resolution."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


VIDEO_EXTENSIONS = frozenset(
    {
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
    }
)


class ProbeError(Exception):
    """An expected failure while reading one video's dimensions."""


@dataclass(frozen=True)
class VideoInfo:
    relative_path: str
    width: int
    height: int

    @property
    def resolution(self) -> str:
        return f"{self.width}x{self.height}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="video-resolutions",
        description="List video files and their resolutions.",
    )
    parser.add_argument(
        "directory",
        nargs="?",
        type=Path,
        default=Path("."),
        help="directory to scan (default: current directory)",
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="scan only the selected directory",
    )
    parser.add_argument(
        "--sort-resolution",
        action="store_true",
        help="sort by pixel area, largest first",
    )
    parser.add_argument(
        "--ascending",
        action="store_true",
        help="sort resolution from smallest to largest",
    )
    return parser


def discover_videos(directory: Path, recursive: bool) -> list[Path]:
    iterator = directory.rglob("*") if recursive else directory.iterdir()
    candidates = (
        path
        for path in iterator
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
    )
    return sorted(
        candidates,
        key=lambda path: (
            str(path.relative_to(directory)).casefold(),
            str(path.relative_to(directory)),
        ),
    )


def probe_video(ffprobe: str, path: Path, directory: Path) -> VideoInfo:
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height",
                "-of",
                "json",
                str(path),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise ProbeError(f"could not run ffprobe: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip()
        raise ProbeError(detail or f"ffprobe exited with status {result.returncode}")
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ProbeError("ffprobe returned malformed JSON") from exc
    streams = data.get("streams")
    if not isinstance(streams, list) or not streams:
        raise ProbeError("ffprobe returned no video stream")
    stream = streams[0]
    if not isinstance(stream, dict):
        raise ProbeError("ffprobe returned an invalid video stream")
    width = stream.get("width")
    height = stream.get("height")
    if (
        not isinstance(width, int)
        or isinstance(width, bool)
        or width <= 0
        or not isinstance(height, int)
        or isinstance(height, bool)
        or height <= 0
    ):
        raise ProbeError("ffprobe returned invalid dimensions")
    return VideoInfo(
        relative_path=str(path.relative_to(directory)),
        width=width,
        height=height,
    )


def sort_by_resolution(
    videos: list[VideoInfo],
    ascending: bool,
) -> list[VideoInfo]:
    if ascending:
        return sorted(
            videos,
            key=lambda video: (
                video.width * video.height,
                video.width,
                video.height,
                video.relative_path.casefold(),
                video.relative_path,
            ),
        )
    return sorted(
        videos,
        key=lambda video: (
            -(video.width * video.height),
            -video.width,
            -video.height,
            video.relative_path.casefold(),
            video.relative_path,
        ),
    )


def print_table(videos: list[VideoInfo]) -> None:
    resolution_width = max(
        len("Resolution"),
        *(len(video.resolution) for video in videos),
    )
    print(f"{'Resolution':<{resolution_width}}  File")
    print(f"{'-' * resolution_width}  ----")
    for video in videos:
        print(f"{video.resolution:<{resolution_width}}  {video.relative_path}")


def error(message: str) -> int:
    print(f"video-resolutions: {message}", file=sys.stderr)
    return 1


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.ascending and not args.sort_resolution:
        parser.error("--ascending requires --sort-resolution")

    directory = args.directory.expanduser().resolve()
    if not directory.is_dir():
        return error(f"path is not a directory: {directory}")

    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        return error("ffprobe was not found on PATH")

    try:
        candidates = discover_videos(directory, recursive=not args.no_recursive)
    except OSError as exc:
        return error(f"could not scan directory {directory}: {exc}")
    if not candidates:
        print("No videos found.")
        return 0

    videos: list[VideoInfo] = []
    had_probe_error = False
    for path in candidates:
        try:
            videos.append(probe_video(ffprobe, path, directory))
        except ProbeError as exc:
            relative_path = path.relative_to(directory)
            print(
                f"video-resolutions: warning: {relative_path}: {exc}",
                file=sys.stderr,
            )
            had_probe_error = True

    if args.sort_resolution:
        videos = sort_by_resolution(videos, ascending=args.ascending)
    if videos:
        print_table(videos)
    return 1 if had_probe_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run focused tests and verify the GREEN state**

Run:

```bash
python3 -m unittest tests.test_video_resolutions -v
```

Expected: 13 tests PASS. Expected failures have concise stderr, valid rows
survive neighboring probe failures, and an all-failed candidate set prints no
table.

- [ ] **Step 5: Commit validation behavior**

Audit the staged diff for secrets, then commit:

```bash
git add bin/video-resolutions tests/test_video_resolutions.py
git diff --staged --check
git diff --staged
git commit -m "feat: handle video probe failures"
```

### Task 4: Documentation and Final Verification

**Files:**
- Modify: `fish/README.md`
- Modify: `fish/conf.d/cheats.fish`

- [ ] **Step 1: Add the executable to the layout summary**

In the `## Layout` list in `fish/README.md`, add after the
`../bin/extract-frames` entry:

```markdown
- `../bin/video-resolutions` — portable `ffprobe` wrapper that lists video
  dimensions and optionally sorts by resolution.
```

- [ ] **Step 2: Add usage documentation**

In `fish/README.md`, after the `## Extract video frames` section and before
`## Install`, add:

````markdown
## List video resolutions

`video-resolutions` recursively lists supported videos and their first video
stream's dimensions. The directory defaults to the current directory:

```sh
video-resolutions
video-resolutions ~/Videos
```

Use `--no-recursive` for only the selected directory. Results are
alphabetical unless resolution sorting is requested:

```sh
video-resolutions ~/Videos --no-recursive
video-resolutions ~/Videos --sort-resolution
video-resolutions ~/Videos --sort-resolution --ascending
```

Resolution sorting uses total pixel area and defaults to largest first. The
command recognizes `.3gp`, `.avi`, `.flv`, `.m2ts`, `.m4v`, `.mkv`, `.mov`,
`.mp4`, `.mpeg`, `.mpg`, `.mts`, `.ts`, `.webm`, and `.wmv`, regardless of
extension letter case. Files that cannot be probed are warned about while
valid results are retained; any such warning makes the command exit nonzero.
The command requires `python3` and `ffprobe` on `PATH`.
````

- [ ] **Step 3: Add the command to `cheats`**

In the `Filesystem & misc` section of `fish/conf.d/cheats.fish`, add after
`extract-frames`:

```fish
    __cheats_row "video-resolutions [dir]" "list video dimensions; --sort-resolution [--ascending]"
```

- [ ] **Step 4: Run full verification**

Run:

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 -m py_compile bin/extract-frames bin/video-resolutions
./bin/video-resolutions --help
git diff --check
```

Expected:

- All 33 Python tests pass: 10 git-cleanup tests, 10 frame-extraction tests,
  and 13 video-resolution tests.
- Both portable executables compile successfully.
- Help output includes the directory argument, `--no-recursive`,
  `--sort-resolution`, and `--ascending`.
- `git diff --check` prints nothing.

- [ ] **Step 5: Commit documentation**

Audit the staged diff for secrets, then commit:

```bash
git add fish/README.md fish/conf.d/cheats.fish
git diff --staged --check
git diff --staged
git commit -m "docs: document video resolution command"
```

- [ ] **Step 6: Verify the committed branch**

Run:

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
git status --short
git log --oneline -6
```

Expected: all 33 tests pass, `git status --short` is empty, and recent history
contains the design, plan, discovery, sorting, probe-failure, and documentation
commits.
