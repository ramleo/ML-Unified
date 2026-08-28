"""
Real YARA file scanning — runs the actual open-source YARA pattern-matching
engine (via yara-python, verified installable as a prebuilt manylinux wheel,
no libyara compile needed) against an uploaded file, either with a small
built-in rule set or a user-supplied custom rule.

The built-in rules are a small, SELF-AUTHORED educational set covering
well-documented indicator classes (EICAR test signature, PowerShell LOLBin
encoding, generic webshell/macro/reverse-shell patterns, embedded-PE
smuggling, and YARA's own entropy math module) — explicitly NOT a pulled
third-party threat-intel feed (whose licensing wasn't verified for this
project), same "curated, disclosed as not exhaustive" honesty pattern as
the QR Phishing Detector's brand list and the Malicious Package Scanner's
typosquat list.

The custom-rule endpoint is the more important half: YARA's real-world
purpose is letting an analyst write and iterate on a detection rule, not
just run a fixed scanner — this lets a user actually do that against their
own uploaded file.

Safety: the file is never executed or written to disk, bytes stay in
memory only. A YARA match timeout guards against a pathological custom
rule (e.g. a catastrophic-backtracking regex) taking too long.
"""
from __future__ import annotations

import base64

import yara
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

_MAX_FILE_BYTES = 5 * 1024 * 1024  # 5MB — matches mm_malware_image.py's precedent
_MAX_RULE_SOURCE_BYTES = 20 * 1024  # a hand-written YARA rule is never this large
_MATCH_TIMEOUT_S = 5  # yara's own timeout param — real hardening, not invented here

_BUILTIN_RULES_SOURCE = r'''
import "math"

rule EICAR_Test_File {
    meta:
        description = "The real, official antivirus test signature (EICAR) — matches on purpose, safe to trigger."
    strings:
        $eicar = "X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
    condition:
        $eicar
}

rule Suspicious_PowerShell_EncodedCommand {
    meta:
        description = "PowerShell -EncodedCommand / -enc flag paired with a long base64 run — a well-documented LOLBin technique for hiding a malicious command line."
    strings:
        $flag1 = "-EncodedCommand" nocase
        $flag2 = "-enc " nocase
        $b64run = /[A-Za-z0-9+\/]{80,}={0,2}/
    condition:
        ($flag1 or $flag2) and $b64run
}

rule Generic_Webshell_PHP {
    meta:
        description = "PHP eval()/base64_decode() combined with $_POST or $_GET — the standard, widely-documented webshell pattern (arbitrary code execution from an HTTP request)."
    strings:
        $eval = "eval(" nocase
        $b64d = "base64_decode(" nocase
        $post = "$_POST"
        $get = "$_GET"
    condition:
        $eval and $b64d and ($post or $get)
}

rule Office_Macro_AutoExec {
    meta:
        description = "Office VBA auto-execute macro trigger (AutoOpen/Document_Open) combined with Shell/CreateObject — the classic documented macro-malware pattern."
    strings:
        $auto1 = "AutoOpen" nocase
        $auto2 = "Document_Open" nocase
        $shell = "Shell" nocase
        $createobj = "CreateObject" nocase
    condition:
        ($auto1 or $auto2) and ($shell or $createobj)
}

rule Embedded_PE_In_Non_Exe {
    meta:
        description = "A Windows PE executable's own marker string found anywhere in the file, not just at offset 0 — a possible executable smuggled inside another file type."
    strings:
        $mz = "MZ"
        $dosmsg = "This program cannot be run in DOS mode"
    condition:
        $mz and $dosmsg
}

rule Possible_Python_Reverse_Shell {
    meta:
        description = "Python socket + subprocess + connect co-occurring — a documented reverse-shell one-liner pattern (also used defensively/in pentesting)."
    strings:
        $socket = "socket" nocase
        $subprocess = "subprocess" nocase
        $connect = ".connect(" nocase
    condition:
        $socket and $subprocess and $connect
}

rule High_Overall_Entropy {
    meta:
        description = "Overall file entropy above 7.5 bits/byte (near the theoretical max of 8) via YARA's real math module — the same signal packer/crypter tools trigger, but also true of ordinary compressed formats (zip/jpg/etc.), so this is informational, not a verdict on its own."
    condition:
        filesize > 256 and math.entropy(0, filesize) > 7.5
}
'''

_builtin_rules: yara.Rules | None = None


def _get_builtin_rules() -> yara.Rules:
    global _builtin_rules
    if _builtin_rules is None:
        _builtin_rules = yara.compile(source=_BUILTIN_RULES_SOURCE)
    return _builtin_rules


def _run_match(rules: yara.Rules, data: bytes) -> list[dict]:
    matches = rules.match(data=data, timeout=_MATCH_TIMEOUT_S)
    results = []
    for m in matches:
        strings = []
        for s in m.strings:
            for instance in s.instances:
                strings.append({
                    "identifier": s.identifier,
                    "offset": instance.offset,
                    "matched_bytes_hex": instance.matched_data.hex()[:120],
                })
        results.append({
            "rule": m.rule,
            "description": m.meta.get("description"),
            "strings": strings,
        })
    return results


class BuiltinScanRequest(BaseModel):
    file: str  # base64


class CustomScanRequest(BaseModel):
    file: str  # base64
    rule_source: str


@router.post("/yara-scan/builtin")
def scan_builtin(req: BuiltinScanRequest):
    raw = base64.b64decode(req.file)
    data = raw[:_MAX_FILE_BYTES]
    rules = _get_builtin_rules()
    matches = _run_match(rules, data)
    return {
        "matches": matches,
        "file_size": len(raw),
        "truncated": len(raw) > _MAX_FILE_BYTES,
    }


@router.post("/yara-scan/custom")
def scan_custom(req: CustomScanRequest):
    if len(req.rule_source.encode()) > _MAX_RULE_SOURCE_BYTES:
        raise HTTPException(status_code=400, detail="Rule source is too large (max 20KB).")

    try:
        rules = yara.compile(source=req.rule_source)
    except yara.SyntaxError as e:
        raise HTTPException(status_code=400, detail=f"Rule compile error: {e}")
    except yara.Error as e:
        raise HTTPException(status_code=400, detail=f"Rule error: {e}")

    raw = base64.b64decode(req.file)
    data = raw[:_MAX_FILE_BYTES]

    try:
        matches = _run_match(rules, data)
    except yara.TimeoutError:
        raise HTTPException(status_code=400, detail="Rule took too long to match (possible pathological pattern) — simplify it and try again.")

    return {
        "matches": matches,
        "file_size": len(raw),
        "truncated": len(raw) > _MAX_FILE_BYTES,
    }
