# Video Resolutions CLI Design

## Goal

Add a portable command that finds videos within a directory, reads the first
video stream's dimensions with `ffprobe`, and displays each relative path with
its resolution. The command must work from Bash, Fish, Zsh, and scripts after
the repository installer links it into `~/.local/bin`.

## Command Interface

The executable is named `video-resolutions` and supports these forms:

```sh
video-resolutions
video-resolutions ~/Videos
video-resolutions ~/Videos --no-recursive
video-resolutions ~/Videos --sort-resolution
video-resolutions ~/Videos --sort-resolution --ascending
```

The optional positional argument selects the directory and defaults to the
current directory.

By default, the command recursively scans the selected directory.
`--no-recursive` restricts discovery to files immediately inside it.

By default, results are sorted alphabetically by relative path using a
case-insensitive comparison. `--sort-resolution` instead sorts by pixel area,
largest first. `--ascending` reverses resolution sorting to smallest first and
is rejected unless `--sort-resolution` is also present.

`--help` prints usage and exits successfully.

## Video Discovery

Discovery is extension-based and case-insensitive. The supported extensions
are:

```text
.3gp .avi .flv .m2ts .m4v .mkv .mov .mp4 .mpeg .mpg .mts .ts .webm .wmv
```

Only regular files and symlinks that resolve to regular files are candidates.
Recursive discovery does not intentionally follow directory symlinks, which
avoids filesystem loops. Extensionless files and files with unrelated
extensions are not probed.

## Probing

`bin/video-resolutions` is a Python 3 executable that uses only the standard
library. It locates `ffprobe` on `PATH` once, then runs one process per video:

```sh
ffprobe -v error -select_streams v:0 \
  -show_entries stream=width,height -of json VIDEO
```

The first video stream must report positive integer `width` and `height`
values. These coded stream dimensions are displayed directly; rotation
metadata is not applied.

One process per file keeps failures attributable to a specific path and is
appropriate for a personal command-line utility. Parallel probing and caching
are outside this feature's scope.

## Output

Successful results are printed as an aligned, plain-text table:

```text
Resolution  File
----------  ----
3840x2160   source/interview.mov
1920x1080   exports/clip.mp4
```

Paths are relative to the selected directory. Spaces and Unicode characters
are preserved. Column widths expand to fit the results.

Resolution ordering uses `width * height` as the primary key. Descending ties
are resolved by width descending, height descending, then relative path
ascending. Ascending ties use width ascending, height ascending, then relative
path ascending.

When no candidate video files exist, the command prints `No videos found.`
and exits successfully. If candidates exist but none can be probed, it prints
no table and exits nonzero after issuing warnings.

## Errors and Partial Results

The command exits nonzero with a concise error when:

- Python cannot find `ffprobe` on `PATH`.
- The selected path does not identify a directory.
- `--ascending` is used without `--sort-resolution`.
- Directory traversal fails before results can be collected.

If an individual candidate cannot be probed, returns no video stream, emits
malformed JSON, or reports invalid dimensions, the command prints a warning
to stderr and continues with the remaining candidates. Valid videos are still
shown, but the final exit status is nonzero to signal incomplete results. Raw
`ffprobe` stderr may be included in the warning when present; Python
tracebacks are not exposed for expected failures.

The command is read-only and never modifies video files.

## Installation and Documentation

The existing `install.sh` behavior already links executables from `bin/` into
`~/.local/bin`, so no installer logic change is required.

`fish/README.md` will document usage, recursion, sorting, supported extensions,
and partial-failure behavior. `fish/conf.d/cheats.fish` will list the command
under filesystem and miscellaneous utilities even though the executable is
shell-independent.

## Testing

Tests will execute the CLI as a subprocess with a temporary fake `ffprobe` on
`PATH`. They will cover:

- Recursive discovery of supported extensions with mixed letter case.
- Default-directory and explicitly selected-directory behavior.
- Exclusion of unrelated extensions and nested files in non-recursive mode.
- Alphabetical default ordering.
- Descending and ascending resolution sorting, including deterministic ties.
- Aligned table output with spaces in paths.
- Help output.
- Empty directories.
- Missing directories, invalid option combinations, and missing `ffprobe`.
- Individual probe failures, missing streams, malformed JSON, and invalid
  dimensions while retaining valid results.

The tests will assert constructed `ffprobe` arguments and output without
requiring real media files or an installed codec suite.
