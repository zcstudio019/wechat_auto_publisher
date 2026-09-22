# Cultivation WeChat Reminder Phase 1.2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Connect cultivation loan maturity nodes to truthful WeChat customer-message delivery status and separate the “咨询” keyword from profile registration.

**Architecture:** Add an independent reminder ledger keyed by customer, loan, and reminder node. The daily cultivation scan remains responsible for lifecycle and follow-up creation, then delegates delivery decisions to a reminder service. The service sends only through the existing WeChat API client, records success only after an `errcode=0` response, and degrades missing bindings, expired interaction windows, or platform permission limits to manual contact.

**Tech Stack:** Flask, SQLite/MySQL-compatible SQL, APScheduler, existing `wechat_api.client`, unittest.

---

### Task 1: Lock the reminder contract with failing tests

**Files:**
- Create: `tests/test_cultivation_wechat_reminders.py`
- Modify: `tests/test_cultivation_wechat_registration.py`

**Steps:**
1. Add tests for 60/30/15/0/overdue node selection and message text.
2. Add due-today delivery, no-OpenID, platform-limit, and duplicate-scan tests.
3. Add tests proving “咨询” returns configured contact details without a registration URL.
4. Run the focused tests and confirm they fail before implementation.

### Task 2: Add an idempotent reminder ledger

**Files:**
- Modify: `services/cultivation_schema.py`
- Modify: `tests/test_cultivation_service.py`

**Steps:**
1. Create `cultivation_wechat_reminders` for SQLite and MySQL.
2. Add `last_interaction_at` to `cultivation_wechat_users` through the existing safe migration helper.
3. Add a unique key on `(customer_id, loan_id, reminder_type)`.
4. Run schema initialization twice and verify no duplicate or migration error.

### Task 3: Add the truthful customer-message sender

**Files:**
- Modify: `wechat_api/client.py`
- Modify: `wechat_api/__init__.py`
- Create: `services/cultivation_wechat_reminder_service.py`

**Steps:**
1. Add a text-only wrapper for `/message/custom/send` using the existing access-token and HTTP helpers.
2. Treat only WeChat `errcode=0` as success.
3. Build reminder text for 60/30/15/0/overdue nodes.
4. Mark no binding, unsubscribed users, expired interaction windows, and permission/time-window API responses as `manual_required`.
5. Mark unexpected transport/API errors as `failed` and never loop-send.

### Task 4: Integrate with the daily scan and callback activity

**Files:**
- Modify: `services/cultivation_service.py`
- Modify: `services/cultivation_wechat_service.py`
- Modify: `web_ui/wechat_callback_routes.py`
- Modify: `scheduler_app.py`

**Steps:**
1. Process every active, unclosed loan after each customer lifecycle refresh.
2. Create special `due_today` and `overdue` follow-up tasks when applicable.
3. Update `last_interaction_at` on inbound subscribe/text activity.
4. Extend scan summaries without changing the 09:00 scheduler or its exception isolation.

### Task 5: Separate “咨询” and expose delivery state

**Files:**
- Modify: `config.py`
- Modify: `.env.example`
- Modify: `web_ui/cultivation_routes.py`
- Modify: `web_ui/templates/cultivation/dashboard.html`
- Modify: `web_ui/templates/cultivation/followups.html`
- Modify: `web_ui/templates/cultivation/customer_detail.html`

**Steps:**
1. Add `CULTIVATION_CONTACT_NAME`, `CULTIVATION_CONTACT_PHONE`, and `CULTIVATION_CONTACT_WECHAT`.
2. Make “咨询” return only contact details; keep “建档/档案/更新档案” on registration URLs.
3. Add Chinese reminder state badges to dashboard, follow-ups, and customer detail.
4. Ensure unknown internal states never leak to operations users.

### Task 6: Verify and report

**Files:**
- Test all files above plus existing cultivation, scheduler, article, and publish tests.

**Steps:**
1. Run focused reminder and callback tests.
2. Run idempotent local migration.
3. Run cultivation, Scheduler, article, draft, and publish regression suites.
4. Report that real WeChat receipt is verified only if a live eligible OpenID receives a successful API response; otherwise report the exact manual-required reason.
