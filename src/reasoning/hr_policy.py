"""General HR evidence patterns, intervention policies, and precedent annotations."""

# Patterns apply to evidence fields, with separate rules for requests and strengths.
FEATURES = {
    "expectation_gap": r"""[1-9](?:\.\d+)?[- ]star gap|say[- ]do gap|promis\w*[^.;]{0,60}contradict""",
    "manager_support": r"micromanagement|without management coaching|weak middle management|uncoached leads",
    "career_clarity": r"unclear promotion|career path opacity|without[^.]{0,50}career progression framework",
    "burnout": r"workload burnout|systemic burnout|management burnout|severe burnout",
    "early_attrition": r"early (?:new.hire )?attrition|leave within their first|first.year turnover",
    "mobile_friction": r"desktop[- ](?:style|first|heavy) |cv upload|multi.page desktop|mobile.{0,30}abandonment",
    "generic_ads": r"generic (?:corporate|job|hq)|corporate boilerplate",
    "local_reputation": r"rating variance|unmonitored centrally|outdated or unaddressed local profiles",
    "review_tracking": r"reviews?[^.;]{0,65}(?:manually|spreadsheet)|manually[^.;]{0,50}(?:facility|hub) reviews",
    "post_tracking": r"manually[^.;]{0,110}(?:post|sharing|ambassador)|ambassador screenshots|post screenshots",
    "feedback_fragmentation": r"(?:post.interview|career day)[^.;]{0,150}(?:disconnected|fragmented|paper sheets|ad.hoc forms)",
    "existing_advocates": r"(?:already share|organic ambassadors are already active|active organic ambassadors)",
    "culture_ready": r"employee sentiment is highly positive|employee satisfaction[^.;]{0,100}(?:strong|healthy)|high evp authenticity",
    "emv": r"earned media value|\bemv\b",
    "agency_spend": r"temporary staffing agencies|agency spend",
}

PROFILE = {
    "tech": r"software|engineer|cloud|fintech|saas",
    "freight": r"truck driver|commercial driver|warehouse|freight|interport|logistics|fulfilment",
    "care": r"clinical|healthcare|nurses|care facilit",
    "retail": r"retail|store staff|in-store|store manager",
    "early_career": r"gen.z|early.career|graduate",
    "distributed": r"multi.site|across \d+|regional|multi.country|distributed",
    "fintech": r"fintech|digital payments|cloud payments",
    "sustainability": r"b[- ]corp|esg|sustainab",
}

# A rule supplies diagnosis, diagnostic work, a structural pilot, a rollout gate,
# and research references. Independent tracks can proceed in parallel.
TRACKS = {
    "expectation_gap": (
        "Recruiting promises appear to exceed day-to-day autonomy or growth. Expectation drift can drive early exits, poor reviews and weaker recruiting.",
        "Compare recruiting claims with interviews, new-hire exit reasons and reviews by affected cohort. Ask which decisions new hires can actually own.",
        "Rewrite unverified promises with team leads and publish a realistic preview of decision rights and progression.",
        "Publish new recruiting stories only after recent hires confirm that the claims match their experience.",
        (1, 5),
    ),
    "manager_support": (
        "Management support is a likely contributor to early attrition where leads lack coaching or employees report micromanagement.",
        "Run confidential 360-degree listening and compare early exits by team, manager and tenure.",
        "Pilot manager coaching and explicit delegation agreements in the affected teams. Review progress with new hires after 30 and 60 days.",
        "Extend coaching only where the pilot improves delegation feedback and early-tenure retention indicators.",
        (4,),
    ),
    "career_clarity": (
        "Unclear promotion criteria weaken the growth promise and may contribute to avoidable exits.",
        "Audit promotion decisions and interview recent hires about how they learned what advancement requires.",
        "Pilot role levels, promotion examples and a monthly career conversation with affected teams.",
        None,
        (4,),
    ),
    "burnout": (
        "Reported workload burnout suggests unsustainable capacity and is a risk to retention and advocacy readiness.",
        "Compare workload, overtime and exits by cohort. Reconcile the itemized turnover estimates with the reported total before presenting savings.",
        "Pilot workload limits and escalation for capacity shortfalls. Review workload and pulse feedback before expanding.",
        None,
        (4, 5),
    ),
    "mobile_friction": (
        "A desktop-oriented application flow creates friction for phone applicants and may prolong frontline vacancies.",
        "Instrument device-level funnel steps and test the current application on a phone with target candidates. Baseline qualified completion and time-to-hire.",
        "Pilot a short mobile application that puts eligibility first and defers account creation and CV upload where feasible. Route qualified candidates to a callback queue.",
        "Expand the pilot when qualified completion improves without lower eligibility or slower callbacks. Track time-to-hire and agency spend where available.",
        (2,),
    ),
    "generic_ads": (
        "Generic job ads hide the information the target workforce needs to decide whether to apply.",
        "Interview candidates and recruiters to verify which job details drive decisions for the target workforce.",
        "Test workforce-specific job ads using verified operational strengths and a clear preview of the role.",
        "Expand the ads after measuring qualified applications by role and channel.",
        (),
    ),
    "local_reputation": (
        "Local reputation and candidate experience vary by site, so company-wide averages can hide local problems.",
        "Audit review profiles and candidate handoffs by site. Break out stale profiles, recurring complaints and response times.",
        "Assign a local owner for profile accuracy and candidate handoffs. Pilot a response queue at the lowest-performing sites.",
        "Expand local ownership after profile coverage and handoff times improve at pilot sites.",
        (),
    ),
    "review_tracking": (
        "Manual review collection fragments site-level evidence and consumes HR reporting capacity.",
        "Inventory review sources, collection hours and site ownership. Establish a baseline for coverage and manual effort.",
        "Centralize review intake by site with source timestamps and an exception queue. Track hours saved against the baseline.",
        None,
        (8,),
    ),
    "feedback_fragmentation": (
        "Disconnected feedback collection obscures candidate drop-off and makes experience reporting difficult to audit.",
        "Map feedback collection from events and interviews through local handoffs. Compare response rates and delays by location and role.",
        "Pilot one timestamped feedback form and a follow-up owner. Use consistent questions, consent and aggregate reporting for small cohorts.",
        "Scale once response rates, handoff times and audit completeness improve.",
        (9,),
    ),
    "post_tracking": (
        "Manual post tracking limits visibility into employee-led reach and consumes HR capacity.",
        "Baseline reporting hours and define verified reach, consent and how paid-media equivalents will be calculated.",
        "Prepare reporting instrumentation with duplicate checks, documented rates and source records for CFO review.",
        None,
        (3, 8),
    ),
}
