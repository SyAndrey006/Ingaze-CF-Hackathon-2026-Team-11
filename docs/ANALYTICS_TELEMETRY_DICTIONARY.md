# Data Guide & Dictionary — Understanding Both JSON Datasets ("What Is What")

> **Files documented in this guide:**
> 1. **[`data/ingaze_sandbox_dataset.json`](../data/ingaze_sandbox_dataset.json)** *(Core Sandbox Dataset)* — HR domain context, empirical research snippets, 11 completed historical case studies, 3 active incoming client scenarios to diagnose, and the output template.
> 2. **[`data/ingaze_synthetic_analytics_snapshots.json`](../data/ingaze_synthetic_analytics_snapshots.json)** *(Optional Quantitative Companion)* — Aggregated synthetic multi-channel telemetry and sector peer benchmarks (`T0 -> T1` for the 11 historical cases + `T0` intake snapshot for the 3 active client scenarios).
>
> **Architectural freedom:** How you ingest, represent, join, weight, or ignore any section of these two files is **100% up to your team**. Nothing in this guide prescribes a specific data structure or reasoning pipeline.

---

## Part 1 — Guide to `data/ingaze_sandbox_dataset.json` ("What Is What")

Because `ingaze_sandbox_dataset.json` bundles domain reference material, past project precedents, active client problems, and the output schema in a single self-contained file, here is the exact role of each top-level key:

### 1.1 The 5 Top-Level Blocks & Their Roles

| Top-Level Key | Records | Role in Your System | Important Distinction |
| :--- | :---: | :--- | :--- |
| **`domain_pillars_and_causal_dynamics`** | `4` pillars + `6` field notes | **General HR Domain Context** — Overview of the 4 HR areas (`pillars`: `pillar_name`, `focus_areas`, `key_board_metrics`) plus `raw_cross_pillar_rules_to_structure` (6 qualitative field notes on cross-pillar dynamics, channel differences, and strategic restraint). | General domain knowledge — **not** data about a specific client. |
| **`raw_empirical_research_snippets`** | `10` studies | **Reference Research Evidence** — Industry & academic findings (`snippet_no`, `source`, `finding`) quantifying Say-Do Gap churn, mobile drop-off, advocacy multipliers, manager coaching impact, and CFO budget criteria. | External benchmark evidence you can use or cite to ground diagnoses and expected ROI. |
| **`raw_case_study_narratives`** | `11` past projects | **Historical Precedent Library** — Anonymized B2B client engagements **already completed in the past**, showing what problem they had (`T0`), what sequence of actions was run, and what ROI was achieved (`T1`). | **Do NOT generate new action plans for these 11 companies** — they are past precedents to learn from, compare against, or retrieve! |
| **`company_scenarios_to_diagnose`** | `3` active clients | **The 3 Target Clients to Solve** (`CloudNova`, `EuroFreight`, `VerdeCare`) — Incoming client intake combining external platform signals and internal client context. | **These are the 3 companies your PoC diagnoses and recommends actions for** in `submission.json`. |
| **`poc_scenario_output_format`** | `1` schema example | **Output Format Reference** (`note` + `example_submission_structure`) — Illustrates the JSON shape expected by `starter_baseline_and_validator.py --validate`. | Output template only — **not** domain input data. |

---

### 1.2 Inside `raw_case_study_narratives` (`11` Completed Past Engagements)

Each object represents a **finished historical project** across Tech/FinTech, Logistics, Retail, Healthcare, Banking, CleanTech, or B-Corp sectors:

| Field | What It Contains |
| :--- | :--- |
| `case_name` | Company label & industry descriptor. **Also acts as the exact `1:1` join key** to `case_study_analytics_snapshots[].case_name` in `ingaze_synthetic_analytics_snapshots.json`. |
| `sector_and_profile` | Sector, approximate employee headcount / multi-site footprint, and target talent or cultural profile. |
| `initial_challenge` | Narrative summary of the pain points, bottlenecks, or healthy starting conditions **before** the project (`T0`). |
| `intervention_sequence` | Numbered chronological steps (`1. ... 2. ... 3. ...`) implemented during the engagement. |
| `measured_roi` | Verified business, conversion, reach, HR time-saved, or retention outcomes **after** execution (`T1`). |

