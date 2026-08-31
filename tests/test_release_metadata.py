"""Release metadata contracts."""

from __future__ import annotations

import re
from pathlib import Path

from aynse import __version__


def test_runtime_version_matches_pyproject() -> None:
    project_root = Path(__file__).resolve().parents[1]
    pyproject = (project_root / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(
        r'^version\s*=\s*["\']([^"\']+)["\']',
        pyproject,
        re.MULTILINE,
    )

    assert match is not None
    assert __version__ == match.group(1)
