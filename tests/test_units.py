"""The helper functions of nova_data.nova, one at a time, against Python oracles.

The program's helpers (everything above "# ---- the program ----") are loaded into a throwaway NovaLang file, followed by a
few lines that call them on many inputs and print the answers. Python computes the same answers independently."""
import csv, io, json, random, subprocess, sys, unittest

from tests import common as c

with open(c.PROGRAM, encoding="utf-8") as _f:
    _SOURCE = _f.read()
PRELUDE = _SOURCE[:_SOURCE.index("# ---- the program ----")]


def lit(text):
    """A NovaLang string literal."""
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def nova(body, engine="vm"):
    d = c.tempdir()
    try:
        path = c.write(d, "unit.nova", PRELUDE + "\n" + body + "\n")
        args = [sys.executable, c.NOVA] + (["--tree-walk"] if engine == "tree" else []) + (["--bootstrap"] if engine == "bootstrap" else []) + [path]
        done = subprocess.run(args, capture_output=True, text=True, timeout=900)
        if done.returncode:
            raise AssertionError(done.stdout + done.stderr)
        return done.stdout.splitlines()
    finally:
        c.cleanup(d)


# cents (an integer) as the amount the program's helpers take: an exact decimal with two places
AS_AMOUNT = 'def D(c) { return dec.div(dec.from_int(c), dec.from_int(100), 2, "down") }\n'


def listing(items):
    return "[" + ", ".join(items) + "]"


