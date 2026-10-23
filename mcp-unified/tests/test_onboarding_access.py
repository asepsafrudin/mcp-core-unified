"""Test onboarding terpandu TASK-273 Fase 2 (NIP -> nama -> handoff)."""

from __future__ import annotations

import asyncio

import pytest

from integrations.whatsapp import onboarding_manager as om

NIP = "197711122006141001"
PHONE = "+628111222333"


def test_strict_name_matching():
    assert om.check_name_similarity_strict("AMARYADI", "AMARYADI, S.Sos")[0]
    assert not om.check_name_similarity_strict("ASEP", "ASEP SAFRUDIN")[0]
    assert om.check_name_similarity_strict("ASEP SAFRUDIN", "ASEP SAFRUDIN")[0]


def test_extract_name():
    assert om._extract_name(f"{NIP}#AMARYADI", NIP) == "AMARYADI"
    assert om._extract_name(f"DAFTAR#{NIP}#AMARYADI#SUPD IV", NIP) == "AMARYADI"
    assert om._extract_name(NIP, NIP) is None


def _setup(tmp_path, monkeypatch):
    monkeypatch.setattr(om, "STATE_DB_PATH", tmp_path / "state.db")
    monkeypatch.setattr(om, "AUDIT_PATH", tmp_path / "audit.jsonl")
    monkeypatch.setattr(
        om,
        "lookup_employee_by_nip",
        lambda nip: {"nama": "AMARYADI", "nip": nip} if nip == NIP else None,
    )
    calls: list[tuple[str, str, str]] = []

    async def fake_register(phone: str, nip: str, name: str) -> bool:
        calls.append((phone, nip, name))
        return True

    monkeypatch.setattr(om, "_call_satria_register", fake_register)
    return calls


def test_guided_flow_nip_then_name(tmp_path, monkeypatch):
    calls = _setup(tmp_path, monkeypatch)

    ok, reply = asyncio.run(om.handle_onboarding_message(PHONE, "Asep", "halo"))
    assert ok and "NIP" in reply

    ok, reply = asyncio.run(om.handle_onboarding_message(PHONE, "Asep", NIP))
    assert ok and "NAMA" in reply

    ok, reply = asyncio.run(om.handle_onboarding_message(PHONE, "Asep", "AMARYADI"))
    assert ok and "berhasil" in reply.lower()
    assert calls == [(PHONE, NIP, "AMARYADI")]
    assert om._get_state(PHONE) is None

    audit = tmp_path / "audit.jsonl"
    assert audit.exists() and "onboarded" in audit.read_text(encoding="utf-8")


def test_one_shot_format(tmp_path, monkeypatch):
    calls = _setup(tmp_path, monkeypatch)
    ok, reply = asyncio.run(
        om.handle_onboarding_message(PHONE, "Asep", f"{NIP}#AMARYADI")
    )
    assert ok and "berhasil" in reply.lower()
    assert calls == [(PHONE, NIP, "AMARYADI")]


def test_wrong_name_locks_after_five(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    asyncio.run(om.handle_onboarding_message(PHONE, "Asep", NIP))
    reply = ""
    for _ in range(5):
        _, reply = asyncio.run(
            om.handle_onboarding_message(PHONE, "Asep", "BUDI SANTOSO")
        )
    assert "Terlalu banyak" in reply
    state = om._get_state(PHONE)
    assert state and state["state"] == "LOCKED"


def test_nip_not_found_bumps_attempts(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    unknown = "197711122006149999"
    _, reply = asyncio.run(om.handle_onboarding_message(PHONE, "Asep", f"{unknown}#AMARYADI"))
    assert "tidak ditemukan" in reply.lower()
    state = om._get_state(PHONE)
    assert state and state["nip_attempts"] == 1
