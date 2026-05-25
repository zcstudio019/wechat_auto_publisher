"""Read-only architecture map for AI Dashboard modules."""

from __future__ import annotations


class AIDashboardArchitectureMapService:
    """Build a system-level architecture map without changing runtime state."""

    RUNTIME_LAYERS = [
        {
            "layer": "Executive Layer",
            "modules": ["Runtime Executive Dashboard", "Runtime Orchestrator"],
            "summary": "汇总运行时状态、优先级、跨模块依赖和管理层视角。",
        },
        {
            "layer": "Governance Layer",
            "modules": ["Control Policy", "Policy Gate", "Governance", "Trust", "Confidence"],
            "summary": "承载治理规则、策略闸门、信任与置信度判断。",
        },
        {
            "layer": "Runtime Layer",
            "modules": ["Observability", "Alert", "Incident", "Recovery", "Postmortem"],
            "summary": "负责运行时观测、告警、事故、恢复和复盘链路。",
        },
        {
            "layer": "Forecast Layer",
            "modules": ["Snapshot", "Timeline", "Forecast", "Predictive Action", "Continuous Improvement"],
            "summary": "从快照和时间线生成预测、预防动作和持续改进建议。",
        },
        {
            "layer": "Learning Layer",
            "modules": ["Learning", "Knowledge Sync", "Weekly Review", "Feedback Loop", "Evolution"],
            "summary": "沉淀学习、知识同步、周复盘、反馈闭环和演进记录。",
        },
        {
            "layer": "Export/Ops Layer",
            "modules": ["Export Operations", "Ops Health", "Ops Maintenance", "Smoke Test"],
            "summary": "提供只读导出、健康检查、维护计划和冒烟测试。",
        },
        {
            "layer": "Boundary Layer",
            "modules": ["Boundary", "Delegation Readiness"],
            "summary": "识别人工边界、授权准备度和可执行范围。",
        },
        {
            "layer": "Constitution Layer",
            "modules": ["Constitution", "Policy Gate"],
            "summary": "作为高约束层，约束策略、边界和人工复核要求。",
        },
    ]

    MODULE_RELATIONSHIPS = [
        ("Snapshot", "Timeline", "快照形成时间线。"),
        ("Timeline", "Forecast", "时间线支撑趋势预测。"),
        ("Forecast", "Predictive Action", "预测结果生成预防动作。"),
        ("Predictive Action", "Continuous Improvement", "预测动作进入持续改进清单。"),
        ("Trust", "Delegation Readiness", "信任状态影响授权准备度。"),
        ("Constitution", "Policy Gate", "宪法约束策略闸门。"),
        ("Runtime Orchestrator", "Control Policy", "编排结果影响控制策略。"),
        ("Runtime Orchestrator", "Policy Gate", "编排阻塞影响闸门判断。"),
        ("Smoke Test", "Ops Health", "冒烟测试结果进入运维健康中心。"),
        ("Ops Health", "Ops Maintenance", "健康风险生成维护计划。"),
        ("Export Operations", "Ops Health", "导出运营状态进入健康检查。"),
    ]

    DATA_DEPENDENCIES = [
        ("Runtime Snapshot", "ai_runtime_snapshots.json", "运行时快照依赖本地 JSON 历史。"),
        ("Runtime Timeline", "snapshot/history data", "时间线依赖快照、事件和导出历史。"),
        ("Runtime Forecast", "timeline center", "预测依赖时间线和健康趋势。"),
        ("Ops Health", "Smoke Test", "运维健康依赖冒烟测试结果。"),
        ("Ops Health", "Export Operations", "运维健康依赖导出运营结果。"),
        ("Export Operations", "ai_dashboard_export_history.json", "导出运营依赖批量导出历史。"),
        ("Ops Maintenance", "Ops Health", "维护计划依赖运维健康结果。"),
    ]

    RISK_PROPAGATION_PATHS = [
        ["Smoke Test fail", "Ops Health warning", "Ops Maintenance urgent"],
        ["Runtime Incident critical", "Recovery warning", "Trust下降", "Delegation readiness下降"],
        ["Snapshot broken", "Timeline incomplete", "Forecast unreliable", "Predictive Action weak"],
        ["Constitution missing", "Policy Gate weak", "Automation boundary unclear"],
        ["Export failure", "Ops Health warning", "Maintenance cleanup/archive task"],
    ]

    AUTOMATION_BOUNDARIES = [
        {"module": "Export Operations", "boundary": "semi-automated", "summary": "可触发现有导出接口，但不自动发布或修改业务数据。"},
        {"module": "Smoke Test", "boundary": "automated-readonly", "summary": "可自动运行只读检查。"},
        {"module": "Ops Health", "boundary": "automated-readonly", "summary": "自动汇总健康状态但不修复。"},
        {"module": "Ops Maintenance", "boundary": "plan-only", "summary": "只生成维护计划，不执行清理或修复。"},
        {"module": "Predictive Action", "boundary": "recommendation-only", "summary": "只生成预测建议，不执行动作。"},
    ]

    HUMAN_BOUNDARIES = [
        {"module": "审核", "summary": "内容审核必须人工确认。"},
        {"module": "发布", "summary": "发布必须由具备权限的人触发。"},
        {"module": "Constitution", "summary": "宪法与高层规则调整必须人工决策。"},
        {"module": "Boundary", "summary": "边界调整必须人工确认。"},
        {"module": "Policy Gate", "summary": "策略闸门结论只辅助人工判断。"},
    ]

    READONLY_BOUNDARIES = [
        {"module": "Forecast", "summary": "只读预测，不执行动作。"},
        {"module": "Timeline", "summary": "只读展示时间线。"},
        {"module": "Learning", "summary": "只读沉淀学习信号，不改知识库。"},
        {"module": "Executive Dashboard", "summary": "只读总览。"},
        {"module": "Ops Health", "summary": "只读健康检查。"},
        {"module": "Ops Maintenance", "summary": "只读维护计划。"},
        {"module": "Architecture Map", "summary": "只读架构地图，不重构。"},
    ]

    CORE_CONTROL_CENTERS = ["Runtime Orchestrator", "Constitution", "Policy Gate", "Executive Dashboard"]
    HIGH_COUPLING_MODULES = ["Runtime Orchestrator", "Executive Dashboard", "Ops Health"]
    SINGLE_POINT_RISKS = ["ai_dashboard_runtime_service.py / ArticleHealthService runtime section", "web_ui/templates/ai_dashboard.html"]
    RUNTIME_DEPENDENCY_CHAIN_LENGTH = 5
    BOUNDARIES_CLEAR = True

    @classmethod
    def build_architecture_map(cls) -> dict:
        runtime_layers = cls._build_runtime_layers()
        module_relationships = cls._build_module_relationships()
        data_dependencies = cls._build_data_dependencies()
        risk_propagation_paths = cls._build_risk_paths()
        automation_boundaries = list(cls.AUTOMATION_BOUNDARIES)
        manual_boundaries = list(cls.HUMAN_BOUNDARIES)
        read_only_boundaries = list(cls.READONLY_BOUNDARIES)
        control_centers = [{"module": item, "summary": "核心控制或汇总枢纽。"} for item in cls.CORE_CONTROL_CENTERS]
        high_coupling_modules = [{"module": item, "reason": "连接多个运行时中心或运维中心。"} for item in cls.HIGH_COUPLING_MODULES]
        single_point_risks = [{"module": item, "risk": "模块集中度较高，后续变更需重点回归。"} for item in cls.SINGLE_POINT_RISKS]
        architecture_risks = cls._build_architecture_risks(
            runtime_layers,
            risk_propagation_paths,
            automation_boundaries,
            high_coupling_modules,
            single_point_risks,
        )
        architecture_status = cls._resolve_architecture_status(
            runtime_layers,
            risk_propagation_paths,
            automation_boundaries,
            high_coupling_modules,
            single_point_risks,
        )
        recommended_actions = cls._build_recommended_actions(architecture_status, high_coupling_modules, single_point_risks)

        return {
            "architecture_status": architecture_status,
            "summary": cls._build_summary(architecture_status, runtime_layers, architecture_risks),
            "runtime_layers": runtime_layers,
            "module_relationships": module_relationships,
            "data_dependencies": data_dependencies,
            "risk_propagation_paths": risk_propagation_paths,
            "automation_boundaries": automation_boundaries,
            "manual_boundaries": manual_boundaries,
            "read_only_boundaries": read_only_boundaries,
            "human_boundaries": manual_boundaries,
            "readonly_boundaries": read_only_boundaries,
            "control_centers": control_centers,
            "core_control_centers": control_centers,
            "high_coupling_modules": high_coupling_modules,
            "single_point_risks": single_point_risks,
            "architecture_risks": architecture_risks,
            "recommended_actions": recommended_actions,
        }

    @classmethod
    def _build_runtime_layers(cls) -> list[dict]:
        return [dict(item) for item in cls.RUNTIME_LAYERS]

    @classmethod
    def _build_module_relationships(cls) -> list[dict]:
        return [
            {"source": source, "target": target, "relationship": relationship}
            for source, target, relationship in cls.MODULE_RELATIONSHIPS
        ]

    @classmethod
    def _build_data_dependencies(cls) -> list[dict]:
        return [
            {"module": module, "depends_on": depends_on, "summary": summary}
            for module, depends_on, summary in cls.DATA_DEPENDENCIES
        ]

    @classmethod
    def _build_risk_paths(cls) -> list[dict]:
        return [
            {"path": path, "summary": " -> ".join(path)}
            for path in cls.RISK_PROPAGATION_PATHS
        ]

    @classmethod
    def _resolve_architecture_status(
        cls,
        runtime_layers: list[dict],
        risk_paths: list[dict],
        automation_boundaries: list[dict],
        high_coupling: list[dict],
        single_points: list[dict],
    ) -> str:
        if (
            len(single_points) > 4
            or len(high_coupling) > 5
            or cls.RUNTIME_DEPENDENCY_CHAIN_LENGTH > 6
        ):
            return "critical"
        if (
            not runtime_layers
            or len(risk_paths) > 6
            or not automation_boundaries
            or not cls.BOUNDARIES_CLEAR
        ):
            return "warning"
        return "normal"

    @classmethod
    def _build_architecture_risks(
        cls,
        runtime_layers: list[dict],
        risk_paths: list[dict],
        automation_boundaries: list[dict],
        high_coupling: list[dict],
        single_points: list[dict],
    ) -> list[dict]:
        risks = []
        if not runtime_layers:
            risks.append({"risk": "Runtime layer 不清晰", "level": "warning", "summary": "未识别到运行时层级。"})
        if len(risk_paths) > 4:
            risks.append({"risk": "风险传播路径复杂", "level": "warning", "summary": f"已识别 {len(risk_paths)} 条风险传播链。"})
        if not automation_boundaries or not cls.BOUNDARIES_CLEAR:
            risks.append({"risk": "自动化边界不明确", "level": "warning", "summary": "需要明确自动化、半自动化和人工边界。"})
        if high_coupling:
            risks.append({"risk": "高耦合模块集中", "level": "warning", "summary": "、".join(item.get("module", "") for item in high_coupling[:5])})
        if single_points:
            risks.append({"risk": "单点风险模块", "level": "warning", "summary": "、".join(item.get("module", "") for item in single_points[:5])})
        if cls.RUNTIME_DEPENDENCY_CHAIN_LENGTH > 6:
            risks.append({"risk": "Runtime dependency chain 过长", "level": "critical", "summary": f"当前链路长度 {cls.RUNTIME_DEPENDENCY_CHAIN_LENGTH}。"})
        return risks[:10]

    @staticmethod
    def _build_summary(status: str, runtime_layers: list[dict], architecture_risks: list[dict]) -> str:
        if status in {"critical", "risky"}:
            return f"AI Dashboard 架构存在较高风险，已识别 {len(architecture_risks)} 个架构风险点。"
        if status == "warning":
            return f"AI Dashboard 架构需要关注，已识别 {len(runtime_layers)} 个层级和 {len(architecture_risks)} 个风险点。"
        return f"AI Dashboard 架构层级和边界清晰，当前识别 {len(runtime_layers)} 个核心层级。"

    @staticmethod
    def _build_recommended_actions(status: str, high_coupling: list[dict], single_points: list[dict]) -> list[str]:
        actions = [
            "后续优先拆分高耦合 Runtime 模块",
            "避免继续堆叠单页面",
            "建议增加模块索引页",
            "建议增加 Runtime 文档中心",
            "为核心控制中心建立回归测试清单",
            "为风险传播链补充架构说明",
            "保持自动化边界和人工边界分离",
            "将只读中心继续与业务写入隔离",
        ]
        if status in {"critical", "risky"}:
            actions.insert(0, "优先梳理单点风险和依赖长链")
        if len(high_coupling) > 3:
            actions.append("为高耦合模块增加分层接口说明")
        if len(single_points) > 2:
            actions.append("为单点风险文件增加变更检查表")
        return actions[:10]

    @staticmethod
    def build_architecture_text(center: dict | None = None) -> str:
        center = center or AIDashboardArchitectureMapService.build_architecture_map()
        lines = [
            "【AI Dashboard 系统架构地图中心】",
            "",
            f"架构状态：{center.get('architecture_status') or 'unknown'}",
            f"摘要：{center.get('summary') or '-'}",
            "",
            "Runtime 架构层级：",
        ]
        for item in center.get("runtime_layers") or []:
            lines.append(f"- {item.get('layer')}: {', '.join(item.get('modules') or [])}")
        lines.extend(["", "架构建议："])
        for index, action in enumerate(center.get("recommended_actions") or [], start=1):
            lines.append(f"{index}. {action}")
        return "\n".join(lines)

    @staticmethod
    def build_architecture_rows(center: dict | None = None) -> list[dict]:
        center = center or AIDashboardArchitectureMapService.build_architecture_map()
        rows = []

        def add(layer: str, module: str, status: str, risk: str, suggestion: str):
            rows.append({"层级": layer, "模块": module, "状态": status, "风险": risk, "建议": suggestion})

        add("架构地图", "架构摘要", center.get("architecture_status") or "", "", center.get("summary") or "")
        for item in center.get("runtime_layers") or []:
            add(item.get("layer") or "", " / ".join(item.get("modules") or []), center.get("architecture_status") or "", "", item.get("summary") or "")
        for item in center.get("module_relationships") or []:
            add("模块关系", f"{item.get('source')} -> {item.get('target')}", "已映射", "", item.get("relationship") or "")
        for item in center.get("architecture_risks") or []:
            add("架构风险", item.get("risk") or "", item.get("level") or "", item.get("summary") or "", "；".join(center.get("recommended_actions") or []))
        return rows
