import unittest
from central_system.backend.analysis import AnalysisEngine

class TestAnalysisEngine(unittest.TestCase):
    def setUp(self):
        self.engine = AnalysisEngine()

    def test_binomial_p_value(self):
        # 10 wins in 10 trades should have a very low p-value
        pv = self.engine.binomial_p_value(10, 10, 0.5)
        self.assertLess(pv, 0.01)

        # 5 wins in 10 trades should have a p-value around 0.5 (actually 1.0 for >=5 if we include the lower tail but binomial.sf(4,10,0.5) is 0.623)
        pv2 = self.engine.binomial_p_value(5, 10, 0.5)
        self.assertGreater(pv2, 0.5)

    def test_cluster_score(self):
        w1_trades = [
            {'timestamp': 1000, 'market_id': 'm1', 'size': 100},
            {'timestamp': 2000, 'market_id': 'm2', 'size': 200},
            {'timestamp': 3000, 'market_id': 'm3', 'size': 300},
        ]
        w2_trades = [
            {'timestamp': 1005, 'market_id': 'm1', 'size': 100},
            {'timestamp': 2005, 'market_id': 'm2', 'size': 200},
            {'timestamp': 3005, 'market_id': 'm3', 'size': 300},
        ]
        result = self.engine.calculate_cluster_score(w1_trades, w2_trades)
        self.assertEqual(result['risk_level'], 'high')
        self.assertGreaterEqual(result['score'], 70)

if __name__ == '__main__':
    unittest.main()
