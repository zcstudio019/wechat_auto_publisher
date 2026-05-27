"""Read-only Runtime layer registry for the AI Dashboard kernel view."""

L1_EXECUTIVE = "L1 Executive Layer"
L2_MISSION = "L2 Mission Layer"
L3_WORKSPACE = "L3 Workspace Layer"
L4_OPERATIONS = "L4 Operations Layer"
L5_RUNTIME = "L5 Runtime Layer"
L6_GOVERNANCE = "L6 Governance Layer"
L7_DIAGNOSTICS = "L7 Diagnostics Layer"
L8_EXPORT_DOCUMENTATION = "L8 Export / Documentation Layer"
L9_RELEASE = "L9 Release Layer"

RUNTIME_LAYERS = [
    L1_EXECUTIVE,
    L2_MISSION,
    L3_WORKSPACE,
    L4_OPERATIONS,
    L5_RUNTIME,
    L6_GOVERNANCE,
    L7_DIAGNOSTICS,
    L8_EXPORT_DOCUMENTATION,
    L9_RELEASE,
]


def _manifest(
    key: str,
    title: str,
    layer: str,
    service: str,
    route: str = "/ai-dashboard",
    export_route: str = "",
    readonly: bool = True,
    required: bool = True,
) -> dict:
    return {
        "key": key,
        "title": title,
        "layer": layer,
        "service": service,
        "route": route,
        "export_route": export_route,
        "readonly": readonly,
        "required": required,
    }


