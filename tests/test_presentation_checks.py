"""Counterexamples for the additional claims on slides 6, 7 and 9."""
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from presentation_checks import donor_sensitivity, compare_extras
from run_analysis import compare_results


class PresentationTests(unittest.TestCase):
    def test_donor_filter_recomputes_counts_and_denominators(self):
        data = {}
        for y in range(2021,2026):
            data['pilot','small',y] = (100,2 if y==2022 else 10,None)
            data['pilot','large',y] = (200,20 if y==2022 else 40,None)
            for u in ('a','b','c'):
                for g in ('small','large'):
                    data[u,g,y] = (100,5,None)
        pools = {('small','bvi'):{'a'},('large','bvi'):{'a','b','c'}}
        rows,members = donor_sensitivity(data,{'pilot':{'small','large'}},pools)
        all_groups = next(r for r in rows if r['min_controls']==1)
        retained = next(r for r in rows if r['min_controls']==3)
        self.assertEqual((all_groups['n0'],all_groups['bvi0']),(300,22))
        self.assertEqual((retained['n0'],retained['bvi0'],retained['bvi1']),(200,20,40))
        self.assertAlmostEqual(retained['share_gap_pp'],10)
        self.assertEqual([m['major_group'] for m in members if m['min_controls']==3],['large'])
        self.assertFalse(any(r['min_controls']==5 for r in rows))

    def test_other_observed_score_components_are_verified(self):
        python,sql = [],dict(comparisons=[],double_fixed=[],bvi_thresholds=[])
        for side,change,background in [('linked',2,0.5),('other_observed',-1,0.6)]:
            row = dict(university='pilot',scope='cohort2023',side=side,metric='score',
                base_year=2022,end_year=2025,fixed_controls=False,min_bvi=0,groups_used=1,
                n0=100,n1=100,growth_pct=0,growth_gap_pp=0,score_gap=change-background,
                own_score_change=change,reference_score_change=background)
            python.append(row)
            sql['comparisons'].append(dict(row,ege_fixed_gap=row['score_gap'],
                ege_fixed_change=change,reference_ege_fixed_change=background))
        self.assertEqual(compare_results(sql,python)['sql_rows_checked'],2)
        sql['comparisons'][1]['ege_fixed_change'] += 1
        with self.assertRaisesRegex(AssertionError,'own_score_change'):
            compare_results(sql,python)

    def test_share_and_internal_contrast_mutations_are_detected(self):
        expected = dict(linked_shares=[dict(university='pilot',year=2022,total_groups=2,
            linked_groups=1,total_admitted=300,linked_admitted=100,linked_share_pct=100/3)],
            internal_contrasts=[dict(university='pilot',weights='current_controls',
            linked_groups=1,other_groups=1,linked_gap=1.25,other_gap=-1.39,internal_gap=2.64)],
            bvi_donors=[],bvi_donor_members=[])
        compare_extras(copy.deepcopy(expected),expected)
        for family,column in [('linked_shares','linked_admitted'),('internal_contrasts','internal_gap')]:
            actual = copy.deepcopy(expected)
            actual[family][0][column] += 1
            with self.assertRaisesRegex(AssertionError,family):
                compare_extras(actual,expected)


if __name__=='__main__':
    unittest.main()
