"""Custom ippserver behaviour: save PDF, detect color, forward via Mobility Print."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import threading
import uuid
from pathlib import Path

from ippserver.behaviour import SaveFilePrinter
from ippserver.constants import SectionEnum, TagEnum
from ippserver.ppd import BasicPdfPPD

from color_detect import pdf_has_color
from ipp_util import (
  SIDES_ONE_SIDED,
  SIDES_TWO_SIDED_LONG_EDGE,
  SIDES_TWO_SIDED_SHORT_EDGE,
  extract_sides_from_request,
  normalize_sides,
)
from mobility_print_client import MobilityPrintClient, MobilityPrintError

logger = logging.getLogger(__name__)


class MtuUserPrinter(SaveFilePrinter):
  """IPP endpoint for one PaperCut user; forwards jobs via Mobility Print."""

  def __init__(
    self,
    *,
    user_id: str,
    display_name: str,
    username: str,
    password: str,
    queue_bw: str,
    queue_color: str,
    spool_dir: str,
    base_uri: bytes,
    printer_uri: bytes,
    mobility_client: MobilityPrintClient,
    color_threshold: float = 0.0001,
    default_bw_on_error: bool = True,
    default_sides: str = SIDES_ONE_SIDED,
  ) -> None:
    self.user_id = user_id
    self.display_name = display_name
    self.username = username
    self.password = password
    self.queue_bw = queue_bw
    self.queue_color = queue_color
    self.mobility_client = mobility_client
    self.color_threshold = color_threshold
    self.default_bw_on_error = default_bw_on_error
    self.default_sides = normalize_sides(default_sides)
    self.base_uri = base_uri
    self.printer_uri = printer_uri
    self._client_lock = threading.Lock()

    os.makedirs(spool_dir, exist_ok=True)
    super().__init__(directory=spool_dir, filename_ext="pdf")
    self.ppd = BasicPdfPPD()

  def printer_list_attributes(self):
    attrs = super().printer_list_attributes()
    attrs.update(
      {
        (
          SectionEnum.printer,
          b"printer-name",
          TagEnum.name_without_language,
        ): [self.display_name.encode("utf-8")],
        (
          SectionEnum.printer,
          b"printer-info",
          TagEnum.text_without_language,
        ): [f"PaperCut print node for {self.user_id}".encode("utf-8")],
        (
          SectionEnum.printer,
          b"printer-uri-supported",
          TagEnum.uri,
        ): [self.printer_uri],
        (
          SectionEnum.printer,
          b"sides-supported",
          TagEnum.keyword,
        ): [
          SIDES_ONE_SIDED.encode("ascii"),
          SIDES_TWO_SIDED_LONG_EDGE.encode("ascii"),
          SIDES_TWO_SIDED_SHORT_EDGE.encode("ascii"),
        ],
        (
          SectionEnum.printer,
          b"sides-default",
          TagEnum.keyword,
        ): [self.default_sides.encode("ascii")],
      }
    )
    return attrs

  def _ensure_pdf(self, path: Path) -> Path:
    """Convert PostScript spool files to PDF when clients send PS."""
    if path.suffix.lower() == ".pdf":
      return path
    pdf_path = path.with_suffix(".pdf")
    gs = shutil.which("gs")
    if not gs:
      raise RuntimeError("Ghostscript required to convert PS to PDF")
    cmd = [
      gs,
      "-q",
      "-dNOPAUSE",
      "-dBATCH",
      "-sDEVICE=pdfwrite",
      f"-sOutputFile={pdf_path}",
      str(path),
    ]
    subprocess.run(cmd, check=True)
    path.unlink(missing_ok=True)
    return pdf_path

  def _pick_queue(self, pdf_path: Path) -> str:
    has_color = pdf_has_color(
      pdf_path,
      threshold=self.color_threshold,
      default_on_error=self.default_bw_on_error,
    )
    queue = self.queue_color if has_color else self.queue_bw
    logger.info(
      "Job for %s: color=%s -> queue=%s", self.user_id, has_color, queue
    )
    return queue

  def run_after_saving(self, filename: str, ipp_request) -> None:
    sides = extract_sides_from_request(
      ipp_request, default=self.default_sides
    )
    self._forward_pdf(Path(filename), sides=sides)

  def process_pdf_bytes(self, pdf_data: bytes) -> None:
    path = Path(self.directory) / f"{self.user_id}-{uuid.uuid4()}.pdf"
    path.write_bytes(pdf_data)
    self._forward_pdf(path, sides=self.default_sides)

  def _forward_pdf(self, path: Path, *, sides: str) -> None:
    try:
      pdf_path = self._ensure_pdf(path)
      queue = self._pick_queue(pdf_path)
      with self._client_lock:
        self.mobility_client.print_pdf(
          pdf_path,
          queue,
          self.username,
          self.password,
          job_name=pdf_path.name,
          sides=sides,
        )
      logger.info(
        "Forwarded %s to Mobility Print queue %s for user %s (sides=%s)",
        pdf_path.name,
        queue,
        self.user_id,
        sides,
      )
    except MobilityPrintError:
      logger.exception("Mobility Print upload failed for user %s", self.user_id)
      raise
    finally:
      for candidate in (path, path.with_suffix(".pdf")):
        candidate.unlink(missing_ok=True)

  def leaf_filename(self, _ipp_request) -> str:
    return f"{self.user_id}-{uuid.uuid4()}.pdf"
