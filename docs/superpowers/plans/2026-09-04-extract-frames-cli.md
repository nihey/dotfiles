# Extract Frames CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a portable `extract-frames` command that writes one lossless PNG per requested video timestamp.

**Architecture:** A standard-library Python executable in `bin/` parses and validates the CLI, then invokes one `ffmpeg` process per timestamp. Subprocess tests place a deterministic fake `ffmpeg` on `PATH`, exercising the public command without requiring codecs or a real video.

**Tech Stack:** Python 3 standard library, `unittest`, `ffmpeg`, existing dotfiles installer and Fish documentation.

---

## File Structure

- Create `bin/extract-frames`: Own argument parsing, timestamp validation,
  output naming, directory creation, `ffmpeg` invocation, and user-facing
  errors.
- Create `tests/test_extract_frames.py`: Exercise the executable as a
  subprocess with a fake `ffmpeg` and temporary files.
- Modify `fish/README.md`: Document installation, usage, output behavior, and
  examples for the portable command.
- Modify `fish/conf.d/cheats.fish`: Add the command to the generated custom
  command cheatsheet.

### Task 1: Happy-Path CLI and Deterministic Output

**Files:**
- Create: `tests/test_extract_frames.py`
- Create: `bin/extract-frames`

- [ ] **Step 1: Write the failing subprocess tests**

Create `tests/test_extract_frames.py` with the following content:

```python
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
        result_after = self.run_cli(
            str(self.video), "3", "-o", str(after)
        )
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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests and verify the RED state**

Run:

```bash
python3 -m unittest tests.test_extract_frames -v
```

Expected: FAIL because `bin/extract-frames` does not exist, so the happy-path
subprocesses cannot create their expected PNG files.

- [ ] **Step 3: Implement the minimal happy path**

Create `bin/extract-frames` with this content:

```python
#!/usr/bin/env python3
"""Extract PNG frames from a video at one or more timestamps."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="extract-frames",
        description="Extract one PNG video frame at each timestamp.",
    )
    parser.add_argument("video", help="input video file")
    parser.add_argument(
        "timestamps",
        nargs="+",
        metavar="timestamp",
        help="seconds, MM:SS, or HH:MM:SS (fractions allowed)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="output directory (default: current directory)",
    )
    return parser


def frame_name(video: Path, position: int, timestamp: str) -> str:
    safe_timestamp = timestamp.replace(":", "-")
    return f"{video.stem}-frame-{position:03d}-{safe_timestamp}.png"


def main() -> int:
    args = build_parser().parse_args()
    video = Path(args.video).expanduser()
    output_dir = (args.output or Path.cwd()).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    for position, timestamp in enumerate(args.timestamps, start=1):
        destination = output_dir / frame_name(video, position, timestamp)
        result = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                timestamp,
                "-i",
                str(video),
                "-frames:v",
                "1",
                str(destination),
            ],
            check=False,
        )
        if result.returncode != 0:
            return result.returncode
        print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Make it executable:

```bash
chmod +x bin/extract-frames
```

- [ ] **Step 4: Run the tests and verify the GREEN state**

Run:

```bash
python3 -m unittest tests.test_extract_frames -v
```

Expected: 4 tests PASS. The fake log proves each timestamp produces a
separate `ffmpeg` invocation with `-frames:v 1`, and the output assertions
prove directory and filename behavior.

- [ ] **Step 5: Commit the happy path**

Audit the staged diff for secrets, then commit:

```bash
git add bin/extract-frames tests/test_extract_frames.py
git diff --staged --check
git diff --staged
git commit -m "feat: add portable frame extraction command"
```

### Task 2: Validation and Concise Failure Handling

**Files:**
- Modify: `tests/test_extract_frames.py`
- Modify: `bin/extract-frames`

- [ ] **Step 1: Add failing validation and failure-path tests**

Add these methods to `ExtractFramesTest` in
`tests/test_extract_frames.py`, before the `if __name__` block:

```python
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
```

- [ ] **Step 2: Run the tests and verify the RED state**

Run:

```bash
python3 -m unittest tests.test_extract_frames -v
```

Expected: the four happy-path tests remain green and the six new tests FAIL
because the initial CLI has no complete preflight validation or contextual
error reporting.

- [ ] **Step 3: Implement validation and error handling**

Replace `bin/extract-frames` with this complete implementation:

```python
#!/usr/bin/env python3
"""Extract PNG frames from a video at one or more timestamps."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path


SECONDS_RE = re.compile(r"^\d+(?:\.\d+)?$")
INTEGER_RE = re.compile(r"^\d+$")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="extract-frames",
        description="Extract one PNG video frame at each timestamp.",
    )
    parser.add_argument("video", help="input video file")
    parser.add_argument(
        "timestamps",
        nargs="*",
        metavar="timestamp",
        help="seconds, MM:SS, or HH:MM:SS (fractions allowed)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="output directory (default: current directory)",
    )
    return parser


