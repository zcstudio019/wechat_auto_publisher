import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.ai_runtime_action_approval_service import AIRuntimeActionApprovalService
from services.ai_runtime_action_approval_store import AIRuntimeActionApprovalStore


class AIRuntimeActionApprovalServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.approval_path = Path(self.tmpdir.name) / "ai_runtime_action_approvals.json"
        self.store = AIRuntimeActionApprovalStore(self.approval_path)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _dashboard(self):
        return {
            "ai_runtime_command_layer": {
                "high_priority_commands": [
                    {
                        "command_key": "COMMAND_OPEN_OPS_HEALTH",
                        "title": "Open Ops Health",
                        "category": "ops",
                        "risk_level": "critical",
                        "human_required": True,
                        "description": "Ops critical should be reviewed.",
                        "recommended_route": "/ai-dashboard/ops-health",
                    }
                ],
                "human_review_commands": [
                    {
                        "command_key": "COMMAND_REVIEW_IMMUNE_ALERT",
                        "title": "Review immune alert",
                        "category": "governance",
                        "risk_level": "high",
                        "human_required": True,
                        "description": "Human review required.",
                        "recommended_route": "/ai-dashboard",
                    }
                ],
            },
            "ai_runtime_daily_operator_brief": {
                "human_review_today": [
                    {"title": "Review governance risk", "priority": "high", "reason": "Needs human review."}
                ],
                "must_do_today": [
                    {"title": "Check release blocker", "priority": "critical", "reason": "Release blocked."}
                ],
            },
            "ai_runtime_governance_summary": {
                "delegation_risks": [
                    {"risk_key": "DELEGATION_HIGH", "title": "High delegation risk", "risk_level": "critical", "summary": "Delegation risk."}
                ]
            },
            "ai_runtime_capability_governance": {
                "approval_required_capabilities": [
                    {"capability_key": "CAP_RELEASE", "title": "Release approval", "risk_level": "critical", "human_required": True, "summary": "Approval required."}
                ]
            },
            "ai_runtime_policy_linter": {
                "critical_issues": [
                    {"issue_key": "POLICY_NO_SOURCE", "title": "Policy missing source", "risk_level": "critical", "summary": "Critical policy lint."}
                ]
            },
            "ai_dashboard_release_readiness_center": {
                "must_fix_before_release": [
                    {"title": "Release blocked", "status": "blocked", "summary": "Must fix before release."}
                ]
            },
            "ai_dashboard_ops_health_center": {
                "ops_status": "critical",
                "risk_items": [
                    {"title": "Ops critical risk", "status": "critical", "summary": "Ops needs attention."}
                ],
            },
        }

    def test_store_can_read_and_write(self):
        items = [{"approval_id": "a1", "action_key": "A", "title": "Action", "source": "Test"}]
        self.store.write_approvals(items)
        approvals = self.store.read_approvals()
        self.assertEqual(len(approvals), 1)
        self.assertEqual(approvals[0]["approval_id"], "a1")

    def test_json_damage_fallback(self):
        self.approval_path.write_text("{bad-json", encoding="utf-8")
        self.assertEqual(self.store.read_approvals(), [])

    def test_append_pending_action_dedupes(self):
        action = {"action_key": "ACTION_DUP", "title": "Action Dup", "source": "Command Layer"}
        first = self.store.append_pending_action(action)
        second = self.store.append_pending_action(action)
        approvals = self.store.read_approvals()
        self.assertEqual(len(approvals), 1)
        self.assertEqual(first["approval_id"], second["approval_id"])

    def test_approve_action_only_changes_approval_state(self):
        pending = self.store.append_pending_action({"action_key": "ACTION_APPROVE", "title": "Approve Action", "source": "Test"})
        approved = self.store.approve_action(pending["approval_id"], approved_by="admin", note="ok")
        self.assertEqual(approved["status"], "approved")
        self.assertEqual(approved["approved_by"], "admin")
        self.assertEqual(approved["action_key"], "ACTION_APPROVE")

    def test_reject_action_only_changes_approval_state(self):
        pending = self.store.append_pending_action({"action_key": "ACTION_REJECT", "title": "Reject Action", "source": "Test"})
        rejected = self.store.reject_action(pending["approval_id"], rejected_by="admin", note="no")
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(rejected["rejected_by"], "admin")
        self.assertEqual(rejected["action_key"], "ACTION_REJECT")

    def test_build_action_approval_center_returns_dict(self):
        center = AIRuntimeActionApprovalService.build_action_approval_center(self._dashboard(), store=self.store)
        self.assertIsInstance(center, dict)
        self.assertIn("approval_status", center)

    def test_pending_high_risk_human_required_are_classified(self):
        center = AIRuntimeActionApprovalService.build_action_approval_center(self._dashboard(), store=self.store)
        self.assertTrue(center["pending_actions"])
        self.assertTrue(center["high_risk_pending"])
        self.assertTrue(center["human_required_pending"])

    def test_approval_status_is_resolved(self):
        empty = AIRuntimeActionApprovalService.build_action_approval_center({}, store=self.store)
        self.assertEqual(empty["approval_status"], "empty")
        center = AIRuntimeActionApprovalService.build_action_approval_center(self._dashboard(), store=self.store)
        self.assertEqual(center["approval_status"], "blocked")

    def test_approval_routes_and_export_route_registered(self):
        from web_ui.app import app

        center = AIRuntimeActionApprovalService.build_action_approval_center(self._dashboard(), store=self.store)
        approval_id = center["pending_actions"][0]["approval_id"]
        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/ai-dashboard/runtime-action-approval/<approval_id>/approve", rules)
        self.assertIn("/ai-dashboard/runtime-action-approval/<approval_id>/reject", rules)
        self.assertIn("/ai-dashboard/runtime-action-approval-export", rules)

        app.config["TESTING"] = True
        with patch.object(AIRuntimeActionApprovalStore, "APPROVAL_FILE_PATH", self.approval_path):
            with patch("web_ui.app._build_ai_dashboard_admin_home_context", return_value={"ai_runtime_action_approval_center": center}):
                with app.test_client() as client:
                    with client.session_transaction() as sess:
                        sess["logged_in"] = True
                        sess["role"] = "admin"
                        sess["username"] = "admin"
                    approve_response = client.post(f"/ai-dashboard/runtime-action-approval/{approval_id}/approve")
                    reject_response = client.post(f"/ai-dashboard/runtime-action-approval/{approval_id}/reject")
                    txt_response = client.get("/ai-dashboard/runtime-action-approval-export?format=txt")
                    csv_response = client.get("/ai-dashboard/runtime-action-approval-export?format=csv")
                    md_response = client.get("/ai-dashboard/runtime-action-approval-export?format=md")

        self.assertEqual(approve_response.status_code, 302)
        self.assertEqual(reject_response.status_code, 302)
        self.assertEqual(txt_response.status_code, 200)
        self.assertIn("AI Runtime 动作审批中心".encode("utf-8"), txt_response.data)
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("审批ID".encode("utf-8"), csv_response.data)
        self.assertEqual(md_response.status_code, 200)
        self.assertIn("# AI Runtime 动作审批中心".encode("utf-8"), md_response.data)

    def test_dashboard_page_contains_action_approval_title(self):
        template = Path("web_ui/templates/ai_dashboard.html").read_text(encoding="utf-8")
        self.assertIn("AI Runtime 动作审批中心", template)
        self.assertIn("/ai-dashboard/runtime-action-approval-export?format=txt", template)

    def test_no_automatic_action_logic_exists(self):
        service_source = Path("services/ai_runtime_action_approval_service.py").read_text(encoding="utf-8")
        store_source = Path("services/ai_runtime_action_approval_store.py").read_text(encoding="utf-8")
        combined = service_source + "\n" + store_source
        for forbidden in [
            "def execute",
            "def dispatch",
            "def run",
            "publish_approved_articles",
            "subprocess",
            "worker",
            "scheduler",
        ]:
            self.assertNotIn(forbidden, combined)


if __name__ == "__main__":
    unittest.main()
