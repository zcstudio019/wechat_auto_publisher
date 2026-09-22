# Public Cultivation Multi-Loan Phase 1.3 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Allow one WeChat cultivation customer to create and safely update zero to ten independent loan records from the public registration page.

**Architecture:** Keep `cultivation_customers 1:N cultivation_loans` and submit indexed `loans[n][field]` form fields. The public route parses the indexed cards, the WeChat cultivation service validates all records before writing, updates owned `loan_id` rows in place, inserts rows without IDs, and only marks existing open loans settled after explicit confirmation. Existing single-loan posts and `registration_loan_id` remain compatibility inputs/pointers, not the source of truth.

**Tech Stack:** Flask, Jinja2, vanilla JavaScript, SQLite/MySQL-compatible SQL, unittest.

---

### Task 1: Parse and prefill multiple loans

**Files:**
- Modify: `web_ui/cultivation_public_routes.py`
- Test: `tests/test_cultivation_wechat_registration.py`

1. Add failing tests for two indexed loan cards and update-page refill.
2. Parse `loans[index][field]` into an ordered `loans` list with a maximum of ten.
3. Load every active loan owned by the bound customer into registration context.
4. Preserve one-card legacy form posts as a compatibility fallback.
5. Run the registration tests.

### Task 2: Synchronize loans without replacement or deletion

**Files:**
- Modify: `services/cultivation_wechat_service.py`
- Test: `tests/test_cultivation_wechat_registration.py`

1. Normalize and validate every submitted loan before database writes.
2. Verify each submitted `loan_id` belongs to the current customer.
3. Update existing IDs in place and insert only rows without IDs.
4. Never delete or implicitly settle omitted loan cards.
5. Require `confirm_all_loans_closed=1` before “没有贷款” settles every open loan.
6. Keep the legacy `registration_loan_id` pointing to the first submitted loan.
7. Refresh lifecycle/risk once after the synchronized write.

### Task 3: Build the mobile loan-card UI

**Files:**
- Modify: `web_ui/templates/cultivation_public/register.html`
- Test: `tests/test_cultivation_wechat_registration.py`

1. Render one card per existing loan with hidden `loan_id`.
2. Add product, amount in ten-thousand yuan, expiry, repayment type, and status.
3. Add/remove only unsaved cards and cap the page at ten cards.
4. Compute the total of non-closed cards in the browser.
5. Show explicit “全部已结清” confirmation when switching an existing borrower to no loans.
6. Verify responsive HTML and submitted field names.

### Task 4: Align derived totals and reminders

**Files:**
- Modify: `web_ui/cultivation_routes.py`
- Test: `tests/test_cultivation_routes.py`
- Test: `tests/test_cultivation_wechat_reminders.py`

1. Exclude closed/renewed loans from current total and current loan count.
2. Verify nearest expiry still uses all open loans ordered by expiry.
3. Verify two loans at reminder nodes create two independent reminders.
4. Verify changing an expiry preserves the loan ID and old reminder history.

### Task 5: Regression verification

**Files:**
- Test: all cultivation tests and full test discovery.

1. Run focused public registration, cultivation route, reminder, service, and scheduler tests.
2. Compile changed Python modules and run `git diff --check`.
3. Run the full unittest suite and report unrelated environment failures separately.

