"""Export endpoint: download the results as xlsx / txt / csv."""

import csv
import io
import re
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlmodel import Session

from app.api.errors import api_error
from app.db.models import Analysis
from app.db.session import get_session
from app.export.tabular import build_table

router = APIRouter(prefix="/api", tags=["export"])

_MEDIA = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "txt": "text/plain; charset=utf-8",
    "csv": "text/csv; charset=utf-8",
}


def _safe_filename(name: str) -> str:
    """Keep a filename header-safe: allow word chars, space, dash, dot, underscore."""
    cleaned = re.sub(r"[^\w \-.]", "_", name).strip() or "analysis"
    return cleaned


def _delimited(headers: list[str], rows: list[list[Any]], sep: str) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=sep, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def _xlsx(headers: list[str], rows: list[list[Any]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = "Results"
    sheet.append(headers)
    for row in rows:
        # openpyxl can't store None-vs-"" distinctions meaningfully; keep as-is.
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


@router.get("/analyses/{analysis_id}/export")
def export_results(
    analysis_id: str,
    format: str = "xlsx",
    session: Session = Depends(get_session),
) -> StreamingResponse:
    if format not in _MEDIA:
        raise api_error(
            422,
            "bad_format",
            f"Unknown export format {format!r}; expected xlsx, txt or csv.",
            field="format",
        )
    analysis = session.get(Analysis, analysis_id)
    if analysis is None:
        raise api_error(404, "not_found", f"Analysis {analysis_id} not found.")

    headers, rows = build_table(analysis)
    if format == "xlsx":
        payload = _xlsx(headers, rows)
    else:
        payload = _delimited(headers, rows, "\t" if format == "txt" else ",")

    filename = f"{_safe_filename(analysis.name)}.{format}"
    return StreamingResponse(
        io.BytesIO(payload),
        media_type=_MEDIA[format],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
