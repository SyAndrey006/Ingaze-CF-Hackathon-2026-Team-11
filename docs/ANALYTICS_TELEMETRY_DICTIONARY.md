# Analytics Telemetry Data Dictionary & Metric Scales

> **File documented:** [`data/ingaze_synthetic_analytics_snapshots.json`](../data/ingaze_synthetic_analytics_snapshots.json)  
> **Usage:** 100% **optional** companion dataset. All values are synthetic. You are free to use these tables alongside the narratives, run standalone statistical/quantitative models, compare client metrics against `sector_peer_benchmarks`, or ignore this file completely.

---

## 1. Top-Level Structure

The JSON file contains two standardized arrays sharing the exact same metric keys and scales:

1. **`case_study_analytics_snapshots` (`11` records)** — Quantitative telemetry for the 11 historical B2B case studies in `ingaze_sandbox_dataset.json` (joinable via `case_name`), each containing:
   - `sector_peer_benchmarks`: Synthetic sector peer averages for that company's industry.
   - `t0_before_intervention`: Multi-channel metrics measured **before** the project started.
   - `t1_after_12_months`: Multi-channel metrics measured **12 months after** execution.
2. **`active_scenario_analytics_snapshots` (`3` records)** — Quantitative telemetry for the 3 target company scenarios (`SCENARIO_A_CLOUDNOVA_FINTECH`, `SCENARIO_B_EUROFREIGHT_LOGISTICS`, `SCENARIO_C_VERDECARE_BCORP`, joinable via `scenario_code`), each containing:
   - `sector_peer_benchmarks`: Synthetic sector peer averages for that company's industry.
   - `t0_current_snapshot`: Current multi-channel metrics at intake.

*(Naming convention tip: keys ending in `_5` are on a **1–5 star** scale; keys ending in `_100` are on a **0–100 index** scale; keys ending in `_pct` are **percentages `0–100%`**).*

---

## 2. Metric Definitions, Scales & Polarity

### A. `public_reputation` (Employee & Candidate Review Telemetry)

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

### B. `career_portal_and_funnel` (Career Website UX & Candidate Funnel)

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

### C. `social_and_employee_voice` (LinkedIn Content & Employee Advocacy)

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

### D. `hiring_and_retention_kpis` (Recruiting Latency, Agency Spend & Attrition)

| Field / Key | Scale / Range | Directionality | What It Measures |
| :--- | :---: | :---: | :--- |
| `early_first_year_attrition_pct` | **`0.0 – 100.0%`** | **Lower** is better | Voluntary + involuntary new-hire turnover within the first `0–12` months (`%`). |
| `estimated_annual_attrition_exposure_eur` | Integer (`EUR / year`) | **Lower** is better | Estimated annual financial cost of avoidable turnover (`€`), combining replacement recruiting, onboarding, and vacancy impact. |
| `avg_time_to_hire_days` | Integer (`days`) | **Lower** is better | Average calendar days required to fill an open target role from requisition to accepted offer. |
| `agency_filled_roles_pct` | **`0.0 – 100.0%`** | **Lower** is better | Share of annual hires filled via paid external staffing or headhunting agencies (`%`) due to insufficient direct applicant flow. |
| *(Scenario-specific context keys)* | `%` or `days` or `0–100` | Context-specific | Additional cohort facts reported in intake (e.g., `six_month_new_hire_attrition_milan_berlin_pct`, `compensation_market_percentile_100`, `tenured_driver_annual_retention_pct`, `hq_admin_time_to_hire_days`, `rd_labs_annual_retention_pct`). |
