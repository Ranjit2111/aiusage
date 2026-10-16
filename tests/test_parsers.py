"""Parser self-checks for aiusage. Run: python3 tests/test_parsers.py"""
import importlib.machinery, importlib.util, os, sys, unittest
from datetime import date

sys.dont_write_bytecode = True  # keep the repo free of __pycache__

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
loader = importlib.machinery.SourceFileLoader("aiusage_mod", os.path.join(ROOT, "aiusage"))
spec = importlib.util.spec_from_loader("aiusage_mod", loader)
au = importlib.util.module_from_spec(spec)
loader.exec_module(au)

CLAUDE_LIMITS = {
    "limits": [
        {"kind": "session", "percent": 90, "resets_at": "2026-10-16T16:20:00+00:00", "severity": "critical"},
        {"kind": "weekly_all", "percent": 31, "resets_at": "2026-10-18T18:00:00+00:00"},
        {"kind": "weekly_scoped", "percent": 12, "resets_at": "2026-10-18T18:00:00+00:00",
         "scope": {"model": {"display_name": "Fable"}}},
    ],
    "extra_usage": {"is_enabled": False},
}
CLAUDE_LEGACY = {
    "five_hour": {"utilization": 55.5, "resets_at": "2026-10-16T16:20:00+00:00"},
    "seven_day": {"utilization": 10.0, "resets_at": "2026-10-18T18:00:00+00:00"},
}
CODEX_RPC = {
    "primary": {"usedPercent": 85, "windowDurationMins": 300, "resetsAt": 1792168629},
    "secondary": {"usedPercent": 29, "windowDurationMins": 10080, "resetsAt": 1792737360},
    "credits": {"hasCredits": False, "unlimited": False, "balance": "0"},
    "planType": "plus",
}
CODEX_SNAPSHOT = {
    "primary": {"used_percent": 85.0, "window_minutes": 300, "resets_at": 1792168629},
    "secondary": {"used_percent": 29.0, "window_minutes": 10080, "resets_at": 1792737360},
    "credits": {"has_credits": False, "unlimited": False, "balance": "0"},
    "plan_type": "plus",
}
OPENCODE = {
    "rolling": {"status": "ok", "percent": 6, "resetsAt": "2026-10-16T13:07:11.000Z"},
    "weekly": {"status": "ok", "percent": 63, "resetsAt": "2026-10-19T00:00:00.000Z"},
    "monthly": {"status": "warning", "percent": 32, "resetsAt": "2026-10-27T05:25:16.000Z"},
}


class Parsers(unittest.TestCase):
    def test_claude_limits_array(self):
        windows, extra = au.parse_claude(CLAUDE_LIMITS)
        self.assertEqual([w["name"] for w in windows], ["session", "weekly", "weekly Fable"])
        self.assertEqual(windows[0]["percent"], 90)
        self.assertEqual(windows[0]["severity"], "critical")
        self.assertEqual(windows[0]["resets_at"].tzinfo is not None, True)
        self.assertEqual(extra, {"is_enabled": False})

    def test_claude_legacy_shape(self):
        windows, _ = au.parse_claude(CLAUDE_LEGACY)
        self.assertEqual([w["name"] for w in windows], ["session", "weekly"])
        self.assertEqual(windows[0]["percent"], 55.5)

    def test_codex_both_shapes(self):
        for fixture in (CODEX_RPC, CODEX_SNAPSHOT):
            p = au.parse_codex(fixture)
            self.assertEqual([w["name"] for w in p["windows"]], ["5h", "weekly"])
            self.assertEqual(p["windows"][0]["percent"], 85)
            self.assertEqual(p["plan"], "plus")
            self.assertEqual(p["credit_note"], "credits: none")

    def test_opencode(self):
        windows = au.parse_opencode(OPENCODE)
        self.assertEqual([w["name"] for w in windows], ["rolling", "weekly", "monthly"])
        self.assertEqual(windows[2]["severity"], "warning")
        self.assertIsNone(windows[0]["severity"])

    def test_fmt_dur(self):
        self.assertEqual(au.fmt_dur(3900), "1h 5m")
        self.assertEqual(au.fmt_dur(90061), "1d 1h")
        self.assertEqual(au.fmt_dur(45), "45s")
        self.assertEqual(au.fmt_dur(600), "10m")
        self.assertEqual(au.fmt_dur(-5), "0s")

    def test_next_renewal_clamps_and_rolls(self):
        self.assertEqual(au.next_renewal(31, date(2026, 2, 10)), date(2026, 2, 28))
        self.assertEqual(au.next_renewal(5, date(2026, 2, 10)), date(2026, 3, 5))
        self.assertEqual(au.next_renewal(20, date(2026, 2, 10)), date(2026, 2, 20))
        self.assertEqual(au.next_renewal(15, date(2026, 12, 20)), date(2027, 1, 15))


if __name__ == "__main__":
    unittest.main(verbosity=2)