def valid_timestamp(value: str) -> bool:
    parts = value.split(":")
    if len(parts) == 1:
        return SECONDS_RE.fullmatch(parts[0]) is not None
    if len(parts) not in (2, 3):
        return False
    if any(INTEGER_RE.fullmatch(part) is None for part in parts[:-1]):
        return False
    if SECONDS_RE.fullmatch(parts[-1]) is None:
        return False
    if int(parts[-2]) >= 60 or float(parts[-1]) >= 60:
        return False
    return True


def frame_name(video: Path, position: int, timestamp: str) -> str:
    safe_timestamp = timestamp.replace(":", "-")
    return f"{video.stem}-frame-{position:03d}-{safe_timestamp}.png"


def error(message: str) -> int:
    print(f"extract-frames: {message}", file=sys.stderr)
    return 1


def main() -> int:
    args = build_parser().parse_args()
    video = Path(args.video).expanduser()

    if not video.is_file():
        return error(f"input video is not a file: {video}")
    if not args.timestamps:
        return error("at least one timestamp is required")
    for timestamp in args.timestamps:
        if not valid_timestamp(timestamp):
            return error(f"invalid timestamp: {timestamp}")

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return error("ffmpeg was not found on PATH")

    output_dir = (args.output or Path.cwd()).expanduser()
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return error(f"cannot create output directory {output_dir}: {exc}")

    for position, timestamp in enumerate(args.timestamps, start=1):
        destination = output_dir / frame_name(video, position, timestamp)
        try:
            result = subprocess.run(
                [
                    ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-ss",
                    timestamp,
                    "-i",
                    str(video),
                    "-frames:v",
                    "1",
                    str(destination),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
        except OSError as exc:
            return error(f"could not run ffmpeg at timestamp {timestamp}: {exc}")
        if result.returncode != 0:
            detail = result.stderr.strip()
            suffix = f": {detail}" if detail else ""
            return error(f"ffmpeg failed at timestamp {timestamp}{suffix}")
        print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run focused tests and verify the GREEN state**

Run:

```bash
python3 -m unittest tests.test_extract_frames -v
```

Expected: 10 tests PASS. No traceback is printed by the tested error paths,
invalid requests do not create their requested output directory, and the
failure test performs exactly two of its three planned invocations.

- [ ] **Step 5: Commit validation behavior**

Audit the staged diff for secrets, then commit:

```bash
git add bin/extract-frames tests/test_extract_frames.py
git diff --staged --check
git diff --staged
git commit -m "feat: validate frame extraction arguments"
```

### Task 3: User Documentation and Final Verification

**Files:**
- Modify: `fish/README.md`
- Modify: `fish/conf.d/cheats.fish`

- [ ] **Step 1: Document the executable in the layout summary**

In the `## Layout` list in `fish/README.md`, add this bullet after the
`anaconda.fish` entry:

```markdown
- `../bin/extract-frames` — portable `ffmpeg` wrapper that extracts one PNG
  frame per requested timestamp.
```

- [ ] **Step 2: Add usage and behavior documentation**

In `fish/README.md`, immediately before `## Install`, add:

````markdown
## Extract video frames

`extract-frames` accepts a video followed by one or more timestamps. Without
an output option it writes lossless PNG files into the current directory:

```sh
extract-frames video.mp4 00:01 00:05.500 01:20
```

Use `-o` or `--output` to select a directory. Missing directories are created:

```sh
extract-frames video.mp4 10 25.5 --output ./selected-frames
```

Output names include the video stem, timestamp position, and timestamp, such
as `video-frame-001-00-01.png`. The command requires `python3` and `ffmpeg` on
`PATH`.
````

- [ ] **Step 3: Add the command to `cheats`**

In the `Filesystem & misc` section of `fish/conf.d/cheats.fish`, add this row
after `dytv`:

```fish
    __cheats_row "extract-frames <video>" "PNG frames at timestamps; -o selects/creates output dir"
```

- [ ] **Step 4: Run all verification commands**

Run:

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 -m py_compile bin/extract-frames
./bin/extract-frames --help
git diff --check
```

Expected:

- The full Python test suite passes, including all 10 extraction tests and
  the existing git cleanup tests.
- Python compilation exits successfully.
- Help output names `extract-frames`, its positional timestamps, and
  `--output`.
- `git diff --check` prints nothing.

- [ ] **Step 5: Commit documentation**

Audit the staged diff for secrets, then commit:

```bash
git add fish/README.md fish/conf.d/cheats.fish
git diff --staged --check
git diff --staged
git commit -m "docs: document frame extraction command"
```

- [ ] **Step 6: Verify the completed branch is clean and reproducible**

Run:

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
git status --short
git log --oneline -4
```

Expected: all tests pass, `git status --short` is empty, and the log shows the
design, plan, feature, validation-test, and documentation commits among the
most recent history (the design commit may be just outside the final four).
