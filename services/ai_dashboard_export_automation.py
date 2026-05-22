"""Read-only AI Dashboard export automation helpers."""

from __future__ import annotations


class AIDashboardExportAutomation:
    """Build a read-only export automation summary for the AI Dashboard."""

    REPORTS = [
        {
            "title": "高管仪表盘 TXT",
            "format": "txt",
            "url": "/ai-dashboard/runtime-executive-dashboard-export?format=txt",
            "summary": "导出 AI 运行时高管仪表盘文本报告。",
        },
        {
            "title": "高管仪表盘 CSV",
            "format": "csv",
            "url": "/ai-dashboard/runtime-executive-dashboard-export?format=csv",
            "summary": "导出 AI 运行时高管仪表盘 CSV 报表。",
        },
        {
            "title": "全部报表 TXT",
            "format": "txt",
            "url": "/ai-dashboard/export-all-reports?format=txt",
            "summary": "导出 AI Dashboard 汇总报表文本包。",
        },
        {
            "title": "全部报表 CSV",
            "format": "csv",
            "url": "/ai-dashboard/export-all-reports?format=csv",
            "summary": "导出 AI Dashboard 汇总报表 CSV 包。",
        },
    ]

    @staticmethod
    def export_all_reports(dashboard: dict | None = None) -> dict:
        """Return the dashboard field for executive export automation."""
        dashboard = dashboard or {}
        exported_reports = []
        for report in AIDashboardExportAutomation.REPORTS:
            exported_reports.append({
                "title": report.get("title"),
                "format": report.get("format"),
                "url": report.get("url"),
                "summary": report.get("summary"),
                "status": "ready",
            })

        executive_dashboard = dashboard.get("ai_runtime_executive_dashboard") or {}
        summary = (
            "AI Runtime Executive Dashboard Export Automation 已就绪，可导出 TXT / CSV 报表。"
            if exported_reports
            else "当前暂无导出报表数据。"
        )
        return {
            "ai_runtime_executive_dashboard_export_automation": {
                "automation_status": "ready" if exported_reports else "empty",
                "summary": summary,
                "source": "ai_runtime_executive_dashboard",
                "source_status": executive_dashboard.get("executive_status") or "empty",
                "exported_reports": exported_reports,
                "recommended_actions": [
                    "按需导出 TXT 或 CSV，不自动触发审核、发布、Agent 或修改文章。"
                ],
            }
        }

    @staticmethod
    def build_export_all_reports_text(dashboard: dict | None = None) -> str:
        """Build TXT content for the all-reports export endpoint."""
        payload = AIDashboardExportAutomation.export_all_reports(dashboard)
        center = payload.get("ai_runtime_executive_dashboard_export_automation") or {}
        reports = list(center.get("exported_reports") or [])
        lines = ["【AI Runtime Executive Dashboard Export Automation】"]
        if not reports:
            lines.append("当前暂无导出报表数据。")
            return "\n".join(lines)
        lines.append(center.get("summary") or "当前暂无导出报表数据。")
        for index, report in enumerate(reports, 1):
            lines.append("")
            lines.append(f"{index}. {report.get('title') or '导出报表'}")
            lines.append(f"   格式：{report.get('format') or ''}")
            lines.append(f"   链接：{report.get('url') or ''}")
            if report.get("summary"):
                lines.append(f"   摘要：{report.get('summary')}")
        return "\n".join(lines)

    @staticmethod
    def build_export_all_reports_rows(dashboard: dict | None = None) -> list[dict]:
        """Build CSV rows for the all-reports export endpoint."""
        payload = AIDashboardExportAutomation.export_all_reports(dashboard)
        center = payload.get("ai_runtime_executive_dashboard_export_automation") or {}
        rows = []
        for report in list(center.get("exported_reports") or []):
            rows.append({
                "报表名称": report.get("title") or "",
                "格式": report.get("format") or "",
                "状态": report.get("status") or "",
                "链接": report.get("url") or "",
                "摘要": report.get("summary") or "",
            })
        if rows:
            return rows
        return [{
            "报表名称": "AI Runtime Executive Dashboard Export Automation",
            "格式": "",
            "状态": "empty",
            "链接": "",
            "摘要": "当前暂无导出报表数据。",
        }]
