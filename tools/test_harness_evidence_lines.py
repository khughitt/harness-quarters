import hashlib
import tempfile
import unittest
from pathlib import Path

from harness_evidence import lines as sl
from harness_evidence_testing import FIXTURES, PATHS, CAPTURES


class LinesTest(unittest.TestCase):
    def write(self, data):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        p = Path(d.name) / "x.jsonl"
        p.write_bytes(data)
        return p

    def test_blank_and_crlf_lines_keep_physical_numbering(self):
        data = b'{"a":1}\r\n\n{"b":2}\n'
        got = list(sl.lines(self.write(data), len(data)))
        self.assertEqual([x.number for x in got], [1, 2, 3])
        self.assertEqual(sl.decode(got[0]), {"a": 1})
        self.assertIsNone(sl.decode(got[1]))
        self.assertEqual(got[0].raw, b'{"a":1}\r\n')
        self.assertEqual(sl.sha256(got[0]), hashlib.sha256(b'{"a":1}\r\n').hexdigest())

    def test_partial_last_line_is_incomplete(self):
        data = b'{"a":1}\n{"b"'
        got = list(sl.lines(self.write(data), len(data)))
        self.assertEqual([x.complete for x in got], [True, False])
        self.assertEqual(got[1].number, 2)

    def test_size_bound_ignores_later_appends(self):
        data = b'{"a":1}\n{"b":2}\n'
        got = list(sl.lines(self.write(data), 8))
        self.assertEqual(len(got), 1)
        self.assertTrue(got[0].complete)

    def test_invalid_utf8_line_is_a_record_with_raw_hash(self):
        data = b'{"t":"a\xffb"}\n'
        (line,) = sl.lines(self.write(data), len(data))
        self.assertEqual(sl.decode(line), {"t": "a�b"})
        self.assertEqual(sl.sha256(line), hashlib.sha256(data).hexdigest())

    def test_decode_requires_an_object(self):
        for raw in (b"[1]\n", b"3\n", b"{bad\n", b"\n"):
            self.assertIsNone(sl.decode(sl.Line(1, raw, True)))

    def test_unescape_lenient_undoes_json_escapes(self):
        out = sl.unescape_lenient('{"c":"\\u006eeedle\\/x\\"')
        self.assertIn('needle/x"', out)
        self.assertEqual(sl.unescape_lenient("a\\nb\\\\c\\tz"), "a\nb\\c\tz")
        self.assertEqual(sl.unescape_lenient("bad \\u00zz \\q end\\"), "bad \\u00zz \\q end\\")

    def test_unescape_lenient_combines_surrogate_pairs(self):
        out = sl.unescape_lenient("x\\ud83d\\ude00y")
        self.assertEqual(out, "x\U0001F600y")
        out.encode("utf-8")
        lone = sl.unescape_lenient("a\\ud83d b \\ude00 c")
        self.assertEqual(lone, "a\\ud83d b \\ude00 c")
        lone.encode("utf-8")

    def test_deeply_nested_line_is_not_an_object(self):
        self.assertIsNone(sl.decode(sl.Line(1, b"[" * 100000 + b"\n", True)))

    def test_lines_reads_incrementally_and_cuts_a_long_line(self):
        data = b'{"a":1}\n{"b":2}\n'
        got = list(sl.lines(self.write(data), 12))
        self.assertEqual([(x.raw, x.complete) for x in got],
                         [(b'{"a":1}\n', True), (b'{"b"', False)])

    def test_block_ref_needs_a_line(self):
        place = sl.Place("claude-code", "h", None, "live", "a.jsonl", Path("/x"))
        with self.assertRaises(ValueError):
            sl.ref(place, None, 0)

    def test_ref_shapes(self):
        p = Path("/x")
        place = sl.Place("claude-code", "claude-work", "work", "live",
                         "projects/-w-beta/x.jsonl", p)
        self.assertEqual(sl.ref(place, 3, 0), "claude-work:projects/-w-beta/x.jsonl#L3#0")
        self.assertEqual(sl.ref(place, 3), "claude-work:projects/-w-beta/x.jsonl#L3")
        self.assertEqual(sl.ref(place), "claude-work:projects/-w-beta/x.jsonl")
        explicit = sl.Place("claude-code", "file", None, "explicit", "cap.jsonl", p)
        self.assertEqual(sl.ref(explicit, 4), "file:cap.jsonl#L4")

    def detect(self, path):
        return sl.detect_format(path, path.stat().st_size)

    def test_detect_format(self):
        self.assertEqual(self.detect(FIXTURES / CAPTURES["SDK"]), "sdk")
        self.assertEqual(self.detect(FIXTURES / PATHS["XP"]), "codex")
        self.assertEqual(self.detect(FIXTURES / PATHS["CA"]), "claude")
        self.assertEqual(self.detect(FIXTURES / PATHS["CD"]), "claude")

    def test_detect_format_synthetic(self):
        cases = [
            (b'{"type":"fork-context-ref","x":1}\n', "claude"),
            (b'{"type":"assistant","sessionId":"a","session_id":"b"}\n', "claude"),
            (b'not json\n[1]\n{"type":"session_meta","payload":{}}\n', "codex"),
            (b'{"type":"result","session_id":"s"}\n', "sdk"),
        ]
        for data, want in cases:
            self.assertEqual(self.detect(self.write(data)), want, data)

    def test_detect_format_unknown(self):
        for data in (b'{"x":1}\n', b"", b"garbage\n"):
            with self.assertRaises(sl.UnknownFormat):
                self.detect(self.write(data))


if __name__ == "__main__":
    unittest.main()
