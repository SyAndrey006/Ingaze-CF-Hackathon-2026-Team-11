#!/usr/bin/env python3
"""Public CLI and programmatic facade for the deterministic recommendation engine."""

import sys

from src.main import (
    DEFAULT_DATA, action_fit, baseline_fit, case_matches, main, plan, plan_from_graph,
    precedent_signals, profile_for, protected_intervention, run_custom_client,
    source_class, tailor_pilot,
)

__all__ = [
    "DEFAULT_DATA", "action_fit", "baseline_fit", "case_matches", "main", "plan",
    "plan_from_graph", "precedent_signals", "profile_for", "protected_intervention",
    "run_custom_client", "source_class", "tailor_pilot",
]

if __name__ == "__main__":
    cli_args = sys.argv[1:]
    # Preserve the official sandbox default for the public compatibility CLI.
    if "--client-input" not in cli_args and "--sandbox" not in cli_args:
        cli_args.insert(0, "--sandbox")
    main(cli_args)
