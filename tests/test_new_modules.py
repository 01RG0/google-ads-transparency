"""Tests for config.py, ai.py, and downloader.py."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── config.py ─────────────────────────────────────────────────────────────────

def test_load_env_file_parses_key_value(tmp_path):
    from client.config import _load_env_file
    f = tmp_path / ".env"
    f.write_text("FOO=bar\nBAZ=qux\n", encoding="utf-8")
    result = _load_env_file(f)
    assert result == {"FOO": "bar", "BAZ": "qux"}


def test_load_env_file_skips_comments(tmp_path):
    from client.config import _load_env_file
    f = tmp_path / ".env"
    f.write_text("# this is a comment\nKEY=value\n", encoding="utf-8")
    result = _load_env_file(f)
    assert "KEY" in result
    assert len(result) == 1


def test_load_env_file_strips_quotes(tmp_path):
    from client.config import _load_env_file
    f = tmp_path / ".env"
    f.write_text('A=\'single\'\nB="double"\n', encoding="utf-8")
    result = _load_env_file(f)
    assert result["A"] == "single"
    assert result["B"] == "double"


def test_load_env_file_missing_file(tmp_path):
    from client.config import _load_env_file
    result = _load_env_file(tmp_path / "nonexistent.env")
    assert result == {}


def test_load_toml_missing_file(tmp_path):
    from client.config import _load_toml
    result = _load_toml(tmp_path / "nonexistent.toml")
    assert result == {}


def test_load_toml_valid(tmp_path):
    from client.config import _load_toml
    f = tmp_path / "config.toml"
    f.write_text('[ai]\nprovider = "groq"\n', encoding="utf-8")
    result = _load_toml(f)
    assert result["ai"]["provider"] == "groq"


def test_get_returns_nested_value():
    from client import config as cfg_mod
    with patch.object(cfg_mod, "_config", {"ai": {"provider": "groq"}}):
        result = cfg_mod.get("ai", "provider", "default")
    assert result == "groq"


def test_get_returns_default_for_missing():
    from client import config as cfg_mod
    with patch.object(cfg_mod, "_config", {}):
        result = cfg_mod.get("ai", "provider", "default")
    assert result == "default"


def test_write_sample_config_creates_file(tmp_path):
    from client.config import write_sample_config
    p = tmp_path / "config.toml"
    write_sample_config(p)
    assert p.exists()
    assert "provider" in p.read_text(encoding="utf-8")


def test_write_sample_env_creates_file(tmp_path):
    from client.config import write_sample_env
    p = tmp_path / ".env"
    write_sample_env(p)
    assert p.exists()
    assert "GROQ_API_KEY" in p.read_text(encoding="utf-8")


# ── ai.py ──────────────────────────────────────────────────────────────────────

def test_providers_dict_has_required_keys():
    from client.ai import PROVIDERS
    for name in ["groq", "openai", "anthropic", "ollama", "together"]:
        assert name in PROVIDERS


def test_list_providers_returns_list():
    from client.ai import list_providers
    providers = list_providers()
    assert isinstance(providers, list)
    assert len(providers) > 0


@pytest.mark.asyncio
async def test_ai_complete_openai_compatible():
    from client.ai import ai_complete
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"choices": [{"message": {"content": "test response"}}]}
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)
    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await ai_complete("hello", provider="groq", api_key="test-key", model="test-model")
    assert result == "test response"


@pytest.mark.asyncio
async def test_ai_complete_anthropic_path():
    from client.ai import ai_complete
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"content": [{"text": "anthropic response"}]}
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)
    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await ai_complete("hello", provider="anthropic", api_key="test-key", model="test-model")
    assert result == "anthropic response"


@pytest.mark.asyncio
async def test_ai_complete_raises_on_missing_key(monkeypatch):
    from client.ai import ai_complete
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("AI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="API key"):
        await ai_complete("x", provider="groq", model="m")


@pytest.mark.asyncio
async def test_ai_complete_raises_on_bad_status():
    from client.ai import ai_complete
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.text = "rate limited"
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)
    with patch("httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(RuntimeError, match="429"):
            await ai_complete("x", provider="groq", api_key="key", model="m")


# ── downloader.py ──────────────────────────────────────────────────────────────

def _make_creative(creative_id: str, advertiser_id: str = "AR123"):
    c = MagicMock()
    c.creative_id = creative_id
    c.advertiser_id = advertiser_id
    return c


def _make_detail(preview_url: str | None, creative_id: str):
    variation_content = MagicMock()
    variation_content.preview_url = preview_url
    variation = MagicMock()
    variation.content = variation_content
    detail = MagicMock()
    detail.creative_id = creative_id
    detail.variations = [variation] if preview_url is not None else []
    return detail


@pytest.mark.asyncio
async def test_download_previews_returns_count(tmp_path):
    from client.downloader import download_previews
    page = MagicMock()
    page.creatives = [_make_creative("CR1"), _make_creative("CR2")]
    page.next_cursor = None
    mock_client = AsyncMock()
    mock_client.list_creatives = AsyncMock(return_value=page)
    mock_client.get_creative = AsyncMock(side_effect=lambda aid, cid: _make_detail("http://x.com/img.jpg", cid))
    mock_http_resp = MagicMock()
    mock_http_resp.status_code = 200
    mock_http_resp.content = b"fake_image"
    mock_http = AsyncMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)
    mock_http.get = AsyncMock(return_value=mock_http_resp)
    with patch("httpx.AsyncClient", return_value=mock_http):
        count = await download_previews(mock_client, "AR123", tmp_path, limit=50, pages=1)
    assert count == 2
    assert (tmp_path / "CR1.jpg").exists()
    assert (tmp_path / "CR2.jpg").exists()


@pytest.mark.asyncio
async def test_download_previews_respects_limit(tmp_path):
    from client.downloader import download_previews
    page = MagicMock()
    page.creatives = [_make_creative("CR1"), _make_creative("CR2"), _make_creative("CR3")]
    page.next_cursor = None
    mock_client = AsyncMock()
    mock_client.list_creatives = AsyncMock(return_value=page)
    mock_client.get_creative = AsyncMock(side_effect=lambda aid, cid: _make_detail("http://x.com/img.jpg", cid))
    mock_http_resp = MagicMock()
    mock_http_resp.status_code = 200
    mock_http_resp.content = b"img"
    mock_http = AsyncMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)
    mock_http.get = AsyncMock(return_value=mock_http_resp)
    with patch("httpx.AsyncClient", return_value=mock_http):
        count = await download_previews(mock_client, "AR123", tmp_path, limit=1, pages=1)
    assert count == 1


@pytest.mark.asyncio
async def test_download_previews_skips_failed_download(tmp_path):
    from client.downloader import download_previews
    page = MagicMock()
    page.creatives = [_make_creative("CR1")]
    page.next_cursor = None
    mock_client = AsyncMock()
    mock_client.list_creatives = AsyncMock(return_value=page)
    mock_client.get_creative = AsyncMock(return_value=_make_detail("http://x.com/img.jpg", "CR1"))
    mock_http_resp = MagicMock()
    mock_http_resp.status_code = 404
    mock_http = AsyncMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)
    mock_http.get = AsyncMock(return_value=mock_http_resp)
    with patch("httpx.AsyncClient", return_value=mock_http):
        count = await download_previews(mock_client, "AR123", tmp_path, limit=50, pages=1)
    assert count == 0
    assert not (tmp_path / "CR1.jpg").exists()


@pytest.mark.asyncio
async def test_download_previews_handles_missing_preview_url(tmp_path):
    from client.downloader import download_previews
    page = MagicMock()
    page.creatives = [_make_creative("CR1")]
    page.next_cursor = None
    mock_client = AsyncMock()
    mock_client.list_creatives = AsyncMock(return_value=page)
    mock_client.get_creative = AsyncMock(return_value=_make_detail(None, "CR1"))
    with patch("httpx.AsyncClient"):
        count = await download_previews(mock_client, "AR123", tmp_path, limit=50, pages=1)
    assert count == 0
