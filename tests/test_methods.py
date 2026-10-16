"""Small counterexamples for the methodological issues raised in the audit."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from independent_check import estimate, valid, number


class MethodTests(unittest.TestCase):
    def test_changing_control_composition_is_not_a_score_change(self):
        data = {}
        for year in (2022,2025):
            data['pilot','g',year] = (100,0,80)
            data['high','g',year] = (90 if year==2022 else 10,0,90)
            data['low','g',year] = (10 if year==2022 else 90,0,60)
        pools = {('g','score'):{'high','low'}}
        dynamic = estimate(data,'pilot',['g'],pools,'score',2022,2025)
        fixed = estimate(data,'pilot',['g'],pools,'score',2022,2025,True)
        self.assertAlmostEqual(dynamic['score_gap'],24)
        self.assertAlmostEqual(fixed['score_gap'],0)

    def test_known_zero_is_distinct_from_missing(self):
        self.assertTrue(valid((0,None,None),'intake'))
        self.assertFalse(valid((None,None,None),'intake'))
        self.assertFalse(valid((0,0,80),'score'))
        self.assertEqual(number('1\u202f077'),1077)
        self.assertEqual(number('0'),0)
        self.assertIsNone(number(''))

    def test_bvi_threshold_requires_recomputing_denominators(self):
        data = {}
        for y in (2022,2025):
            data['pilot','small',y] = (100,1 if y==2022 else 20,None)
            data['pilot','large',y] = (100,10,None)
            for g in ('small','large'):
                data['control',g,y] = (100,5,None)
        pools = {(g,'bvi'):{'control'} for g in ('small','large')}
        all_groups = estimate(data,'pilot',['small','large'],pools,'bvi',2022,2025)
        retained = estimate(data,'pilot',['large'],pools,'bvi',2022,2025)
        self.assertAlmostEqual(all_groups['share_gap_pp'],9.5)
        self.assertAlmostEqual(retained['share_gap_pp'],0)
        self.assertEqual(retained['n0'],100)


if __name__=='__main__':
    unittest.main()
