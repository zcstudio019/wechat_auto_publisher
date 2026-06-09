import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.ai_runtime_action_approval_store import AIRuntimeActionApprovalStore
from services.ai_runtime_batch_approval_insight_service import AIRuntimeBatchApprovalInsightService


class AIRuntimeBatchApprovalInsightServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.store = AIRuntimeActionApprovalStore(Path(self.tmpdir.name) / "approvals.json")

    def tearDown(self):
        self.tmpdir.cleanup()

    def _approval(self, approval_id, risk="medium", status="pending", source="Command Layer"):
        return {
            "approval_id": approval_id,
            "created_at": "2026-06-01T00:00:00+00:00",
            "updated_at": "2026-06-01T00:00:00+00:00",
            "action_key": approval_id,
            "title": f"Action {approval_id}",
            "source": source,
            "risk_level": risk,
            "status": status,
            "human_required": True,
            "reason": "test",
            "recommended_route": "/ai-dashboard",
        }

    def test_build_batch_approval_insight_returns_dict(self):
        center = AIRuntimeBatchApprovalInsightService.build_batch_approval_insight({}, store=self.store)
        self.assertIsInstance(center, dict)
        self.assertIn("insight_status", center)

    def test_grouping_and_high_risk(self):
        self.store.write_approvals([self._approval("a1", "high"), self._approval("a2", "medium")])
        center = AIRuntimeBatchApprovalInsightService.build_batch_approval_insight({}, store=self.store)
        self.assertEqual(center["pending_count"], 2)
        self.assertTrue(center["grouped_by_source"])
        self.assertTrue(center["grouped_by_risk"])
        self.assertTrue(center["high_risk_pending"])

    def test_status_blocked_for_critical(self):
        self.store.write_approvals([self._approval("a1", "critical")])
        center = AIRuntimeBatchApprovalInsightService.build_batch_approval_insight({}, store=self.store)
        self.assertEqual(center["insight_status"], "blocked")

    def test_export_route_registered(self):
        from web_ui.app import app

        center = AIRuntimeBatchApprovalInsightService.build_batch_approval_insight({}, store=self.store)
        self.assertIn("/ai-dashboard/runtime-batch-approval-insight-export", {rule.rule for rule in app.url_map.iter_rules()})
        app.config["TESTING"] = True
        with patch("web_ui.app._build_ai_dashboard_admin_home_context", return_value={"ai_runtime_batch_approval_insight": center}):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["logged_in"] = True
                    sess["role"] = "admin"
                self.assertEqual(client.get("/ai-dashboard/runtime-batch-approval-insight-export?format=txt").status_code, 200)
                self.assertEqual(client.get("/ai-dashboard/runtime-batch-approval-insight-export?format=csv").status_code, 200)
                self.assertEqual(client.get("/ai-dashboard/runtime-batch-approval-insight-export?format=md").status_code, 200)

    def test_dashboard_page_contains_title(self):
        template = Path("web_ui/templates/ai_dashboard.html").read_text(encoding="utf-8")
        self.assertIn("AI Runtime 批量审批洞察中心", template)

    def test_no_automatic_logic_exists(self):
        source = Path("services/ai_runtime_batch_approval_insight_service.py").read_text(encoding="utf-8")
        for forbidden in ["def execute", "def run", "def dispatch", "publish_approved_articles", "subprocess", "worker", "scheduler"]:
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
