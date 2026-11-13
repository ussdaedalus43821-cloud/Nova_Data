"""The restricted profile: read-only access to the CSV, the default limits, and where those limits end.

Nothing here raises a limit to make a test pass: every restricted run uses the DEFAULT limits."""
import hashlib, os, stat, subprocess, sys, unittest

from tests import common as c


def digest(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


class Restricted(unittest.TestCase):
    def setUp(self):
        self.dir = c.tempdir()
        self.addCleanup(c.cleanup, self.dir)

    def test_the_sample_is_well_under_the_string_limit(self):
        with open(c.SAMPLE, encoding="utf-8", newline="") as f:
            self.assertLess(len(f.read()), 1000000)

    def test_ten_thousand_rows_with_default_limits_match_the_oracle(self):
        done = c.run(c.SAMPLE, profile="restricted")
        self.assertEqual(done.returncode, 0, done.stderr + done.stdout)
        want = c.oracle_file(c.SAMPLE)
        got = c.parse(done.stdout)
        self.assertEqual((got.valid, got.rejected, got.total[1]), (want.valid, want.rejected, want.grand))
        self.assertEqual({r[0]: r[2] for r in got.rows}, want.net)
        self.assertIn("records/s", done.stdout)  # the clock was granted
        # the same bytes as the trusted run, apart from the timing line
        trusted = c.run(c.SAMPLE).stdout
        strip = lambda text: "\n".join(l for l in text.splitlines() if "records/s" not in l)
        self.assertEqual(strip(done.stdout), strip(trusted))

    def test_the_other_engines_in_the_sandbox_on_smaller_files(self):
        # the self-hosted engine does about 50 records a second here, so 100 rows is as many as it can do comfortably in 5 s (G-042)
        for engine, rows in (("tree", 300), ("bootstrap", 100)):
            path = c.make_synthetic(self.dir, rows, "%s.csv" % engine)
            with self.subTest(engine=engine):
                done = c.run(path, engine, profile="restricted")
                self.assertEqual(done.returncode, 0, done.stderr + done.stdout)
                self.assertEqual(c.parse(done.stdout).total[1], c.oracle_file(path).grand)

    def test_without_the_clock_grant_the_timings_are_left_out(self):
        path = c.make_synthetic(self.dir, 200)
        done = c.run(path, profile="restricted", clock=False)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn("records/s", done.stdout)
        self.assertEqual(c.parse(done.stdout).total[1], c.oracle_file(path).grand)

    def test_without_the_process_grant_the_file_name_cannot_arrive(self):
        # G-033 (Nova_Sort): `args` belongs to `process`
        done = c.run(c.SAMPLE, profile="restricted", process=False)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("undefined name 'args'", done.stderr + done.stdout)

    def test_a_file_outside_the_read_grant_is_refused(self):
        other = c.tempdir()
        self.addCleanup(c.cleanup, other)
        elsewhere = c.write(other, "elsewhere.csv", HEADER_ROW)
        done = c.run(elsewhere, profile="restricted", read_dir=self.dir)
        self.assertEqual(done.returncode, 1)
        self.assertIn("outside the folders this program may use", done.stdout)

    def test_the_program_runs_from_a_folder_it_could_not_write_to_anyway(self):
        ro = os.path.join(self.dir, "ro")
        os.mkdir(ro)
        path = c.write(ro, "t.csv", HEADER_ROW + "2025-01-01,x,1.00,A\n")
        os.chmod(ro, stat.S_IRUSR | stat.S_IXUSR)
        self.addCleanup(os.chmod, ro, stat.S_IRWXU)
        done = c.run(path, profile="restricted")
        self.assertEqual(done.returncode, 0, done.stderr + done.stdout)


HEADER_ROW = "Date,Description,Amount,Category\n"


class ReadOnly(unittest.TestCase):
    """The grant is read-only: a program that tries to change the CSV, or anything beside it, is refused."""

    def setUp(self):
        self.dir = c.tempdir()
        self.addCleanup(c.cleanup, self.dir)
        self.csv = c.write(self.dir, "t.csv", HEADER_ROW + "2025-01-01,x,1.00,A\n")
        self.before = digest(self.csv)

    def attempt(self, statement):
        path = c.write(self.dir, "attempt.nova", statement + "\n")
        done = subprocess.run([sys.executable, c.NOVA, "--profile", "restricted", "--allow-read", self.dir, path],
                              capture_output=True, text=True, timeout=60)
        return done.returncode, done.stdout + done.stderr

    def test_write_remove_rename_copy_and_mkdir_do_not_exist(self):
        csv = self.csv.replace("\\", "/")
        for name, statement in [("write", 'write("%s", "x")' % csv), ("remove", 'remove("%s")' % csv),
                                ("rename", 'rename("%s", "%s.old")' % (csv, csv)), ("copy", 'copy("%s", "%s.copy")' % (csv, csv)),
                                ("mkdir", 'mkdir("%s/sub")' % self.dir)]:
            with self.subTest(call=name):
                code, out = self.attempt(statement)
                self.assertNotEqual(code, 0)
                self.assertIn("undefined name '%s'" % name, out)
        self.assertEqual(digest(self.csv), self.before)

    def test_append_to_a_file_is_refused_with_a_capability_error(self):
        code, out = self.attempt('append("%s", "tampered")' % self.csv)
        self.assertNotEqual(code, 0)
        self.assertIn("the 'files.write' capability is not granted", out)
        self.assertEqual(digest(self.csv), self.before)

    def test_reading_is_allowed_and_a_path_that_climbs_out_is_not(self):
        code, out = self.attempt('print(len(read("%s")))' % self.csv)
        self.assertEqual((code, out.strip()), (0, str(len(HEADER_ROW + "2025-01-01,x,1.00,A\n"))))
        code, out = self.attempt('print(read("%s/../outside.txt"))' % self.dir)
        self.assertNotEqual(code, 0)
        self.assertIn("outside the folders this program may use", out)

    def test_the_real_program_leaves_the_file_byte_for_byte_alone(self):
        sample_before = digest(c.SAMPLE)
        c.run(c.SAMPLE, profile="restricted")
        self.assertEqual(digest(c.SAMPLE), sample_before)


class Ceiling(unittest.TestCase):
    """G-036: where the default limits end. A string stops at 1,000,000 characters and `read` is the only way in."""

    def setUp(self):
        self.dir = c.tempdir()
        self.addCleanup(c.cleanup, self.dir)

    def test_G036_a_csv_over_one_million_characters_is_refused_in_the_sandbox_and_read_whole_outside_it(self):
        path = c.make_synthetic(self.dir, 26000, "big.csv")  # 1,036,183 characters
        with open(path, encoding="utf-8", newline="") as f:
            self.assertGreater(len(f.read()), 1000000)
        done = c.run(path, profile="restricted")
        self.assertEqual(done.returncode, 1)
        self.assertIn("a string cannot grow beyond 1000000 characters", done.stdout)
        trusted = c.run(path)
        self.assertEqual(trusted.returncode, 0, trusted.stderr)
        self.assertEqual(c.parse(trusted.stdout).total[1], c.oracle_file(path).grand)

    def test_G042_the_self_hosted_engine_runs_out_of_time_in_the_sandbox_long_before_the_vm_does(self):
        # 600 rows: the VM needs about 0.1 s of the 5 s budget, the self-hosted engine about 12 s (not pinned to the row: it depends on the machine)
        path = c.make_synthetic(self.dir, 600, "slow.csv")
        self.assertEqual(c.run(path, profile="restricted").returncode, 0)
        done = c.run(path, "bootstrap", profile="restricted")
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("LimitError: time limit of 5000 ms exceeded", done.stdout + done.stderr)

    def test_G036_one_character_decides(self):
        # exactly 1,000,000 characters reads; one more does not (the same boundary as Nova_Log)
        filler = "x" * (1000000 - len(HEADER_ROW))
        ok = c.write(self.dir, "ok.csv", HEADER_ROW + filler[:-1] + "\n")
        over = c.write(self.dir, "over.csv", HEADER_ROW + filler + "\n")
        self.assertEqual(os.path.getsize(ok), 1000000)
        self.assertEqual(c.run(ok, profile="restricted").returncode, 0)
        self.assertEqual(c.run(over, profile="restricted").returncode, 1)


if __name__ == "__main__":
    unittest.main()