---

### 1.3 Inside `company_scenarios_to_diagnose` (`3` Active Clients to Solve)

Each of the 3 scenarios represents a **new client arriving at intake** and separates what external data shows (*Outside-In*) from what internal stakeholders report (*Inside-Out*):

| Field / Sub-Object | What It Contains & How to Read It |
| :--- | :--- |
| **Company Profile Keys**<br>(`scenario_code`, `company_name`, `industry`, `headcount_and_footprint`, `workforce_target`, `organizational_context`) | Core identity of the client: industry, multi-hub/store/clinic footprint, **which specific roles they urgently need to hire or retain** (`workforce_target`), governance context, and their currently declared EVP. `scenario_code` **also acts as the exact `1:1` join key** to `active_scenario_analytics_snapshots[].scenario_code`. |
| **`ingaze_platform_signals`** *(Outside-In)*<br>• `reputation_and_reviews`<br>• `recruiting_and_jds`<br>• `linkedin_and_content_analytics` | External signals observed across public reviews, career portal / job descriptions, and LinkedIn. **Note on real-world data hygiene:** just like real scraped feeds, external review exports can occasionally contain noisy or out-of-scope rows (e.g., unverified pilot artifacts) that should be filtered rather than blindly turned into corporate HR policy. |
| **`client_internal_context`** *(Inside-Out)*<br>• `healthy_metrics_and_strengths_not_to_break`<br>• `cohort_and_site_asymmetries`<br>• `budget_and_capacity_constraints`<br>• `leadership_perceptions_and_requests` | Internal discovery context shared by the client:<br>• **`healthy_metrics_and_strengths_not_to_break`**: Baselines, pay bands, or cohorts that are **already healthy** (useful for deciding what *not* to over-fix or disrupt).<br>• **`cohort_and_site_asymmetries`**: How metrics differ across specific hubs, regional clinics, labs, or HQ vs. frontline populations.<br>• **`budget_and_capacity_constraints`**: Financial turnover/agency exposure, manual spreadsheet hours, and CFO approval gates.<br>• **`leadership_perceptions_and_requests`**: Urgent proposals from the CEO, Marketing, VP Eng, or Hub Directors. **Read critically:** treat these as stakeholder hypotheses to test against the evidence—not blind instructions! |
| **`narrative_situation_to_solve`** | Single-paragraph executive summary consolidating the scenario's situation (handy if your pipeline consumes unified prose alongside or instead of the structured sub-fields above). |
| **`key_questions_your_structure_must_answer`** | 4 open guiding questions highlighting key diagnostic and strategic tensions for that client (reflection prompts — they contain no hidden extra facts). |

---

### 1.4 How the Two JSON Files Connect (Optional Join Map)

If your team chooses to use the optional quantitative companion file (`data/ingaze_synthetic_analytics_snapshots.json`), records link `1:1` with zero fuzzy matching needed:

