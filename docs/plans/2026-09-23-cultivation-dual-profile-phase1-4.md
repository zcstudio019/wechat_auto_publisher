# Cultivation Dual Profile Phase 1.4 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add company and individual financing profiles without splitting the customer, loan, WeChat reminder, or lifecycle systems.

**Architecture:** Extend `cultivation_customers` with a stable profile enum and individual MVP columns, centralize profile validation/display in the cultivation services, and conditionally render the existing admin and public forms. Keep all loans in `cultivation_loans` and preserve existing loan rows during profile updates.

**Tech Stack:** Python, Flask, Jinja2, SQLite/MySQL-compatible SQL, unittest/pytest

---

### Task 1: Add an idempotent dual-profile schema migration

**Files:**
- Modify: `services/cultivation_schema.py`
- Test: `tests/test_cultivation_service.py`

**Steps:**
1. Add a failing test that initializes an old customer table, reruns initialization twice, and asserts the new columns, `company` backfill, and nullable `company_name`.
2. Run the focused test and confirm failure.
3. Add profile columns to fresh SQLite/MySQL definitions and an idempotent legacy migration.
4. Run the focused test and confirm pass.

### Task 2: Add profile-aware service validation and display metadata

**Files:**
- Modify: `services/cultivation_service.py`
- Test: `tests/test_cultivation_service.py`

**Steps:**
1. Add failing tests for enterprise-name validation, personal creation without enterprise name, personal fields, display name, and history preservation while switching modes.
2. Add enum constants, field allowlists, validation, normalization, and customer decoration helpers.
3. Run service tests.

### Task 3: Extend public WeChat registration

**Files:**
- Modify: `services/cultivation_wechat_service.py`
- Modify: `web_ui/cultivation_public_routes.py`
- Modify: `web_ui/templates/cultivation_public/register.html`
- Test: `tests/test_cultivation_wechat_registration.py`

**Steps:**
1. Add failing registration tests for both profile types, conditional required fields, update-mode restoration, multiple personal loans, and loan preservation.
2. Add profile-aware form normalization and per-type weak deduplication.
3. Add the subject-type selector, conditional sections, personal qualification fields, and non-destructive switching JavaScript.
4. Run registration tests.

### Task 4: Extend admin forms and customer views

**Files:**
- Modify: `web_ui/cultivation_routes.py`
- Modify: `web_ui/templates/cultivation/customer_form.html`
- Modify: `web_ui/templates/cultivation/customers.html`
- Modify: `web_ui/templates/cultivation/dashboard.html`
- Modify: `web_ui/templates/cultivation/customer_detail.html`
- Modify: `web_ui/templates/cultivation/loans.html`
- Modify: `web_ui/templates/cultivation/followups.html`
- Modify: `web_ui/templates/cultivation/tags.html`
- Test: `tests/test_cultivation_routes.py`

**Steps:**
1. Add failing route tests for personal creation, type filtering, company/personal display, detail sections, and absence of technical enum values.
2. Parse new fields and booleans, decorate every joined customer row, and add the type filter.
3. Implement conditional admin fields and unified display names across all cultivation pages.
4. Run route tests.

### Task 5: Regression and visual verification

**Files:**
- Test: `tests/test_cultivation_scheduler.py`
- Test: `tests/test_cultivation_wechat_reminders.py`

**Steps:**
1. Run all cultivation service, route, registration, scheduler, and reminder tests.
2. Run the full test suite.
3. Start the local web app and inspect enterprise/individual registration and admin pages.
4. Fix any regression or visual issue, rerun affected tests, and record final counts.
