import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.ai_runtime_action_approval_store import AIRuntimeActionApprovalStore
from services.ai_runtime_execution_plan_service import AIRuntimeExecutionPlanService


class AIRuntimeExecutionPlanServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.approval_path = Path(self.tmpdir.name) / "ai_runtime_action_approvals.json"
        self.store = AIRuntimeActionApprovalStore(self.approval_path)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _approval(self, approval_id, status="approved", risk_level="medium", human_required=True, title="Approved action"):
        return {
            "approval_id": approval_id,
            "created_at": "2026-06-01T00:00:00+00:00",
            "updated_at": "2026-06-01T00:00:00+00:00",
            "action_key": f"ACTION_{approval_id}",
            "title": title,
            "source": "Action Approval",
            "risk_level": risk_level,
            "status": status,
            "human_required": human_required,
            "reason": "Approved by human for planning.",
            "recommended_route": "/ai-dashboard",
            "approved_by": "admin" if status == "approved" else "",
            "rejected_by": "admin" if status == "rejected" else "",
            "decision_note": "",
        }

    def test_build_execution_plan_center_returns_dict(self):
        center = AIRuntimeExecutionPlanService.build_execution_plan_center({}, store=self.store)
        self.assertIsInstance(center, dict)
        self.assertIn("plan_status", center)

    def test_approved_action_can_generate_plan(self):
        self.store.write_approvals([self._approval("a1", status="approved", human_required=False)])
        center = AIRuntimeExecutionPlanService.build_execution_plan_center({}, store=self.store)
        self.assertEqual(center["pending_plan_count"], 1)
        self.assertEqual(center["execution_plans"][0]["approval_id"], "a1")
        self.assertEqual(center["execution_plans"][0]["status"], "planned")

    def test_pending_action_does_not_generate_plan(self):
        self.store.write_approvals([self._approval("a1", status="pending")])
        center = AIRuntimeExecutionPlanService.build_execution_plan_center({}, store=self.store)
        self.assertEqual(center["pending_plan_count"], 0)
        self.assertFalse(center["execution_plans"])

    def test_rejected_action_does_not_generate_plan(self):
        self.store.write_approvals([self._approval("a1", status="rejected")])
        center = AIRuntimeExecutionPlanService.build_execution_plan_center({}, store=self.store)
        self.assertEqual(center["pending_plan_count"], 0)
        self.assertFalse(center["execution_plans"])

    def test_rollback_steps_exist(self):
        self.store.write_approvals([self._approval("a1", status="approved")])
        center = AIRuntimeExecutionPlanService.build_execution_plan_center({}, store=self.store)
        self.assertTrue(center["execution_plans"][0]["rollback_steps"])
        self.assertTrue(center["rollback_required"])

    def test_verification_steps_exist(self):
        self.store.write_approvals([self._approval("a1", status="approved")])
        center = AIRuntimeExecutionPlanService.build_execution_plan_center({}, store=self.store)
        self.assertTrue(center["execution_plans"][0]["verification_steps"])
        self.assertTrue(center["verification_required"])

    def test_plan_status_is_resolved(self):
        empty = AIRuntimeExecutionPlanService.build_execution_plan_center({}, store=self.store)
        self.assertEqual(empty["plan_status"], "empty")

        self.store.write_approvals([self._approval("a1", status="approved", risk_level="low", human_required=False)])
        planned = AIRuntimeExecutionPlanService.build_execution_plan_center({}, store=self.store)
        self.assertEqual(planned["plan_status"], "planned")

        self.store.write_approvals([self._approval("a2", status="approved", risk_level="high", human_required=False)])
        attention = AIRuntimeExecutionPlanService.build_execution_plan_center({}, store=self.store)
        self.assertEqual(attention["plan_status"], "attention")

        self.store.write_approvals([self._approval("a3", status="approved", risk_level="critical", human_required=True)])
        blocked = AIRuntimeExecutionPlanService.build_execution_plan_center({}, store=self.store)
        self.assertEqual(blocked["plan_status"], "blocked")

    def test_runtime_execution_plan_export_route_registered(self):
        from web_ui.app import app

        self.store.write_approvals([self._approval("a1", status="approved")])
        center = AIRuntimeExecutionPlanService.build_execution_plan_center({}, store=self.store)
        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/runtime-execution-plan-export", rules)

        app.config["TESTING"] = True
        with patch("web_ui.app._build_ai_dashboard_admin_home_context", return_value={"ai_runtime_execution_plan_center": center}):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["logged_in"] = True
                    sess["role"] = "admin"
                    sess["username"] = "admin"
                txt_response = client.get("/ai-dashboard/runtime-execution-plan-export?format=txt")
                csv_response = client.get("/ai-dashboard/runtime-execution-plan-export?format=csv")
                md_response = client.get("/ai-dashboard/runtime-execution-plan-export?format=md")

        self.assertEqual(txt_response.status_code, 200)
        self.assertIn("AI Runtime 动作执行计划中心".encode("utf-8"), txt_response.data)
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("审批ID".encode("utf-8"), csv_response.data)
        self.assertEqual(md_response.status_code, 200)
        self.assertIn("# AI Runtime 动作执行计划中心".encode("utf-8"), md_response.data)

    def test_dashboard_page_contains_execution_plan_title(self):
        template = Path("web_ui/templates/ai_dashboard.html").read_text(encoding="utf-8")
        self.assertIn("AI Runtime 动作执行计划中心", template)
        self.assertIn("/ai-dashboard/runtime-execution-plan-export?format=txt", template)

    def test_no_automatic_execution_logic_exists(self):
        service_source = Path("services/ai_runtime_execution_plan_service.py").read_text(encoding="utf-8")
        for forbidden in [
            "def execute",
            "def run",
            "def dispatch",
            "publish_approved_articles",
            "subprocess",
            "worker",
            "scheduler",
        ]:
            self.assertNotIn(forbidden, service_source)


if __name__ == "__main__":
    unittest.main()
