#!/usr/bin/env python3
"""Offline tests for bin/tldv-dl (no network)."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "tldv-dl"
SCRIPT_LOADER = importlib.machinery.SourceFileLoader("tldv_dl", str(SCRIPT))
SCRIPT_SPEC = importlib.util.spec_from_loader(SCRIPT_LOADER.name, SCRIPT_LOADER)
if SCRIPT_SPEC is None or SCRIPT_SPEC.loader is None:
    raise RuntimeError(f"could not load {SCRIPT}")
TLDV = importlib.util.module_from_spec(SCRIPT_SPEC)
sys.modules[SCRIPT_SPEC.name] = TLDV
SCRIPT_SPEC.loader.exec_module(TLDV)


def word(text, start, end, speaker="Ana"):
    ts = lambda s: {"seconds": str(int(s)), "nanos": int(round((s % 1) * 1e9))}
    return {"word": text, "startTime": ts(start), "endTime": ts(end), "speaker": speaker}


class TldvDlTest(unittest.TestCase):
    def test_meeting_id_from_url_and_bare_id(self):
        mid = "6ab3064e32651100137c93da"
        self.assertEqual(TLDV.meeting_id(f"https://tldv.io/app/meetings/{mid}/"), mid)
        self.assertEqual(TLDV.meeting_id(mid), mid)
        with self.assertRaises(SystemExit):
            TLDV.meeting_id("https://tldv.io/app/meetings/")

    def test_unshift_letters_only(self):
        self.assertEqual(TLDV.unshift("kpcvs_000001.ba", 8), "chunk_000001.ts")
        self.assertEqual(TLDV.unshift("F-Iuh-Libm", 8), "X-Amz-Date")

    def test_detect_shift_from_extension(self):
        self.assertEqual(TLDV.detect_shift("zi9O_kpcvs_000000.ba?F-Iuh=1"), 8)
        self.assertEqual(TLDV.detect_shift("abc_chunk_000000.ts"), 0)

    def test_safe_name_strips_path_characters(self):
        self.assertEqual(TLDV.safe_name('a/b: c?  "d"'), "a b c d")
        self.assertEqual(TLDV.safe_name(""), "tldv-meeting")

    def test_save_transcript_writes_srt_txt_json(self):
        data = [[word(" Olá", 1.5, 2.0), word(" mundo.", 2.0, 2.75)],
                [word(" Oi", 3661.0, 3661.25, "Bia")]]
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "meeting"
            TLDV.save_transcript(data, base)
            srt = Path(f"{base}.srt").read_text(encoding="utf-8")
            self.assertIn("1\n00:00:01,500 --> 00:00:02,750\nOlá mundo.\n", srt)
            self.assertIn("2\n01:01:01,000 --> 01:01:01,250\nOi\n", srt)
            txt = Path(f"{base}.txt").read_text(encoding="utf-8")
            self.assertIn("[00:00:01] Ana: Olá mundo.", txt)
            self.assertIn("[01:01:01] Bia: Oi", txt)
            self.assertTrue(Path(f"{base}.transcript.json").exists())

    def test_save_transcript_srt_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "meeting"
            TLDV.save_transcript([[word(" Oi", 0, 1)]], base, srt_only=True)
            self.assertTrue(Path(f"{base}.srt").exists())
            self.assertFalse(Path(f"{base}.txt").exists())

    def test_main_fails_when_transcript_missing(self):
        info = {"meeting": {"name": "Call", "duration": 60}, "video": {"transcript": {"data": []}}}
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(TLDV, "fetch", return_value=json.dumps(info).encode()), \
                mock.patch.object(sys, "argv", ["tldv-dl", "6ab3064e32651100137c93da", "--no-video", "-o", tmp]):
            with self.assertRaises(SystemExit) as ctx:
                TLDV.main()
            self.assertIn(".srt", str(ctx.exception.code))

    def test_main_writes_video_and_transcript_by_default(self):
        info = {"meeting": {"name": "Call", "duration": 60},
                "video": {"transcript": {"data": [[word(" Oi", 0, 1)]]}}}

        def fake_video(mid, out_base, workers):
            Path(f"{out_base}.mp4").write_bytes(b"video")

        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(TLDV, "fetch", return_value=json.dumps(info).encode()), \
                mock.patch.object(TLDV, "download_video", side_effect=fake_video), \
                mock.patch.object(sys, "argv", ["tldv-dl", "6ab3064e32651100137c93da", "-o", tmp]):
            TLDV.main()
            for ext in (".mp4", ".srt", ".txt", ".transcript.json"):
                self.assertGreater(Path(tmp, f"Call{ext}").stat().st_size, 0, ext)


if __name__ == "__main__":
    unittest.main()
