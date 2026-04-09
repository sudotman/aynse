"""
Shared standardization helpers for the public aynse API.
"""

from __future__ import annotations

import csv
import io
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence, Union


DateLike = Union[date, datetime, str]


class AynseError(Exception):
    """Base error for aynse public API failures."""


class InputValidationError(AynseError, ValueError):
    """Raised when a caller passes invalid input."""


class DataUnavailableError(AynseError):
    """Raised when upstream data is unavailable for a valid request."""


class UpstreamResponseError(AynseError):
    """Raised when an upstream service returns an unsupported response."""


def coerce_date(value: DateLike, field_name: str = "date") -> date:
    """Coerce supported date-like values to ``datetime.date``."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        raw = value.strip()
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d-%b-%Y", "%d-%b-%y", "%d %b %Y"):
            try:
                return datetime.strptime(raw, fmt).date()
            except ValueError:
                continue
    raise InputValidationError(
        f"Invalid {field_name!r}: expected date, datetime, or supported date string"
    )


def coerce_optional_date(
    value: Optional[DateLike],
    field_name: str = "date",
) -> Optional[date]:
    if value is None:
        return None
    return coerce_date(value, field_name=field_name)


def coerce_year(year: Optional[Union[int, str]]) -> Optional[int]:
    if year is None:
        return None
    if isinstance(year, int):
        return year
    if isinstance(year, str) and year.strip().isdigit():
        return int(year.strip())
    raise InputValidationError("year must be an integer")


def coerce_month(month: Optional[Union[int, str]]) -> Optional[int]:
    if month is None:
        return None
    if isinstance(month, int):
        value = month
    elif isinstance(month, str) and month.strip().isdigit():
        value = int(month.strip())
    else:
        raise InputValidationError("month must be an integer")
    if not 1 <= value <= 12:
        raise InputValidationError("month must be between 1 and 12")
    return value


def normalize_symbol(symbol: str) -> str:
    raw = str(symbol).strip()
    if not raw:
        raise InputValidationError("symbol cannot be empty")
    return raw.upper()


def normalize_name(name: str) -> str:
    raw = " ".join(str(name).strip().split())
    if not raw:
        raise InputValidationError("name cannot be empty")
    return raw


def snake_case(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z]+", "_", str(value).strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_").lower()
    return cleaned or "value"


def clean_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = " ".join(str(value).strip().split())
    return text or None


def to_float(value: Any) -> Optional[float]:
    if value in (None, "", "-", "--"):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    text = text.replace("%", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def to_int(value: Any) -> Optional[int]:
    number = to_float(value)
    if number is None:
        return None
    return int(number)


def to_bool(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    return None


def parse_date_maybe(value: Any) -> Optional[date]:
    if value in (None, "", "-", "--"):
        return None
    try:
        return coerce_date(value)
    except InputValidationError:
        return None


def parse_datetime_maybe(value: Any) -> Optional[datetime]:
    if value in (None, "", "-", "--"):
        return None
    if isinstance(value, datetime):
        return value
    raw = str(value).strip()
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%d-%b-%Y %H:%M:%S",
        "%d-%b-%Y %H:%M",
        "%d%m%Y%H%M%S",
    ):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def ensure_directory(path: Union[str, Path]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    return output


def records_to_csv_text(
    records: Sequence[dict[str, Any]],
    fieldnames: Optional[Sequence[str]] = None,
) -> str:
    if not records:
        names = list(fieldnames or [])
        if not names:
            return ""
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=names)
        writer.writeheader()
        return buf.getvalue()

    names = list(fieldnames or records[0].keys())
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=names)
    writer.writeheader()
    for record in records:
        row = {}
        for key in names:
            value = record.get(key)
            if isinstance(value, date) and not isinstance(value, datetime):
                row[key] = value.isoformat()
            elif isinstance(value, datetime):
                row[key] = value.isoformat(sep=" ")
            elif value is None:
                row[key] = ""
            else:
                row[key] = value
        writer.writerow(row)
    return buf.getvalue()


def write_records_csv(
    path: Union[str, Path],
    records: Sequence[dict[str, Any]],
    fieldnames: Optional[Sequence[str]] = None,
) -> str:
    output = ensure_directory(path)
    output.write_text(records_to_csv_text(records, fieldnames), encoding="utf-8")
    return str(output)


def write_records_json(path: Union[str, Path], records: Any) -> str:
    output = ensure_directory(path)
    output.write_text(json.dumps(records, ensure_ascii=True, indent=2, default=_json_default), encoding="utf-8")
    return str(output)


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def sort_by_date(
    records: Iterable[dict[str, Any]],
    field_name: str = "date",
) -> list[dict[str, Any]]:
    def _sort_key(record: dict[str, Any]) -> tuple[int, Any]:
        value = record.get(field_name)
        if isinstance(value, datetime):
            return (0, value)
        if isinstance(value, date):
            return (0, datetime.combine(value, datetime.min.time()))
        parsed = parse_datetime_maybe(value) or (
            datetime.combine(parse_date_maybe(value), datetime.min.time())
            if parse_date_maybe(value)
            else None
        )
        return (0, parsed) if parsed is not None else (1, str(value))

    return sorted(list(records), key=_sort_key)


def dataframe_from_records(
    records: Sequence[dict[str, Any]],
    fieldnames: Optional[Sequence[str]] = None,
):
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - depends on optional dependency
        raise ModuleNotFoundError("pandas is required for dataframe helpers") from exc

    frame = pd.DataFrame(records)
    if fieldnames:
        missing = [field for field in fieldnames if field not in frame.columns]
        for field in missing:
            frame[field] = None
        frame = frame[list(fieldnames)]
    return frame

