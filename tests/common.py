"""Shared helpers: an independent Python oracle (csv module + decimal), a runner for nova_data.nova on any engine and
profile, and a reader that turns the printed report back into numbers."""
import csv, datetime, decimal, io, os, re, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOVA = os.path.join(ROOT, "novalang", "novalang.py")
PROGRAM = os.path.join(ROOT, "nova_data.nova")
MAKE_CSV = os.path.join(ROOT, "tools", "make_csv.py")
SAMPLE = os.path.join(ROOT, "data", "transactions.csv")
Decimal = decimal.Decimal

BAR_WIDTH = 20  # must equal BAR_WIDTH in nova_data.nova
EIGHTHS = ["", "▏", "▎", "▍", "▌", "▋", "▊", "▉"]

# ---------------------------------------------------------------------------------------------------------------
# The oracle. It follows the same RULES as the program (documented in the README) but shares no code and no method:
# the csv module does the quoting, a regular expression does the money syntax, decimal.Decimal does the sums.
# ---------------------------------------------------------------------------------------------------------------
_PLAIN = r"[-+]?\$?(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]{1,2})?"  # [0-9], not \d: \d matches Arabic-Indic digits too
MONEY = re.compile(r"^(?:\((?P<paren>%s)\)|(?P<plain>%s))$" % (_PLAIN, _PLAIN))


def oracle_cents(raw):
    """Money text -> integer cents, or None. 12 12.5 12.50 -12.50 +12.50 $12.50 -$12.50 (12.50) 1,250.50."""
    text = raw.strip(" ")
    m = MONEY.match(text)
    if not m:
        return None
    inner = m.group("paren") or m.group("plain")
    negative = bool(m.group("paren")) or inner.startswith("-")
    digits = inner.lstrip("+-").lstrip("$").replace(",", "")
    whole, _, frac = digits.partition(".")
    if len(whole) > 12:
        return None
    cents = int(whole) * 100 + int((frac + "00")[:2])
    return -cents if negative else cents


def oracle_date(text):
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", text):
        return False
    try:
        datetime.date.fromisoformat(text)
        return True
    except ValueError:
        return False


class Result:
    pass


def oracle(text):
    """Read CSV text the Python way. -> Result with the numbers the report must show."""
    r = Result()
    r.records = r.valid = r.rejected = r.blank = r.charge_n = r.refund_n = 0
    r.count, r.net, r.charges, r.refunds = {}, {}, {}, {}
    r.largest = r.refund = None  # (cents, date, description, category, line)
    r.first = r.last = ""
    r.rejects = []  # (line, text)
    if text.startswith("﻿"):
        text = text[1:]
    lines = io.StringIO(text, newline="").readlines()
    reader = csv.reader(iter(lines), strict=True)
    header = None
    previous_end = 0
    while True:
        try:
            row = next(reader)
            error = None
        except StopIteration:
            break
        except csv.Error as e:
            row, error = None, str(e)
        start = previous_end + 1
        previous_end = reader.line_num
        if error is None and (not row or (len(row) == 1 and row[0].strip() == "")):
            r.blank += 1
            continue
        if header is None:
            if error is not None:
                raise ValueError("oracle: bad header")
            header = [h.strip().lower() for h in row]
            cols = {n: header.index(n) for n in ("date", "description", "amount", "category")}
            continue
        r.records += 1
        if error is not None or len(row) != len(header):
            r.rejected += 1
            r.rejects.append((start, error or "fields"))
            continue
        date = row[cols["date"]].strip()
        cents = oracle_cents(row[cols["amount"]])
        if not oracle_date(date) or cents is None:
            r.rejected += 1
            r.rejects.append((start, "date" if not oracle_date(date) else "amount"))
            continue
        r.valid += 1
        cat = row[cols["category"]].strip() or "Uncategorized"
        desc = row[cols["description"]].strip().replace("\r", " ").replace("\n", " ")
        r.first = date if not r.first or date < r.first else r.first
        r.last = date if not r.last or date > r.last else r.last
        r.count[cat] = r.count.get(cat, 0) + 1
        r.net[cat] = r.net.get(cat, 0) + cents
        r.charges.setdefault(cat, 0)
        r.refunds.setdefault(cat, 0)
        if cents >= 0:
            r.charge_n += 1
            r.charges[cat] += cents
            if cents > 0 and (r.largest is None or cents > r.largest[0]):  # the program keeps the first of equals
                r.largest = (cents, date, desc, cat, start)
        else:
            r.refund_n += 1
            r.refunds[cat] += cents
            if r.refund is None or cents < r.refund[0]:
                r.refund = (cents, date, desc, cat, start)
    r.grand = sum(r.net.values())
    r.charge_total = sum(r.charges.values())
    r.refund_total = sum(r.refunds.values())
    return r


def oracle_file(path):
    with open(path, encoding="utf-8", newline="") as f:
        return oracle(f.read())


