import unittest
from pathlib import Path
from unittest.mock import patch

from services.ai_runtime_task_priority_view_service import AIRuntimeTaskPriorityViewService


class AIRuntimeTaskPriorityViewServiceTest(unittest.TestCase):
    def test_build_task_priority_view_returns_dict(self):
        center = AIRuntimeTaskPriorityViewService.build_task_priority_view({})
        self.assertIsInstance(center, dict)
        self.assertIn("priority_status", center)

    def test_priority_buckets(self):
        center = AIRuntimeTaskPriorityViewService.build_task_priority_view({
            "ai_runtime_daily_operator_brief": {
                "must_do_today": [{"title": "Ops critical", "risk_level": "critical"}],
                "watch_today": [{"title": "Signal warning", "status": "warning"}],
            }
        })
        self.assertEqual(center["priority_status"], "urgent")
        self.assertTrue(center["p0_tasks"])
        self.assertTrue(center["watch_tasks"])

    def test_normal_status(self):
        center = AIRuntimeTaskPriorityViewService.build_task_priority_view({})
        self.assertEqual(center["priority_status"], "normal")

    def test_export_route_registered(self):
        from web_ui.app import app

        center = AIRuntimeTaskPriorityViewService.build_task_priority_view({})
        self.assertIn("/ai-dashboard/runtime-task-priority-view-export", {rule.rule for rule in app.url_map.iter_rules()})
        app.config["TESTING"] = True
        with patch("web_ui.app._build_ai_dashboard_admin_home_context", return_value={"ai_runtime_task_priority_view": center}):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["logged_in"] = True
                    sess["role"] = "admin"
                self.assertEqual(client.get("/ai-dashboard/runtime-task-priority-view-export?format=txt").status_code, 200)
                self.assertEqual(client.get("/ai-dashboard/runtime-task-priority-view-export?format=csv").status_code, 200)
                self.assertEqual(client.get("/ai-dashboard/runtime-task-priority-view-export?format=md").status_code, 200)

    def test_dashboard_page_contains_title(self):
        template = Path("web_ui/templates/ai_dashboard.html").read_text(encoding="utf-8")
        self.assertIn("AI Runtime 任务优先级动态视图", template)

    def test_no_automatic_logic_exists(self):
        source = Path("services/ai_runtime_task_priority_view_service.py").read_text(encoding="utf-8")
        for forbidden in ["def execute", "def run", "def dispatch", "publish_approved_articles", "subprocess", "worker", "scheduler"]:
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