class Helpers(unittest.TestCase):
    def test_money(self):
        values = [0, 1, 5, 9, 10, 99, 100, 101, 999, 1000, 99999, 100000, 100001, 99999999, 100000000, 123456789012, 99999999999999,
                  -1, -5, -99, -100, -101, -12345, -1250050, -100000, -99999999999]
        rng = random.Random(1)
        values += [rng.randint(-10 ** 9, 10 ** 9) for _ in range(250)] + [rng.randint(-10 ** 14, 10 ** 14) for _ in range(50)]
        got = nova(AS_AMOUNT + "for v in %s { print(money(D(v))) }" % listing(map(str, values)))
        self.assertEqual(got, [c.money(v) for v in values])

    def test_group_digits(self):
        values = [0, 1, 12, 123, 1234, 12345, 123456, 1234567, 100000, 1000000, 123456789012345678]
        rng = random.Random(2)
        values += [rng.randint(0, 10 ** rng.randint(1, 15)) for _ in range(100)]
        got = nova("for v in %s { print(group_digits(v)) }" % listing(map(str, values)))
        self.assertEqual(got, [format(v, ",") for v in values])

    def test_half_up_division_through_std_decimal_is_half_away_from_zero_and_exact(self):
        rng = random.Random(3)
        pairs = [(1, 2), (-1, 2), (3, 2), (-3, 2), (5, 10), (-5, 10), (0, 7), (7, 7), (1, 3), (2, 3), (-2, 3), (25, 100), (35, 100), (-35, 100)]
        pairs += [(rng.randint(-10 ** 7, 10 ** 7), rng.randint(1, 10 ** 5)) for _ in range(300)]
        pairs += [(rng.randint(-10 ** 18, 10 ** 18), rng.randint(1, 10 ** 9)) for _ in range(40)]  # far beyond 2**53: floats would fail
        got = nova("for p in %s { print(dec.to_int(dec.div(dec.from_int(p[0]), dec.from_int(p[1]), 0, \"half_up\"), \"half_up\")) }" % listing("[%d, %d]" % p for p in pairs))
        self.assertEqual(got, [str(c.half_up(a, b)) for a, b in pairs])

    def test_percent(self):
        rng = random.Random(4)
        pairs = [(0, 5), (5, 5), (1, 3), (2, 3), (1, 8), (-1, 8), (1, 1000), (1, 2000), (1, 1999), (-7, 9), (5, 0), (5, -3)]
        pairs += [(rng.randint(-10 ** 6, 10 ** 8), rng.randint(1, 10 ** 8)) for _ in range(300)]
        got = nova(AS_AMOUNT + "for p in %s { print(percent(D(p[0]), D(p[1]))) }" % listing("[%d, %d]" % p for p in pairs))
        self.assertEqual(got, [c.percent(a, b) for a, b in pairs])

    def test_bar(self):
        rng = random.Random(5)
        pairs = [(1, 1), (0, 5), (-3, 5), (5, 0), (1, 100000), (99999, 100000), (50, 100), (1, 8 * 20), (3, 160), (7, 160)]
        pairs += [(rng.randint(-100, 10 ** 7), rng.randint(1, 10 ** 7)) for _ in range(300)]
        got = nova(AS_AMOUNT + "for p in %s { print(\"|\" + bar(D(p[0]), D(p[1])) + \"|\") }" % listing("[%d, %d]" % p for p in pairs))
        self.assertEqual(got, ["|" + c.bar(a, b) + "|" for a, b in pairs])

    def test_all_digits_accepts_only_ascii_digits(self):
        rng = random.Random(6)
        alphabet = "0123456789.+- ex_,٣"
        cases = ["", "0", "00", "7", "٣", "1٢3", "12 ", " 12", "1.5", "1e5", "1E5", "0x10", "+5", "-5", "1_0", "9" * 30, "007", "12\u00a0"]
        cases += ["".join(rng.choice(alphabet) for _ in range(rng.randint(0, 6))) for _ in range(500)]
        got = nova("for t in %s { print(all_digits(t)) }" % listing(map(lit, cases)))
        want = [str(text != "" and all(ch in "0123456789" for ch in text)).lower() for text in cases]
        self.assertEqual(got, want)

    def test_parse_amount_agrees_with_the_regex_and_decimal_oracle(self):
        rng = random.Random(7)
        cases = ["0", "0.00", "12", "12.5", "12.50", "-12.50", "+12.50", "$12.50", "-$12.50", "(12.50)", "($12.50)", "1,250.50", "-1,250.50",
                 "1,000,000.00", "007.50", " 3.25 ", "999999999999", "999,999,999,999.99", "", " ", "abc", "1.234", "1.2.3", "5.", ".5", "--5",
                 "1,23.45", "12,34", "1,2345.00", "1e3", "$", "-", "()", "(", ")", "1 000", "1000000000000", "$-5.00", "1,,000.00", "٣.٥٠", "(12.50", "12.50)",
                 "(-5.00)", "(5)", "+-5", "-+5", "$$5", "1,000", ",100", "100,", "1,000,", "0,000", "00,000.00"]
        alphabet = "0123456789.,$-+() "
        cases += ["".join(rng.choice(alphabet) for _ in range(rng.randint(0, 9))) for _ in range(700)]
        # structured near-misses: valid shapes with one character damaged
        for _ in range(300):
            base = rng.choice(["1,250.50", "$99.99", "(45.10)", "-0.05", "12", "1,000,000", "-$3.5"])
            i = rng.randrange(len(base))
            cases.append(base[:i] + rng.choice("0123456789.,$-+() x") + base[i + 1:])
        got = nova("for t in %s {\n let r = parse_amount(t)\n if r[1] == \"\" { print(str(dec.to_int(dec.mul(r[0], dec.from_int(100)), \"down\"))) } else { print(\"bad\") }\n}" % listing(map(lit, cases)))
        want = []
        for text in cases:
            cents = c.oracle_cents(text)
            want.append("bad" if cents is None else str(cents))
        bad = [(t, g, w) for t, g, w in zip(cases, got, want) if g != w]
        self.assertEqual(bad, [], "parse_amount disagrees with the oracle (text, program, oracle)")

    def test_is_date_knows_leap_years_and_month_lengths(self):
        import calendar
        cases = []
        for year in (1900, 1999, 2000, 2023, 2024, 2025, 2100, 2400):
            for month in range(1, 13):
                last = calendar.monthrange(year, month)[1]
                cases += ["%04d-%02d-%02d" % (year, month, d) for d in (1, last, last + 1)]
        rng = random.Random(8)
        alphabet = "0123456789-"
        cases += ["".join(rng.choice(alphabet) for _ in range(rng.choice([8, 9, 10, 10, 10, 11]))) for _ in range(300)]
        cases += ["2025-02-29", "2024-02-29", "2025-1-5", "2025/01/01", "20250101", "", "2025-01-01 ", "٢٠٢٥-01-01", "0000-01-01", "9999-12-31"]
        got = nova("for t in %s { print(is_date(t)) }" % listing(map(lit, cases)))
        want = [str(c.oracle_date(t)).lower() for t in cases]
        bad = [(t, g, w) for t, g, w in zip(cases, got, want) if g != w]
        self.assertEqual(bad, [], "is_date disagrees with datetime (text, program, oracle)")


