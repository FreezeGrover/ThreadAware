from __future__ import annotations


def percent_agreement(automated: list[bool], expert: list[bool]) -> float:
    if len(automated) != len(expert):
        raise ValueError("Automated and expert labels must have equal length")
    if not automated:
        raise ValueError("At least one label is required")
    matches = sum(a == e for a, e in zip(automated, expert))
    return matches / len(automated)
