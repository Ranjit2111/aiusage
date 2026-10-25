"""Parser self-checks for aiusage. Run: python3 tests/test_parsers.py"""
import contextlib, importlib.machinery, importlib.util, io, os, shutil, sys, tempfile, unittest
from datetime import date, timedelta, timezone

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


class Timezone(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.cfg = os.path.join(self.tmp, "config.toml")
        self._cfg, self._zone, self._name = au.CONFIG, au.ZONE, au.ZONE_NAME
        au.CONFIG = self.cfg
        au.ZONE, au.ZONE_NAME = timezone.utc, "UTC"

    def tearDown(self):
        au.CONFIG, au.ZONE, au.ZONE_NAME = self._cfg, self._zone, self._name
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_defaults_to_utc(self):
        au.set_display_zone({})
        self.assertEqual(au.ZONE_NAME, "UTC")
        self.assertIn("UTC", au.zlabel())

    def test_config_zone_is_used(self):
        au.set_display_zone({"timezone": "Asia/Kolkata"})
        self.assertEqual(au.ZONE_NAME, "Asia/Kolkata")
        when = au.fmt_when(au.now() + timedelta(hours=2))
        self.assertNotIn("UTC", when)
        self.assertNotIn(" / ", when)          # one clock, not two
        self.assertRegex(when, r"in \d+h \d+m \(\d\d:\d\d\)")

    def test_case_and_spaces_are_forgiven(self):
        au.set_display_zone({"timezone": "asia/kolkata"})
        self.assertEqual(au.ZONE_NAME, "Asia/Kolkata")
        au.set_display_zone({"timezone": "America/New York"})
        self.assertEqual(au.ZONE_NAME, "America/New_York")

    def test_unknown_zone_raises(self):
        with self.assertRaises(au.CliError):
            au.set_display_zone({"timezone": "Mars/Olympus"})

    def test_only_iana_names_are_accepted(self):
        for typed, want in {"europe/berlin": "Europe/Berlin", "Asia/Tokyo": "Asia/Tokyo",
                            "utc": "UTC", "australia/sydney": "Australia/Sydney"}.items():
            self.assertEqual(au.canonical_zone(typed), want, typed)

    def test_city_names_are_rejected_with_instructions(self):
        for typed in ("madurai", "tokyo", "india", "pst"):
            with self.assertRaises(au.CliError) as ctx:
                au.canonical_zone(typed)
            message = str(ctx.exception)
            self.assertIn("IANA", message)
            self.assertIn("Search online", message)
            self.assertIn(f'"{typed} IANA timezone"', message)
            self.assertIn("aiusage tz Asia/Kolkata", message)

    def test_write_timezone_keeps_plans_and_comments(self):
        with open(self.cfg, "w") as fh:
            fh.write("# my plans\n\n[[plans]]\nname = \"Claude Pro\"\nprice = \"$20/mo\"\nrenew_day = 24\n")
        au.write_timezone("Asia/Tokyo")
        doc = au.load_config()
        self.assertEqual(doc["timezone"], "Asia/Tokyo")
        self.assertEqual(doc["plans"][0]["renew_day"], 24)
        with open(self.cfg) as fh:
            body = fh.read()
        self.assertIn("# my plans", body)
        self.assertEqual(body.count("timezone ="), 1)
        self.assertLess(body.index("timezone ="), body.index("[[plans]]"))
        au.write_timezone("Europe/Berlin")     # replaces, never duplicates
        self.assertEqual(au.load_config()["timezone"], "Europe/Berlin")
        with open(self.cfg) as fh:
            self.assertEqual(fh.read().count("timezone ="), 1)

    def test_write_timezone_lifts_nested_key(self):
        with open(self.cfg, "w") as fh:
            fh.write("[[plans]]\nname = \"X\"\ntimezone = \"UTC\"\nrenew_day = 1\n")
        au.write_timezone("Asia/Kolkata")
        doc = au.load_config()
        self.assertEqual(doc["timezone"], "Asia/Kolkata")
        self.assertEqual(doc["plans"][0]["name"], "X")

    def test_write_timezone_creates_missing_file(self):
        au.write_timezone("Asia/Tokyo")
        self.assertEqual(au.load_config()["timezone"], "Asia/Tokyo")

    def test_tz_command_prints_and_sets(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            au.tz_command(None)
        self.assertIn("UTC (default)", buf.getvalue())
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            au.tz_command("Asia/Kolkata")
        self.assertIn("Asia/Kolkata", buf.getvalue())
        self.assertEqual(au.load_config()["timezone"], "Asia/Kolkata")

    def test_render_uses_one_clock(self):
        au.set_display_zone({"timezone": "Asia/Kolkata"})
        data = {"generated_at": au.now(), "errors": {}, "plans": None,
                "providers": {"claude": {"title": "Claude (pro)", "source": "test",
                                         "windows": [{"name": "session", "percent": 42,
                                                      "resets_at": au.now() + timedelta(minutes=30)}],
                                         "notes": []}}}
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            au.render(data, verbose=False)
        out = buf.getvalue()
        self.assertIn("IST", out)
        self.assertNotIn("UTC", out)
        self.assertNotIn(" / ", out)
        self.assertNotIn("v0.", out)


    def test_main_tz_roundtrip(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(au.main(["tz", "asia/tokyo"]), 0)
        self.assertEqual(au.load_config()["timezone"], "Asia/Tokyo")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(au.main(["tz"]), 0)
        self.assertIn("Asia/Tokyo", buf.getvalue())
        with self.assertRaises(SystemExit):
            au.main(["claude", "extra-argument"])


    def test_json_carries_timezone(self):
        au.set_display_zone({"timezone": "Europe/Berlin"})
        data = {"generated_at": au.now(), "errors": {}, "providers": {}, "plans": None}
        self.assertEqual(au.jsonable(data)["timezone"], "Europe/Berlin")


    def test_tz_with_a_city_name_explains_what_to_do(self):
        with self.assertRaises(au.CliError) as ctx:
            au.main(["tz", "madurai"])
        message = str(ctx.exception)
        self.assertIn("not an IANA timezone", message)
        self.assertIn('Search online for "madurai IANA timezone"', message)
        self.assertIn("aiusage tz Asia/Kolkata", message)
        self.assertFalse(au.load_config().get("timezone"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
