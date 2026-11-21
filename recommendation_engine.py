#!/usr/bin/env python3
"""Command-line entry point for the offline recommendation engine."""

from src.reasoning.engine import DEFAULT_DATA, case_matches, main, plan

__all__ = ["DEFAULT_DATA", "case_matches", "main", "plan"]

if __name__ == "__main__":
    main()
