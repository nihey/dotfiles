# Extract Frames CLI Design

## Goal

Add a portable command that extracts one video frame for each requested
timestamp by invoking `ffmpeg`. The command must work from Bash, Fish, Zsh,
and scripts after the repository installer links it into `~/.local/bin`.

## Command Interface

The executable is named `extract-frames` and supports these forms:

```sh
extract-frames video.mp4 00:01 00:05.500 01:20
extract-frames video.mp4 10 25.5 --output ./selected-frames
```

The first positional argument is the input video. Every remaining positional
argument is a timestamp. `--output DIR` and `-o DIR` select the output
directory and may appear before or after timestamps.

At least one timestamp is required. Timestamps may use non-negative seconds,
with an optional decimal fraction, or colon-separated `MM:SS` and
`HH:MM:SS` forms. Minutes and seconds in colon-separated timestamps must be
less than 60. Hours may exceed two digits.

`--help` prints usage and exits successfully.

## Output

When no output directory is supplied, files are written directly into the
current directory. An explicitly supplied output directory is created,
including missing parent directories.

Frames use lossless PNG. Each filename contains the input video's basename,
the timestamp's one-based argument position, and a filesystem-safe timestamp:

```text
video-frame-001-00-01.png
video-frame-002-00-05.500.png
```

The ordinal prevents duplicate timestamp arguments from overwriting each
other. An existing destination file is replaced so rerunning the same command
has deterministic results.

## Implementation

`bin/extract-frames` is a Python 3 executable. It uses only the standard
library and delegates media decoding to the `ffmpeg` executable found on
`PATH`.

The command validates all arguments before creating directories or invoking
`ffmpeg`. It then runs one `ffmpeg` process per timestamp. Each invocation
seeks to the requested timestamp, reads the input video, emits exactly one PNG
frame, suppresses routine banner output, and permits replacement of the
deterministic destination path.

One process per timestamp favors simple behavior and useful per-frame errors
over a more opaque filter graph. This command is intended for selecting a
small number of frames, so process startup overhead is acceptable.

## Errors and Partial Results

The command exits nonzero with a concise message when:

- Python cannot find `ffmpeg` on `PATH`.
- The input path does not identify a file.
- No timestamps are supplied.
- A timestamp has an invalid or negative form.
- The output directory cannot be created.
- `ffmpeg` fails to extract a frame.

If `ffmpeg` fails after earlier frames were written, those earlier files are
left in place and the command stops immediately. The error identifies the
timestamp that failed. The command does not delete user files during error
handling.

## Installation and Documentation

The existing `install.sh` behavior already links executable files from
`bin/` into `~/.local/bin`, so no installer logic change is required.

`fish/README.md` will document the command and examples.
`fish/conf.d/cheats.fish` will list it under filesystem and miscellaneous
utilities even though the executable itself is shell-independent.

## Testing

Tests will execute the CLI as a subprocess with a temporary fake `ffmpeg` on
`PATH`. They will cover:

- Multiple timestamps and deterministic output filenames.
- Default output in the current directory.
- Creation of an explicitly selected nested output directory.
- Duplicate timestamps producing separate files.
- Options placed before or after timestamps.
- Help output.
- Missing input, missing timestamps, invalid timestamps, missing `ffmpeg`,
  and an `ffmpeg` failure.

The tests will assert the constructed `ffmpeg` arguments without requiring a
real video codec installation.
