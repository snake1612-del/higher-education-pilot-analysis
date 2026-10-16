"""Regression checks for independent BVI coverage and safe reruns; synthetic only."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from run_analysis import compare_results, execute


def fixture():
    row = dict(university='pilot',scope='cohort2023',metric='bvi',base_year=2022,
               end_year=2025,fixed_controls=False,min_bvi=0,groups_used=1,
               n0=100,n1=110,growth_pct=10,growth_gap_pp=5,
               bvi0=10,bvi1=12,share_gap_pp=0.5)
    main = dict(row,side='linked',bvi_share_gap_pp=row['share_gap_pp'])
    return dict(comparisons=[main],double_fixed=[],bvi_thresholds=[dict(row)]),[row]


class IndependentCoverageTests(unittest.TestCase):
    def test_main_and_threshold_zero_are_both_checked(self):
        sql,python = fixture()
        result = compare_results(sql,python)
        self.assertEqual(result['sql_rows_checked'],2)
        self.assertEqual(result['numeric_checks'],14)

    def test_corrupt_main_bvi_cannot_hide_behind_threshold_zero(self):
        for field in ('bvi1','bvi_share_gap_pp'):
            with self.subTest(field=field):
                sql,python = fixture()
                sql['comparisons'][0][field] += 1
                with self.assertRaisesRegex(AssertionError,'comparisons'):
                    compare_results(sql,python)

    def test_corrupt_threshold_zero_is_detected_separately(self):
        sql,python = fixture()
        sql['bvi_thresholds'][0]['bvi1'] += 1
        with self.assertRaisesRegex(AssertionError,'bvi_thresholds'):
            compare_results(sql,python)

    def test_missing_main_row_is_not_masked_by_threshold_row(self):
        sql,python = fixture()
        sql['comparisons'] = []
        with self.assertRaisesRegex(AssertionError,'Missing/extra SQL rows'):
            compare_results(sql,python)

    def test_duplicate_sql_keys_fail(self):
        sql,python = fixture()
        sql['comparisons'].append(copy.deepcopy(sql['comparisons'][0]))
        with self.assertRaisesRegex(AssertionError,'Duplicate SQL row'):
            compare_results(sql,python)


class RunStateTests(unittest.TestCase):
    def args(self,output):
        return SimpleNamespace(output=output,psql='psql',dsn='synthetic',
                               mkp=Path('synthetic.xlsx'),mev=None)

    def test_rerun_preserves_all_previous_files_and_never_prepares(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)/'run'
            (out/'inputs').mkdir(parents=True)
            (out/'inputs/input.csv').write_text('old input')
            (out/'validation.json').write_text('{"status":"pass","run_id":"old"}')
            before = {p.relative_to(out):p.read_bytes() for p in out.rglob('*') if p.is_file()}
            with patch('run_analysis.prepare') as prepare, patch('run_analysis.subprocess.run') as run:
                with self.assertRaisesRegex(ValueError,'empty or new'):
                    execute(self.args(out))
                prepare.assert_not_called()
                run.assert_not_called()
            after = {p.relative_to(out):p.read_bytes() for p in out.rglob('*') if p.is_file()}
            self.assertEqual(before,after)

    def test_existing_database_is_checked_before_any_file_write(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)/'run'
            with patch('run_analysis.prepare') as prepare, patch('run_analysis.subprocess.run',
                    return_value=SimpleNamespace(returncode=0,stdout='t\n')):
                with self.assertRaisesRegex(ValueError,'schemas already exist'):
                    execute(self.args(out))
                prepare.assert_not_called()
            self.assertFalse(out.exists())

    def test_partial_preparation_has_failed_status_and_no_pass(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)/'run'
            def fail(mkp,mev,private):
                self.assertEqual(json.loads((out/'validation.json').read_text())['status'],'running')
                private.mkdir()
                (private/'partial.csv').write_text('partial')
                raise ValueError('synthetic preparation failure')
            with patch('run_analysis.prepare',side_effect=fail), patch('run_analysis.subprocess.run',
                    return_value=SimpleNamespace(returncode=0,stdout='f\n')):
                with self.assertRaisesRegex(ValueError,'synthetic preparation failure'):
                    execute(self.args(out))
            state = json.loads((out/'validation.json').read_text())
            self.assertEqual(state['status'],'failed')
            self.assertEqual(state['error_type'],'ValueError')
            self.assertIn('finished_at',state)
            self.assertTrue(state['run_id'])

    def test_unreachable_database_creates_no_outputs(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)/'run'
            with patch('run_analysis.prepare') as prepare, patch('run_analysis.subprocess.run',
                    return_value=SimpleNamespace(returncode=1,stdout='')):
                with self.assertRaises(RuntimeError):
                    execute(self.args(out))
                prepare.assert_not_called()
            self.assertFalse(out.exists())


if __name__=='__main__':
    unittest.main()
