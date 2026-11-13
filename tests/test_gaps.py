"""Gap probes: each one PASSES while the gap exists and FAILS the day NovaLang is fixed, so docs/GAPS.md cannot rot.
Each runs a few lines of NovaLang on the VM and on the self-hosted engine (a few also need the sandbox flags, so the VM only)."""
import subprocess, sys, unittest

from tests import common as c


def nova(source, engine="vm", flags=()):
    """-> (exit code, stdout + stderr). engine: vm | bootstrap. flags go before the program (G-034 in Nova_Sort)."""
    d = c.tempdir()
    try:
        path = c.write(d, "probe.nova", source)
        args = [sys.executable, c.NOVA] + list(flags) + (["--bootstrap"] if engine == "bootstrap" else []) + [path]
        done = subprocess.run(args, capture_output=True, text=True, timeout=300)
        return done.returncode, done.stdout + done.stderr
    finally:
        c.cleanup(d)


class Gaps(unittest.TestCase):
    def both(self, source):
        return [(e, nova(source, e)) for e in ("vm", "bootstrap")]

    def undefined(self, names, call):
        for name in names:
            for engine, (code, out) in self.both(call % name):
                with self.subTest(name=name, engine=engine):
                    self.assertNotEqual(code, 0)
                    self.assertIn("undefined name '%s'" % name, out)

    # --- G-043 ---------------------------------------------------------------------------------------------
    def test_G043_round_is_half_to_even(self):
        src = "for x in [0.5, 1.5, 2.5, 3.5, 4.5, -0.5, -1.5, -2.5, 0.125 * 4, 2.675 * 100, 1.005 * 100] { print(round(x)) }"
        for engine, (code, out) in self.both(src):
            with self.subTest(engine=engine):
                # a shop that rounds half up would print 1 2 3 4 5 -1 -2 -3 1 268 101 (the last two are also the float's fault)
                self.assertEqual((code, out.split()), (0, ["0", "2", "2", "4", "4", "0", "-2", "-2", "0", "268", "100"]))

    def test_G043_and_so_is_round_with_digits_plus_the_binary_float(self):
        src = "for x in [0.125, 0.375, 2.675, 1.005, 10.075] { print(round(x, 2)) }\nprint(str(round(5.0, 2)))"
        for engine, (code, out) in self.both(src):
            with self.subTest(engine=engine):
                # half-up on the decimal text would be 0.13 0.38 2.68 1.01 10.08
                self.assertEqual((code, out.split()), (0, ["0.12", "0.38", "2.67", "1", "10.07", "5"]))

    # --- G-044 ---------------------------------------------------------------------------------------------
    def test_G044_floats_drift_and_there_is_no_decimal_type(self):
        src = "let t = 0.0\nfor i = 1 to 10 { t = t + 0.1 }\nprint(t)\nprint(0.1 + 0.2 == 0.3)\nprint(0.1 + 0.2)\nprint(1.1 * 3)"
        for engine, (code, out) in self.both(src):
            with self.subTest(engine=engine):
                self.assertEqual((code, out.split()), (0, ["0.9999999999999999", "false", "0.30000000000000004", "3.3000000000000003"]))
        self.undefined(["decimal", "Decimal", "fixed", "money", "cents"], "print(%s(1))")

    def test_G044_an_int_and_a_float_are_not_told_apart_and_str_hides_it(self):
        for engine, (code, out) in self.both('print(type(5) == type(5.0))\nprint(str(5.0))\nprint(5.0 == 5)'):
            with self.subTest(engine=engine):
                self.assertEqual((code, out.split()), (0, ["true", "5", "true"]))

    def test_G044_but_integers_are_exact_far_beyond_a_float(self):
        # the PASS the design stands on: integer cents never lose a digit (Nova_Stats G-001)
        for engine, (code, out) in self.both("print(9007199254740993 + 2)\nprint(123456789012345678 * 100)"):
            with self.subTest(engine=engine):
                self.assertEqual((code, out.split()), (0, ["9007199254740995", "12345678901234567800"]))

    # --- G-045 ---------------------------------------------------------------------------------------------
    def test_G045_floor_division_and_modulo_round_toward_minus_infinity(self):
        src = "print(-1250050 // 100)\nprint(-1250050 % 100)\nprint(-7 // 2)\nprint(7 // -2)\nprint(-7 % 3)"
        for engine, (code, out) in self.both(src):
            with self.subTest(engine=engine):
                # a person (and truncating languages) expect -12500, -50, -3, -3, -1
                self.assertEqual((code, out.split()), (0, ["-12501", "50", "-4", "-4", "2"]))
        self.undefined(["divmod", "trunc", "int", "truncate"], "print(%s(7, 2))")

    # --- G-046 ---------------------------------------------------------------------------------------------
    def test_G046_no_date_support_and_max_min_refuse_text(self):
        self.undefined(["parse_date", "parse_time", "date", "datetime", "strptime", "days_in_month", "is_leap"], 'print(%s("2025-01-01"))')
        for call in ["max", "min"]:
            for engine, (code, out) in self.both('print(%s("2025-01-02", "2025-01-01"))' % call):
                with self.subTest(call=call, engine=engine):
                    self.assertNotEqual(code, 0)
                    self.assertIn("%s() needs a number, but got a string" % call, out)

    def test_G046_but_iso_dates_compare_correctly_as_text(self):
        for engine, (code, out) in self.both('print("2025-01-02" > "2025-01-01")\nprint("2024-12-31" < "2025-01-01")'):
            with self.subTest(engine=engine):
                self.assertEqual((code, out.split()), (0, ["true", "true"]))

    # --- G-047 ---------------------------------------------------------------------------------------------
    def test_G047_no_csv_reader_and_split_lines_cuts_a_quoted_newline(self):
        self.undefined(["csv", "parse_csv", "read_csv", "csv_split", "split_csv"], 'print(%s("a,b"))')
        src = 'let parts = split_lines("a,\\"two\\nlines\\",b\\nc,d,e")\nprint(len(parts))\nprint(parts[0])'
        for engine, (code, out) in self.both(src):
            with self.subTest(engine=engine):
                self.assertEqual((code, out.split("\n")[:2]), (0, ["3", 'a,"two']))  # a record that is really 2 lines becomes 3 pieces

    # --- G-048 ---------------------------------------------------------------------------------------------
    def test_G048_small_floats_print_in_exponent_form_and_cannot_be_read_back(self):
        for engine, (code, out) in self.both('print(str(0.0000001))\nprint(0.00000001)\nprint(str(0.00001))'):
            with self.subTest(engine=engine):
                self.assertEqual((code, out.split()), (0, ["1e-07", "1e-08", "1e-05"]))
        for text in ["1e-07", "1e3", "1E5"]:
            for engine, (code, out) in self.both('print(num("%s"))' % text):
                with self.subTest(text=text, engine=engine):
                    self.assertNotEqual(code, 0)
                    self.assertIn("num() cannot read a number from", out)

    def test_G048_there_is_no_exponent_literal_and_big_floats_never_use_one(self):
        for engine, (code, out) in self.both("print(1e3)"):
            with self.subTest(engine=engine):
                self.assertNotEqual(code, 0)
                self.assertIn("found 'e3'", out)
        for engine, (code, out) in self.both("print(1000000.0 * 1000000.0 * 1000000.0)"):
            with self.subTest(engine=engine):
                self.assertEqual((code, out.split()), (0, ["1000000000000000000"]))

    # --- G-049 ---------------------------------------------------------------------------------------------
    def test_G049_no_compound_assignment_no_conditional_expression_and_or_give_only_booleans(self):
        for src, message in [("let x = 1\nx += 1", "unexpected '='"),
                             ("print(true ? 1 : 2)", "unexpected character '?'"),
                             ('print(1 if true else 2)', "found 'if'"),
                             ('print(true and "y")', "the right side of 'and' must be true or false, but it is a string"),
                             ('print(false or "y")', "the right side of 'or' must be true or false, but it is a string")]:
            for engine, (code, out) in self.both(src):
                with self.subTest(source=src, engine=engine):
                    self.assertNotEqual(code, 0)
                    self.assertIn(message, out)

    # --- G-050 ---------------------------------------------------------------------------------------------
    def test_G050_replace_all_needs_the_regex_capability(self):
        src = 'print(replace_all("a-b-c", "-", "+"))'
        self.assertEqual(nova(src), (0, "a+b+c\n"))  # trusted: there
        code, out = nova(src, flags=["--profile", "restricted"])
        self.assertNotEqual(code, 0)
        self.assertIn("undefined name 'replace_all'", out)
        self.assertEqual(nova(src, flags=["--profile", "restricted", "--allow-regex"]), (0, "a+b+c\n"))  # granted: there

    def test_G050_but_split_and_join_do_the_same_job(self):
        src = 'print(join(split("a-b-c", "-"), "+"))'
        self.assertEqual(nova(src, flags=["--profile", "restricted"]), (0, "a+b+c\n"))


if __name__ == "__main__":
    unittest.main()
