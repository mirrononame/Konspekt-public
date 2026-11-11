"""Доступ з телефона через Tailscale (приватна мережа, безкоштовно).

Застосунок і далі слухає лише 127.0.0.1, а `tailscale serve` публікує його
всередині вашої Tailscale-мережі за адресою https://<пк>.<tailnet>.ts.net —
сторонні люди з інтернету його не бачать.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def exe() -> str | None:
    cands = [os.environ.get("TAILSCALE_EXE"), shutil.which("tailscale")]
    if sys.platform == "win32":
        for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"), r"C:\Program Files"):
            if base:
                cands.append(os.path.join(base, "Tailscale", "tailscale.exe"))
    elif sys.platform == "darwin":
        cands.append("/Applications/Tailscale.app/Contents/MacOS/Tailscale")
    for c in cands:
        if c and os.path.isfile(c):
            return c
    return None


def _run(args: list[str], timeout: float = 8) -> tuple[int, str]:
    t = exe()
    if not t:
        return 127, "tailscale не знайдено"
    try:
        p = subprocess.run([t, *args], capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace", creationflags=_NO_WINDOW)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "Tailscale не відповів вчасно"
    except OSError as e:
        return 1, str(e)


def _serve_ports(serve_json: dict) -> set[int]:
    """Витягує локальні порти, на які проксіює `tailscale serve`."""
    ports = set()
    for host_cfg in (serve_json.get("Web") or {}).values():
        for h in (host_cfg.get("Handlers") or {}).values():
            proxy = str(h.get("Proxy") or "")
            tail = proxy.rstrip("/").rsplit(":", 1)[-1]
            if tail.isdigit():
                ports.add(int(tail))
    for v in (serve_json.get("TCP") or {}).values():
        fwd = str(v.get("TCPForward") or "")
        tail = fwd.rsplit(":", 1)[-1]
        if tail.isdigit():
            ports.add(int(tail))
    return ports


def status(port: int) -> dict:
    out = {"installed": bool(exe()), "running": False, "logged_in": False, "dns": None, "ip": None,
           "serve": False, "url": None, "port": port, "message": ""}
    if not out["installed"]:
        return out
    code, text = _run(["status", "--json"])
    try:
        st = json.loads(text[text.find("{"):]) if "{" in text else {}
    except json.JSONDecodeError:
        st = {}
    backend = st.get("BackendState")
    out["running"] = backend is not None
    out["logged_in"] = backend == "Running"
    if backend and backend != "Running":
        out["message"] = {"NeedsLogin": "Потрібно увійти в Tailscale (іконка в треї → Log in).",
                          "Stopped": "Tailscale вимкнено — увімкніть його в треї (Connect).",
                          "Starting": "Tailscale запускається…"}.get(backend, backend)
    elif not backend:
        out["message"] = "Служба Tailscale не запущена."
    me = st.get("Self") or {}
    dns = (me.get("DNSName") or "").rstrip(".")
    out["dns"] = dns or None
    ips = me.get("TailscaleIPs") or []
    out["ip"] = next((i for i in ips if "." in i), None)
    if out["logged_in"]:
        code, text = _run(["serve", "status", "--json"])
        try:
            sj = json.loads(text[text.find("{"):]) if "{" in text else {}
        except json.JSONDecodeError:
            sj = {}
        if port in _serve_ports(sj):
            out["serve"] = True
            out["url"] = f"https://{dns}" if dns else None
    return out


def enable(port: int) -> dict:
    code, text = _run(["serve", "--bg", str(port)], timeout=25)
    res = status(port)
    res["output"] = text.strip()[-2000:]
    res["ok"] = res["serve"]
    if not res["ok"]:
        low = text.lower()
        if "access denied" in low or "denied" in low:
            res["hint"] = "Запустіть tailscale-setup.bat від імені адміністратора (ПКМ → Запуск від імені адміністратора)."
        elif "https://" in text:
            res["hint"] = "Відкрийте посилання з повідомлення нижче, дозвольте HTTPS / Serve для вашої мережі й натисніть кнопку ще раз."
        else:
            res["hint"] = "Спробуйте tailscale-setup.bat у папці застосунку."
    return res


def disable(port: int) -> dict:
    _run(["serve", "--https=443", "off"], timeout=15)
    return status(port)
