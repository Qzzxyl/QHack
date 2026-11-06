"""Run with: python -m unittest test_integration -v"""
import os
import unittest
from unittest.mock import patch
from datetime import datetime

from data_adapter import build_walking_matrix, load_ride_durations
from route_optimizer import optimize_route
from my_optimizer import get_attractions, optimize


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.env_patch = patch.dict(os.environ, {'UNIVERSAL_SOLVER_MODE': 'demo', 'UNIVERSAL_ALLOW_FAKE_QUEUES': '1'})
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

    def request(self, current_location='R_1', budget=120, tags=None):
        return {'current_location': current_location,
                'preferences': tags or ['magic'],
                'total_time_minutes': budget}

    def test_route_starts_from_selected_location(self):
        matrix = build_walking_matrix('data/walking_time-matrix.csv')
        r, minutes = optimize_route(['R_3'], matrix, start_location='R_1')
        self.assertEqual(r, ['R_3'])
        self.assertEqual(minutes, 5)

    def test_full_response_fits_budget(self):
        result = optimize(self.request())
        self.assertEqual(result['status'], 'SUCCESS')
        self.assertTrue(result['steps'])
        total = sum(s['walk_minutes']+s['queue_minutes']+s['ride_minutes'] for s in result['steps'])
        self.assertAlmostEqual(total, result['total_time_minutes'])
        self.assertLessEqual(total, 120)
        self.assertTrue(all(s['walk_distance_m'] is None and s['origin_distance_m'] is None for s in result['steps']))

    def test_budget_start_and_unique_ride_ids(self):
        result = optimize(self.request('R_5', 30, ['thrill']))
        rides = [s['ride_id'] for s in result['steps']]
        self.assertEqual(len(rides), len(set(rides)))
        self.assertLessEqual(sum(s['walk_minutes'] + s['queue_minutes'] + s['ride_minutes'] for s in result['steps']), 30)

    def test_catalog_null_ratings_and_distance(self):
        catalog = get_attractions('R_1')
        self.assertEqual(len(catalog), 8)
        self.assertIsNone(catalog[0]['rating'])
        self.assertIsNone(catalog[0]['origin_distance_m'])

    def test_invalid_input_rejected(self):
        for x in [self.request('NONSENSE'), self.request(budget=1000), self.request(tags=['other'])]:
            with self.assertRaises(ValueError):
                optimize(x)

    def test_qaoa_mode_requires_real_queue_data(self):
        with patch.dict(os.environ, {'UNIVERSAL_SOLVER_MODE': 'qaoa'}):
            with self.assertRaisesRegex(ValueError, 'No historical queue CSV found'):
                optimize(self.request())

    def test_real_duration_file(self):
        durations = load_ride_durations('data/ride_durations.csv')
        self.assertEqual(durations['R_3']['duration'], 7)


if __name__ == '__main__':
    unittest.main()
