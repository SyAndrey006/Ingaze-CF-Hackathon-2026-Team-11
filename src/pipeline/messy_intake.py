"""Adapt the organizer's discovery-call, survey and scraped-telemetry format."""

from __future__ import annotations

import re

from src.schemas.pipeline_models import ExtractedSignal, FilteredNoiseItem


FORMAT = "organizer_messy_intake"
STREAMS = (
    "raw_discovery_call_notes", "ingaze_onboarding_surveys_raw", "outside_in_scraped_telemetry",
)
ENGINE_TO_CANONICAL = {
    "early_attrition": "EARLY_FIRST_YEAR_ATTRITION",
    "interview_capacity_reported": "HIGH_TIME_TO_HIRE",
    "documented_broken_promise": "SAY_DO_GAP",
    "manager_support": "WEAK_MIDDLE_MANAGEMENT",
    "career_clarity": "CAREER_PATH_OPACITY",
    "agency_spend": "HIGH_EXTERNAL_AGENCY_DEPENDENCY",
    "mobile_friction": "MOBILE_PORTAL_FRICTION",
    "generic_ads": "GENERIC_BOILERPLATE_JDS",
    "manual_tracking_load": "MANUAL_HR_SPREADSHEET_DRAG",
}

EXIT_COUNT = re.compile(
    r"\b(\d+)\s+(?:of|out of)\s+(?:the\s+)?(?:last\s+)?(\d+)\s+(?:new\s+)?hires?"
    r"\s+(?:resigned|quit|left)\b[^.!?]{0,100}?\b(\d+)[- ]month", re.I,
)
INTERVIEW_QUEUE = re.compile(
    r"(?<!not )(?<!never )(?<!without )(?<!didn't )\bwait(?:ed|ing)?\b"
    r".{0,130}\b(?:calendar\s+slots?|(?:interview|panel)\s+slots?|"
    r"(?:technical|interview)\s+panels?)\b", re.I,
)
INTERVIEW_GAP = re.compile(
    r"\b(?:avg\.?|average(?:d)?)\s+(\d+)\s+(?:calendar\s+)?days?\b"
    r".{0,45}\b(?:between|from)\s+HR\b.{0,60}\b(?:first|1st)\s+(?:technical|tech)\b", re.I,
)
AGENCY_SHARE = re.compile(
    r"\b(\d+)\s+(?:of|out of)\s+(\d+)\s+hires?\b.{0,90}\b"
    r"(?:agenc(?:y|ies)|headhunters?|external recruiters?)\b", re.I,
)
VETO = re.compile(
    r"\b(?:do not|don't|never)\s+(?:propose|launch|start|run|turn|make|use)\b"
    r"[^.!?]{0,170}\b(?:ambassadors?|advocacy|LinkedIn influencers?)\b", re.I,
)
EXPECTATION_CLAIM = re.compile(r"\b(?:job ads?|recruiting ads?|posting|recruiter)\b.{0,75}\bpromis", re.I)
REALITY = re.compile(r"\b(?:day one|actual (?:job|work)|in reality|instead it was)\b", re.I)
MANAGER = re.compile(r"\b(?:cancell?ed|missed)\b.{0,65}\b(?:1[- ]on[- ]1s?|one[- ]on[- ]ones?)\b", re.I)
CAREER = re.compile(
    r"\b(?:nobody|no one) explained\b.{0,85}\b(?:move from|progress|promotion)\b"
    r"|\b(?:no|zero|unclear)\s+career (?:ladder|path|progression)\b"
    r"|\b(?:block|blocked|blocking)\w*\b.{0,110}\b(?:internal transfers?|internal mobility|career|promotion|advance|progress)\b"
    r"|\bresign\w*\b.{0,70}\b(?:to grow|to advance|career|a grade)\b", re.I,
)
MOBILE_FRICTION = re.compile(
    r"\b(?:mobile|smartphone|phone)\b.{0,180}\b(?:apply\w*|application|portal|form|ATS)\b"
    r".{0,180}\b(?:account|register\w*|OTP|upload\w*|PDFs?|screens?|abandon\w*|gave up)\b"
    r"|\b(?:portal|ATS|application form)\b.{0,180}\b(?:mobile|smartphone|phone)\b"
    r".{0,180}\b(?:account|register\w*|OTP|upload\w*|PDFs?|abandon\w*)\b", re.I,
)
GENERIC_JOB_AD = re.compile(
    r"\b(?:job ads?|job postings?|vacanc(?:y|ies))\b.{0,120}"
    r"\b(?:read like|legal notice|boilerplate|outdated|199\d|none of which is written|"
    r"do not mention|does not mention)\b", re.I,
)
AGENCY_PERCENT = re.compile(
    r"(?:~|about\s+|approximately\s+)?(?P<pct>\d+(?:[.,]\d+)?)%"
    r"\s+of\b.{0,130}\b(?:agenc(?:y|ies)|headhunters?|temporary staffing)\b", re.I,
)
MANUAL_SCREENING = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:hours?|h)\s*(?:/\s*week|per week)\b"
    r".{0,100}\b(?:recruiters?|screen(?:ing|ing)?|PDFs?|CVs?)\b", re.I,
)
RETENTION_STRENGTH = re.compile(
    r"\b(?:over\s+|above\s+)?\d+(?:[.,]\d+)?%\s+(?:of\s+)?(?:employees?\s+)?stay\s+for years\b",
    re.I,
)
OFF_TOPIC = re.compile(r"\b(?:vending machine|visitor parking|air conditioning)\b", re.I)


