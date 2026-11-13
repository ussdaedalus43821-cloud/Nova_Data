"""Behaviour: nova_data.nova reports exactly what an independent Python oracle (csv + decimal) computes, on the VM,
the tree-walker and the self-hosted interpreter."""
import filecmp, os, random, subprocess, sys, unittest

from tests import common as c

ENGINES = ["vm", "tree", "bootstrap"]
HEADER = "Date,Description,Amount,Category\n"


class Checked(unittest.TestCase):
    """Run the program on a file and compare every number in the report with the oracle's."""

    def setUp(self):
        self.dir = c.tempdir()
        self.addCleanup(c.cleanup, self.dir)

    def file(self, text, name="t.csv"):
        return c.write(self.dir, name, text)

    def check(self, path, engine="vm", profile=None):
        done = c.run(path, engine, profile)
        self.assertEqual(done.returncode, 0, done.stderr + done.stdout)
        out = done.stdout
        want = c.oracle_file(path)
        got = c.parse(out)
        self.assertEqual((got.records, got.valid, got.rejected, got.blank), (want.records, want.valid, want.rejected, want.blank), out)
        if want.valid == 0:
            self.assertIn("Nothing to report", out)
            return out
        order = c.expected_order(want)
        self.assertEqual([r[0] for r in got.rows], order, "categories are not in biggest-first order\n" + out)
        biggest = max(want.net.values())
        for (name, n, total, avg, share, bar), key in zip(got.rows, order):
            with self.subTest(category=key):
                self.assertEqual(n, want.count[key])
                self.assertEqual(total, want.net[key], "total of " + key)
                self.assertEqual(avg, c.half_up(want.net[key], want.count[key]), "average of " + key)
                self.assertEqual(share, c.percent(want.net[key], want.grand), "share of " + key)
                self.assertEqual(bar, c.bar(want.net[key], biggest), "bar of " + key)
        self.assertEqual(got.total, (want.valid, want.grand, c.half_up(want.grand, want.valid)))
        self.assertEqual(got.charges, (want.charge_total, want.charge_n))
        self.assertEqual(got.refunds, (want.refund_total, want.refund_n))
        self.assertEqual(got.largest, want.largest, out)
        self.assertEqual(got.refund, want.refund, out)
        self.assertEqual((got.first, got.last, got.categories), (want.first, want.last, len(want.net)))
        self.assertEqual([n for n, _ in got.reject_lines], [line for line, _ in want.rejects[:5]], out)
        self.assertIn("exact sum (integer cents)", out)
        self.assertIn(c.money(want.grand), out)
        return out


