# 贷款行业底层规律型文章 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an `industry_law` article mode that generates non-homogeneous enterprise-finance articles while leaving publication, QR, cover, and review flows unchanged.

**Architecture:** Add a structured topic library to `TopicEngine`; route its metadata through the existing asynchronous generation/save path; give the generation agent and local fallback a constrained eight-part structure. Add a default writing template and focused service tests.

**Tech Stack:** Python, Flask, SQLite/MySQL-compatible database helpers, unittest.

---

### Task 1: Define industry-law topic data

**Files:**
- Modify: `services/topic_engine.py`
- Test: `tests/test_content_growth_services.py`

**Step 1:** Add eight core-law topic records with the required public fields.

**Step 2:** Implement `generate_industry_law_topics()` and preserve legacy topic output.

**Step 3:** Assert a returned record has `article_type=industry_law` and all requested metadata.

### Task 2: Generate industry-law content

**Files:**
- Modify: `services/article_generation_agent.py`
- Modify: `ai_processor/content_writer.py`
- Modify: `services/title_guard.py`
- Modify: `services/title_score_service.py`
- Test: `tests/test_content_growth_services.py`

**Step 1:** Add an explicit prompt/normalization branch and safe title validation.

**Step 2:** Add a deterministic fallback with anti-conventional opening, scenario, 3--5 explained laws, actions, conclusion, and CTA text only.

**Step 3:** Make template writing recognize `industry_law` without emitting QR markup.

**Step 4:** Test structure, title guard, and fallback behavior.

### Task 3: Persist template and wire dashboard generation

**Files:**
- Modify: `database.py`
- Modify: `web_ui/app.py`
- Test: `tests/test_content_growth_services.py`

**Step 1:** Seed the `industry_law` default template idempotently.

**Step 2:** Carry topic metadata into the existing background save call, preserving source/generated title fields and draft review status.

**Step 3:** Expose the new topic category to the recommendation payload and test the save endpoint.

### Task 4: Verify

**Files:**
- Test: `tests/test_content_growth_services.py`

**Step 1:** Run the requested unittest module.

**Step 2:** Run the requested `py_compile` command against all touched runtime modules.

