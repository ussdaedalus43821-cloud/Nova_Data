# GAPS.md - where NovaLang struggled building Nova_Data

The fourth proof of concept, after [Nova_Stats](https://github.com/ussdaedalus43821-cloud/Nova_Stats) (the language),
[Nova_Sort](https://github.com/ussdaedalus43821-cloud/Nova_Sort) (the sandbox) and
[Nova_Log](https://github.com/ussdaedalus43821-cloud/Nova_Log) (text at scale). This one is **money**: read a CSV of
financial transactions, total it per category, find the largest transaction and print a formatted report with dollar
amounts. It tests **floating-point math and currency formatting**. Numbering continues the ecosystem list (Nova_Stats
G-001 to G-026, Nova_Sort G-027 to G-035, Nova_Log G-036 to G-042), so these start at **G-043**.

Written against NovaLang v2.2.0 (`develop` at f458f1d). Entries marked **M13** are the ones to fix there.

**How to read an entry.** *Tried* is what was attempted and the exact result. *Workaround* says what the code does
instead and **who does the work**: `program` (nova_data.nova), `host` (a Python launcher: none here) or `none` (cannot
be done). *Probe* is a reproducible check in `tests/`; the ones in `tests/test_gaps.py` pass while the gap exists and
fail the day NovaLang is fixed, so this log cannot rot.

**Severity:** LIMIT (the sandbox cannot express what is needed) - BLOCKER - FRICTION (worked around in the program) -
TRAP (works, gives a wrong answer silently) - minor.

| # | Gap | Severity | Who works around it | M13 |
| --- | --- | --- | --- | --- |
| G-043 | `round()` is half-to-even: `round(2.5)` is 2, `round(0.5)` is 0 | TRAP (money) | program (never rounds money) | yes |
| G-044 | No decimal or fixed-point type; floats drift; an int and a float cannot be told apart | FRICTION (the central one) | program (integer cents, hand-parsed) | yes |
| G-045 | `//` and `%` round toward minus infinity, so negative cents format wrong; no `trunc`/`divmod`/`int` | TRAP | program (sign taken off first) | yes |
| G-046 | No date support at all; `max`/`min` refuse text; calendar checked by hand | FRICTION | program | yes |
| G-047 | No CSV reader, and `split_lines` cuts a quoted newline in two | FRICTION | program (re-glue, capped) | yes |
| G-048 | Small floats print as `1e-07`, which `num()` cannot read back; no exponent literal | TRAP | program (avoids `str` of a float) | yes |
| G-049 | No `+=`, no conditional expression, and `and`/`or` return only true or false | minor | program | yes |
| G-050 | `replace_all` needs the `regex` capability, so a restricted program has no replace | FRICTION | program (`join(split())`) | yes |

Re-confirmed, not new: **G-008** (Nova_Stats; `str(5.0)` is `5`, no formatting: the reason `money()` exists),
**G-007** (no thousands separator), **G-039** (`num` too loose: why `all_digits` has guards), **G-037** (no `find`),
**G-038** (`sorted` cannot order pairs: categories are packed into one number), **G-036** and **G-042** (the string and
time limits: measured for this program under "The ceiling" below), **G-004** (no way to write an ESC: **no colour** in
the report, for that reason).

---

## G-043 `round()` is half-to-even - TRAP for money (M13)
- **Tried:** `round(0.5)` is 0, `round(1.5)` 2, `round(2.5)` 2, `round(3.5)` 4, `round(4.5)` 4, `round(-0.5)` 0, `round(-2.5)`
  -2. It is Python's banker's rounding, on the VM and on the self-hosted engine. A shop, a bank statement and every
  tax form round half **up** (away from zero): 2.5 is 3. The two-argument form exists and is the one a currency
  report reaches for, and it has the same two problems, one from the rule and one from the binary float:
  `round(0.125, 2)` is `0.12` (half-even; half-up is 0.13), `round(0.375, 2)` is `0.38`, `round(2.675, 2)` is
  `2.67` (2.675 is really 2.67499999...; half-up on the decimal text is 2.68) and `round(1.005, 2)` is `1`
  (not 1.01), and `str(round(5.0, 2))` is `5` (G-008). There is no rounding mode.
- **Why it matters here:** a naive report does `round(total * 100) / 100`. For most totals that is fine, and
  for the ones that land on a half cent it is wrong in the less favourable direction half the time, with no error.
- **Workaround (program):** nothing in `nova_data.nova` rounds a float. Division that must round (averages, percent,
  bar widths) is `div_round(a, b)`: `(2a + b) // 2b` on **integers**, half away from zero, exact at any size
  (tested beyond 2^53). A test fails if the program ever calls `round(`.
- **Suggested for M13:** a rounding-mode argument (`round(x, 2, "half-up")`), or say "half-even" loudly in the reference; and a
  half-up integer divide.
- **Probe:** `tests/test_gaps.py` `test_G043_*`; `tests/test_units.py` `test_div_round_*`; `tests/test_data.py`
  `test_no_round_anywhere_*`.

## G-044 No decimal or fixed-point type; floats drift - FRICTION, the central finding (M13)
- **Tried:** `0.1 + 0.2` is `0.30000000000000004`; ten additions of `0.1` give `0.9999999999999999`; `1.1 * 3` is
  `3.3000000000000003`. There is no `decimal`, `Decimal`, `fixed`, `money` or `cents` (`undefined name`), no `sprintf`,
  no way to ask whether a number is whole: `type(5)` and `type(5.0)` are both `number`, `5.0 == 5`, and `str(5.0)` is
  `5` (G-008).
- **What the program measures:** it adds every amount **twice**, as exact integer cents and as a naive float
  (`float_sum + cents / 100`), and prints both. On the 10,000-row sample the float sum is `2231316.930000008` and
  the exact one `$2,231,316.93`: an error of **$0.000000008** after 9,993 additions. That is tiny, and it is the
  honest result: **at this scale a float total, rounded at the end, would have been right.** The drift grows with the
  number of additions and with the size of the running total, and it is invisible until a column of figures has to
  tie out to the cent. The risk is not this report; it is the pattern.
- **Workaround (program):** money is **never** a float. `parse_cents` reads `"1,250.50"` by hand into the integer
  `125050`; every sum is an integer; `money(cents)` is the only place cents become text. Integers are exact at any
  size (Nova_Stats G-001; `123456789012345678 * 100` is exact), so nothing is lost. The cost is a 70-line parser
  and a formatter that every program doing arithmetic on money must rewrite.
- **Suggested for M13:** a `decimal` type (or `fixed(2)`) with exact `+ - *`, comparison and formatting, and
  `num(text)` returning it on request. Even `divmod` and a rounding mode on integers would make cents bearable.
- **Probe:** `tests/test_gaps.py` `test_G044_*`; `tests/test_data.py` `test_cents_add_exactly_where_floats_do_not`
  (ten dimes) and `test_the_float_check_is_shown_and_the_float_is_not_the_total`.

## G-045 `//` and `%` round toward minus infinity - TRAP for negative amounts (M13)
- **Tried:** `-1250050 // 100` is `-12501` and `-1250050 % 100` is `50`. The naive `str(c // 100) + "." + str(c % 100)`
  prints `-12501.50` for a refund of **$12,500.50**: wrong by a dollar and with the cents inverted, from two operators
  that "work". `-7 // 2` is `-4`. There is no `divmod`, `trunc` or `int` (`undefined name`), so there is no way to
  truncate toward zero except by taking the sign off first.
- **Workaround (program):** `money()` strips the sign, formats the magnitude, then puts the sign back. Refunds are 2.8 %
  of the sample rows, so every report exercises it. The unit tests check 250 random values including negatives
  against Python's own formatting, and `test_negative_amounts_do_not_lose_a_cent_to_floor_division` pins the
  -$12,500.50 case.
- **Suggested for M13:** `divmod`, `trunc`/`int`, or a truncating operator, and a sentence in the language reference
  that says which way `//` goes.
- **Probe:** `tests/test_gaps.py` `test_G045_*`.

## G-046 No date support at all - FRICTION (M13)
- **Tried:** `parse_date`, `parse_time`, `date`, `datetime`, `strptime`, `days_in_month`, `is_leap`: all `undefined name`.
  `format_time(t, fmt)` turns a timestamp into text but nothing turns text into a date. `max("2025-01-02",
  "2025-01-01")` and `min` fail with `max() needs a number, but got a string`. What **does** work: `<` and `>` on text,
  and ISO `YYYY-MM-DD` sorts correctly as text.
- **Workaround (program):** `is_date` checks length 10, the two dashes, digits, month 1-12, year >= 1 and the day against a
  table of month lengths with a hand-written leap-year rule (`4`, not `100`, unless `400`). The first and last
  date are found with `<` and `>`. Checked against Python's `datetime` on every month end of eight years (including
  1900, 2100 and 2400, the century traps), `tests/test_units.py` `test_is_date_*`. That test found a real bug in the
  first draft: it accepted year `0000`.
- **Suggested for M13:** `parse_date(text)` returning a number of days (or a record), with `nil`/an error for an
  impossible day; `max`/`min` on text.
- **Probe:** `tests/test_gaps.py` `test_G046_*`.

## G-047 No CSV reader, and `split_lines` cuts a quoted newline in two - FRICTION (M13)
- **Tried:** `csv`, `parse_csv`, `read_csv`, `csv_split`, `split_csv`: all `undefined name`. `split(line, ",")` is right for a
  plain row and wrong the moment a field is quoted (`"Costco, Inc."`) or holds a doubled quote (`"The ""Corner"" Cafe"`).
  A quoted field may also contain a newline, and `split_lines` (the only way to get lines) has already cut the record in two:
  `split_lines("a,\"two\nlines\",b\nc,d,e")` has **3** pieces for 2 records.
- **Workaround (program):** `parse_fields` has a fast path (no quote on the line: one `split`) and a slow path that walks
  the line with `split`/`join` on a quote-by-quote basis (a per-character loop was measured at 346 microseconds a
  row; this is 85). A line with an odd number of quotes is **glued** to the next lines until the quotes balance, **but at
  most 8 lines**, so one stray quote costs one row, not the rest of the file (`test_a_stray_quote_costs_one_row`).
  Anything dubious (a quote mid-field, text after a closing quote, a row with the wrong number of fields) is
  **rejected and listed with its line number**, never guessed. Fuzzed against Python's `csv` module (strict) in
  `tests/test_units.py` and 40 random files in `tests/test_data.py`.
- **Not handled:** a quoted field that legitimately spans more than 9 lines is rejected.
- **Suggested for M13:** `csv.parse(text)` returning rows (quoted fields, doubled quotes, embedded newlines), like
  `json.loads` already does for JSON.
- **Probe:** `tests/test_gaps.py` `test_G047_*`.

## G-048 Small floats print as `1e-07` and cannot be read back; no exponent literal - TRAP (M13)
- **Tried:** `str(0.0000001)` is `1e-07`, `0.00000001` prints `1e-08`, `0.00001` prints `1e-05`; but a big float never
  switches: `1000000.0 * 1000000.0 * 1000000.0` prints `1000000000000000000`, and a float product near 1.5e16 prints
  every digit of the float's value (`15241578750190520`, where the true product ends in 1). `num("1e-07")`, `num("1e3")` and `num("1E5")` all throw (G-039), and
  the literal `1e3` is a syntax error (`found 'e3'`). So `num(str(x))` **fails** for a small `x`: a program cannot
  save a float it computed and read it back.
- **Where it bit:** the precision check wanted to show "float error 8e-09 dollars". `str()` gave exponent form; the program prints
  the error as fixed-point text built from integers (`$0.000000008`) instead.
- **Workaround (program):** never `str()` a float that might be small; build the text from integers (`floor(x * 10^9)`).
- **Suggested for M13:** accept exponent text in `num()` and in literals, and give `str()` one rule.
- **Probe:** `tests/test_gaps.py` `test_G048_*`.

## G-049 No `+=`, no conditional expression, and `and`/`or` return only true or false - minor (M13)
- **Tried:** `x += 1` is `unexpected '='`; `true ? 1 : 2` is `unexpected character '?'`; `1 if true else 2` is
  `found 'if'`; `true and "y"` is `the right side of 'and' must be true or false, but it is a string`. So the usual
  idioms for "1 record" / "2 records", for a default (`a or b`) and for a counter all take an `if` or a helper.
- **Workaround (program):** `counted(n, one, many)` for plurals; `x = x + 1` everywhere (about 40 times).
- **Suggested for M13:** compound assignment, and either a conditional expression or value-returning `and`/`or`.
- **Probe:** `tests/test_gaps.py` `test_G049_*`.

## G-050 `replace_all` needs the `regex` capability - FRICTION (M13)
- **Tried:** under `--profile restricted`, `replace_all("a-b-c", "-", "+")` is `undefined name 'replace_all'`; with
  `--allow-regex` or on `trusted` it works. It is a plain substring replacement with no pattern in it, filed with
  the regex functions (`novalang.py` groups it with `regex`). It was discovered by running the sandbox
  tests: the first draft used it and every restricted run died with that error. (Nova_Sort G-029: a program cannot ask
  which names it was given, so it cannot choose between `replace_all` and a fallback at run time either.)
- **Workaround (program):** `join(split(text, old), new)`, which is available everywhere, in `one_line`.
- **Suggested for M13:** move `replace_all` out of `regex`, or document the grouping.
- **Probe:** `tests/test_gaps.py` `test_G050_*` (the three profiles, and the workaround).

---

## The ceiling: what the `restricted` profile can do with default limits
Measured with the program as it is, on the VM, an Apple M1, all limits at their defaults (nothing raised):

| Rows | Characters | Result |
| --- | --- | --- |
| 10,000 (the sample) | 397,577 | **ok, about 2 s** (the headline run, in the tests) |
| 20,000 | 795,923 | ok, 4.07 s of the 5 s budget |
| 25,000 | 996,365 | ok, but **4.94 s of 5 s**: one slow moment from failing |
| 26,000 | 1,036,183 | **refused**: `a string cannot grow beyond 1000000 characters` (G-036) |

The same 26,000-row file runs on the `trusted` profile in 4.4 s and matches the oracle. The two sandbox limits arrive at almost
the same size for this program (the string limit at about 25,100 rows, and the 5 s time limit at about the same
point on this machine), so there is no safe margin above about **20,000 rows**. That is G-036 and G-042 again, not new
gaps; the 25,000-row point is **measured and reported, not pinned** in a test (it would be flaky). What is pinned:
26,000 rows is refused and one character decides the 1,000,000 boundary (`tests/test_sandbox.py` `Ceiling`).

On the **self-hosted engine** the sandbox is far tighter: about 50 records a second (about 100 times slower than the VM here),
so the 5 s budget ends at roughly **250 rows**. 100 rows run in 2 s; 600 rows die with `LimitError: time limit of 5000 ms exceeded`
(`test_G042_*`). A statement-count limit would give the same answer on every engine (G-042).

---

## What worked (no entry needed)
- **Integers are exact, and that is enough.** With them, `parse_cents` / `money` / `div_round` are exact at any size, and a Python
  `Decimal` oracle agrees on every report number (the whole report, number by number, on the sample and on 40 fuzzed files).
- **The restricted sandbox does what it says for a read-only program.** `--allow-read DIR --allow-process` is the whole
  grant: `write`, `remove`, `rename`, `copy` and `mkdir` do not exist (`undefined name`), `append(path, ...)` fails with
  `the 'files.write' capability is not granted`, a path that climbs out of `DIR` is refused, and the CSV is byte-for-byte
  unchanged after every run (`tests/test_sandbox.py` `ReadOnly`, compared by SHA-256).
- **`split`, slicing, `join` and `in` carry a CSV parser** with quoting, once the fast path and the slow path are separate.
- **Unicode works.** `█▏▎▍▌▋▊▉` bars, `·`, `━`, `─`, `…` and accented category names pass through `pad`, `len` and slicing. What
  does **not** work is colour: there is still no way to write an ESC (G-004), so the report is monochrome.
- **The three engines agree.** The VM, the tree-walker (`--tree-walk`) and the self-hosted interpreter print the same report
  on the same file (the comparison is part of `tests/test_data.py`).
