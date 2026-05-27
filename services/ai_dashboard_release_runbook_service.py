from __future__ import annotations

from services.ai_dashboard_ops_health_service import AIDashboardOpsHealthService
from services.ai_dashboard_production_hardening_service import AIDashboardProductionHardeningService
from services.ai_dashboard_release_package_service import AIDashboardReleasePackageService
from services.ai_dashboard_release_readiness_service import AIDashboardReleaseReadinessService
from services.ai_dashboard_smoke_test_service import AIDashboardSmokeTestService


class AIDashboardReleaseRunbookService:
    """Read-only release runbook generator for AI Dashboard."""

    @classmethod
    def build_release_runbook_center(cls) -> dict:
        readiness = cls._safe_call(AIDashboardReleaseReadinessService.build_release_readiness_center)
        release_package = cls._safe_call(AIDashboardReleasePackageService.build_release_package_center)
        hardening = cls._safe_call(AIDashboardProductionHardeningService.build_production_hardening_center)
        ops = cls._safe_call(AIDashboardOpsHealthService.build_ops_health_center)
        smoke = cls._safe_call(AIDashboardSmokeTestService.run_smoke_test)

        runbook_status = cls._resolve_status(readiness, release_package, hardening, smoke)
        return {
            "runbook_status": runbook_status,
            "summary": cls._build_summary(runbook_status, readiness, release_package),
            "pre_release_steps": cls._build_pre_release_steps(readiness, release_package),
            "release_steps": cls._build_release_steps(),
            "post_release_validation": cls._build_post_release_validation(readiness, ops, smoke),
            "rollback_steps": cls._build_rollback_steps(release_package),
            "responsibility_matrix": cls._build_responsibility_matrix(),
            "risk_playbooks": cls._build_risk_playbooks(),
            "verification_commands": cls._build_verification_commands(),
            "common_issues": cls._build_common_issues(),
            "completion_checklist": cls._build_completion_checklist(),
            "recommended_actions": cls._build_recommended_actions(runbook_status),
        }

    @staticmethod
    def _safe_call(fn) -> dict:
        try:
            value = fn()
            return value if isinstance(value, dict) else {}
        except Exception as exc:
            return {"status": "failed", "summary": f"读取上线手册依赖失败：{exc}"}

    @classmethod
    def _resolve_status(cls, readiness: dict, release_package: dict, hardening: dict, smoke: dict) -> str:
        readiness_status = cls._status(readiness, "release_status", "readiness_status")
        package_status = cls._status(release_package, "package_status")
        hardening_status = cls._status(hardening, "hardening_status")
        smoke_status = cls._status(smoke, "status", "smoke_status")
        failed_count = int(smoke.get("failed_count") or smoke.get("fail_count") or 0)

        if (
            readiness_status in {"blocked", "critical", "failed"}
            or package_status in {"blocked", "critical", "not_ready"}
            or smoke_status in {"failed", "fail", "critical"}
            or failed_count > 0
            or hardening_status in {"risky", "critical"}
        ):
            return "blocked"

        if (
            readiness_status in {"conditional", "warning", "attention"}
            or package_status in {"partial", "draft", "warning", "attention"}
            or hardening_status in {"warning", "attention"}
            or (readiness.get("warning_checks") or readiness.get("acceptable_risks"))
            or (release_package.get("manual_confirmation_items") or [])
        ):
            return "needs_review"

        return "ready"

    @staticmethod
    def _status(source: dict, *keys: str) -> str:
        for key in keys:
            value = (source or {}).get(key)
            if value is not None:
                return str(value).strip().lower()
        return ""

    @staticmethod
    def _build_summary(status: str, readiness: dict, release_package: dict) -> str:
        if status == "blocked":
            return "上线执行手册处于阻断状态：上线准备度、上线包、Smoke Test 或生产加固存在阻断项，禁止按手册推进上线。"
        if status == "needs_review":
            return "上线执行手册需要人工复核：当前可作为有条件上线 runbook，但 warning、可接受风险和人工确认项必须逐项确认。"
        release_status = readiness.get("release_status") or "ready"
        package_status = release_package.get("package_status") or "packaged"
        return f"上线执行手册已就绪：Release Readiness={release_status}，Release Package={package_status}，可进入人工执行窗口。"

    @staticmethod
    def _step(title: str, owner: str, verification: str, notes: str) -> dict:
        return {"step": title, "owner": owner, "verification": verification, "notes": notes}

    @classmethod
    def _build_pre_release_steps(cls, readiness: dict, release_package: dict) -> list[dict]:
        steps = [
            cls._step("拉取最新代码", "开发负责人", "确认远端分支和本地提交一致", "只生成步骤，不自动执行 git pull。"),
            cls._step("确认分支", "开发负责人", "记录当前 branch 和 commit hash", "上线前避免从错误分支部署。"),
            cls._step("运行 py_compile", "开发负责人", "python -m py_compile services/ai_dashboard_release_runbook_service.py web_ui/app.py", "本中心仅展示命令。"),
            cls._step("运行 unittest", "开发负责人", "python -m unittest", "归档测试结果文本。"),
            cls._step("备份 data 目录", "运维负责人", "确认备份文件存在且可读", "不自动备份，不自动删除。"),
            cls._step("备份 .env", "运维负责人", "确认备份不泄露到报告", "保留敏感配置恢复路径。"),
            cls._step("检查 Nginx 配置", "运维负责人", "nginx -t", "只作为人工验证命令。"),
            cls._step("检查 systemd 服务", "运维负责人", "systemctl status <service>", "确认服务名、日志路径和 restart policy。"),
            cls._step("检查 RDS 连接", "运维负责人", "使用既有健康检查或数据库连接检查", "不上线前不要变更数据库结构。"),
            cls._step("运行 Smoke Test", "开发负责人", "访问 /ai-dashboard/smoke-test", "确认 Dashboard key/title/route/export 检查通过。"),
        ]
        if readiness.get("blocking_checks") or release_package.get("blocking_issues"):
            steps.insert(0, cls._step("处理阻断项", "开发负责人", "Release Readiness 和 Release Package 均非 blocked", "阻断项未清零时不得上线。"))
        return steps

    @classmethod
    def _build_release_steps(cls) -> list[dict]:
        return [
            cls._step("进入项目目录", "运维负责人", "pwd 显示项目路径", "示例：cd /opt/wechat_auto_publisher。"),
            cls._step("部署代码", "运维负责人", "确认目标 commit 已部署", "可使用 git pull 或既有部署流程，本中心不执行。"),
            cls._step("安装依赖", "运维负责人", "pip install -r requirements.txt", "按生产规范执行，记录输出。"),
            cls._step("重启服务", "运维负责人", "systemctl restart <service>", "本中心不自动重启。"),
            cls._step("检查日志", "运维负责人", "journalctl -u <service> -n 100", "确认无严重错误。"),
            cls._step("访问 /ai-dashboard", "业务验收负责人", "HTTP 200 且页面可见", "确认主入口可用。"),
            cls._step("运行 smoke-test", "开发负责人", "访问 /ai-dashboard/smoke-test", "确认上线后关键检查仍通过。"),
            cls._step("检查核心页面", "业务验收负责人", "Home / Ops Health / Release Readiness 可访问", "记录截图或验收结果。"),
        ]

    @classmethod
    def _build_post_release_validation(cls, readiness: dict, ops: dict, smoke: dict) -> list[dict]:
        return [
            cls._step("Dashboard 可访问", "业务验收负责人", "GET /ai-dashboard 返回 200", "确认主页面正常。"),
            cls._step("Admin Home 可访问", "业务验收负责人", "GET /ai-dashboard/home 返回 200", "确认管理首页可用。"),
            cls._step("Executive Digest 可访问", "业务验收负责人", "GET /ai-dashboard/executive-digest 返回 200", "确认高层摘要可用。"),
            cls._step("Smoke Test pass", "开发负责人", "Smoke Test 无 failed_count", smoke.get("summary") or "运行后记录结果。"),
            cls._step("Ops Health 非 critical", "运维负责人", "Ops Health status != critical", ops.get("summary") or "运维健康需持续观察。"),
            cls._step("Release Readiness 非 blocked", "开发负责人", "Release status != blocked", readiness.get("summary") or "上线后复核准备度。"),
            cls._step("Export route 正常", "开发负责人", "访问导出接口返回 200", "只检查只读导出接口。"),
            cls._step("Ctrl+F 搜索核心模块", "业务验收负责人", "页面可搜索核心模块标题", "确认 Dashboard 标题可见。"),
        ]

    @classmethod
    def _build_rollback_steps(cls, release_package: dict) -> list[dict]:
        steps = [
            cls._step("切回上一个 Git tag", "回滚负责人", "git checkout <previous_tag>", "仅作为手册步骤，不自动执行。"),
            cls._step("恢复 data 备份", "回滚负责人", "确认 data 文件恢复完成", "恢复前保留当前异常现场。"),
            cls._step("恢复 .env", "回滚负责人", "确认环境变量生效", "不要在报告中暴露密钥。"),
            cls._step("重启服务", "回滚负责人", "systemctl restart <service>", "由人工执行。"),
            cls._step("验证 /ai-dashboard", "业务验收负责人", "GET /ai-dashboard 返回 200", "确认回滚后主页面可用。"),
            cls._step("运行 Smoke Test", "开发负责人", "Smoke Test pass", "确认回滚版本健康。"),
            cls._step("检查日志", "运维负责人", "journalctl 无严重错误", "记录回滚结论。"),
        ]
        for item in (release_package.get("rollback_package") or [])[:3]:
            title = item.get("item")
            if title and not any(step["step"] == title for step in steps):
                steps.append(cls._step(title, "回滚负责人", "人工确认", item.get("summary") or "上线包回滚材料。"))
        return steps[:10]

    @staticmethod
    def _build_responsibility_matrix() -> list[dict]:
        return [
            {"role": "开发负责人", "responsibility": "确认代码、测试、Smoke Test、Release Readiness 和核心页面验收。", "checkpoints": ["py_compile", "unittest", "Smoke Test", "Release Readiness"]},
            {"role": "运维负责人", "responsibility": "执行部署窗口内的服务、Nginx、systemd、日志和备份检查。", "checkpoints": ["data 备份", ".env 备份", "nginx -t", "systemctl status"]},
            {"role": "审核发布负责人", "responsibility": "确认审核发布业务流程未被上线变更影响。", "checkpoints": ["审核入口", "发布入口", "权限检查"]},
            {"role": "业务验收负责人", "responsibility": "确认 Dashboard、Admin Home、核心中心和业务页面可访问。", "checkpoints": ["/ai-dashboard", "/ai-dashboard/home", "核心模块 Ctrl+F"]},
            {"role": "回滚负责人", "responsibility": "保管回滚 tag、data 备份、.env 备份和回滚命令说明。", "checkpoints": ["Git tag", "data 备份", ".env 备份", "回滚验证"]},
        ]

    @staticmethod
    def _build_risk_playbooks() -> list[dict]:
        return [
            {"risk": "Dashboard 打不开", "owner": "运维负责人", "response": "检查服务状态、Nginx 反代、应用日志和登录权限。"},
            {"risk": "Smoke Test fail", "owner": "开发负责人", "response": "先定位 failed checks，暂停上线推进，修复后重新运行。"},
            {"risk": "导出失败", "owner": "开发负责人", "response": "检查导出路由、导出目录权限、文件大小和 Export Operations。"},
            {"risk": "JSON 损坏", "owner": "开发负责人", "response": "先备份损坏文件，再人工按 JsonStore 结构恢复。"},
            {"risk": "RDS 连接失败", "owner": "运维负责人", "response": "检查网络、凭据、连接池、RDS 白名单和慢查询。"},
            {"risk": "Nginx 配置异常", "owner": "运维负责人", "response": "运行 nginx -t，失败则回退配置备份。"},
            {"risk": "systemd 服务异常", "owner": "运维负责人", "response": "检查 journalctl、环境变量和工作目录，必要时回滚。"},
        ]

    @staticmethod
    def _build_verification_commands() -> list[dict]:
        return [
            {"command": "python -m py_compile services/ai_dashboard_release_runbook_service.py web_ui/app.py", "purpose": "检查新增 Runbook 服务与 Flask 路由语法。"},
            {"command": "python -m unittest tests.test_ai_dashboard_release_runbook_service", "purpose": "运行上线执行手册专项测试。"},
            {"command": "python -m unittest tests.test_article_health_service", "purpose": "确认 Dashboard 注入不影响文章健康服务。"},
            {"command": "python -m unittest", "purpose": "运行全量测试。"},
            {"command": "systemctl status <service>", "purpose": "生产环境人工检查应用服务状态。"},
            {"command": "journalctl -u <service> -n 100 --no-pager", "purpose": "生产环境人工检查最近日志。"},
            {"command": "nginx -t", "purpose": "生产环境人工检查 Nginx 配置。"},
            {"command": "curl -I https://<domain>/ai-dashboard", "purpose": "生产环境人工检查 Dashboard HTTP 状态。"},
            {"command": "curl -I https://<domain>/ai-dashboard/smoke-test", "purpose": "生产环境人工检查 Smoke Test 页面状态。"},
        ]

    @staticmethod
    def _build_common_issues() -> list[dict]:
        return [
            {"issue": "路径错误", "handling": "确认工作目录、虚拟环境和服务 WorkingDirectory。"},
            {"issue": "端口冲突", "handling": "检查监听端口和反向代理配置。"},
            {"issue": ".env 未生效", "handling": "确认 systemd EnvironmentFile 或启动脚本加载正确。"},
            {"issue": "RDS 不通", "handling": "检查网络、账号、密码、白名单和连接池。"},
            {"issue": "Nginx 反代错误", "handling": "检查 upstream、proxy_pass、超时和 HTTPS 证书。"},
            {"issue": "权限不足", "handling": "检查登录角色、can_approve/can_publish 和导出目录权限。"},
            {"issue": "导出目录过大", "handling": "人工归档旧导出文件，禁止自动删除。"},
        ]

    @staticmethod
    def _build_completion_checklist() -> list[dict]:
        return [
            {"item": "功能可访问", "status": "manual", "summary": "Dashboard 主入口与核心独立页面均可访问。"},
            {"item": "核心页面可访问", "status": "manual", "summary": "Admin Home、Ops Health、Release Readiness、Release Package 可访问。"},
            {"item": "测试通过", "status": "manual", "summary": "py_compile、专项测试、article health、全量 unittest 已归档。"},
            {"item": "日志无严重错误", "status": "manual", "summary": "应用日志和 Web 服务日志无严重错误。"},
            {"item": "回滚方案已准备", "status": "manual", "summary": "Git tag、data 备份、.env 备份和回滚命令说明均已确认。"},
            {"item": "业务流程未受影响", "status": "manual", "summary": "审核发布流程未被本次只读中心改动影响。"},
        ]

    @staticmethod
    def _build_recommended_actions(status: str) -> list[str]:
        if status == "blocked":
            return ["停止上线推进", "先修复阻断项", "重新运行 Smoke Test", "重新生成 Release Readiness 和 Release Package", "确认回滚材料完整"]
        if status == "needs_review":
            return ["人工复核 warning 与可接受风险", "确认 data 与 .env 备份", "归档测试结果", "指定回滚负责人", "上线后加强 Ops Health 观察"]
        return ["按 Runbook 进入上线窗口", "执行上线前检查", "归档验证命令输出", "完成上线后验收", "保留回滚窗口"]

    @classmethod
    def build_release_runbook_text(cls, center: dict | None = None) -> str:
        center = center or cls.build_release_runbook_center()
        lines = [
            "【AI Dashboard 上线执行手册中心】",
            f"状态：{center.get('runbook_status')}",
            center.get("summary") or "",
            "",
            "上线前检查：",
        ]
        for item in center.get("pre_release_steps") or []:
            lines.append(f"- {item.get('step')}（{item.get('owner')}）：{item.get('verification')}")
        lines.append("")
        lines.append("推荐动作：")
        for item in center.get("recommended_actions") or []:
            lines.append(f"- {item}")
        return "\n".join(lines)

    @classmethod
    def build_release_runbook_markdown(cls, center: dict | None = None) -> str:
        center = center or cls.build_release_runbook_center()
        lines = [
            "# AI Dashboard 上线执行手册中心",
            "",
            f"- 状态：{center.get('runbook_status')}",
            f"- 摘要：{center.get('summary')}",
            "",
        ]
        sections = [
            ("上线前检查", "pre_release_steps"),
            ("上线中步骤", "release_steps"),
            ("上线后验收", "post_release_validation"),
            ("回滚步骤", "rollback_steps"),
        ]
        for title, key in sections:
            lines.append(f"## {title}")
            for item in center.get(key) or []:
                lines.append(f"- **{item.get('step')}**（{item.get('owner')}）：{item.get('verification')}。{item.get('notes')}")
            lines.append("")
        lines.append("## 验证命令")
        for item in center.get("verification_commands") or []:
            lines.append(f"- `{item.get('command')}`：{item.get('purpose')}")
        return "\n".join(lines)

    @classmethod
    def build_release_runbook_rows(cls, center: dict | None = None) -> list[dict]:
        center = center or cls.build_release_runbook_center()
        rows = []

        def add(stage: str, item: dict, title_key: str = "step") -> None:
            rows.append({
                "阶段": stage,
                "步骤/事项": item.get(title_key) or item.get("role") or item.get("risk") or item.get("issue") or item.get("item") or item.get("command") or "",
                "负责人": item.get("owner") or item.get("role") or "",
                "验证方式": item.get("verification") or item.get("purpose") or "",
                "备注": item.get("notes") or item.get("summary") or item.get("response") or item.get("handling") or item.get("responsibility") or "",
            })

        for stage, key in [
            ("上线前检查", "pre_release_steps"),
            ("上线中步骤", "release_steps"),
            ("上线后验收", "post_release_validation"),
            ("回滚步骤", "rollback_steps"),
        ]:
            for item in center.get(key) or []:
                add(stage, item)
        for item in center.get("responsibility_matrix") or []:
            add("责任分工", item, "role")
        for item in center.get("risk_playbooks") or []:
            add("风险预案", item, "risk")
        for item in center.get("verification_commands") or []:
            add("验证命令", item, "command")
        for item in center.get("common_issues") or []:
            add("常见问题", item, "issue")
        for item in center.get("completion_checklist") or []:
            add("上线完成确认", item, "item")
        return rows
