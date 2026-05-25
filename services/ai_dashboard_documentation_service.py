"""Read-only AI Dashboard documentation center."""

from __future__ import annotations

from services.ai_dashboard_architecture_map_service import AIDashboardArchitectureMapService


class AIDashboardDocumentationService:
    """Build documentation for AI Dashboard modules, routes, exports, and tests."""

    MODULES = [
        ("Runtime Observability", "AI 运行时可观测中心", "Runtime Layer", "ai_runtime_observability_center", "", "运行时观测入口。"),
        ("Runtime Alert", "AI 运行时告警中心", "Runtime Layer", "ai_runtime_alert_center", "", "运行时告警汇总。"),
        ("Runtime Recovery", "AI 运行时恢复中心", "Runtime Layer", "ai_runtime_recovery_center", "", "恢复状态和建议。"),
        ("Runtime Incident", "AI 运行时事故中心", "Runtime Layer", "ai_runtime_incident_center", "", "事故聚合和风险事件。"),
        ("Runtime Postmortem", "AI 运行时事故复盘中心", "Runtime Layer", "ai_runtime_postmortem_center", "", "事故复盘和沉淀。"),
        ("Runtime Learning", "AI 运行时学习中心", "Learning Layer", "ai_runtime_learning_center", "/ai-dashboard/runtime-learning-export", "学习信号和经验沉淀。"),
        ("Runtime Knowledge Sync", "AI 运行时知识同步中心", "Learning Layer", "ai_runtime_knowledge_sync_center", "/ai-dashboard/runtime-knowledge-sync-export", "知识/SOP/治理同步建议。"),
        ("Runtime Weekly Review", "AI 运行时周复盘中心", "Learning Layer", "ai_runtime_weekly_review_center", "/ai-dashboard/runtime-weekly-review-export", "周维度复盘。"),
        ("Runtime Feedback Loop", "AI 运行时反馈闭环中心", "Learning Layer", "ai_runtime_feedback_loop_center", "/ai-dashboard/runtime-feedback-loop-export", "反馈闭环分析。"),
        ("Runtime Evolution", "AI 运行时进化中心", "Learning Layer", "ai_runtime_evolution_center", "/ai-dashboard/runtime-evolution-export", "运行时演进记录。"),
        ("Runtime Orchestrator", "AI 运行时编排中心", "Executive Layer", "ai_runtime_orchestrator_center", "/ai-dashboard/runtime-orchestrator-export", "跨模块编排和优先级。"),
        ("Runtime Control Policy", "AI 运行时控制策略中心", "Governance Layer", "ai_runtime_control_policy_center", "/ai-dashboard/runtime-control-policy-export", "控制策略视图。"),
        ("Runtime Policy Gate", "AI 运行时策略闸门中心", "Governance Layer", "ai_runtime_policy_gate_center", "/ai-dashboard/runtime-policy-gate-export", "策略闸门判断。"),
        ("Runtime Confidence", "AI 运行时置信度中心", "Governance Layer", "ai_runtime_confidence_center", "/ai-dashboard/runtime-confidence-export", "置信度分析。"),
        ("Runtime Trust", "AI 运行时信任中心", "Trust & Boundary Layer", "ai_runtime_trust_center", "/ai-dashboard/runtime-trust-export", "信任状态分析。"),
        ("Runtime Delegation Readiness", "AI 运行时授权准备度中心", "Trust & Boundary Layer", "ai_runtime_delegation_readiness_center", "/ai-dashboard/runtime-delegation-readiness-export", "授权准备度分析。"),
        ("Runtime Boundary", "AI 运行时边界中心", "Trust & Boundary Layer", "ai_runtime_boundary_center", "/ai-dashboard/runtime-boundary-export", "人工和自动化边界。"),
        ("Runtime Constitution", "AI 运行时宪法中心", "Trust & Boundary Layer", "ai_runtime_constitution_center", "/ai-dashboard/runtime-constitution-export", "高约束原则。"),
        ("Runtime Snapshot", "AI 运行时快照中心", "Snapshot & Forecast Layer", "ai_runtime_snapshot_center", "/ai-dashboard/runtime-snapshot-export", "运行时快照。"),
        ("Runtime Snapshot Diff", "AI 运行时快照差异中心", "Snapshot & Forecast Layer", "ai_runtime_snapshot_diff_center", "/ai-dashboard/runtime-snapshot-diff-export", "快照差异。"),
        ("Runtime Timeline", "AI 运行时时间线中心", "Snapshot & Forecast Layer", "ai_runtime_timeline_center", "/ai-dashboard/runtime-timeline-export", "时间线视图。"),
        ("Runtime Forecast", "AI 运行时预测中心", "Snapshot & Forecast Layer", "ai_runtime_forecast_center", "/ai-dashboard/runtime-forecast-export", "趋势预测。"),
        ("Runtime Predictive Action", "AI 运行时预测动作中心", "Snapshot & Forecast Layer", "ai_runtime_predictive_action_center", "/ai-dashboard/runtime-predictive-action-export", "预测动作建议。"),
        ("Runtime Continuous Improvement", "AI 运行时持续改进中心", "Snapshot & Forecast Layer", "ai_runtime_continuous_improvement_center", "/ai-dashboard/runtime-continuous-improvement-export", "持续改进建议。"),
        ("Runtime Executive Dashboard", "AI 运行时高管仪表盘", "Executive Layer", "ai_runtime_executive_dashboard", "/ai-dashboard/runtime-executive-dashboard-export", "高管汇总视图。"),
        ("Export Operations", "AI Dashboard 导出运营中心", "Export Layer", "ai_dashboard_export_operations_center", "", "导出运营状态。"),
        ("Ops Health", "AI Dashboard 运维健康中心", "Ops Layer", "ai_dashboard_ops_health_center", "/ai-dashboard/ops-health-export", "Dashboard 自身健康检查。"),
        ("Ops Maintenance", "AI Dashboard 运维维护计划中心", "Ops Layer", "ai_dashboard_ops_maintenance_center", "/ai-dashboard/ops-maintenance-export", "维护计划建议。"),
        ("Architecture Map", "AI Dashboard 系统架构地图中心", "Documentation Layer", "ai_dashboard_architecture_map_center", "/ai-dashboard/architecture-map-export", "系统架构地图。"),
        ("Smoke Test", "AI Dashboard 冒烟测试中心", "Ops Layer", "ai_dashboard_smoke_test_center", "", "Dashboard 冒烟测试。"),
        ("Documentation Center", "AI Dashboard 文档中心", "Documentation Layer", "ai_dashboard_documentation_center", "/ai-dashboard/documentation-export", "统一文档索引。"),
        ("Navigation Center", "AI Dashboard 导航与索引中心", "Documentation Layer", "ai_dashboard_navigation_index_center", "/ai-dashboard/navigation-index-export", "Dashboard 导航与索引入口。"),
    ]

    STANDALONE_ROUTES = {
        "Export Operations": "/ai-dashboard/export-operations",
        "Ops Health": "/ai-dashboard/ops-health",
        "Ops Maintenance": "/ai-dashboard/ops-maintenance",
        "Architecture Map": "/ai-dashboard/architecture-map",
        "Smoke Test": "/ai-dashboard/smoke-test",
        "Documentation Center": "/ai-dashboard/documentation",
        "Navigation Center": "/ai-dashboard/navigation-index",
    }

    TEST_FILES = {
        "Export Operations": "tests/test_ai_dashboard_export_operations_service.py",
        "Ops Health": "tests/test_ai_dashboard_ops_health_service.py",
        "Ops Maintenance": "tests/test_ai_dashboard_ops_maintenance_service.py",
        "Architecture Map": "tests/test_ai_dashboard_architecture_map_service.py",
        "Smoke Test": "tests/test_ai_dashboard_smoke_test_service.py",
        "Documentation Center": "tests/test_ai_dashboard_documentation_service.py",
        "Navigation Center": "tests/test_ai_dashboard_navigation_service.py",
    }

    @classmethod
    def build_documentation_center(cls) -> dict:
        module_catalog = cls._build_module_catalog()
        layer_docs = cls._build_layer_docs(module_catalog)
        module_docs = cls._build_module_docs(module_catalog)
        runtime_docs = [item for item in module_docs if item.get("type") == "runtime"]
        ops_docs = [item for item in module_docs if item.get("type") == "ops"]
        architecture_docs = [item for item in module_docs if item.get("type") == "architecture"]
        maintenance_docs = [item for item in module_docs if item.get("type") == "maintenance"]
        route_docs = cls._build_route_docs()
        export_docs = cls._build_export_docs(module_catalog)
        service_docs = cls._build_service_docs()
        test_docs = cls._build_test_docs()
        readonly_matrix = cls._build_readonly_matrix(module_catalog)
        data_file_docs = cls._build_data_file_docs()
        usage_guides = cls._build_usage_guides()
        maintenance_notes = cls._build_maintenance_notes()
        documentation_status = cls._resolve_documentation_status(module_catalog, route_docs, export_docs, test_docs)
        recommended_actions = cls._build_recommended_actions(documentation_status, module_catalog)

        return {
            "documentation_status": documentation_status,
            "summary": cls._build_summary(documentation_status, module_catalog, route_docs, export_docs),
            "module_docs": module_docs,
            "runtime_docs": runtime_docs,
            "export_docs": export_docs,
            "ops_docs": ops_docs,
            "architecture_docs": architecture_docs,
            "maintenance_docs": maintenance_docs,
            "route_docs": route_docs,
            "data_file_docs": data_file_docs,
            "usage_guides": usage_guides,
            "recommended_actions": recommended_actions,
            "module_catalog": module_catalog,
            "layer_docs": layer_docs,
            "service_docs": service_docs,
            "test_docs": test_docs,
            "readonly_matrix": readonly_matrix,
            "maintenance_notes": maintenance_notes,
        }

    @staticmethod
    def _doc_type(module_name: str, layer: str) -> str:
        if "Maintenance" in module_name:
            return "maintenance"
        if module_name.startswith("Runtime"):
            return "runtime"
        if module_name.startswith("Export"):
            return "export"
        if module_name.startswith("Ops") or module_name == "Smoke Test":
            return "ops"
        if module_name == "Architecture Map":
            return "architecture"
        if module_name in {"Documentation Center", "Navigation Center"}:
            return "module"
        return "module"

    @classmethod
    def _build_module_docs(cls, module_catalog: list[dict]) -> list[dict]:
        docs = []
        for item in module_catalog:
            docs.append({
                "type": cls._doc_type(item.get("module_name", ""), item.get("layer", "")),
                "title": item.get("chinese_name") or item.get("module_name") or "",
                "summary": item.get("summary") or "",
                "path": item.get("service_file") or item.get("route") or "",
                "status": "normal" if item.get("service_file") else "missing",
                "suggestion": "保持文档、路由、导出和测试同步。",
                "module_name": item.get("module_name") or "",
                "dashboard_key": item.get("dashboard_key") or "",
                "layer": item.get("layer") or "",
            })
        return docs

    @classmethod
    def _build_module_catalog(cls) -> list[dict]:
        catalog = []
        for module_name, chinese_name, layer, dashboard_key, export_route, summary in cls.MODULES:
            standalone_route = cls.STANDALONE_ROUTES.get(module_name, "")
            service_file = cls._service_file_for(module_name)
            test_file = cls.TEST_FILES.get(module_name, "tests/test_article_health_service.py")
            catalog.append({
                "module_name": module_name,
                "chinese_name": chinese_name,
                "layer": layer,
                "dashboard_key": dashboard_key,
                "service_file": service_file,
                "template_title": chinese_name,
                "route": standalone_route or "/ai-dashboard",
                "export_route": export_route,
                "readonly": True,
                "has_standalone_page": bool(standalone_route),
                "test_file": test_file,
                "summary": summary,
            })
        return catalog

    @staticmethod
    def _service_file_for(module_name: str) -> str:
        mapping = {
            "Export Operations": "services/ai_dashboard_export_operations_service.py",
            "Ops Health": "services/ai_dashboard_ops_health_service.py",
            "Ops Maintenance": "services/ai_dashboard_ops_maintenance_service.py",
            "Architecture Map": "services/ai_dashboard_architecture_map_service.py",
            "Smoke Test": "services/ai_dashboard_smoke_test_service.py",
            "Documentation Center": "services/ai_dashboard_documentation_service.py",
            "Navigation Center": "services/ai_dashboard_navigation_service.py",
        }
        return mapping.get(module_name, "services/article_health_service.py")

    @staticmethod
    def _build_layer_docs(module_catalog: list[dict]) -> list[dict]:
        layers = [
            "Executive Layer",
            "Runtime Layer",
            "Trust & Boundary Layer",
            "Snapshot & Forecast Layer",
            "Ops Layer",
            "Export Layer",
            "Documentation Layer",
            "Learning Layer",
            "Governance Layer",
        ]
        docs = []
        for layer in layers:
            modules = [item["module_name"] for item in module_catalog if item.get("layer") == layer]
            if modules:
                docs.append({"layer": layer, "modules": modules, "summary": f"{layer} contains {len(modules)} documented modules."})
        return docs

    @staticmethod
    def _build_route_docs() -> list[dict]:
        return [
            {"route": "/ai-dashboard", "purpose": "AI Dashboard 主页面", "method": "GET", "permission": "can_approve / can_publish"},
            {"route": "/ai-dashboard/smoke-test", "purpose": "冒烟测试中心", "method": "GET", "permission": "can_approve / can_publish"},
            {"route": "/ai-dashboard/export-operations", "purpose": "导出运营详情", "method": "GET", "permission": "can_approve / can_publish"},
            {"route": "/ai-dashboard/ops-health", "purpose": "运维健康详情", "method": "GET", "permission": "can_approve / can_publish"},
            {"route": "/ai-dashboard/ops-maintenance", "purpose": "维护计划详情", "method": "GET", "permission": "can_approve / can_publish"},
            {"route": "/ai-dashboard/architecture-map", "purpose": "系统架构地图", "method": "GET", "permission": "can_approve / can_publish"},
            {"route": "/ai-dashboard/documentation", "purpose": "文档中心", "method": "GET", "permission": "can_approve / can_publish"},
            {"route": "/ai-dashboard/navigation-index", "purpose": "导航与索引中心", "method": "GET", "permission": "can_approve / can_publish"},
        ]

    @staticmethod
    def _build_export_docs(module_catalog: list[dict]) -> list[dict]:
        docs = []
        for item in module_catalog:
            route = item.get("export_route")
            if not route:
                continue
            export_format = "txt/csv/md" if item.get("module_name") in {"Documentation Center", "Navigation Center"} else "txt/csv"
            docs.append({
                "export_route": route,
                "format": export_format,
                "module": item.get("module_name"),
                "summary": f"{item.get('chinese_name')} export endpoint.",
                "type": "export",
                "title": item.get("chinese_name"),
                "path": route,
                "status": "normal",
                "suggestion": "保持导出接口只读并覆盖 TXT/CSV。",
            })
        docs.append({"export_route": "/ai-dashboard/export-all-reports", "format": "txt/csv/zip", "module": "All Reports", "summary": "批量导出全部报表。", "type": "export", "title": "批量导出全部报表", "path": "/ai-dashboard/export-all-reports", "status": "normal", "suggestion": "保持批量导出历史可追溯。"})
        return docs

    @staticmethod
    def _build_data_file_docs() -> list[dict]:
        return [
            {"type": "data_file", "title": "导出历史", "summary": "记录 Dashboard 批量导出历史。", "path": "data/ai_dashboard_export_history.json", "status": "normal", "suggestion": "JSON 损坏时按空历史兜底。"},
            {"type": "data_file", "title": "运行时快照", "summary": "记录 Runtime Snapshot 历史。", "path": "data/ai_runtime_snapshots.json", "status": "normal", "suggestion": "保持只读页面可降级展示。"},
            {"type": "data_file", "title": "运营评分历史", "summary": "记录 AI 运营评分趋势。", "path": "data/ai_ops_score_history.json", "status": "normal", "suggestion": "异常时不拖垮 Dashboard。"},
            {"type": "data_file", "title": "值班历史", "summary": "记录 AI 运营值班历史。", "path": "data/ai_ops_duty_history.json", "status": "normal", "suggestion": "异常时按空历史处理。"},
        ]

    @staticmethod
    def _build_usage_guides() -> list[dict]:
        return [
            {"type": "guide", "title": "查看总控区", "summary": "从 /ai-dashboard 查看导出、运维、架构和 Runtime 中心。", "path": "/ai-dashboard", "status": "normal", "suggestion": "优先使用顶部总控区定位模块。"},
            {"type": "guide", "title": "查看详情页", "summary": "通过每个中心右上角详情按钮进入独立页面。", "path": "/ai-dashboard/documentation", "status": "normal", "suggestion": "详情页保持只读。"},
            {"type": "guide", "title": "导出文档", "summary": "通过文档中心导出 TXT 或 CSV。", "path": "/ai-dashboard/documentation-export", "status": "normal", "suggestion": "导出不触发业务动作。"},
        ]

    @staticmethod
    def _build_service_docs() -> list[dict]:
        return [
            {"service_file": "services/article_health_service.py", "responsibility": "构建 AI Dashboard Runtime 系列中心。", "key_methods": ["build_ai_risk_dashboard", "build_ai_dashboard_centers"]},
            {"service_file": "services/ai_dashboard_smoke_test_service.py", "responsibility": "运行只读冒烟测试。", "key_methods": ["run_smoke_test"]},
            {"service_file": "services/ai_dashboard_export_operations_service.py", "responsibility": "汇总导出运营状态。", "key_methods": ["build_export_operations_center"]},
            {"service_file": "services/ai_dashboard_ops_health_service.py", "responsibility": "汇总 Dashboard 运维健康。", "key_methods": ["build_ops_health_center"]},
            {"service_file": "services/ai_dashboard_ops_maintenance_service.py", "responsibility": "生成运维维护计划。", "key_methods": ["build_maintenance_plan"]},
            {"service_file": "services/ai_dashboard_architecture_map_service.py", "responsibility": "生成系统架构地图。", "key_methods": ["build_architecture_map"]},
            {"service_file": "services/ai_dashboard_documentation_service.py", "responsibility": "生成统一文档中心。", "key_methods": ["build_documentation_center"]},
            {"service_file": "services/ai_dashboard_navigation_service.py", "responsibility": "生成导航与索引中心。", "key_methods": ["build_navigation_center"]},
        ]

    @staticmethod
    def _build_test_docs() -> list[dict]:
        return [
            {"test_file": "tests/test_article_health_service.py", "coverage": "Runtime Dashboard core", "summary": "覆盖主 Dashboard 和 ArticleHealthService。"},
            {"test_file": "tests/test_ai_dashboard_smoke_test_service.py", "coverage": "Smoke Test", "summary": "覆盖冒烟测试服务。"},
            {"test_file": "tests/test_ai_dashboard_export_operations_service.py", "coverage": "Export Operations", "summary": "覆盖导出运营中心。"},
            {"test_file": "tests/test_ai_dashboard_ops_health_service.py", "coverage": "Ops Health", "summary": "覆盖运维健康中心。"},
            {"test_file": "tests/test_ai_dashboard_ops_maintenance_service.py", "coverage": "Ops Maintenance", "summary": "覆盖维护计划中心。"},
            {"test_file": "tests/test_ai_dashboard_architecture_map_service.py", "coverage": "Architecture Map", "summary": "覆盖架构地图中心。"},
            {"test_file": "tests/test_ai_dashboard_documentation_service.py", "coverage": "Documentation Center", "summary": "覆盖文档中心。"},
            {"test_file": "tests/test_ai_dashboard_navigation_service.py", "coverage": "Navigation Center", "summary": "覆盖导航与索引中心。"},
        ]

    @staticmethod
    def _build_readonly_matrix(module_catalog: list[dict]) -> list[dict]:
        return [
            {
                "module": item.get("module_name"),
                "readonly": True,
                "writes_json": False,
                "writes_business_state": False,
                "affects_review_publish": False,
            }
            for item in module_catalog
        ]

    @staticmethod
    def _build_maintenance_notes() -> list[str]:
        return [
            "新增模块必须加入 Smoke Test",
            "新增模块必须加入 Architecture Map",
            "新增模块必须有 Dashboard title",
            "新增模块必须有导出/测试/页面验证",
            "Runtime 模块必须保持只读",
        ]

    @staticmethod
    def _resolve_documentation_status(module_catalog: list[dict], route_docs: list[dict], export_docs: list[dict], test_docs: list[dict]) -> str:
        core_modules = {"Runtime Observability", "Runtime Alert", "Runtime Orchestrator", "Runtime Executive Dashboard", "Ops Health", "Architecture Map"}
        documented = {item.get("module_name") for item in module_catalog if item.get("dashboard_key") and item.get("service_file")}
        if not core_modules.issubset(documented):
            return "missing"
        incomplete = [
            item for item in module_catalog
            if not item.get("service_file") or not item.get("test_file") or ("Runtime" in item.get("module_name", "") and not item.get("template_title"))
        ]
        if incomplete or not route_docs or not export_docs or not test_docs:
            return "attention"
        return "normal"

    @staticmethod
    def _build_summary(status: str, module_catalog: list[dict], route_docs: list[dict], export_docs: list[dict]) -> str:
        if status == "missing":
            return "AI Dashboard 文档中心缺少核心模块信息，请优先补齐。"
        if status in {"attention", "partial"}:
            return f"AI Dashboard 文档中心已覆盖 {len(module_catalog)} 个模块，但仍有部分信息需补齐。"
        return f"AI Dashboard 文档中心已覆盖 {len(module_catalog)} 个模块、{len(route_docs)} 条路由和 {len(export_docs)} 个导出接口。"

    @staticmethod
    def _build_recommended_actions(status: str, module_catalog: list[dict]) -> list[str]:
        actions = [
            "新增 Dashboard 模块时同步更新文档中心",
            "保持 Smoke Test / Architecture Map / Documentation 三者同步",
            "为新增独立页面补充路由和导出说明",
            "为新增服务补充测试文件",
            "定期复查只读矩阵",
            "保持审核发布边界说明可见",
        ]
        if status not in {"normal", "healthy"}:
            actions.insert(0, "优先补齐缺失的 service/test/export 信息")
        return actions[:8]

    @staticmethod
    def build_documentation_text(center: dict | None = None) -> str:
        center = center or AIDashboardDocumentationService.build_documentation_center()
        lines = [
            "【AI Dashboard 文档中心】",
            "",
            f"文档状态：{center.get('documentation_status') or '-'}",
            f"摘要：{center.get('summary') or '-'}",
            "",
            "模块清单：",
        ]
        for item in center.get("module_catalog") or []:
            lines.append(f"- {item.get('module_name')} / {item.get('layer')} / {item.get('dashboard_key')}")
        return "\n".join(lines)

    @staticmethod
    def build_documentation_markdown(center: dict | None = None) -> str:
        center = center or AIDashboardDocumentationService.build_documentation_center()
        lines = [
            "# AI Dashboard 文档中心",
            "",
            f"- 文档状态：{center.get('documentation_status') or '-'}",
            f"- 摘要：{center.get('summary') or '-'}",
            "",
            "## 模块清单",
        ]
        for item in center.get("module_catalog") or []:
            lines.append(f"- **{item.get('module_name')}**：{item.get('chinese_name')}，层级 `{item.get('layer')}`，Key `{item.get('dashboard_key')}`")
        lines.extend(["", "## 路由清单"])
        for item in center.get("route_docs") or []:
            lines.append(f"- `{item.get('route')}`：{item.get('purpose')}")
        lines.extend(["", "## 导出清单"])
        for item in center.get("export_docs") or []:
            lines.append(f"- `{item.get('export_route')}`：{item.get('module')} / {item.get('format')}")
        lines.extend(["", "## Service 清单"])
        for item in center.get("service_docs") or []:
            lines.append(f"- `{item.get('service_file')}`：{item.get('responsibility')}")
        lines.extend(["", "## 只读矩阵"])
        for item in center.get("readonly_matrix") or []:
            lines.append(f"- {item.get('module')}：readonly={item.get('readonly')}，affects_review_publish={item.get('affects_review_publish')}")
        lines.extend(["", "## 运维备注"])
        for item in center.get("maintenance_notes") or []:
            lines.append(f"- {item}")
        return "\n".join(lines)

    @staticmethod
    def build_documentation_rows(center: dict | None = None) -> list[dict]:
        center = center or AIDashboardDocumentationService.build_documentation_center()
        rows = []
        for item in (
            (center.get("module_docs") or [])
            + (center.get("export_docs") or [])
            + (center.get("route_docs") or [])
            + (center.get("data_file_docs") or [])
            + (center.get("usage_guides") or [])
        ):
            rows.append({
                "文档分类": item.get("type") or "module",
                "标题": item.get("title") or item.get("module") or item.get("route") or item.get("module_name") or "",
                "说明": item.get("summary") or item.get("purpose") or "",
                "路径/路由": item.get("path") or item.get("route") or item.get("export_route") or item.get("service_file") or "",
                "状态": item.get("status") or "normal",
                "建议": item.get("suggestion") or "",
            })
        return rows
