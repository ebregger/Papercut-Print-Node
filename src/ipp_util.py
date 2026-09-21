"""Helpers for IPP job template attributes."""

from __future__ import annotations

from ippserver.constants import SectionEnum, TagEnum

SIDES_ONE_SIDED = "one-sided"
SIDES_TWO_SIDED_LONG_EDGE = "two-sided-long-edge"
SIDES_TWO_SIDED_SHORT_EDGE = "two-sided-short-edge"

VALID_SIDES = frozenset(
  {
    SIDES_ONE_SIDED,
    SIDES_TWO_SIDED_LONG_EDGE,
    SIDES_TWO_SIDED_SHORT_EDGE,
  }
)


def normalize_sides(value: str | None, *, default: str = SIDES_ONE_SIDED) -> str:
  """Return a valid IPP sides keyword, falling back to *default*."""
  if value in VALID_SIDES:
    return value
  if default in VALID_SIDES:
    return default
  return SIDES_ONE_SIDED


def extract_sides_from_request(ipp_request, *, default: str = SIDES_ONE_SIDED) -> str:
  """
  Read the ``sides`` job template attribute from an IPP Print-Job request.

  Windows and other IPP clients may place ``sides`` in the operation or job
  attribute group.
  """
  for section in (SectionEnum.operation, SectionEnum.job):
    try:
      values = ipp_request.lookup(section, b"sides", TagEnum.keyword)
    except (KeyError, RuntimeError):
      continue
    if not values:
      continue
    candidate = values[0].decode("utf-8", errors="replace")
    if candidate in VALID_SIDES:
      return candidate
  return normalize_sides(None, default=default)
