from typing import List, Sequence


def clean_tags(tags: Sequence[str]) -> List[str]:
    """Clean a list of tag strings: strip whitespace, drop blanks, deduplicate
    while preserving the first-seen order."""
    seen: set = set()
    result: List[str] = []
    for tag in tags:
        cleaned = tag.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result