def is_messy_intake(document):
    return "client_intake_case" in document or (
        "basic_company_facts" in document and any(key in document for key in STREAMS)
    )


def _object(record, key):
    value = record.get(key)
    return value if isinstance(value, dict) else {}


def _array(record, key):
    value = record.get(key)
    return value if isinstance(value, list) else []


def _text(record, key):
    value = record.get(key)
    return value.strip() if isinstance(value, str) else ""


def _site_names(footprint):
    parents = re.findall(r"\(([^()]*)\)", footprint)
    sites = {name.strip() for block in parents for name in re.split(r"[,/]", block) if name.strip().isalpha()}
    sites.update(re.findall(r"\b([A-Z][a-zÀ-ÿ-]+)\s+(?:office|(?:software\s+)?hub)\b", footprint))
    return sorted(sites)


def _scope(text, sites, tenure=None):
    named = [name.casefold() for name in sites if re.search(rf"\b{re.escape(name)}\b", text, re.I)]
    cohort = None
    if re.search(r"\b(?:software|automation|firmware|IoT|developer|C\+\+|data|cloud|digital|cybersecurity)", text, re.I):
        cohort = "engineering_workforce"
    elif re.search(r"\b(?:commissioning|plant|assembl(?:y|er)|mechatronic|electrician|technician|grid|depot|field)\b", text, re.I):
        cohort = "field_and_plant_workforce"
    return {"cohort": cohort, "site": named[0] if len(named) == 1 else None, "tenure": tenure, "window": "intake"}


