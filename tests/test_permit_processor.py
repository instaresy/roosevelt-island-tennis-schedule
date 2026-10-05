import unittest
from unittest.mock import Mock, patch

import requests

import permit_processor as processor


class PermitRetryTests(unittest.TestCase):
    def setUp(self):
        self.post = patch.object(processor.requests, 'post').start()
        self.sleep = patch.object(processor.time, 'sleep').start()
        patch.object(processor, 'logger').start()
        self.addCleanup(patch.stopall)

    def create(self, **kwargs):
        return processor.create_permit('court-1', 'start', 'stop', {}, **kwargs)

    def response(self, status):
        return Mock(status_code=status, text='response')

    def test_success_stops_retries(self):
        self.post.side_effect = [self.response(500), self.response(503), self.response(200)]
        self.assertTrue(self.create())
        self.assertEqual(self.post.call_count, 3)
        self.assertEqual(self.sleep.call_count, 2)
        self.assertEqual(self.post.call_args.kwargs['timeout'], (2, 3))
        self.assertFalse(self.post.call_args.kwargs['allow_redirects'])

    def test_failures_stop_at_30_total_attempts(self):
        self.post.return_value = self.response(500)
        self.assertFalse(self.create())
        self.assertEqual(self.post.call_count, 30)
        self.assertEqual(self.sleep.call_count, 29)

    def test_network_errors_and_rate_limits_are_retried(self):
        self.post.side_effect = [
            requests.exceptions.Timeout('slow server'),
            requests.exceptions.ConnectionError('connection lost'),
            self.response(429), self.response(200),
        ]
        self.assertTrue(self.create())
        self.assertEqual(self.post.call_count, 4)

    def test_permanent_errors_and_redirects_are_not_retried(self):
        for status in (400, 401, 403, 409, 302):
            with self.subTest(status=status):
                self.post.reset_mock()
                self.post.return_value = self.response(status)
                self.assertFalse(self.create())
                self.post.assert_called_once()

    def test_insufficient_time_prevents_request(self):
        with patch.object(processor.time, 'monotonic', return_value=96):
            self.assertFalse(self.create(deadline=100))
        self.post.assert_not_called()

    def test_time_budget_stops_further_retries(self):
        self.post.return_value = self.response(500)
        with patch.object(processor.time, 'monotonic', side_effect=[90, 95]):
            self.assertFalse(self.create(deadline=100))
        self.post.assert_called_once()
        self.sleep.assert_not_called()

    def test_record_returns_booking_failure(self):
        record = {'body': '{"account_info":{"username":"user","password":"pw"},"court":"court-1","start_time":"start","stop_time":"stop"}'}
        with patch.object(processor, 'authenticate', return_value={}), \
                patch.object(processor, 'wait_until_8am_est_edt', return_value=True), \
                patch.object(processor, 'create_permit', return_value=False) as create:
            self.assertFalse(processor.process_record(record, deadline=100))
        self.assertEqual(create.call_args.kwargs['deadline'], 100)


if __name__ == '__main__':
    unittest.main()
