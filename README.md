# Nova_Data

> **Updated for NovaLang 2.3 (M13): money now goes through NovaLang's own `std:decimal` and `std:format` instead of hand-written integer-cent helpers; the report is byte for byte the same (see "Results").**
>
> **The fourth proof of concept for [NovaLang](https://github.com/ussdaedalus43821-cloud/Nova_Lang), after [Nova_Stats](https://github.com/ussdaedalus43821-cloud/Nova_Stats), [Nova_Sort](https://github.com/ussdaedalus43821-cloud/Nova_Sort) and [Nova_Log](https://github.com/ussdaedalus43821-cloud/Nova_Log).**
> A spending report from a CSV of financial transactions, written entirely in NovaLang: one program, no Python host,
> no regular expressions, and no imports but NovaLang's own standard modules. It tests **floating-point math and currency formatting**, in the **`restricted` sandbox**.

It reads `Date,Description,Amount,Category`, totals the spending per category, finds the largest single transaction and
prints a terminal report with dollar amounts (`$1,250.50`) and bar charts.

```bash
python3 novalang/novalang.py nova_data.nova data/transactions.csv
```

```
  NOVA_DATA  ·  data/transactions.csv
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  9,999 records: 9,993 read, 6 rejected, 1 blank line skipped
  2024-01-01  to  2025-12-31   ·   10 categories

  SPENDING BY CATEGORY  (net of refunds)
  ──────────────────────────────────────────────────────────────────────────────
  Category        Txns          Total    Average   Share  Bar
  Travel           333    $972,491.85  $2,920.40   43.6%  ████████████████████
  Rent             192    $387,710.00  $2,019.32   17.4%  ████████
  Shopping       1,384    $266,443.41    $192.52   11.9%  █████▌
  Groceries      2,378    $208,731.36     $87.78    9.4%  ████▎
  Health           500    $140,794.55    $281.59    6.3%  ██▉
  Dining         1,825     $88,231.83     $48.35    4.0%  █▉
  ...
  TOTAL          9,993  $2,231,316.93    $223.29  100.0%

  Charges  $2,266,143.33   in 9,714 transactions
  Refunds    -$34,826.40   in 279 transactions

  LARGEST SINGLE TRANSACTION
  Charge    $8,931.95   Marriott, Downtown
                        Travel  ·  2025-06-01  ·  line 7,129
  Refund   -$3,866.79   Marriott, Downtown (refund)
                        Travel  ·  2024-10-20  ·  line 4,077

  PRECISION CHECK
  exact sum (integer cents)     $2,231,316.93
  naive float sum, via str()    2231316.930000008
  float error                   $0.000000008 after 9,993 additions

  REJECTED RECORDS  (first 5 of 6)
  line 1,008: not a valid date (YYYY-MM-DD): 2025-02-29
  line 3,008: amount is not money: N/A
  ...
```

(Abridged. `python3 tools/make_csv.py OUT.csv [ROWS]` regenerates the sample byte for byte; `data/transactions.csv` is
committed because it is only 400 KB.)

Needs only Python 3 to start NovaLang.

## The one design rule: money is never a float

NovaLang has no decimal type, `round` is half-to-even (`round(0.125, 2)` is `0.12`), `str(5.0)` is `5`, and `//` rounds
toward minus infinity so `-1250050 // 100` is `-12501` ([`docs/GAPS.md`](docs/GAPS.md) G-043 to G-045). So:

1. An amount such as `"1,250.50"` is **checked by hand and read into an exact decimal** by `std:decimal`: sign, `$`,
   parentheses, thousands separators, one or two decimals are accepted or refused with a reason. More than two decimals is
   rejected, not rounded.
2. **Every sum is a decimal** (`dec.add`), exact at any size.
3. `money(amount)` is the only place an amount becomes text: sign off, `std:decimal` for the digits, `std:format`'s
   `grouped` for the commas.
4. Anything that must round (averages, percentages, bar widths) is `dec.div(..., "half_up")` with the places spelled
   out, never `round`.

Before NovaLang had `std:decimal` (it arrived in 2.3, M13 slice 2) this program read amounts into integer cents by hand
and divided with its own half-up routine: about 70 lines of helpers (`parse_cents`, `money`, `div_round`, `group_digits`,
`two_digits`). They are deleted; the report printed for the sample is **byte for byte the same** (compared with the output of
the previous version, apart from the timing line), and every test that compared it with the `decimal.Decimal` oracle still passes.
5. A naive **float** sum is kept on the side purely to be compared (the *Precision check*). On this file the error is
   $0.000000008 after 9,993 additions: tiny, and the point is that the exact figure does not depend on it.

Sign convention (a credit-card export): a charge is positive, a refund negative. *Spent* is the net of both; the
report also shows charges and refunds separately and the largest of each.

## What it accepts

| | |
| --- | --- |
| Columns | `Date`, `Description`, `Amount`, `Category` in **any order**, extra columns ignored, names case-insensitive, a BOM tolerated |
| Dates | `YYYY-MM-DD`, a real calendar day (leap years and month lengths checked by hand) |
| Amounts | `12`, `12.5`, `12.50`, `-12.50`, `+12.50`, `$12.50`, `-$12.50`, `(12.50)`, `"1,250.50"` |
| CSV | quoted fields, `""` for a quote, commas and **newlines inside quotes**, CRLF, blank lines, no final newline |
| Empty category | counted as `Uncategorized` |
| Anything else | the row is **rejected and listed with its line number**; the first five are shown. Nothing is guessed |

Rejected, deliberately: a fraction of a cent (`4.999`), a wrong number of fields (the classic unquoted comma in
`Costco, Inc.`), a quote in the middle of a field, text after a closing quote, an impossible date (`2025-02-29`).

## Sandbox use

The program only reads, and needs `process` (for `args()` and `exit`), plus `clock` for the timings if you grant it:

```bash
python3 novalang/novalang.py --profile restricted --allow-read data --allow-process --allow-clock nova_data.nova data/transactions.csv
```

That is the whole grant. Verified by the tests: `write`, `remove`, `rename`, `copy` and `mkdir` do not exist,
`append(path, ...)` fails with `the 'files.write' capability is not granted`, a path that climbs out of `data` is
refused, and the CSV is byte-for-byte unchanged afterwards (SHA-256 before and after).

### The ceiling (default limits, nothing raised)

| Rows | Result |
| --- | --- |
| 10,000 (the sample) | ok, about 2.9 s of the 5 s time limit |
| 15,000 | ok, 4.2 s |
| 20,000 | **refused**: `LimitError: time limit of 5000 ms exceeded` |
| 26,000 and up | **refused**: `LimitError: time limit of 5000 ms exceeded`. Before `std:files` this row died earlier, on `a string cannot grow beyond 1000000 characters` (G-036); the program now reads the file in pieces, so the string limit applies to each line only and the time limit is the ceiling |

So the sandbox can do **10,000 rows comfortably and about 15,000 at most** (it was about 20,000 with the hand-written cents: the
exact decimals cost about 50% more per row, the price of the library; the first, pure-NovaLang version of `std:decimal` made it
four times slower and was replaced by a native one for exactly this reason). On the self-hosted engine (`--bootstrap`)
the 5 s budget ends at roughly 250 rows (G-042). The 25,000-row figure is measured, not pinned in a test (it would be flaky).

## Results

| | |
| --- | --- |
| Tests | **82**, all green: 13 helper tests, 41 behaviour, 14 gap probes, 14 sandbox |
| Oracle | independent Python: the `csv` module (strict) and `decimal.Decimal`; every number in the report is compared |
| Engines | VM, tree-walker (`--tree-walk`) and self-hosted (`--bootstrap`) print the same report |
| Fuzz | 40 seeded random files of valid and invalid rows, plus hundreds of random amounts, dates and CSV lines per helper |
| Speed | 10,000 rows in about 1.8 s on the VM (about 5,700 records/s) |
| Gaps found | **8**, G-043 to G-050 |

The gaps, in short: `round` is half-to-even (G-043), no decimal type and floats drift (G-044, the central one),
`//` and `%` floor toward minus infinity so negative cents print wrong (G-045), no date support (G-046), no CSV
reader and `split_lines` cuts a quoted newline (G-047), small floats print as `1e-07` and cannot be read back (G-048), no
`+=` or conditional expression (G-049), and `replace_all` is locked behind the `regex` capability (G-050).
**How painful was the math?** Not very, once money stops being a float: integers are exact, and the cost is a 70-line
parser and a formatter ([G-044](docs/GAPS.md)). The traps are the ones that fail silently (G-043, G-045, G-048).
**No colour:** there is still no way to write an ESC character (G-004), so the report is monochrome.

## Layout

| Path | Role |
| --- | --- |
| `nova_data.nova` | the program: parse, total, format, report (about 650 lines) |
| `data/transactions.csv` | the sample: 10,000 rows, seeded, with a few bad rows on purpose |
| `tools/make_csv.py` | the seeded generator (the only thing here that needs Python besides the tests) |
| `tests/` | `test_units.py` helpers vs oracles, `test_data.py` whole reports vs the oracle, `test_gaps.py` gap probes, `test_sandbox.py` restricted runs and the ceiling |
| `docs/GAPS.md` | every gap found (G-043 to G-050) and what worked |
| `novalang/` | the interpreter, standard modules and the tool files it needs, copied unmodified from the NovaLang commit named in `novalang/VENDORED.md` |

## Test

```bash
python3 tests/run_suite.py       # about 90 s
```

## Limits

Amounts are USD-style text (`.` for decimals, `,` for thousands); another locale (`1.250,50`) is rejected. Categories are
matched exactly (`Groceries` and `groceries` are two). The whole file is held in memory (G-041 in Nova_Log), a quoted
field may span at most 9 lines, and a failure in the sandbox is all-or-nothing: the report is printed at the end, so a
time-limit stop prints nothing.

## Where it fits

Built as the precursor to NovaSteward.