def adapt_messy_intake(document):
    """Map a detected intake document into the existing scenario contract."""
    case = document.get("client_intake_case", document)
    if not isinstance(case, dict) or not case:
        raise ValueError("client_intake_case must be a nonempty JSON object.")
    prefix = "/client_intake_case" if case is not document else ""
    facts = _object(case, "basic_company_facts")
    footprint = _text(facts, "footprint_and_headcount")
    sites = _site_names(footprint)
    context, observations, measurements, excluded, protected = {}, [], [], [], []

    def observe(signal, source, text, scope, origin):
        observation = {
            "id": f"intake:{len(observations) + 1}:{signal}", "signal": signal,
            "state": "present", "quality": "reported", "scope": scope,
            "source_ref": source, "origins": [origin], "text": text,
        }
        if scope["tenure"] == "new_or_early_tenure" and scope["site"] and scope["cohort"]:
            observation["population_ids"] = [f"intake:{scope['site']}:{scope['cohort']}:recent_hires"]
        observations.append(observation)

    def measure(metric, value, unit, source, scope, **definitions):
        measurements.append({
            "metric_path": metric, "value": value, "unit": unit,
            "source_ref": source, "scope": scope, "quality": "reported", **definitions,
        })

    def exclude(source, topic, reason, excerpt):
        excluded.append({"source": source, "topic": topic, "reason": reason, "excerpt": excerpt})

    strengths = []
    for index, call in enumerate(_array(case, "raw_discovery_call_notes")):
        if not isinstance(call, dict):
            continue
        source = f"{prefix}/raw_discovery_call_notes/{index}/raw_notes"
        text = _text(call, "raw_notes")
        if re.search(r"\b(?:forwarded|marketing|trade.fair)\b", _text(call, "source"), re.I):
            if re.search(r"\b(?:campaign|trade.fair|CTA|clicks)\b", text, re.I):
                exclude(source, "promotional traffic", "Campaign visitors are not a qualified applicant sample.", text)
                continue
        if MOBILE_FRICTION.search(text):
            observe("mobile_friction", source, text, _scope(text, sites, "applicant"), "intake_candidate_feedback")
        if CAREER.search(text):
            observe("career_clarity", source, text, _scope(text, sites, "mid_tenure"), "intake_employee_feedback")
        if GENERIC_JOB_AD.search(text):
            observe("generic_ads", source, text, _scope(text, sites, "applicant"), "intake_job_posting_feedback")
        if MANUAL_SCREENING.search(text):
            observe("manual_tracking_load", source, text, _scope(text, sites, "applicant"), "recruiting_self_report")
        if RETENTION_STRENGTH.search(text):
            strengths.append({"text": text, "source_ref": source})
        veto = VETO.search(text)
        if veto:
            protected.append({
                "scope": {"cohort": "all"}, "rules": ["advocacy_pilot"], "source_ref": source,
                "reason": "The client explicitly vetoed public employee advocacy.",
            })
        for clause in re.split(r"""(?<=[.!?])['"’”]?\s+(?=[A-Z])""", text):
            match = EXIT_COUNT.search(clause)
            if match:
                exits, hires, months = map(int, match.groups())
                if 0 < exits <= hires and 0 < months <= 12:
                    scope = _scope(clause, sites, "new_or_early_tenure")
                    observe("early_attrition", source, clause, scope, "recruiting_self_report")
                    measure("reported_early_exits", exits, "count", source, scope,
                            denominator="reported_hires", denominator_count=hires,
                            measurement_horizon=f"{months}_months")
            if INTERVIEW_QUEUE.search(clause):
                scope = _scope(clause, sites, "applicant")
                observe("interview_capacity_reported", source, clause, scope, "recruiting_self_report")
                withdrawals = re.search(r"\b(\d+)\s+(?:shortlisted\s+)?candidates? withdrew\b", clause, re.I)
                if withdrawals:
                    measure("reported_candidate_withdrawals_while_waiting", int(withdrawals[1]), "count",
                            source, scope, denominator="shortlisted_candidates")
            if re.search(r"\b(?:veteran|tenured)\b.*\brarely leave\b", clause, re.I):
                strengths.append({
                    "text": re.split(r"[—–;]", clause, maxsplit=1)[0].strip(),
                    "source_ref": source,
                })

    surveys = _object(case, "ingaze_onboarding_surveys_raw")
    employer = _object(surveys, "employer_archetype_survey_response")
    cost_key = "recruiting_cost_review_survey_response"
    cost = _object(surveys, cost_key)
    cost_path = f"{prefix}/ingaze_onboarding_surveys_raw/{cost_key}"
    process = _text(cost, "q5_process_note")
    gap = INTERVIEW_GAP.search(process)
    if gap:
        measure("reported_hr_to_first_technical_interview", int(gap[1]), "days",
                f"{cost_path}/q5_process_note", _scope(process, sites, "applicant"),
                clock="HR interview to first technical round", statistic="reported_average")
    agency = _text(cost, "q8_agency_note")
    count = AGENCY_SHARE.search(agency)
    if count:
        placed, total = map(int, count.groups())
        if 0 < placed <= total:
            source = f"{cost_path}/q8_agency_note"
            scope = {"cohort": "all", "site": "all", "tenure": "all", "window": "intake"}
            observe("agency_spend", source, agency, scope, "recruiting_self_report")
            measure("reported_agency_filled_roles_pct", round(100 * placed / total, 2), "%", source, scope,
                    numerator=placed, denominator="reported_hires", denominator_count=total)
    else:
        percent = AGENCY_PERCENT.search(agency)
        if percent:
            pct = float(percent.group("pct").replace(",", "."))
            source = f"{cost_path}/q8_agency_note"
            scope = {"cohort": "field_and_plant_workforce", "site": "all", "tenure": "all", "window": "intake"}
            observe("agency_spend", source, agency, scope, "recruiting_self_report")
            measure("reported_agency_filled_roles_pct", pct, "%", source, scope,
                    numerator=None, denominator="reported approximate share")

    screening_note = _text(cost, "q4_screening_note")
    if screening_note and MANUAL_SCREENING.search(screening_note):
        observe(
            "manual_tracking_load",
            f"{cost_path}/q4_screening_note",
            screening_note,
            {"cohort": "recruiters", "site": "all", "tenure": "all", "window": "intake"},
            "recruiting_self_report",
        )

    feedback_key = "internal_climate_and_candidate_feedback_notes"
    feedback = _object(surveys, feedback_key)
    for index, note in enumerate(_array(feedback, "raw_unfiltered_snippets")):
        if not isinstance(note, str):
            continue
        source = f"{prefix}/ingaze_onboarding_surveys_raw/{feedback_key}/raw_unfiltered_snippets/{index}"
        if OFF_TOPIC.search(note) and not re.search(r"\b(?:burnout|workload|resigned|hire|safety)\b", note, re.I):
            exclude(source, "off-topic feedback", "No link to the hiring or retention diagnosis was reported.", note)
            continue
        is_exit = re.search(r"^\[\s*exit (?:note|interview)\b", note, re.I)
        if MOBILE_FRICTION.search(note):
            observe("mobile_friction", source, note, _scope(note, sites, "applicant"), "intake_candidate_feedback")
        if GENERIC_JOB_AD.search(note):
            observe("generic_ads", source, note, _scope(note, sites, "applicant"), "intake_job_posting_feedback")
        if not is_exit:
            continue
        scope = _scope(note, sites, "mid_tenure" if CAREER.search(note) else "new_or_early_tenure")
        if EXPECTATION_CLAIM.search(note) and REALITY.search(note):
            observe("documented_broken_promise", source, note, scope, "intake_exit_feedback")
        if MANAGER.search(note):
            observe("manager_support", source, note, scope, "intake_exit_feedback")
        if CAREER.search(note):
            observe("career_clarity", source, note, scope, "intake_exit_feedback")

    outside = _object(case, "outside_in_scraped_telemetry")
    outside_path = f"{prefix}/outside_in_scraped_telemetry"
    reviews = _object(outside, "public_reputation_telemetry")
    if reviews:
        exclude(f"{outside_path}/public_reputation_telemetry", "unfiltered reputation",
                "Unfiltered review aggregates need an employee-sample check and screening for external or coordinated entries.",
                reviews.get("raw_unfiltered_overall_rating_5"))
    funnel = _object(_object(outside, "career_website_and_jd_telemetry"), "traffic_and_funnel_metrics")
    tracking_note = _text(funnel, "tracking_diagnostic_note")
    if tracking_note and MOBILE_FRICTION.search(tracking_note):
        observe(
            "mobile_friction",
            f"{outside_path}/career_website_and_jd_telemetry/traffic_and_funnel_metrics/tracking_diagnostic_note",
            tracking_note,
            _scope(tracking_note, sites, "applicant"),
            "outside_in_platform",
        )
    job_ad = _text(_object(outside, "career_website_and_jd_telemetry"), "sample_live_job_ad_text")
    if job_ad and re.search(r"\b(?:NOTICE OF SELECTION|register|attach scanned copies|sections [A-E])\b", job_ad, re.I):
        observe(
            "generic_ads",
            f"{outside_path}/career_website_and_jd_telemetry/sample_live_job_ad_text",
            job_ad,
            _scope(job_ad, sites, "applicant"),
            "outside_in_platform",
        )
    if "last_30d_raw_bounce_or_dropoff_pct" in funnel:
        exclude(f"{outside_path}/career_website_and_jd_telemetry/traffic_and_funnel_metrics/last_30d_raw_bounce_or_dropoff_pct",
                "ambiguous bounce or drop-off", "A combined traffic measure cannot establish application-form abandonment.",
                funnel["last_30d_raw_bounce_or_dropoff_pct"])
    social = _object(outside, "linkedin_and_content_telemetry")
    if "er_by_post_format_pct" in social:
        exclude(f"{outside_path}/linkedin_and_content_telemetry/er_by_post_format_pct", "post-format engagement",
                "Compare sample size and audience before using format engagement as recruiting evidence.",
                _text(social, "format_note"))

    missing = {}
    for record, path, keys in (
        (cost, cost_path, ("tracked_first_year_attrition_pct", "tracked_annual_turnover_cost_eur")),
        (funnel, f"{outside_path}/career_website_and_jd_telemetry/traffic_and_funnel_metrics",
         ("applicant_conversion_rate_pct", "candidate_survey_completion_rate_pct")),
    ):
        missing.update({f"{path}/{key}": None for key in keys if key in record and record[key] is None})
    if strengths:
        context["healthy_metrics_and_strengths_not_to_break"] = " ".join(row["text"] for row in strengths)
    career_evidence = next(
        (row for row in observations if row["signal"] == "career_clarity"),
        None,
    )
    if career_evidence and strengths:
        context["cohort_and_site_asymmetries"] = (
            f"Struggling: {career_evidence['text']} "
            f"Healthy comparison: {strengths[0]['text']}"
        )
    request_notes = [
        context.get("leadership_perceptions_and_requests", ""),
        protected[0]["reason"] if protected else "",
        _text(employer, "q8_initiative_hr_believes_they_need"),
    ]
    if any(note.strip() for note in request_notes if isinstance(note, str)):
        request_text = " ".join(note.strip() for note in request_notes if isinstance(note, str) and note.strip())
        request_parts = [part.strip() for part in re.split(r"\s*[+;]\s*", request_text) if part.strip()]
        context["leadership_perceptions_and_requests"] = " ".join(
            f"The CHRO proposed {part.rstrip('.')}" + "." for part in request_parts
        )

    cfo_constraint = _text(employer, "q4_internal_budget_approver")
    if cfo_constraint:
        context["budget_and_capacity_constraints"] = cfo_constraint

    workflow_notes = [
        _text(cost, "q4_screening_note"),
        _text(funnel, "tracking_diagnostic_note"),
    ]
    if any(workflow_notes):
        context["recruiting_process_diagnostic_notes"] = " ".join(
            note for note in workflow_notes if note
        )

    return {
        **{key: case[key] for key in ("scenario_code", "scenario_id", "company_name") if key in case},
        "industry": _text(facts, "industry") or _text(case, "industry"),
        "headcount_and_footprint": footprint,
        "workforce_target": _text(facts, "open_roles_mentioned_verbally"),
        "client_internal_context": context,
        "ingaze_platform_signals": {},
        "protected_scopes": protected,
        "reported_intake_observations": observations,
        "intake_normalization_audit": {
            "format": FORMAT, "measurements": measurements, "excluded": excluded, "missing": missing,
            "reported_strengths": strengths,
        },
    }


def summarized_intake(raw):
    """Summarize adapted evidence in the public Step 1 model."""
    signals = [
        ExtractedSignal(
            signal_code=ENGINE_TO_CANONICAL[row["signal"]],
            evidence_quote=row["text"],
            source_stream="inside_out_client",
            affected_cohorts=[row["scope"]["cohort"]] if row["scope"]["cohort"] else [],
        )
        for row in raw["reported_intake_observations"]
    ]
    noise = [
        FilteredNoiseItem(
            raw_excerpt=f"{item['source']}: {item['excerpt']}",
            inferred_mismatched_action_or_topic=item["topic"],
            reason_filtered=item["reason"],
        )
        for item in raw["intake_normalization_audit"]["excluded"]
    ]
    return signals, noise