RUNTIME_CENTER_MANIFESTS = [
    _manifest("ai_dashboard_admin_home_center", "AI Dashboard 管理首页中心", L1_EXECUTIVE, "services.ai_dashboard_admin_home_service", "/ai-dashboard/home", "/ai-dashboard/home-export"),
    _manifest("ai_runtime_executive_digest_center", "AI Runtime 高层摘要中心", L1_EXECUTIVE, "services.ai_runtime_executive_digest_service", "/ai-dashboard/executive-digest", "/ai-dashboard/executive-digest-export"),
    _manifest("ai_runtime_executive_summary_center", "AI Runtime Executive Summary Center", L1_EXECUTIVE, "services.ai_runtime_executive_summary_service", "/ai-dashboard/runtime-executive-summary", "/ai-dashboard/runtime-executive-summary-export"),
    _manifest("ai_runtime_executive_dashboard", "AI Runtime Executive Dashboard Center", L1_EXECUTIVE, "services.article_health_service", "/ai-dashboard", "/ai-dashboard/runtime-executive-dashboard-export"),
    _manifest("ai_decision_brief", "AI Decision Brief", L1_EXECUTIVE, "services.article_health_service"),

    _manifest("ai_runtime_task_command_center", "AI Runtime 任务指挥中心", L2_MISSION, "services.ai_runtime_mission_control_service", "/ai-dashboard/runtime-task-command", "/ai-dashboard/runtime-task-command-export"),
    _manifest("ai_runtime_mission_control_center", "AI Runtime Mission Control Center", L2_MISSION, "services.ai_runtime_mission_control_service", "/ai-dashboard/mission-control", "/ai-dashboard/runtime-task-command-export"),
    _manifest("ai_dashboard_action_launchpad_center", "AI Dashboard Action Launchpad Center", L2_MISSION, "services.ai_dashboard_action_launchpad_service", "/ai-dashboard/action-launchpad", "/ai-dashboard/action-launchpad-export"),
    _manifest("ai_dashboard_action_launcher_center", "AI Dashboard Action Launcher Center", L2_MISSION, "services.ai_dashboard_action_launchpad_service", "/ai-dashboard/action-launcher", "/ai-dashboard/action-launchpad-export"),

    _manifest("ai_dashboard_workspace_center", "AI Dashboard 工作台中心", L3_WORKSPACE, "services.ai_dashboard_workspace_service", "/ai-dashboard/workspace", "/ai-dashboard/workspace-export"),
    _manifest("ai_dashboard_ux_declutter_entry_reorder_center", "AI Dashboard UX Declutter Entry Reorder Center", L3_WORKSPACE, "services.ai_dashboard_ux_declutter_service", "/ai-dashboard/ux-declutter", "/ai-dashboard/ux-declutter-export"),
    _manifest("ai_dashboard_module_search_center", "AI Dashboard 模块搜索中心", L3_WORKSPACE, "services.ai_dashboard_module_search_service", "/ai-dashboard/module-search", "/ai-dashboard/module-search-export"),

    _manifest("ai_dashboard_ops_health_center", "AI Dashboard 运维健康中心", L4_OPERATIONS, "services.ai_dashboard_ops_health_service", "/ai-dashboard/ops-health", "/ai-dashboard/ops-health-export"),
    _manifest("ai_dashboard_ops_maintenance_plan_center", "AI Dashboard 运维维护计划中心", L4_OPERATIONS, "services.ai_dashboard_ops_maintenance_service", "/ai-dashboard/ops-maintenance", "/ai-dashboard/ops-maintenance-export"),
    _manifest("ai_dashboard_ops_maintenance_center", "AI Dashboard 运维维护中心", L4_OPERATIONS, "services.ai_dashboard_ops_maintenance_service", "/ai-dashboard/ops-maintenance", "/ai-dashboard/ops-maintenance-export"),
    _manifest("ai_runtime_observability_center", "AI Runtime 可观测中心", L4_OPERATIONS, "services.article_health_service", "/ai-dashboard", "/ai-dashboard/runtime-observability-export"),
    _manifest("ai_runtime_alert_center", "AI Runtime 告警中心", L4_OPERATIONS, "services.article_health_service", "/ai-dashboard", "/ai-dashboard/runtime-alert-export"),
    _manifest("ai_runtime_recovery_center", "AI Runtime 恢复中心", L4_OPERATIONS, "services.article_health_service", "/ai-dashboard", "/ai-dashboard/runtime-recovery-export"),
    _manifest("ai_runtime_incident_center", "AI Runtime 事故中心", L4_OPERATIONS, "services.article_health_service", "/ai-dashboard", "/ai-dashboard/runtime-incident-export"),

    _manifest("ai_runtime_postmortem_center", "AI Runtime 事故复盘中心", L5_RUNTIME, "services.article_health_service", "/ai-dashboard", "/ai-dashboard/runtime-postmortem-export"),
    _manifest("ai_runtime_learning_center", "AI Runtime 学习中心", L5_RUNTIME, "services.article_health_service", "/ai-dashboard", "/ai-dashboard/runtime-learning-export"),
    _manifest("ai_runtime_knowledge_sync_center", "AI Runtime 知识同步中心", L5_RUNTIME, "services.article_health_service", "/ai-dashboard", "/ai-dashboard/runtime-knowledge-sync-export"),
    _manifest("ai_runtime_weekly_review_center", "AI Runtime 周复盘中心", L5_RUNTIME, "services.article_health_service", "/ai-dashboard", "/ai-dashboard/runtime-weekly-review-export"),
    _manifest("ai_runtime_feedback_loop_center", "AI Runtime 反馈闭环中心", L5_RUNTIME, "services.article_health_service", "/ai-dashboard", "/ai-dashboard/runtime-feedback-loop-export"),
    _manifest("ai_runtime_evolution_center", "AI Runtime 进化中心", L5_RUNTIME, "services.article_health_service", "/ai-dashboard", "/ai-dashboard/runtime-evolution-export"),
    _manifest("ai_runtime_snapshot_center", "AI Runtime 快照中心", L5_RUNTIME, "services.article_health_service", "/ai-dashboard", "/ai-dashboard/runtime-snapshot-export"),
    _manifest("ai_runtime_snapshot_diff_center", "AI Runtime 快照差异分析中心", L5_RUNTIME, "services.article_health_service", "/ai-dashboard", "/ai-dashboard/runtime-snapshot-diff-export"),
    _manifest("ai_runtime_timeline_center", "AI Runtime 时间轴中心", L5_RUNTIME, "services.article_health_service", "/ai-dashboard", "/ai-dashboard/runtime-timeline-export"),
    _manifest("ai_runtime_forecast_center", "AI Runtime 预测中心", L5_RUNTIME, "services.article_health_service", "/ai-dashboard", "/ai-dashboard/runtime-forecast-export"),
    _manifest("ai_runtime_predictive_action_center", "AI Runtime 预测动作中心", L5_RUNTIME, "services.article_health_service", "/ai-dashboard", "/ai-dashboard/runtime-predictive-action-export"),
    _manifest("ai_runtime_continuous_improvement_center", "AI Runtime 持续改进中心", L5_RUNTIME, "services.article_health_service", "/ai-dashboard", "/ai-dashboard/runtime-continuous-improvement-export"),

    _manifest("ai_runtime_orchestrator_center", "AI Runtime 编排中心", L6_GOVERNANCE, "services.article_health_service", "/ai-dashboard", "/ai-dashboard/runtime-orchestrator-export"),
    _manifest("ai_runtime_control_policy_center", "AI Runtime 控制策略中心", L6_GOVERNANCE, "services.article_health_service", "/ai-dashboard", "/ai-dashboard/runtime-control-policy-export"),
    _manifest("ai_runtime_policy_gate_center", "AI Runtime 策略闸门中心", L6_GOVERNANCE, "services.article_health_service", "/ai-dashboard", "/ai-dashboard/runtime-policy-gate-export"),
    _manifest("ai_runtime_confidence_center", "AI Runtime 置信度中心", L6_GOVERNANCE, "services.article_health_service", "/ai-dashboard", "/ai-dashboard/runtime-confidence-export"),
    _manifest("ai_runtime_trust_center", "AI Runtime 信任中心", L6_GOVERNANCE, "services.article_health_service", "/ai-dashboard", "/ai-dashboard/runtime-trust-export"),
    _manifest("ai_runtime_delegation_readiness_center", "AI Runtime 授权准备度中心", L6_GOVERNANCE, "services.article_health_service", "/ai-dashboard", "/ai-dashboard/runtime-delegation-readiness-export"),
    _manifest("ai_runtime_boundary_center", "AI Runtime 边界中心", L6_GOVERNANCE, "services.article_health_service", "/ai-dashboard", "/ai-dashboard/runtime-boundary-export"),
    _manifest("ai_runtime_constitution_center", "AI Runtime 宪法中心", L6_GOVERNANCE, "services.article_health_service", "/ai-dashboard", "/ai-dashboard/runtime-constitution-export"),
    _manifest("ai_autoops_control_tower", "AI AutoOps Control Tower", L6_GOVERNANCE, "services.article_health_service"),
    _manifest("ai_autoops_action_review_center", "AI AutoOps Action Review Center", L6_GOVERNANCE, "services.article_health_service"),
    _manifest("ai_execution_sandbox_center", "AI Execution Sandbox Center", L6_GOVERNANCE, "services.article_health_service"),
    _manifest("ai_approval_pipeline_center", "AI Approval Pipeline Center", L6_GOVERNANCE, "services.article_health_service"),
    _manifest("ai_approval_audit_center", "AI Approval Audit Center", L6_GOVERNANCE, "services.article_health_service"),
    _manifest("ai_governance_center", "AI Governance Center", L6_GOVERNANCE, "services.article_health_service"),
    _manifest("ai_governance_action_plan", "AI Governance Action Plan", L6_GOVERNANCE, "services.article_health_service"),

    _manifest("ai_memory_center", "AI Memory Center", L7_DIAGNOSTICS, "services.article_health_service"),
    _manifest("ai_memory_insights", "AI Memory Insights", L7_DIAGNOSTICS, "services.article_health_service"),
    _manifest("ai_strategy_center", "AI Strategy Center", L7_DIAGNOSTICS, "services.article_health_service"),
    _manifest("ai_strategy_execution_plan", "AI Strategy Execution Plan", L7_DIAGNOSTICS, "services.article_health_service"),
    _manifest("ai_simulation_center", "AI Simulation Center", L7_DIAGNOSTICS, "services.article_health_service"),
    _manifest("ai_simulation_history_summary", "AI Simulation History Summary", L7_DIAGNOSTICS, "services.article_health_service"),

    _manifest("ai_dashboard_export_history", "AI Dashboard Export History", L8_EXPORT_DOCUMENTATION, "services.ai_dashboard_export_automation", "/ai-dashboard", "/ai-dashboard/export-all-reports"),
    _manifest("ai_dashboard_export_operations_center", "AI Dashboard 导出运营中心", L8_EXPORT_DOCUMENTATION, "services.ai_dashboard_export_operations_service", "/ai-dashboard/export-operations", "/ai-dashboard/export-operations-export"),
    _manifest("ai_dashboard_architecture_map_center", "AI Dashboard 系统架构地图中心", L8_EXPORT_DOCUMENTATION, "services.ai_dashboard_architecture_map_service", "/ai-dashboard/architecture-map", "/ai-dashboard/architecture-map-export"),
    _manifest("ai_dashboard_documentation_center", "AI Dashboard 文档中心", L8_EXPORT_DOCUMENTATION, "services.ai_dashboard_documentation_service", "/ai-dashboard/documentation", "/ai-dashboard/documentation-export"),
    _manifest("ai_dashboard_navigation_index_center", "AI Dashboard 导航与索引中心", L8_EXPORT_DOCUMENTATION, "services.ai_dashboard_navigation_index_service", "/ai-dashboard/navigation-index", "/ai-dashboard/navigation-index-export"),
    _manifest("ai_dashboard_navigation_center", "AI Dashboard 导航中心", L8_EXPORT_DOCUMENTATION, "services.ai_dashboard_navigation_index_service", "/ai-dashboard/navigation", "/ai-dashboard/navigation-index-export"),
    _manifest("ai_knowledge_base", "AI Knowledge Base", L8_EXPORT_DOCUMENTATION, "services.article_health_service"),
    _manifest("ai_runtime_executive_dashboard_export_automation", "AI Runtime Executive Dashboard Export Automation", L8_EXPORT_DOCUMENTATION, "services.ai_dashboard_export_automation", "/ai-dashboard", "/ai-dashboard/runtime-executive-dashboard-export"),

    _manifest("ai_dashboard_production_hardening_center", "AI Dashboard 生产级加固中心", L9_RELEASE, "services.ai_dashboard_production_hardening_service", "/ai-dashboard/production-hardening", "/ai-dashboard/production-hardening-export"),
    _manifest("ai_dashboard_release_readiness_center", "AI Dashboard 上线准备度中心", L9_RELEASE, "services.ai_dashboard_release_readiness_service", "/ai-dashboard/release-readiness", "/ai-dashboard/release-readiness-export"),
    _manifest("ai_dashboard_launch_readiness_center", "AI Dashboard 发布准备度中心", L9_RELEASE, "services.ai_dashboard_launch_readiness_service", "/ai-dashboard/launch-readiness", "/ai-dashboard/launch-readiness-export"),
    _manifest("ai_dashboard_release_package_center", "AI Dashboard 上线包中心", L9_RELEASE, "services.ai_dashboard_release_package_service", "/ai-dashboard/release-package", "/ai-dashboard/release-package-export"),
    _manifest("ai_dashboard_release_runbook_center", "AI Dashboard 上线执行手册中心", L9_RELEASE, "services.ai_dashboard_release_runbook_service", "/ai-dashboard/release-runbook", "/ai-dashboard/release-runbook-export"),
    _manifest("ai_dashboard_launch_runbook_center", "AI Dashboard 发布执行手册中心", L9_RELEASE, "services.ai_dashboard_launch_runbook_service", "/ai-dashboard/launch-runbook", "/ai-dashboard/launch-runbook-export"),
]


def get_runtime_layers() -> list[str]:
    return list(RUNTIME_LAYERS)


def get_runtime_center_manifests() -> list[dict]:
    return [dict(item) for item in RUNTIME_CENTER_MANIFESTS]


def get_runtime_manifest_by_key() -> dict[str, dict]:
    return {item["key"]: dict(item) for item in RUNTIME_CENTER_MANIFESTS}
