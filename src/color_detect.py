"""Detect whether a PDF contains any color pages using Ghostscript inkcov."""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# inkcov output lines look like:
#   0.00000 0.00000 0.00000 0.05040 CMYK OK
# or (with -q and no "Page N" prefix on some builds):
# Page 1
#  0.00000 0.00000 0.00000 0.05040 CMYK OK
INKCOV_LINE = re.compile(
    r"^\s*"
    r"(?P<c>\d+\.\d+)\s+"
    r"(?P<m>\d+\.\d+)\s+"
    r"(?P<y>\d+\.\d+)\s+"
    r"(?P<k>\d+\.\d+)\s+"
    r"CMYK\s+OK\s*$"
)


@dataclass(frozen=True)
class ColorAnalysis:
    total_pages: int
    color_pages: list[int]
    bw_pages: list[int]

    @property
    def has_color(self) -> bool:
        return bool(self.color_pages)


def _resolve_gs_binary() -> str:
  """Return the Ghostscript binary name, preferring Termux's `gs`."""
  for candidate in ("gs", "gswin64c", "gswin32c"):
    if shutil.which(candidate):
      return candidate
  raise FileNotFoundError(
    "Ghostscript not found. Install with: pkg install ghostscript"
  )


def analyze_pdf_color(
    pdf_path: str | Path,
    *,
    threshold: float = 0.0001,
    gs_binary: str | None = None,
) -> ColorAnalysis:
  """
  Analyze a PDF and return per-page color information.

  A page is considered color if any of C, M, or Y ink coverage exceeds
  `threshold`. K-only (grayscale) pages count as black and white.

  Raises:
    FileNotFoundError: PDF or Ghostscript missing.
    RuntimeError: Ghostscript failed.
  """
  pdf = Path(pdf_path)
  if not pdf.is_file():
    raise FileNotFoundError(f"PDF not found: {pdf}")

  gs = gs_binary or _resolve_gs_binary()
  cmd = [
    gs,
    "-q",
    "-o",
    "-",
    "-sDEVICE=inkcov",
    "-dNOPAUSE",
    "-dBATCH",
    str(pdf),
  ]
  logger.debug("Running color analysis: %s", " ".join(cmd))
  proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
  if proc.returncode != 0:
    raise RuntimeError(
      f"Ghostscript inkcov failed ({proc.returncode}): {proc.stderr.strip()}"
    )

  color_pages: list[int] = []
  bw_pages: list[int] = []
  page_num = 0

  for raw_line in proc.stdout.splitlines():
    line = raw_line.strip()
    if line.startswith("Page "):
      continue
    match = INKCOV_LINE.match(line)
    if not match:
      continue
    page_num += 1
    c = float(match.group("c"))
    m = float(match.group("m"))
    y = float(match.group("y"))
    if c > threshold or m > threshold or y > threshold:
      color_pages.append(page_num)
    else:
      bw_pages.append(page_num)

  if page_num == 0:
    raise RuntimeError(
      "Ghostscript produced no inkcov page data; is this a valid PDF?"
    )

  return ColorAnalysis(
    total_pages=page_num,
    color_pages=color_pages,
    bw_pages=bw_pages,
  )


def pdf_has_color(
    pdf_path: str | Path,
    *,
    threshold: float = 0.0001,
    default_on_error: bool = False,
) -> bool:
  """
  Return True if any page in the PDF uses color ink.

  If analysis fails and `default_on_error` is True, returns False (route BW).
  If analysis fails and `default_on_error` is False, re-raises.
  """
  try:
    return analyze_pdf_color(pdf_path, threshold=threshold).has_color
  except Exception:
    logger.exception("Color detection failed for %s", pdf_path)
    if default_on_error:
      return False
    raise
