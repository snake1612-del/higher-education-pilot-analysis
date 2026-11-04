import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from placebo_synthetic import absolute_rank, contrast, estimate, fit, summarize


class SyntheticChecks(unittest.TestCase):
    def test_weights_match_known_regularized_solution(self):
        w = fit(np.array([1.]), np.array([[0.],[4.]]))
        np.testing.assert_allclose(w, [13/18,5/18], atol=1e-7)
        np.testing.assert_allclose(fit(np.array([10.]),np.array([[0.],[4.]])),[0,1],atol=1e-7)

    def test_post_values_cannot_change_weights(self):
        basket=['A','B']
        groups={'A':[(100+i,0,70+i) for i in range(5)],
                'B':[(50+i,0,60+i) for i in range(5)]}
        weights=np.array([2/3,1/3])
        features,path=summarize(groups,basket,weights)
        self.assertEqual(path[0,1],100)
        groups['B'][2]=(99,0,95)
        revised,path2=summarize(groups,basket,weights)
        np.testing.assert_array_equal(features,revised)
        self.assertNotEqual(path[2,1],path2[2,1])

    def test_holdout_is_unadjusted_and_post_contrast_uses_2022(self):
        y=np.array([[70,100],[73,105],[74,110],[75,113],[76,126]],float)
        c=np.array([[68,100],[69,100],[71,105],[72,108],[73,110]],float)
        out=estimate('pilot',['a','b'],{'pilot':np.array([0.]),'a':np.array([0.]),'b':np.array([0.])},
                     {'pilot':y,'a':c,'b':c},False)
        self.assertEqual(out['gap_2022'],[4,5])
        np.testing.assert_allclose(contrast(y,c)[-1],[-1,10])
        self.assertEqual(absolute_rank(-2,[-3,1,2]),{'placebos':3,'at_least_as_large':2})


if __name__=='__main__':
    unittest.main()
