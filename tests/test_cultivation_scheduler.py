import unittest
from unittest.mock import patch

import scheduler_app


class CultivationSchedulerTestCase(unittest.TestCase):
    def test_daily_job_is_registered(self):
        scheduler = scheduler_app.build_scheduler()
        job = scheduler.get_job("cultivation_daily_scan")
        self.assertIsNotNone(job)
        self.assertEqual(str(job.trigger), "cron[hour='9', minute='0']")

    def test_scan_failure_is_isolated(self):
        with patch("services.cultivation_service.scan_cultivation_customers", side_effect=RuntimeError("boom")):
            result = scheduler_app.job_scan_cultivation_customers()
        self.assertEqual(result["errors"], 1)


if __name__ == "__main__":
    unittest.main()
