"""Offline contracts for lazy history and archive HTTP clients."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest

from aynse.nse import archives, history


pytestmark = pytest.mark.offline


def _unexpected_pool_access():
    raise AssertionError("constructor accessed the global connection pool")


@pytest.mark.parametrize(
    "constructor",
    [history.NSEHistory, history.NSEIndexHistory],
)
def test_history_constructors_do_not_access_connection_pool(monkeypatch, constructor):
    monkeypatch.setattr(history, "get_connection_pool", _unexpected_pool_access)

    instance = constructor()

    assert instance._connection_pool is None
    assert instance._client is None


@pytest.mark.parametrize(
    "constructor",
    [
        archives.NSEArchives,
        archives.NSEIndicesArchives,
        archives.NSEIndexConstituents,
    ],
)
def test_archive_constructors_do_not_access_connection_pool(monkeypatch, constructor):
    monkeypatch.setattr(archives, "get_connection_pool", _unexpected_pool_access)

    instance = constructor()

    assert instance._connection_pool is None
    assert instance._client_arch is None
    assert instance._client_nse is None


@pytest.mark.parametrize(
    ("constructor", "expected_base_url"),
    [
        (history.NSEHistory, "https://www.nseindia.com"),
        (history.NSEIndexHistory, "https://niftyindices.com"),
    ],
)
def test_history_public_client_property_acquires_and_caches_lazily(
    monkeypatch,
    constructor,
    expected_base_url,
):
    client = object()
    pool = Mock()
    pool.get_client.return_value = client
    pool_factory = Mock(return_value=pool)
    monkeypatch.setattr(history, "get_connection_pool", pool_factory)
    instance = constructor()

    assert pool_factory.call_count == 0
    assert instance.connection_pool is pool
    assert instance.connection_pool is pool
    pool_factory.assert_called_once_with()
    assert pool.get_client.call_count == 0

    assert instance.client is client
    assert instance.client is client
    pool.get_client.assert_called_once_with(expected_base_url)


@pytest.mark.parametrize(
    ("constructor", "expected_base_url"),
    [
        (archives.NSEArchives, "https://nsearchives.nseindia.com/"),
        (archives.NSEIndicesArchives, "https://www.niftyindices.com"),
        (archives.NSEIndexConstituents, "https://www.niftyindices.com"),
    ],
)
def test_archive_public_client_properties_acquire_and_cache_lazily(
    monkeypatch,
    constructor,
    expected_base_url,
):
    archive_client = object()
    nse_client = object()
    pool = Mock()
    pool.get_client.side_effect = [archive_client, nse_client]
    pool_factory = Mock(return_value=pool)
    monkeypatch.setattr(archives, "get_connection_pool", pool_factory)
    instance = constructor()

    assert pool_factory.call_count == 0
    assert instance.client_arch is archive_client
    assert instance.client_arch is archive_client
    assert instance.client_nse is nse_client
    assert instance.client_nse is nse_client
    pool_factory.assert_called_once_with()
    assert pool.get_client.call_args_list[0].args == (expected_base_url,)
    assert pool.get_client.call_args_list[1].args == ("https://www.nseindia.com",)
    assert pool.get_client.call_count == 2


def test_public_pool_and_client_attributes_remain_assignable():
    history_instance = history.NSEHistory()
    history_pool = Mock()
    history_client = object()
    history_instance.connection_pool = history_pool
    history_instance.client = history_client
    assert history_instance.connection_pool is history_pool
    assert history_instance.client is history_client

    archive_instance = archives.NSEArchives()
    archive_pool = Mock()
    archive_client = object()
    nse_client = object()
    archive_instance.connection_pool = archive_pool
    archive_instance.client_arch = archive_client
    archive_instance.client_nse = nse_client
    assert archive_instance.connection_pool is archive_pool
    assert archive_instance.client_arch is archive_client
    assert archive_instance.client_nse is nse_client


def test_import_aynse_does_not_construct_global_pool_or_hold_process_open():
    repository = Path(__file__).resolve().parents[1]
    code = (
        "import aynse; "
        "import aynse.nse.connection_pool as connection_pool; "
        "print(connection_pool._connection_pool is None)"
    )

    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=repository,
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )

    assert completed.stdout.strip() == "True"