class Sample(Checked):
    """The committed 10,000-row file, and the generator behind it."""

    def test_the_sample_is_what_the_generator_makes(self):
        again = os.path.join(self.dir, "again.csv")
        subprocess.run([sys.executable, c.MAKE_CSV, again], check=True, capture_output=True)
        self.assertTrue(filecmp.cmp(again, c.SAMPLE, shallow=False), "tools/make_csv.py no longer reproduces data/transactions.csv")

    def test_the_sample_has_ten_thousand_rows_and_a_few_bad_ones(self):
        want = c.oracle_file(c.SAMPLE)
        self.assertEqual(want.records + want.blank, 10000)
        self.assertEqual((want.valid, want.rejected, want.blank), (9993, 6, 1))
        self.assertEqual(len(want.net), 10)

    def test_the_whole_report_matches_the_oracle_on_the_vm(self):
        out = self.check(c.SAMPLE)
        want = c.oracle_file(c.SAMPLE)
        self.assertIn(c.money(want.grand), out)
        self.assertIn(c.money(want.largest[0]), out)

    def test_every_engine_matches_on_a_smaller_generated_file(self):
        path = c.make_synthetic(self.dir, 1000)
        for engine in ENGINES:
            with self.subTest(engine=engine):
                self.check(path, engine)

    def test_a_different_size_still_matches(self):
        for rows in (50, 333):
            with self.subTest(rows=rows):
                self.check(c.make_synthetic(self.dir, rows, "n%d.csv" % rows))

    def test_the_float_check_is_shown_and_the_float_is_not_the_total(self):
        out = c.run(c.SAMPLE).stdout
        want = c.oracle_file(c.SAMPLE)
        float_line = [l for l in out.splitlines() if "naive float sum" in l][0]
        shown = float_line.split()[-1]
        self.assertNotEqual(shown, "%d.%02d" % (want.grand // 100, want.grand % 100), "the float sum came out exact; pick another file")
        self.assertAlmostEqual(float(shown), want.grand / 100, places=4)
        self.assertRegex(out, r"float error +\$0\.\d{9} after 9,993 additions")


def rows(*lines):
    return HEADER + "\n".join(lines) + "\n"


class Money(Checked):
    """Amount syntax, in every form the program accepts or refuses."""

    VALID = ["0", "0.00", "0.5", "12", "12.5", "12.50", "-12.50", "+12.50", "$12.50", "-$12.50", "(12.50)", "($12.50)",
             "\"1,250.50\"", "\"-1,250.50\"", "\"$1,250.50\"", "\"1,000,000.00\"", "007.50", " 3.25 ", "\"999,999,999,999.99\"",
             "999999999999", "0.01", "-0.01", "100000", "99.99"]
    INVALID = ["", "abc", "N/A", "1.234", "1.2.3", "5.", ".5", "--5", "1,23.45", "\"1,2345.00\"", "\"12,34\"", "1e3", "$", "-", "()",
               "1 000", "12.5x", "\"1,250,.50\"", "1000000000000", "$-5.00", "\"1,,000.00\"", "٣.٥٠"]

    def line(self, amount, i=0):
        return "2025-01-%02d,Item %d,%s,Misc" % (1 + i % 28, i, amount)

    def test_every_valid_form_is_read_as_the_oracle_reads_it(self):
        path = self.file(rows(*[self.line(a, i) for i, a in enumerate(self.VALID)]))
        want = c.oracle_file(path)
        self.assertEqual(want.rejected, 0, "the oracle disagrees that these are valid: %s" % want.rejects)
        for engine in ENGINES:
            with self.subTest(engine=engine):
                self.check(path, engine)

    def test_every_invalid_form_is_rejected(self):
        path = self.file(rows(*[self.line(a, i) for i, a in enumerate(self.INVALID)]))
        want = c.oracle_file(path)
        self.assertEqual((want.valid, want.rejected), (0, len(self.INVALID)), want.rejects)
        out = c.run(path).stdout
        got = c.parse(out)
        self.assertEqual((got.valid, got.rejected), (0, len(self.INVALID)), out)
        self.assertIn("Nothing to report", out)

    def test_each_invalid_form_alone_is_rejected_with_its_line_number(self):
        for amount in self.INVALID:
            with self.subTest(amount=amount):
                path = self.file(rows("2025-01-01,ok,1.00,A", self.line(amount), "2025-01-02,ok,2.00,A"), "one.csv")
                got = c.parse(c.run(path).stdout)
                self.assertEqual((got.valid, got.rejected), (2, 1))
                self.assertEqual([n for n, _ in got.reject_lines], [3])

    def test_a_fraction_of_a_cent_is_refused_not_rounded(self):
        for amount in ["0.005", "0.004", "2.675", "4.999", "0.1234"]:
            with self.subTest(amount=amount):
                out = c.run(self.file(rows(self.line(amount)))).stdout
                self.assertIn("amount has a fraction of a cent: " + amount, out)

    def test_formatting_at_the_edges(self):
        cases = {"0.00": "$0.00", "0.05": "$0.05", "0.99": "$0.99", "1000": "$1,000.00", "999.99": "$999.99", "12345.6": "$12,345.60",
                 "\"999,999.99\"": "$999,999.99", "1000000": "$1,000,000.00", "999999999999.99": "$999,999,999,999.99", "-0.01": "-$0.01",
                 "-1234567.89": "-$1,234,567.89", "-1000": "-$1,000.00", "100": "$100.00"}
        for amount, shown in cases.items():
            with self.subTest(amount=amount):
                out = c.run(self.file(rows(self.line(amount)))).stdout
                self.assertIn("TOTAL", out)
                total = [l for l in out.splitlines() if l.startswith("  TOTAL")][0]
                self.assertIn(shown, total)

    def test_negative_amounts_do_not_lose_a_cent_to_floor_division(self):
        # G-045: -1250050 // 100 is -12501 in NovaLang. money() must still print -$12,500.50
        out = c.run(self.file(rows(self.line("-12500.50")))).stdout
        self.assertIn("-$12,500.50", out)
        self.assertNotIn("12,501", out)

    def test_cents_add_exactly_where_floats_do_not(self):
        # ten times 0.10 is exactly 1.00 in cents; in floats it is 0.9999999999999999
        path = self.file(rows(*["2025-01-01,dime,0.10,Coins"] * 10))
        out = c.run(path).stdout
        self.assertIn("$1.00", [l for l in out.splitlines() if l.startswith("  TOTAL")][0])
        self.assertIn("0.9999999999999999", out)  # what a naive float sum gives; shown in the precision check

    def test_a_refund_only_category_has_a_negative_total_and_no_bar(self):
        path = self.file(rows("2025-01-01,shirt,50.00,Shopping", "2025-01-02,fee back,-8.00,Bank", "2025-01-03,fee back,-2.50,Bank"))
        out = self.check(path)
        got = c.parse(out)
        self.assertEqual([(r[0], r[2], r[5]) for r in got.rows][1], ("Bank", -1050, ""))

    def test_a_category_that_nets_to_zero(self):
        path = self.file(rows("2025-01-01,a,10.00,Even", "2025-01-02,b,-10.00,Even", "2025-01-03,c,5.00,Other"))
        self.check(path)


class Csv(Checked):
    """Quoting, line ends, headers."""

    def test_quoted_fields_commas_doubled_quotes_and_a_newline_inside(self):
        path = self.file(rows(
            '2025-01-01,"Costco, Inc.",10.00,Groceries',
            '2025-01-02,"The ""Corner"" Cafe",5.50,Dining',
            '2025-01-03,"""",1.00,Dining',
            '2025-01-04,"",2.00,Dining',
            '2025-01-05,"two\nlines",3.00,Dining',
            '2025-01-06,"three\nlines\nhere",4.00,Dining',
            '2025-01-07,"ends with comma,",6.00,Dining',
            '2025-01-08,plain,7.00,"Quoted, category"',
            '2025-01-09,"a ""b"", c",8.00,Dining',
        ))
        for engine in ENGINES:
            with self.subTest(engine=engine):
                out = self.check(path, engine)
                self.assertIn("Quoted, category", out)

    def test_line_numbers_stay_right_after_a_record_that_spans_lines(self):
        path = self.file(rows('2025-01-01,"a\nb\nc",1.00,X', "2025-01-02,huge,999.00,X", "2025-01-03,bad,oops,X"))
        out = self.check(path)
        self.assertEqual(c.parse(out).largest[4], 5)  # the header is line 1, the three-line record is lines 2-4
        self.assertEqual(c.parse(out).reject_lines[0][0], 6)

    def test_a_trailing_comma_is_an_empty_last_field_and_rejects_the_row(self):
        path = self.file(rows("2025-01-01,x,1.00,Food,", "2025-01-02,x,1.00,Food"))
        got = c.parse(self.check(path))
        self.assertEqual((got.valid, got.rejected), (1, 1))

    def test_an_empty_category_becomes_uncategorized(self):
        path = self.file(rows("2025-01-01,x,1.00,", "2025-01-02,x,2.00,   "))
        got = c.parse(self.check(path))
        self.assertEqual([(r[0], r[1], r[2]) for r in got.rows], [("Uncategorized", 2, 300)])

    def test_crlf_blank_lines_and_a_missing_final_newline(self):
        text = "Date,Description,Amount,Category\r\n2025-01-01,a,1.00,X\r\n\r\n2025-01-02,b,2.00,X\r\n\r\n2025-01-03,c,3.00,Y"
        path = self.file(text)
        for engine in ENGINES:
            with self.subTest(engine=engine):
                got = c.parse(self.check(path, engine))
                self.assertEqual((got.valid, got.blank), (3, 2))

    def test_a_byte_order_mark_and_reordered_extra_and_mixed_case_headers(self):
        text = "﻿category, AMOUNT ,Account,Description,DATE\nX,1.50,checking,a,2025-01-01\nY,\"2,000.00\",savings,\"b, c\",2025-01-02\n"
        path = self.file(text)
        for engine in ENGINES:
            with self.subTest(engine=engine):
                got = c.parse(self.check(path, engine))
                self.assertEqual((got.valid, got.rejected), (2, 0))
                self.assertEqual(got.largest[:2], (200000, "2025-01-02"))

    def test_a_whitespace_only_line_is_blank(self):
        got = c.parse(self.check(self.file(rows("2025-01-01,a,1.00,X", "   ", "\t", "2025-01-02,b,1.00,X"))))
        self.assertEqual((got.valid, got.blank), (2, 2))

    def test_a_row_with_the_wrong_number_of_fields_is_rejected_not_guessed(self):
        # the classic corruption: an unquoted comma in a description moves every column one to the right
        path = self.file(rows("2025-01-01,Costco, Inc.,10.00,Groceries", "2025-01-02,Costco,10.00,Groceries"))
        got = c.parse(self.check(path))
        self.assertEqual((got.valid, got.rejected), (1, 1))
        self.assertIn("expected 4 fields, found 5", c.run(path).stdout)

    def test_dates(self):
        good = ["2024-02-29", "2000-02-29", "2025-12-31", "2025-01-01", "1999-09-09", "2025-04-30"]
        bad = ["2025-02-29", "1900-02-29", "2100-02-29", "2025-04-31", "2025-13-01", "2025-00-10", "2025-01-00", "2025-1-5", "25-01-01",
               "2025/01/01", "20250101", "2025-01-01T00:00", "yesterday", "", "2025-01-32", "2025-06-31", "2025-02-30", "٢٠٢٥-01-01"]
        path = self.file(rows(*["%s,d,1.00,D" % d for d in good + bad]))
        want = c.oracle_file(path)
        self.assertEqual((want.valid, want.rejected), (len(good), len(bad)), want.rejects)
        got = c.parse(self.check(path))
        self.assertEqual((got.valid, got.rejected), (len(good), len(bad)))
        self.assertEqual((got.first, got.last), ("1999-09-09", "2025-12-31"))

    def test_a_stray_quote_costs_one_row_not_the_rest_of_the_file(self):
        # G-047: the program glues lines together while a quote is open, but only up to 8 lines
        body = ["2025-01-%02d,ok %d,1.00,A" % (1 + i % 28, i) for i in range(30)]
        body[5] = '2025-01-06,"never closed,1.00,A'
        body[12] = '2025-01-13,half "quoted" text,1.00,A'
        body[20] = '2025-01-21,"Closed early"oops,1.00,A'
        got = c.parse(c.run(self.file(rows(*body))).stdout)
        self.assertEqual((got.valid, got.rejected), (27, 3))
        self.assertEqual([n for n, _ in got.reject_lines], [7, 14, 22])


class Header(unittest.TestCase):
    def setUp(self):
        self.dir = c.tempdir()
        self.addCleanup(c.cleanup, self.dir)

    def test_header_only_reports_nothing(self):
        done = c.run(c.write(self.dir, "h.csv", HEADER))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("0 records: 0 read, 0 rejected", done.stdout)
        self.assertIn("Nothing to report", done.stdout)

    def test_an_empty_file_is_an_error(self):
        for text in ["", "\n\n  \n"]:
            with self.subTest(text=text):
                done = c.run(c.write(self.dir, "e.csv", text))
                self.assertEqual(done.returncode, 1)
                self.assertIn("the file has no header line", done.stdout)

    def test_a_missing_column_is_an_error_that_names_the_header(self):
        done = c.run(c.write(self.dir, "m.csv", "Date,Memo,Amount\n2025-01-01,x,1.00\n"))
        self.assertEqual(done.returncode, 1)
        self.assertIn("the header must name Date, Description, Amount and Category (found: Date,Memo,Amount)", done.stdout)

    def test_a_broken_header_is_an_error(self):
        done = c.run(c.write(self.dir, "b.csv", 'Date,"Descr,Amount,Category\n'))
        self.assertEqual(done.returncode, 1)
        self.assertIn("the header line is not valid CSV", done.stdout)

    def test_a_missing_file_is_an_error_not_a_crash(self):
        done = c.run(os.path.join(self.dir, "nope.csv"))
        self.assertEqual(done.returncode, 1)
        self.assertIn("nova_data: cannot read", done.stdout)

    def test_no_argument_prints_usage(self):
        done = subprocess.run([sys.executable, c.NOVA, c.PROGRAM], capture_output=True, text=True)
        self.assertEqual(done.returncode, 2)
        self.assertIn("usage: nova_data.nova TRANSACTIONS.CSV", done.stdout)


class Ties(Checked):
    def test_equal_totals_are_ordered_by_name_and_equal_charges_by_first_line(self):
        path = self.file(rows("2025-01-01,first,50.00,Zeta", "2025-01-02,second,50.00,Alpha", "2025-01-03,third,50.00,Mid"))
        out = self.check(path)
        got = c.parse(out)
        self.assertEqual([r[0] for r in got.rows], ["Alpha", "Mid", "Zeta"])
        self.assertEqual(got.largest[2:], ("first", "Zeta", 2))

    def test_all_zero_amounts_have_no_largest_charge(self):
        out = self.check(self.file(rows("2025-01-01,free,0.00,A", "2025-01-02,free,0,A")))
        self.assertIn("(no charges)", out)

    def test_a_long_category_name_is_cut_with_an_ellipsis(self):
        long_name = "Home Improvement and Garden Supplies"
        out = c.run(self.file(rows("2025-01-01,x,9.00,%s" % long_name))).stdout
        table = out.split("SPENDING BY CATEGORY")[1].split("TOTAL")[0]
        self.assertIn(long_name[:15] + "…", table)
        self.assertNotIn(long_name, table)  # the full name is still shown on the largest-transaction card
        self.assertIn(long_name, out.split("LARGEST SINGLE TRANSACTION")[1])


class Fuzz(Checked):
    """Seeded random files full of valid and invalid rows, compared with the oracle on the VM."""

    def make(self, rng, n):
        import csv, io
        cats = ["Food", "Rent", "Fun", "Gas", "Health", "Tax, local", 'Say "hi"', "Étoile"]
        out = io.StringIO()
        w = csv.writer(out, lineterminator="\n")
        w.writerow(["Date", "Description", "Amount", "Category"])
        for i in range(n):
            roll = rng.random()
            y = rng.choice([2023, 2024, 2025]); m = rng.randint(1, 12); d = rng.randint(1, 31)
            date = "%04d-%02d-%02d" % (y, m, d)  # some are impossible (Feb 30): the oracle decides
            cents = int(rng.random() ** 3 * rng.choice([500, 50000, 5000000]))
            if rng.random() < 0.12:
                cents = -cents
            amount = c.money(cents).replace("$", "") if rng.random() < 0.5 else "%d.%02d" % (cents // 100 if cents >= 0 else -(-cents // 100), abs(cents) % 100)
            if cents < 0 and not amount.startswith("-"):
                amount = "-" + amount
            if roll < 0.04:
                amount = rng.choice(["N/A", "", "1.005", "12,34", "$", "9.9.9"])
            elif roll < 0.07:
                date = rng.choice(["2025-02-30", "2025-13-01", "01/02/2025", ""])
            desc = rng.choice(["Shop", "A, B", 'He said "yes"', "multi\nline", "", "  padded  ", "Zoë"])
            row = [date, desc, amount, rng.choice(cats + [""])]
            if rng.random() < 0.03:
                row = row[:3]
            w.writerow(row)
        return out.getvalue()

    def test_forty_random_files(self):
        for seed in range(40):
            with self.subTest(seed=seed):
                rng = random.Random(seed)
                path = self.file(self.make(rng, rng.randint(1, 120)), "f%d.csv" % seed)
                self.check(path)

    def test_a_few_random_files_on_the_other_engines(self):
        for seed in (101, 102):
            rng = random.Random(seed)
            path = self.file(self.make(rng, 40), "g%d.csv" % seed)
            for engine in ("tree", "bootstrap"):
                with self.subTest(seed=seed, engine=engine):
                    self.check(path, engine)


class Source(unittest.TestCase):
    """The program keeps to its brief: pure NovaLang, no float rounding of money, no writes."""

    def code(self):
        import re
        with open(c.PROGRAM, encoding="utf-8") as f:
            source = f.read()
        source = re.sub(r"#[^\n]*", "", source)
        return re.sub(r'"(?:[^"\\\n]|\\.)*"', '""', source)

    def test_no_regex_import_python_or_file_writes(self):
        import re
        code = self.code()
        for name in ["regex", "import", "python", "write", "remove", "delete", "rename", "copy", "append", "mkdir", "stdin", "env"]:
            self.assertIsNone(re.search(r"\b%s\b" % name, code), "nova_data.nova uses " + name)

    def test_no_round_anywhere_because_round_is_half_to_even(self):
        import re
        self.assertIsNone(re.search(r"\bround\(", self.code()), "G-043: round() is half-to-even, money must not use it")

    def test_the_only_float_division_is_the_comparison_sum(self):
        import re
        for line in self.code().splitlines():
            if re.search(r"/ 100\b|\b/\b", line.replace("//", "")):
                self.assertIn("float_sum", line, "a float division outside the precision check: " + line.strip())

    def test_it_uses_split_slicing_and_len(self):
        code = self.code()
        for name in ["split(", "len(", "[:"]:
            self.assertIn(name, code)


if __name__ == "__main__":
    unittest.main()
