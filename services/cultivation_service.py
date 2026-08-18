"""融资客户培育 Phase 1 领域服务。"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any

from database import get_db, get_lastrowid, get_placeholder, is_mysql

logger = logging.getLogger(__name__)


class CustomerCultivationService:
    INDUSTRIES = ("科技", "软件", "制造", "批发零售", "建筑工程", "服务业", "其他")
    LOAN_STATUSES = ("正常", "即将到期", "已结清", "已逾期", "已续贷", "其他")
    CLOSED_LOAN_STATUSES = ("已结清", "已续贷")
    REPAYMENT_TYPES = ("先息后本", "等额本息", "等额本金", "随借随还", "分段还本", "气球贷", "其他", "不确定")
    FOLLOWUP_STATUSES = ("待处理", "已联系", "已预约诊断", "客户暂无需求", "延期跟进", "已完成")
    TAG_TYPES = ("risk", "stage", "industry", "feature", "need")
    STAGE_THRESHOLDS = ((15, "紧急续贷期"), (30, "到期前30天"), (60, "到期前60天"), (90, "到期前90天"))
    RISK_RANK = {"正常": 0, "关注": 1, "高风险": 2, "紧急": 3}

    @staticmethod
    def _row(row):
        return dict(row) if row is not None else None

    @staticmethod
    def _rows(rows):
        return [dict(row) for row in rows]

    @staticmethod
    def _date(value: Any) -> date | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        try:
            return date.fromisoformat(str(value)[:10])
        except (TypeError, ValueError):
            return None

    @classmethod
    def days_to_expire(cls, expire_date: Any, today: date | None = None) -> int | None:
        parsed = cls._date(expire_date)
        return (parsed - (today or date.today())).days if parsed else None

    @classmethod
    def calculate_stage(cls, customer: dict, nearest_loan: dict | None, today: date | None = None) -> str:
        today = today or date.today()
        if nearest_loan:
            days = cls.days_to_expire(nearest_loan.get("expire_date"), today)
            if days is not None:
                for threshold, stage in cls.STAGE_THRESHOLDS:
                    if days <= threshold:
                        return stage

            start_date = cls._date(nearest_loan.get("start_date"))
            created_at = cls._date(customer.get("created_at"))
            if (start_date and (today - start_date).days <= 30) or (
                created_at and (today - created_at).days <= 30
            ):
                return "贷后0-30天"
            return "贷后1-6个月"
        return "待完善贷款信息"

    @classmethod
    def analyze_rules(
        cls, customer: dict, nearest_loan: dict | None, today: date | None = None
    ) -> tuple[list[tuple[str, str]], str]:
        """返回内部培育标签和最高风险等级，不表达任何银行官方标准。"""
        today = today or date.today()
        tags: list[tuple[str, str]] = []
        levels = ["正常"]
        stage = cls.calculate_stage(customer, nearest_loan, today)
        tags.append(("stage", stage))
        if customer.get("industry"):
            tags.append(("industry", str(customer["industry"])))
        if customer.get("financing_need"):
            tags.append(("need", str(customer["financing_need"])))

        if nearest_loan:
            days = cls.days_to_expire(nearest_loan.get("expire_date"), today)
            if days is not None:
                if days <= 15:
                    tags.append(("risk", "紧急续贷")); levels.append("紧急")
                elif days <= 30:
                    tags.append(("risk", "续贷高风险")); levels.append("高风险")
                elif days <= 60:
                    tags.append(("risk", "续贷高关注")); levels.append("关注")
                elif days <= 90:
                    tags.append(("risk", "即将到期")); levels.append("关注")

        usage = customer.get("credit_card_usage")
        if usage not in (None, ""):
            usage = float(usage)
            if usage > 70:
                tags.append(("risk", "信用卡高使用率")); levels.append("高风险")
            elif usage > 30:
                tags.append(("risk", "信用卡使用率关注")); levels.append("关注")

        query_count = customer.get("credit_query_count")
        if query_count not in (None, ""):
            query_count = int(query_count)
            if query_count > 40:
                tags.append(("risk", "征信查询高风险")); levels.append("高风险")
            elif query_count > 20:
                tags.append(("risk", "征信查询偏多")); levels.append("关注")
            elif query_count >= 10:
                tags.append(("risk", "征信查询关注")); levels.append("关注")

        cashflow = str(customer.get("cashflow_type") or "")
        if cashflow and "对公账户" not in cashflow and any(word in cashflow for word in ("微信", "支付宝", "个人卡")):
            tags.append(("risk", "经营流水待优化")); levels.append("关注")
        if int(customer.get("bank_count") or 0) >= 5:
            tags.append(("risk", "多头贷款关注")); levels.append("关注")
        if customer.get("has_collateral") in (0, False, "0", "false", "False"):
            tags.append(("feature", "无抵押物"))
        if customer.get("has_online_loans") in (1, True, "1", "true", "True"):
            tags.append(("feature", "有网贷"))

        risk_level = max(levels, key=lambda value: cls.RISK_RANK[value])
        return list(dict.fromkeys(tags)), risk_level

    @staticmethod
    def _event(conn, customer_id: int, event_type: str, data: dict | None = None):
        p = get_placeholder()
        conn.execute(
            f"INSERT INTO cultivation_events (customer_id,event_type,event_data) VALUES ({p},{p},{p})",
            (customer_id, event_type, json.dumps(data or {}, ensure_ascii=False)),
        )

    @classmethod
    def create_customer(cls, payload: dict) -> int:
        fields = (
            "company_name", "legal_person", "phone", "industry", "annual_revenue", "source", "advisor_id",
            "consultation_status", "cashflow_type", "credit_card_usage", "credit_query_count", "has_online_loans",
            "bank_count", "has_collateral", "tax_grade", "financing_need",
        )
        if not str(payload.get("company_name") or "").strip():
            raise ValueError("企业名称不能为空")
        p = get_placeholder()
        values = [payload.get(field) if payload.get(field) != "" else None for field in fields]
        values[3] = values[3] or "其他"
        values[7] = values[7] or "未咨询"
        conn = get_db()
        try:
            cursor = conn.execute(
                f"INSERT INTO cultivation_customers ({','.join(fields)}) VALUES ({','.join([p] * len(fields))})",
                tuple(values),
            )
            customer_id = int(get_lastrowid(cursor))
            cls._event(conn, customer_id, "customer_created", {"company_name": values[0]})
            conn.commit()
            cls.refresh_customer(customer_id)
            logger.info("[cultivation-customer-created] customer_id=%s company=%s", customer_id, values[0])
            return customer_id
        except Exception:
            conn.rollback(); raise
        finally:
            conn.close()

    @classmethod
    def update_customer(cls, customer_id: int, payload: dict):
        allowed = (
            "company_name", "legal_person", "phone", "industry", "annual_revenue", "source", "advisor_id",
            "consultation_status", "cashflow_type", "credit_card_usage", "credit_query_count", "has_online_loans",
            "bank_count", "has_collateral", "tax_grade", "financing_need",
        )
        assignments, values = [], []
        p = get_placeholder()
        for field in allowed:
            if field in payload:
                assignments.append(f"{field}={p}")
                values.append(payload[field] if payload[field] != "" else None)
        if not assignments:
            return
        assignments.append("updated_at=CURRENT_TIMESTAMP" if is_mysql() else "updated_at=datetime('now','localtime')")
        values.append(customer_id)
        conn = get_db()
        try:
            conn.execute(f"UPDATE cultivation_customers SET {','.join(assignments)} WHERE id={p} AND is_active=1", tuple(values))
            conn.commit()
        finally:
            conn.close()
        cls.refresh_customer(customer_id)

    @classmethod
    def add_loan(cls, customer_id: int, payload: dict) -> int:
        fields = ("customer_id", "bank_name", "product_name", "loan_amount", "loan_balance", "interest_rate", "start_date", "expire_date", "repayment_type", "loan_term", "status")
        if not str(payload.get("bank_name") or "").strip() or not cls._date(payload.get("expire_date")):
            raise ValueError("贷款银行和到期日期不能为空")
        values = [customer_id] + [payload.get(field) if payload.get(field) != "" else None for field in fields[1:]]
        values[3] = values[3] or 0
        values[8] = values[8] or "不确定"
        values[10] = values[10] or "正常"
        p = get_placeholder()
        conn = get_db()
        try:
            cursor = conn.execute(
                f"INSERT INTO cultivation_loans ({','.join(fields)}) VALUES ({','.join([p]*len(fields))})", tuple(values)
            )
            loan_id = int(get_lastrowid(cursor))
            cls._event(conn, customer_id, "loan_created", {"loan_id": loan_id, "bank_name": values[1]})
            conn.commit()
            logger.info("[cultivation-loan-created] customer_id=%s loan_id=%s bank=%s", customer_id, loan_id, values[1])
        except Exception:
            conn.rollback(); raise
        finally:
            conn.close()
        cls.refresh_customer(customer_id, create_task=True)
        return loan_id

    @classmethod
    def update_loan(cls, loan_id: int, payload: dict):
        p = get_placeholder()
        conn = get_db()
        try:
            loan = cls._row(conn.execute(f"SELECT * FROM cultivation_loans WHERE id={p}", (loan_id,)).fetchone())
            if not loan:
                raise ValueError("贷款不存在")
            allowed = ("bank_name", "product_name", "loan_amount", "loan_balance", "interest_rate", "start_date", "expire_date", "repayment_type", "loan_term", "status")
            assignments, values = [], []
            for field in allowed:
                if field in payload:
                    assignments.append(f"{field}={p}"); values.append(payload[field] if payload[field] != "" else None)
            assignments.append("updated_at=CURRENT_TIMESTAMP" if is_mysql() else "updated_at=datetime('now','localtime')")
            values.append(loan_id)
            conn.execute(f"UPDATE cultivation_loans SET {','.join(assignments)} WHERE id={p}", tuple(values))
            conn.commit()
        finally:
            conn.close()
        cls.refresh_customer(int(loan["customer_id"]), create_task=True)

    @classmethod
    def get_nearest_open_loan(cls, conn, customer_id: int) -> dict | None:
        p = get_placeholder()
        status_placeholders = ",".join([p] * len(cls.CLOSED_LOAN_STATUSES))
        row = conn.execute(
            f"SELECT * FROM cultivation_loans WHERE customer_id={p} AND is_active=1 AND status NOT IN ({status_placeholders}) ORDER BY expire_date ASC,id ASC LIMIT 1",
            (customer_id, *cls.CLOSED_LOAN_STATUSES),
        ).fetchone()
        return cls._row(row)

    @classmethod
    def refresh_customer(cls, customer_id: int, today: date | None = None, create_task: bool = False) -> dict:
        today = today or date.today()
        p = get_placeholder()
        conn = get_db()
        try:
            customer = cls._row(conn.execute(f"SELECT * FROM cultivation_customers WHERE id={p} AND is_active=1", (customer_id,)).fetchone())
            if not customer:
                raise ValueError("客户不存在")
            nearest = cls.get_nearest_open_loan(conn, customer_id)
            stage = cls.calculate_stage(customer, nearest, today)
            tags, risk_level = cls.analyze_rules(customer, nearest, today)
            old_stage, old_risk = customer.get("current_stage"), customer.get("risk_level")
            conn.execute(f"DELETE FROM cultivation_tags WHERE customer_id={p} AND source='system'", (customer_id,))
            for tag_type, tag_name in tags:
                try:
                    conn.execute(
                        f"INSERT INTO cultivation_tags (customer_id,tag_type,tag_name,source) VALUES ({p},{p},{p},'system')",
                        (customer_id, tag_type, tag_name),
                    )
                except Exception as exc:
                    if "unique" not in str(exc).lower() and "duplicate" not in str(exc).lower():
                        raise
            conn.execute(
                f"UPDATE cultivation_customers SET current_stage={p},risk_level={p},updated_at=" +
                ("CURRENT_TIMESTAMP" if is_mysql() else "datetime('now','localtime')") + f" WHERE id={p}",
                (stage, risk_level, customer_id),
            )
            if old_stage != stage:
                event_type = {"到期前90天": "entered_90_day_stage", "到期前60天": "entered_60_day_stage", "到期前30天": "entered_30_day_stage", "紧急续贷期": "entered_15_day_stage"}.get(stage, "lifecycle_changed")
                cls._event(conn, customer_id, event_type, {"from": old_stage, "to": stage})
                logger.info("[cultivation-stage-changed] customer_id=%s from=%s to=%s", customer_id, old_stage, stage)
            if old_risk != risk_level:
                logger.info("[cultivation-risk-changed] customer_id=%s from=%s to=%s", customer_id, old_risk, risk_level)
            conn.commit()
        except Exception:
            conn.rollback(); raise
        finally:
            conn.close()
        task_id = cls.ensure_followup_task(customer_id, nearest, stage, risk_level, today) if create_task and nearest else None
        return {"customer_id": customer_id, "stage": stage, "risk_level": risk_level, "tags": tags, "nearest_loan": nearest, "task_id": task_id}

    @classmethod
    def _trigger_for_stage(cls, stage: str) -> tuple[str, str, str] | None:
        mapping = {
            "到期前90天": ("90_day", "low", "开始准备续贷材料"),
            "到期前60天": ("60_day", "medium", "联系客户确认续贷需求"),
            "到期前30天": ("30_day", "high", "尽快完成续贷/转贷方案评估"),
            "紧急续贷期": ("15_day", "urgent", "立即人工介入，确认续贷及资金安排"),
        }
        return mapping.get(stage)

    @classmethod
    def ensure_followup_task(cls, customer_id: int, loan: dict, stage: str, risk_level: str, today: date | None = None) -> int | None:
        trigger = cls._trigger_for_stage(stage)
        if not trigger:
            return None
        trigger_type, priority, action = trigger
        p = get_placeholder()
        conn = get_db()
        try:
            existing = conn.execute(
                f"SELECT id FROM cultivation_followups WHERE customer_id={p} AND loan_id={p} AND trigger_type={p}",
                (customer_id, loan["id"], trigger_type),
            ).fetchone()
            if existing:
                logger.info("[cultivation-followup-skip-duplicate] customer_id=%s loan_id=%s trigger=%s", customer_id, loan["id"], trigger_type)
                return None
            customer = cls._row(conn.execute(f"SELECT * FROM cultivation_customers WHERE id={p}", (customer_id,)).fetchone())
            article = cls.recommend_article(customer_id, connection=conn)
            cursor = conn.execute(
                f"""INSERT INTO cultivation_followups
                (customer_id,loan_id,task_type,trigger_type,priority,due_date,recommended_article_id,advisor_id,status,followup_note)
                VALUES ({','.join([p]*10)})""",
                (customer_id, loan["id"], "到期提醒", trigger_type, priority, (today or date.today()).isoformat(), article.get("id") if article else None, customer.get("advisor_id"), "待处理", action),
            )
            task_id = int(get_lastrowid(cursor))
            cls._event(conn, customer_id, "followup_created", {"task_id": task_id, "trigger_type": trigger_type})
            conn.commit()
            logger.info("[cultivation-followup-created] customer_id=%s loan_id=%s trigger=%s article_id=%s", customer_id, loan["id"], trigger_type, article.get("id") if article else None)
            return task_id
        except Exception:
            conn.rollback(); raise
        finally:
            conn.close()

    @classmethod
    def recommend_article(cls, customer_id: int, connection=None) -> dict | None:
        owns = connection is None
        conn = connection or get_db()
        p = get_placeholder()
        try:
            customer = cls._row(conn.execute(f"SELECT * FROM cultivation_customers WHERE id={p}", (customer_id,)).fetchone())
            if not customer:
                return None
            risk_tags = {row["tag_name"] for row in conn.execute(f"SELECT tag_name FROM cultivation_tags WHERE customer_id={p} AND tag_type='risk'", (customer_id,)).fetchall()}
            rows = cls._rows(conn.execute("SELECT a.id,a.title,a.summary,t.tag_type,t.tag_value FROM articles a JOIN article_cultivation_tags t ON t.article_id=a.id ORDER BY a.created_at DESC,a.id DESC").fetchall())
            scored: dict[int, dict] = {}
            for row in rows:
                item = scored.setdefault(row["id"], {"id": row["id"], "title": row["title"], "summary": row.get("summary"), "score": 0, "tags": []})
                item["tags"].append((row["tag_type"], row["tag_value"]))
                if row["tag_type"] == "customer_stage" and row["tag_value"] == customer.get("current_stage"):
                    item["score"] += 100
                elif row["tag_type"] == "risk_tag" and row["tag_value"] in risk_tags:
                    item["score"] += 50
                elif row["tag_type"] == "industry_tag" and row["tag_value"] == customer.get("industry"):
                    item["score"] += 20
                elif row["tag_type"] == "industry_tag" and row["tag_value"] == "通用":
                    item["score"] += 5
                elif row["tag_type"] == "cultivation_category":
                    item["score"] += 1
            if not scored:
                logger.info("[cultivation-recommendation-miss] customer_id=%s", customer_id)
                return None
            result = sorted(scored.values(), key=lambda item: (item["score"], item["id"]), reverse=True)[0]
            logger.info("[cultivation-recommendation-success] customer_id=%s article_id=%s score=%s", customer_id, result["id"], result["score"])
            return result
        finally:
            if owns:
                conn.close()

    @classmethod
    def set_article_tags(cls, article_id: int, tags: dict[str, str]):
        allowed = ("cultivation_category", "customer_stage", "risk_tag", "industry_tag")
        p = get_placeholder()
        conn = get_db()
        try:
            conn.execute(f"DELETE FROM article_cultivation_tags WHERE article_id={p}", (article_id,))
            for tag_type in allowed:
                value = str(tags.get(tag_type) or "").strip()
                if value:
                    conn.execute(f"INSERT INTO article_cultivation_tags (article_id,tag_type,tag_value) VALUES ({p},{p},{p})", (article_id, tag_type, value))
            conn.commit()
        except Exception:
            conn.rollback(); raise
        finally:
            conn.close()

    @classmethod
    def record_followup(cls, customer_id: int, payload: dict) -> int:
        p = get_placeholder()
        trigger_type = "manual_" + datetime.now().strftime("%Y%m%d%H%M%S%f")
        conn = get_db()
        try:
            customer = cls._row(conn.execute(f"SELECT advisor_id FROM cultivation_customers WHERE id={p}", (customer_id,)).fetchone())
            completed_sql = "CURRENT_TIMESTAMP" if is_mysql() else "datetime('now','localtime')"
            cursor = conn.execute(
                "INSERT INTO cultivation_followups "
                "(customer_id,task_type,trigger_type,priority,due_date,advisor_id,status,contact_method,followup_result,followup_note,next_followup_at,completed_at) "
                f"VALUES ({','.join([p]*11)},{completed_sql})",
                (customer_id, "人工跟进", trigger_type, "medium", date.today().isoformat(), customer.get("advisor_id") if customer else None, payload.get("status") or "已联系", payload.get("contact_method"), payload.get("followup_result"), payload.get("followup_note"), payload.get("next_followup_at") or None),
            )
            followup_id = int(get_lastrowid(cursor))
            if payload.get("followup_result") in ("有需求", "预约诊断"):
                conn.execute(f"UPDATE cultivation_customers SET consultation_status={p} WHERE id={p}", ("已产生咨询", customer_id))
                cls._event(conn, customer_id, "consultation_created", {"followup_id": followup_id})
            cls._event(conn, customer_id, "followup_completed", {"followup_id": followup_id})
            conn.commit()
            logger.info("[cultivation-followup-completed] customer_id=%s followup_id=%s", customer_id, followup_id)
            return followup_id
        except Exception:
            conn.rollback(); raise
        finally:
            conn.close()

    @classmethod
    def update_followup(cls, followup_id: int, payload: dict):
        p = get_placeholder()
        conn = get_db()
        try:
            followup = cls._row(conn.execute(f"SELECT * FROM cultivation_followups WHERE id={p}", (followup_id,)).fetchone())
            if not followup:
                raise ValueError("跟进任务不存在")
            status = payload.get("status") or followup["status"]
            is_completed = status not in ("待处理", "延期跟进")
            completed_sql = ("CURRENT_TIMESTAMP" if is_mysql() else "datetime('now','localtime')") if is_completed else "NULL"
            conn.execute(
                f"UPDATE cultivation_followups SET status={p},contact_method={p},followup_result={p},followup_note={p},next_followup_at={p},completed_at={completed_sql} WHERE id={p}",
                (status, payload.get("contact_method"), payload.get("followup_result"), payload.get("followup_note"), payload.get("next_followup_at") or None, followup_id),
            )
            if payload.get("followup_result") in ("有需求", "预约诊断") or status == "已预约诊断":
                conn.execute(f"UPDATE cultivation_customers SET consultation_status={p} WHERE id={p}", ("已产生咨询", followup["customer_id"]))
                cls._event(conn, followup["customer_id"], "consultation_created", {"followup_id": followup_id})
            cls._event(conn, followup["customer_id"], "followup_completed", {"followup_id": followup_id, "status": status})
            conn.commit()
            logger.info("[cultivation-followup-completed] customer_id=%s followup_id=%s status=%s", followup["customer_id"], followup_id, status)
        except Exception:
            conn.rollback(); raise
        finally:
            conn.close()

    @classmethod
    def scan_cultivation_customers(cls, today: date | None = None) -> dict:
        today = today or date.today()
        conn = get_db()
        try:
            customer_ids = [int(row["id"]) for row in conn.execute("SELECT id FROM cultivation_customers WHERE is_active=1 ORDER BY id").fetchall()]
        finally:
            conn.close()
        summary = {"scanned": 0, "tasks_created": 0, "errors": 0}
        for customer_id in customer_ids:
            try:
                result = cls.refresh_customer(customer_id, today=today, create_task=True)
                summary["scanned"] += 1
                if result.get("task_id"):
                    summary["tasks_created"] += 1
            except Exception:
                summary["errors"] += 1
                logger.exception("[cultivation-scan-customer-error] customer_id=%s", customer_id)
        logger.info("[cultivation-scan-result] %s", summary)
        return summary


scan_cultivation_customers = CustomerCultivationService.scan_cultivation_customers
