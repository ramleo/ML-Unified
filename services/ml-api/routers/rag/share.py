"""Shareable session links — let a session owner hand out read+chat access
to their uploaded documents via a time-limited, revocable token, without
exposing the raw session_id (which has no expiry/revoke of its own)."""
from __future__ import annotations

import time
import uuid as _uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from routers.rag import get_rag_state

router = APIRouter()

_TTL_SECONDS = 24 * 60 * 60


def resolve_share_token(token: str, state, client_ip: str = "") -> str | None:
    """Return the owning session_id if `token` is valid, not revoked, and not
    expired. Returns None otherwise — callers should treat that as no access.

    First successful resolution binds the token to that client_ip; later
    resolutions from a different IP are rejected, so forwarding the link to
    a third party doesn't extend access beyond whoever opened it first. An
    empty client_ip (can't be determined) never binds or blocks — avoids
    false lockouts when the caller has no way to know the real IP."""
    entry = state.share_links.get(token)
    if not entry or entry["revoked"]:
        return None
    if time.time() - entry["created_at"] > _TTL_SECONDS:
        return None
    if client_ip:
        if entry["bound_ip"] is None:
            entry["bound_ip"] = client_ip
        elif entry["bound_ip"] != client_ip:
            return None
    return entry["session_id"]


class CreateShareRequest(BaseModel):
    session_id: str


class RevokeShareRequest(BaseModel):
    token: str
    session_id: str


@router.post("/share-session")
def create_share(req: CreateShareRequest) -> dict:
    if not req.session_id:
        raise HTTPException(status_code=400, detail="session_id is required.")
    state = get_rag_state()
    token = _uuid.uuid4().hex
    created_at = time.time()
    state.share_links[token] = {
        "session_id": req.session_id,
        "created_at": created_at,
        "revoked": False,
        "bound_ip": None,
    }
    return {"token": token, "expires_at": created_at + _TTL_SECONDS}


@router.get("/share-status/{token}")
def share_status(token: str) -> dict:
    state = get_rag_state()
    entry = state.share_links.get(token)
    if not entry:
        raise HTTPException(status_code=404, detail="Unknown share link.")
    active = not entry["revoked"] and (time.time() - entry["created_at"] <= _TTL_SECONDS)
    return {
        "active": active,
        "revoked": entry["revoked"],
        "expires_at": entry["created_at"] + _TTL_SECONDS,
        "bound": entry["bound_ip"] is not None,
    }


@router.post("/revoke-share")
def revoke_share(req: RevokeShareRequest) -> dict:
    state = get_rag_state()
    entry = state.share_links.get(req.token)
    if not entry:
        raise HTTPException(status_code=404, detail="Unknown share link.")
    if entry["session_id"] != req.session_id:
        raise HTTPException(status_code=403, detail="Only the session that created this link can revoke it.")
    entry["revoked"] = True
    return {"status": "ok", "revoked": True}