class Csv(unittest.TestCase):
    def test_parse_fields_round_trips_what_the_csv_module_writes(self):
        rng = random.Random(9)
        pieces = ["", "a", "b c", "Costco, Inc.", 'say "hi"', '"', '""', ",", ",,", "a,b,c", "tail,", ",head", 'q"', '"q', "x\ny", "é", " pad ", "1,250.50", "end\n", "\nstart"]
        rows = [[rng.choice(pieces) for _ in range(rng.randint(1, 6))] for _ in range(500)]
        rows = [r for r in rows if r != [""]]  # an empty line is not a record (csv writes a lone empty field as "")
        lines = []
        for r in rows:
            buf = io.StringIO()
            csv.writer(buf, lineterminator="").writerow(r)
            lines.append(buf.getvalue())
        got = nova("for t in %s { print(json.dumps(parse_fields(t)[0])) }" % listing(map(lit, lines)))
        self.assertEqual([json.loads(g) for g in got], rows)

    def test_malformed_records_are_errors_not_guesses(self):
        cases = {
            'a"b,c': "a quote in the middle of an unquoted field",
            'a,b"': "a quote in the middle of an unquoted field",
            '"abc': "a quoted field is never closed",
            '"abc,def': "a quoted field is never closed",
            'x,"abc': "a quoted field is never closed",
            '"abc"x,1': "text after a closing quote",
            '"abc" ,1': "text after a closing quote",
            '"a""': "a quoted field is never closed",
            'a,"b"c': "text after a closing quote",
        }
        got = nova("for t in %s { let r = parse_fields(t)\n print(str(len(r[0])) + \"|\" + r[1]) }" % listing(map(lit, cases)))
        self.assertEqual(got, ["0|" + why for why in cases.values()])

    def test_the_small_cases(self):
        cases = {"": [""], ",": ["", ""], "a": ["a"], "a,": ["a", ""], ",a": ["", "a"], '""': [""], '"",""': ["", ""], '"a",': ["a", ""],
                 ',"a"': ["", "a"], '""""': ['"'], '"""",1': ['"', "1"], '"a""b"': ['a"b'], '"a,b",c': ["a,b", "c"], 'a,"b,c",d': ["a", "b,c", "d"],
                 "a,b,c,d,e": ["a", "b", "c", "d", "e"]}
        got = nova("for t in %s { print(json.dumps(parse_fields(t)[0])) }" % listing(map(lit, cases)))
        self.assertEqual([json.loads(g) for g in got], list(cases.values()))

    def test_open_quote_counts_quote_characters_by_parity(self):
        cases = ['', 'a', '"', '""', '"""', 'a"b', 'a"b"c', '"a,b', '"a","b', 'x,"y""z",w', 'x,"y""z', '""""']
        got = nova("for t in %s { print(open_quote(t)) }" % listing(map(lit, cases)))
        self.assertEqual(got, [str(t.count('"') % 2 == 1).lower() for t in cases])


class Engines(unittest.TestCase):
    """The same helpers on the tree-walker and the self-hosted interpreter, on a small fixed set."""

    def test_money_and_parse_amount_agree_across_engines(self):
        texts = ["12.50", "-12.50", "(1,250.50)", "$3", "1.234", "abc", "1,23.45", ""]
        body = (AS_AMOUNT + "for t in %s {\n let r = parse_amount(t)\n if r[1] == \"\" { print(money(r[0])) } else { print(\"bad\") }\n}\n"
                "for v in [0, 5, -5, 123456789, -123456789] { print(money(D(v))) }") % listing(map(lit, texts))
        reference = nova(body, "vm")
        for engine in ("tree", "bootstrap"):
            with self.subTest(engine=engine):
                self.assertEqual(nova(body, engine), reference)
        self.assertEqual(reference[:8], ["$12.50", "-$12.50", "-$1,250.50", "$3.00", "bad", "bad", "bad", "bad"])


if __name__ == "__main__":
    unittest.main()
