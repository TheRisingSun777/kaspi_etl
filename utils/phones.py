"""
Utilities for parsing and normalizing Kazakhstan phone numbers to E.164 format.

Primary function:
- parse_kz_phone(text) -> str: Returns "+7XXXXXXXXXX" if valid KZ number, else "".

Heuristics:
- Remove all non-digit characters.
- Handle leading international/national prefixes:
  - If starts with "007", drop the leading "00".
  - If starts with "8" and has 11 digits, replace leading 8 with 7.
  - If has 10 digits and starts with "7" (e.g., 701...), prefix with "7".
- Valid KZ numbers must be 11 digits and start with "7" after normalization.
"""

from __future__ import annotations

import re
from typing import Optional


_NON_DIGITS_RE = re.compile(r"\D+")


def _only_digits(text: object) -> str:
    if text is None:
        return ""
    s = str(text)
    # Fast path for already clean
    if s.isdigit():
        return s
    return _NON_DIGITS_RE.sub("", s)


def parse_kz_phone(text: object) -> str:
    """Parse possibly messy KZ phone text into E.164 "+7..." or return empty string.

    Examples accepted:
    - "+7 701 123-45-67" -> "+77011234567"
    - "8 (701) 123 45 67" -> "+77011234567"
    - "7011234567" -> "+77011234567"
    - "0077011234567" -> "+77011234567"
    """
    digits = _only_digits(text)
    if not digits:
        return ""

    # Handle international prefix "00"
    if digits.startswith("007") and len(digits) >= 13:
        digits = digits[2:]

    # Replace national prefix 8 -> 7 for 11-digit numbers
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]

    # If 10 digits starting with 7 (e.g., 701...), assume missing country prefix
    if len(digits) == 10 and digits.startswith("7"):
        digits = "7" + digits

    # Final validation: KZ (and RU) share +7; we accept if 11 digits and starts with 7
    if len(digits) == 11 and digits.startswith("7"):
        return "+" + digits

    return ""


