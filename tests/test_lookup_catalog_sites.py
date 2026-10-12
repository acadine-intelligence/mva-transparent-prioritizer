"""Invented VCF records only: direct lookup and content-free refusal contract."""
import io
import csv
import json
import stat
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from tests.test_select_candidates import entry

ROOT = Path(__file__).resolve().parents[1]
KEY = ("1", 1000, "A", "G")
HEADER = ('##fileformat=VCFv4.2\n##contig=<ID=chr1,length=100000>\n'
          '#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSYN_SAMPLE\n')


def record(chrom="chr1", pos=1000, ref="A", alt="G", gt="0/1"):
    return f"{chrom}\t{pos}\t.\t{ref}\t{alt}\t50\tPASS\t.\tGT:DP\t{gt}:20\n"


class ParserTest(unittest.TestCase):
    def parse(self, text):
        from mva_prioritizer.catalog_lookup import parse_records
        return parse_records(text, KEY)

    def test_exact_and_multi_alt_carried_allele(self):
        for chrom in ("1", "chr1"):
            self.assertEqual(self.parse(record(chrom=chrom)), "0/1")
        self.assertEqual(self.parse(record(alt="C,G", gt="0/2")), "0/2")
        for gt in ("1", "1|0", "1/1", "./1", "0/1/0"):
            self.assertEqual(self.parse(record(gt=gt)), gt)

    def test_nonmatches(self):
        for text in ("", record(alt="C"), record(ref="T"), record(pos=999),
                     record(chrom="2"), record(alt="C,G", gt="0/1")):
            self.assertIsNone(self.parse(text))
        for gt in ("0/0", "./.", "0|0", ".", "0", "0/."):
            self.assertIsNone(self.parse(record(gt=gt)))

    def test_breakend_alts_beside_catalog_allele(self):
        # Review of d3ce4c0: valid breakend ALTs must not abort the lookup.
        self.assertEqual(self.parse(record(alt="G,A]2:2000]", gt="0/1")), "0/1")
        self.assertEqual(self.parse(record(alt="A.,G", gt="0/2")), "0/2")
        self.assertEqual(self.parse(record(alt="[2:2000[A,G", gt="0/2")), "0/2")
        self.assertIsNone(self.parse(record(alt="G,A]2:2000]", gt="0/2")))
        self.assertIsNone(self.parse(record(alt="A.", gt="0/1")))

    def test_malformed_breakends_refused(self):
        # Delta review of 3af1760: mismatched brackets and bad mate loci must refuse.
        from mva_prioritizer.bounded_input import InputRejected
        for alt in ("G,A[2:2000]", "G,A]not-a-locus]", "G,[2:xyz[A", "G,A]2:01]", "G,A]2:2000[", "G,A]]"):
            with self.subTest(alt=alt):
                with self.assertRaises(InputRejected):
                    self.parse(record(alt=alt, gt="0/1"))
        self.assertEqual(self.parse(record(alt="G,A]<ctg1>:5]", gt="0/1")), "0/1")
        # Delta review of 56a691c: VCF 4.2 telomeric mates sit at position 0.
        self.assertEqual(self.parse(record(alt="G,A]2:0]", gt="0/1")), "0/1")
        self.assertEqual(self.parse(record(alt="G,[2:0[A", gt="0/1")), "0/1")

    def test_malformed_records_refused(self):
        for text in ("bad\n", record().replace("\t1000\t", "\t1.5\t"),
                     record().replace("\tGT:DP\t", "\tDP\t"),
                     record().replace("\tGT:DP\t", "\tGT:GT\t"),
                     record().rstrip() + "\tSECOND_SAMPLE\n", record(alt="G,G"),
                     record(gt="0/2"), record(gt="-1/1"), record(gt="0//1"),
                     record(gt="x"), record(gt=""), record() + record()):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    self.parse(text)


class LookupRunnerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.out = self.root / "output"
        self.vcf = self.root / "synthetic input;literal.vcf.gz"
        self.vcf.write_bytes(b"synthetic: fake bcftools supplies header and records")
        self.catalog = self.root / "catalog.json"
        self.catalog.write_text(json.dumps([entry()]))
        self.fake = self.root / "fake bcftools"
        self.calls = self.root / "calls.jsonl"
        self.configure()

    def configure(self, records=None, header=HEADER, fail=False):
        self.fake.write_text(f'''#!{sys.executable}
import json, sys
from pathlib import Path
args = sys.argv[1:]
with Path({str(self.calls)!r}).open('a') as f:
    f.write(json.dumps(args) + '\\n')
if {fail!r}:
    print('SYN_SECRET chr1:1000 path', file=sys.stderr)
    sys.exit(7)
if args[:2] == ['view', '-h']:
    sys.stdout.write({header!r})
elif args[:3] == ['view', '-H', '-r']:
    sys.stdout.write({(record() if records is None else records)!r})
else:
    sys.exit(8)
''')
        self.fake.chmod(0o700)

    def run_cli(self, *extra):
        return subprocess.run([sys.executable, str(ROOT / 'scripts/lookup_catalog_sites.py'),
                               '--vcf', str(self.vcf), '--catalog', str(self.catalog),
                               '--out', str(self.out), '--bcftools', str(self.fake), *extra],
                              capture_output=True, text=True, timeout=20)

    def assert_refused(self, proc):
        self.assertEqual((proc.returncode, proc.stdout, proc.stderr),
                         (2, '', 'catalog lookup refused\n'))
        self.assertFalse(self.out.exists())

    def test_lookup_exact_counts_privacy_and_argv(self):
        null = entry(); null['grch38'] = None
        low = entry(pos=2000, confidence='low')
        counted = entry(); counted['mechanism'] = 'regulatory'
        self.catalog.write_text(json.dumps([counted, null, low]))
        proc = self.run_cli()
        self.assertEqual((proc.returncode, proc.stderr), (0, ''))
        summary_text = (self.out / 'lookup-summary.json').read_text()
        summary = json.loads(summary_text)
        self.assertEqual(json.loads(proc.stdout), summary)
        self.assertEqual(len(proc.stdout.splitlines()), 1)
        self.assertEqual({k: summary[k] for k in ('entries_counted', 'null_skipped', 'looked_up', 'matched')},
                         dict(entries_counted=1, null_skipped=1, looked_up=1, matched=1))
        self.assertEqual(summary['matched_by_mechanism_class']['regulatory'], 1)
        self.assertEqual(sum(summary['matched_by_mechanism_class'].values()), 1)
        for token in ('SYN1', 'chr1', '1000', str(self.root), 'genotype', 'variant'):
            self.assertNotIn(token, summary_text + proc.stdout)
        self.assertEqual(stat.S_IMODE(self.out.stat().st_mode), 0o700)
        self.assertEqual(json.loads((self.out / 'matches.json').read_text()),
                         [{'variant': list(KEY), 'genotype': '0/1', 'gene': 'SYN1'}])
        calls = [json.loads(line) for line in self.calls.read_text().splitlines()]
        self.assertEqual(calls, [['view', '-h', '--', str(self.vcf)],
                                ['view', '-H', '-r', 'chr1:1000-1000', '--', str(self.vcf)]])

    def test_unprefixed_vcf_and_second_alt(self):
        self.catalog.write_text(json.dumps([entry(chrom='chr1')]))
        self.configure(record(chrom='1', alt='C,G', gt='0/2'), HEADER.replace('ID=chr1', 'ID=1'))
        proc = self.run_cli()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)['matched'], 1)
        self.assertIn('1:1000-1000', self.calls.read_text())
        self.assertEqual(json.loads((self.out / 'matches.json').read_text())[0]['genotype'], '0/2')

    def test_zero_matches(self):
        self.configure(record(alt='C'))
        proc = self.run_cli()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)['matched'], 0)
        self.assertEqual(json.loads((self.out / 'matches.json').read_text()), [])

    def test_each_counted_entry_queries_even_at_same_position(self):
        second = entry(confidence='medium'); second['grch38']['alt'] = 'C'
        self.catalog.write_text(json.dumps([entry(), second]))
        self.configure(record(alt='G,C', gt='1/2'))
        proc = self.run_cli()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        summary = json.loads(proc.stdout)
        self.assertEqual((summary['entries_counted'], summary['looked_up'], summary['matched']), (2, 2, 2))
        self.assertEqual(len(self.calls.read_text().splitlines()), 3)

    def test_mitochondrial_alias_mapping(self):
        from mva_prioritizer.catalog_lookup import parse_header, parse_records
        for name in ('M', 'MT', 'chrM', 'chrMT'):
            self.assertEqual(parse_header(HEADER.replace('ID=chr1', 'ID=' + name)), {'MT': name})
            self.assertEqual(parse_records(record(chrom=name), ('MT', 1000, 'A', 'G')), '0/1')

    def test_lookup_to_selection_journey_and_empty_replay(self):
        from scripts import build_candidate_pool
        from tests.test_candidate_pool import AUDIT_CORE, write_fixture
        fixture = self.root / 'fixture'; fixture.mkdir()
        (fixture / 'audit_core.py').write_text(AUDIT_CORE)
        write_fixture(fixture)
        build_candidate_pool.build(fixture, self.root / 'pool', fixture / 'audit_core.py')
        self.catalog.write_text(json.dumps([entry(pos=45000)]))
        self.configure(record(pos=45000, alt='C,G', gt='0/2'))
        self.assertEqual(self.run_cli().returncode, 0)
        command = [sys.executable, str(ROOT / 'scripts/select_candidates.py'), '--pool',
                   str(self.root / 'pool/pool.json'), '--catalog', str(self.catalog)]
        selected = self.root / 'selected'
        proc = subprocess.run(command + ['--extra-candidates', str(self.out / 'matches.json'),
                                        '--out', str(selected)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)['catalog_direct_added'], 1)
        from mva_prioritizer.track1_submission import parse_submission
        parsed = parse_submission((selected / 'submission.csv').read_text(), allow_repeated_pairings=True)
        self.assertTrue(any(r.variants == frozenset({('chr1', 1000, 'A', 'G'),
                                                    ('chr1', 45000, 'A', 'G')}) for r in parsed.rows))
        baseline = self.root / 'baseline'
        proc = subprocess.run(command + ['--out', str(baseline)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.out = self.root / 'empty-lookup'
        self.configure(record(pos=45000, gt='0|0'))
        self.assertEqual(self.run_cli().returncode, 0)
        replay = self.root / 'empty-replay'
        proc = subprocess.run(command + ['--extra-candidates', str(self.out / 'matches.json'),
                                        '--out', str(replay)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual((baseline / 'submission.csv').read_bytes(), (replay / 'submission.csv').read_bytes())

    def test_mechanism_free_text_never_echoed(self):
        item = entry(); item['mechanism'] = 'SYN1 chr1:1000 /secret/path'
        self.catalog.write_text(json.dumps([item]))
        proc = self.run_cli()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn(item['mechanism'], proc.stdout)
        self.assertEqual(json.loads(proc.stdout)['matched_by_mechanism_class']['other'], 1)

    def test_subprocess_failure_and_malformed_record_leave_no_output(self):
        self.configure(fail=True)
        self.assert_refused(self.run_cli())
        self.configure('SYN_SECRET malformed record\n')
        self.assert_refused(self.run_cli())

    def test_invalid_header_catalog_arguments_and_executable(self):
        for header in ('', HEADER.replace('SYN_SAMPLE', 'SYN_SAMPLE\tSECOND'),
                       HEADER.replace('#CHROM', '##contig=<ID=1>\n#CHROM')):
            self.configure(header=header)
            self.assert_refused(self.run_cli())
        self.configure()
        self.assert_refused(self.run_cli('--private-secret'))
        self.assert_refused(self.run_cli('--bcftools', str(self.root / 'missing')))
        self.catalog.write_text('[{"gene":"SYN1","gene":"SYN2"}]')
        self.assert_refused(self.run_cli())

    def test_existing_output_untouched(self):
        self.out.mkdir(); marker = self.out / 'keep'; marker.write_text('keep')
        proc = self.run_cli()
        self.assertEqual((proc.returncode, proc.stdout, proc.stderr), (2, '', 'catalog lookup refused\n'))
        self.assertEqual(list(self.out.iterdir()), [marker])
        self.assertEqual(marker.read_text(), 'keep')

    def test_runtime_errors_are_quiet_and_partial_writes_removed(self):
        from scripts import lookup_catalog_sites as runner
        for error in (OSError('private'), ValueError('private'), csv.Error('private'),
                      json.JSONDecodeError('private', 'secret', 0), subprocess.TimeoutExpired('private', 1)):
            with patch.object(runner, 'lookup_sites', side_effect=error):
                stdout, stderr = io.StringIO(), io.StringIO()
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    code = runner.main(['--vcf', str(self.vcf), '--catalog', str(self.catalog),
                                        '--out', str(self.out), '--bcftools', str(self.fake)])
                self.assertEqual((code, stdout.getvalue(), stderr.getvalue()),
                                 (2, '', 'catalog lookup refused\n'))
        original = Path.open
        def fail_summary(path, *args, **kwargs):
            if path.name == 'lookup-summary.json':
                raise OSError('private write error')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'open', fail_summary):
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = runner.main(['--vcf', str(self.vcf), '--catalog', str(self.catalog),
                                    '--out', str(self.out), '--bcftools', str(self.fake)])
        self.assertEqual(code, 2)
        self.assertFalse(self.out.exists())


if __name__ == '__main__':
    unittest.main()