def money(cents):
    """The text a person expects: -$1,250.50. Python's own formatting, not the program's."""
    sign = "-" if cents < 0 else ""
    return "%s$%s.%02d" % (sign, format(abs(cents) // 100, ","), abs(cents) % 100)


def half_up(numerator, denominator):
    """numerator / denominator rounded half away from zero, exactly (Decimal, no floats)."""
    q = (Decimal(numerator) / Decimal(denominator)).quantize(Decimal(1), rounding=decimal.ROUND_HALF_UP)
    return int(q)


def percent(part, whole):
    if whole <= 0:
        return "-"
    tenths = half_up(part * 1000, whole)
    sign = "-" if tenths < 0 else ""
    tenths = abs(tenths)
    return "%s%d.%d%%" % (sign, tenths // 10, tenths % 10)


def bar(value, biggest):
    if value <= 0 or biggest <= 0:
        return ""
    eighths = max(1, half_up(value * BAR_WIDTH * 8, biggest))
    return "█" * (eighths // 8) + EIGHTHS[eighths % 8]


def expected_order(r):
    """Biggest net total first, alphabetical on a tie."""
    return sorted(r.net, key=lambda name: (-r.net[name], name))


# ---------------------------------------------------------------------------------------------------------------
# Running the program and reading the report back
# ---------------------------------------------------------------------------------------------------------------
def run(path, engine="vm", profile=None, process=True, clock=True, read_dir=None, extra=(), cwd=None, timeout=900):
    """Run nova_data.nova on `path`. engine: vm | tree | bootstrap (self-hosted, CLI only).
    profile=None is the CLI default (trusted); "restricted" grants read access to one folder and nothing else."""
    args = [sys.executable, NOVA]
    if engine == "tree":
        args += ["--tree-walk"]
    if profile == "restricted":
        args += ["--profile", "restricted", "--allow-read", read_dir or os.path.dirname(os.path.abspath(path))]
        if process:
            args += ["--allow-process"]
        if clock:
            args += ["--allow-clock"]
        args += list(extra)
    if engine == "bootstrap":
        args += ["--bootstrap"]  # must come last before the program (G-034 in Nova_Sort)
    args += [PROGRAM, path]
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, cwd=cwd)


AMOUNT = r"-?\$[\d,]+\.\d\d"
ROW = re.compile(r"^  (?P<name>\S.*?)[ ]+(?P<n>[\d,]+)[ ]+(?P<total>%s)[ ]+(?P<avg>%s)[ ]+(?P<share>-?\d+\.\d%%|-)(?:[ ]+(?P<bar>\S+))?[ ]*$" % (AMOUNT, AMOUNT), re.M)
SUMMARY = re.compile(r"^  ([\d,]+) records?: ([\d,]+) read, ([\d,]+) rejected(?:, ([\d,]+) blank lines? skipped)?$", re.M)
DASHES = "─" * 78


def num(text):
    return int(text.replace(",", ""))


def cents(text):
    sign = -1 if text.startswith("-") else 1
    return sign * int(re.sub(r"[^\d]", "", text))


def parse(output):
    """Read the printed report back into numbers (cents, counts) and strings."""
    p = Result()
    m = SUMMARY.search(output)
    p.records, p.valid, p.rejected, p.blank = (num(m.group(1)), num(m.group(2)), num(m.group(3)), num(m.group(4) or "0")) if m else (None,) * 4
    section = output.split("SPENDING BY CATEGORY")[1].split("TOTAL")[0] if "SPENDING BY CATEGORY" in output else ""
    p.rows = [(m.group("name"), num(m.group("n")), cents(m.group("total")), cents(m.group("avg")), m.group("share"), m.group("bar") or "")
              for m in ROW.finditer(section)]
    total = re.search(r"^  TOTAL +([\d,]+) +(%s) +(%s) +100\.0%%$" % (AMOUNT, AMOUNT), output, re.M)
    p.total = (num(total.group(1)), cents(total.group(2)), cents(total.group(3))) if total else None
    for label, key in (("Charges", "charges"), ("Refunds", "refunds")):
        m = re.search(r"^  %s +(%s)   in ([\d,]+) transactions?$" % (label, AMOUNT), output, re.M)
        setattr(p, key, (cents(m.group(1)), num(m.group(2))) if m else None)
    for label, key in (("Charge", "largest"), ("Refund", "refund")):
        m = re.search(r"^  %s +(%s)   (.*)\n {20,}(.*?)  ·  (\d{4}-\d\d-\d\d)  ·  line ([\d,]+)$" % (label, AMOUNT), output, re.M)
        setattr(p, key, (cents(m.group(1)), m.group(4), m.group(2), m.group(3), num(m.group(5))) if m else None)
    m = re.search(r"^  (\d{4}-\d\d-\d\d)  to  (\d{4}-\d\d-\d\d)   ·   ([\d,]+) categor(?:y|ies)$", output, re.M)
    p.first, p.last, p.categories = (m.group(1), m.group(2), num(m.group(3))) if m else (None, None, None)
    m = re.search(r"REJECTED RECORDS  \(first (\d+) of ([\d,]+)\)\n.*\n((?:  line .*\n?)+)", output)
    p.reject_lines = [(num(a), b) for a, b in re.findall(r"^  line ([\d,]+): (.*)$", m.group(3), re.M)] if m else []
    return p


def write(directory, name, data):
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(data)
    return path


def make_synthetic(directory, rows, name="synthetic.csv"):
    path = os.path.join(directory, name)
    subprocess.run([sys.executable, MAKE_CSV, path, str(rows)], check=True, capture_output=True)
    return path


def tempdir():
    return tempfile.mkdtemp(prefix="nova_data_test_")


def cleanup(path):
    shutil.rmtree(path, ignore_errors=True)