| Narrative Record in `ingaze_sandbox_dataset.json` | Join Key | Quantitative Record in `ingaze_synthetic_analytics_snapshots.json` | Available Snapshots |
| :--- | :---: | :--- | :--- |
| `raw_case_study_narratives[i]` (`11` past cases) | **`case_name`** | `case_study_analytics_snapshots[i]` (`11` records) | `sector_peer_benchmarks` + `t0_before_intervention` + `t1_after_12_months` |
| `company_scenarios_to_diagnose[j]` (`3` active clients) | **`scenario_code`** | `active_scenario_analytics_snapshots[j]` (`3` records) | `sector_peer_benchmarks` + `t0_current_snapshot` *(no `T1`, since the client's plan has not been executed yet)* |

---

## Part 2 — Guide to `data/ingaze_synthetic_analytics_snapshots.json` (Metric Scales & Polarity)

> **Usage:** 100% **optional** companion dataset. All values are synthetic. You are free to use these tables alongside the narratives, run standalone statistical/quantitative models, compare client metrics against `sector_peer_benchmarks`, or ignore this file completely.

### 2.1 Top-Level Structure & Naming Conventions

Both `case_study_analytics_snapshots` (`11` records) and `active_scenario_analytics_snapshots` (`3` records) share the exact same 4 telemetry channel blocks (`public_reputation`, `career_portal_and_funnel`, `social_and_employee_voice`, `hiring_and_retention_kpis`).

- Keys ending in **`_5`** are on a **`1.0 – 5.0` star** scale.
- Keys ending in **`_100`** are on a **`0.0 – 100.0` index** scale.
- Keys ending in **`_pct`** are **percentages (`0.0 – 100.0%`)**.

---

### 2.2 Metric Definitions, Scales & Polarity

#### A. `public_reputation` (Employee & Candidate Review Telemetry)

| Field / Key | Scale / Range | Directionality | What It Measures |
| :--- | :---: | :---: | :--- |
| `reviews_analyzed` | Integer (`>= 1`) | Volume | Total public employee reviews aggregated across review platforms (note: equals the sum of `reviews` in `segment_or_site_breakdown`). |
| `overall_review_rating_5` | **`1.0 – 5.0` stars** | Higher is better | Weighted overall public employer rating across platforms (`1.0` = lowest, `5.0` = highest). |
| `recommend_to_friend_pct` | **`0.0 – 100.0%`** | Higher is better | Share of reviewers answering *"Yes"* to recommending the employer to a friend. |
| `employer_review_reply_rate_pct` | **`0.0 – 100.0%`** | Higher is better | Share of public reviews receiving an official, constructive company response (`0.0%` = no reviews answered). |
| `cross_location_rating_std_dev_5` | **`0.00 – 2.00` stars** | **Lower** = more consistent | Standard deviation of average review ratings across countries, hubs, or regional sites (high values indicate fragmented local reality). |
| `brand_alignment_index_100` | **`0.0 – 100.0` (`0–100`)** | Higher is better | Alignment score measuring how closely external employer messaging matches verified employee review themes. |
| `external_claims_gap_stars_5` | **`0.0 – 4.0` stars** | **Lower** is better | Divergence (in stars) between positive recruiting promises and actual internal employee sentiment (values `> 1.0` indicate a severe *Say-Do Gap*). |
| `sub_ratings_5.management` | **`1.0 – 5.0` stars** | Higher is better | Sub-rating for direct manager & leadership effectiveness. |
| `sub_ratings_5.career_growth` | **`1.0 – 5.0` stars** | Higher is better | Sub-rating for internal mobility, leveling clarity, and promotion fairness. |
| `sub_ratings_5.work_life_balance` | **`1.0 – 5.0` stars** | Higher is better | Sub-rating for workload sustainability, shift predictability, and work-life balance. |
| `sub_ratings_5.compensation` | **`1.0 – 5.0` stars** | Higher is better | Sub-rating for pay competitiveness, benefits, and payroll reliability. |
| `sub_ratings_5.culture_and_values` | **`1.0 – 5.0` stars** | Higher is better | Sub-rating for day-to-day team culture, trust, and mission authenticity. |
| `segment_or_site_breakdown` | Map `{name: {reviews, rating_5}}` | `rating_5` on **`1.0 – 5.0`** | Disaggregated review count and `1.0–5.0` star rating per hub, facility group, or department (reveals internal asymmetries hidden by the company average). |

---

#### B. `career_portal_and_funnel` (Career Website UX & Candidate Funnel)

| Field / Key | Scale / Range | Directionality | What It Measures |
| :--- | :---: | :---: | :--- |
| `monthly_visits` | Integer (`>= 0`) | Volume | Average unique monthly visits to the company's career portal. |
| `smartphone_traffic_pct` | **`0.0 – 100.0%`** | Context trait | Share of career portal visitors browsing on mobile devices (`>75%` typical for frontline logistics/retail; `<35%` typical for desktop B2B tech). |
| `application_form_dropoff_pct` | **`0.0 – 100.0%`** | **Lower** is better | Share of candidates who start an application but abandon the form before submitting. |
| `applicant_conversion_rate_pct` | **`0.0 – 100.0%`** | Higher is better | Completed job applications divided by total career portal visits (`%`). |
| `candidate_survey_completion_rate_pct` | **`0.0 – 100.0%`** | Higher is better | Share of interviewed / Career Day candidates completing post-interaction feedback surveys. |
| `portal_component_scores_100.seo_and_reach_100` | **`0.0 – 100.0` index** | Higher is better | Search discoverability and inbound organic reach of the career portal (`0.0` = worst, `100.0` = best). |
| `portal_component_scores_100.technical_speed_100` | **`0.0 – 100.0` index** | Higher is better | Page load speed and core web performance score (`0.0–100.0`). |
| `portal_component_scores_100.job_ad_clarity_100` | **`0.0 – 100.0` index** | Higher is better | Specificity and persona-alignment of job descriptions (`0.0–100.0`; low scores indicate generic corporate boilerplate). |
| `portal_component_scores_100.role_benefits_transparency_100` | **`0.0 – 100.0` index** | Higher is better | Visibility of concrete role conditions, growth tracks, schedules, or benefits directly on job pages (`0.0–100.0`). |
| `portal_component_scores_100.application_flow_simplicity_100` | **`0.0 – 100.0` index** | Higher is better | Frictionless completion score of the apply flow, especially on mobile (`0.0–100.0`; low scores indicate multi-page desktop login walls). |
| `portal_component_scores_100.authentic_team_social_proof_100` | **`0.0 – 100.0` index** | Higher is better | Presence of credible peer/team voices and day-in-the-life proof on role & career pages (`0.0–100.0`). |

---

#### C. `social_and_employee_voice` (LinkedIn Content & Employee Advocacy)

| Field / Key | Scale / Range | Directionality | What It Measures |
| :--- | :---: | :---: | :--- |
| `corporate_linkedin_er_pct` | **`0.0 – 100.0%`** | Higher is better | Average engagement rate (`(reactions + comments + reposts) / impressions * 100`) on official corporate LinkedIn posts. |
| `organic_employee_post_er_pct` *(in peer benchmarks)* | **`0.0 – 100.0%`** | Higher is better | Sector benchmark engagement rate on posts shared directly by individual employees/ambassadors. |
| `quarterly_organic_impressions` | Integer (`>= 0`) | Higher is better | Total unpaid organic impressions generated across corporate + employee talent content per quarter. |
| `er_by_post_format_pct` | **`0.0 – 100.0%`** per format | Higher is better | Breakdown of engagement rate (`%`) across three post categories: `institutional_updates`, `generic_job_posts`, and `authentic_team_and_domain_stories`. |
| `spontaneous_employee_mentions_quarter` | Integer (`>= 0`) | Volume | Number of organic LinkedIn posts/mentions by employees per quarter. |
| `positive_mention_share_pct` | **`0.0 – 100.0%`** | Higher is better | Share of organic employee mentions with positive sentiment (`%`). |
| `manual_hr_tracking_hours_month` | Float (`>= 0.0` hours/mo) | **Lower** is better | Monthly HR staff hours spent manually copying review rows, post analytics, or ambassador screenshots into spreadsheets. |

---

#### D. `hiring_and_retention_kpis` (Recruiting Latency, Agency Spend & Attrition)

| Field / Key | Scale / Range | Directionality | What It Measures |
| :--- | :---: | :---: | :--- |
| `early_first_year_attrition_pct` | **`0.0 – 100.0%`** | **Lower** is better | Voluntary + involuntary new-hire turnover within the first `0–12` months (`%`). |
| `estimated_annual_attrition_exposure_eur` | Integer (`EUR / year`) | **Lower** is better | Estimated annual financial cost of avoidable turnover (`€`), combining replacement recruiting, onboarding, and vacancy impact. |
| `avg_time_to_hire_days` | Integer (`days`) | **Lower** is better | Average calendar days required to fill an open target role from requisition to accepted offer. |
| `agency_filled_roles_pct` | **`0.0 – 100.0%`** | **Lower** is better | Share of annual hires filled via paid external staffing or headhunting agencies (`%`) due to insufficient direct applicant flow. |
| *(Scenario-specific context keys)* | `%` or `days` or `0–100` | Context-specific | Additional cohort facts reported in intake (e.g., `six_month_new_hire_attrition_milan_berlin_pct`, `compensation_market_percentile_100`, `tenured_driver_annual_retention_pct`, `hq_admin_time_to_hire_days`, `rd_labs_annual_retention_pct`). |
