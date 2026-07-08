from __future__ import annotations

import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


@contextmanager
def temporary_cookie_file(cookies: Any) -> Iterator[Path | None]:
    rows = normalize_cookies(cookies)
    if not rows:
        yield None
        return

    handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", suffix=".cookies.txt", delete=False)
    path = Path(handle.name)
    try:
        with handle:
            handle.write("# Netscape HTTP Cookie File\n")
            for row in rows:
                handle.write(format_cookie_row(row))
                handle.write("\n")
        yield path
    finally:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def normalize_cookies(cookies: Any) -> list[dict[str, Any]]:
    if not isinstance(cookies, list):
        return []
    result = []
    for cookie in cookies:
        if not isinstance(cookie, dict):
            continue
        name = str(cookie.get("name") or "")
        value = str(cookie.get("value") or "")
        domain = str(cookie.get("domain") or "")
        if not name or not domain:
            continue
        result.append({
            "domain": domain,
            "hostOnly": bool(cookie.get("hostOnly")),
            "path": str(cookie.get("path") or "/"),
            "secure": bool(cookie.get("secure")),
            "httpOnly": bool(cookie.get("httpOnly")),
            "expirationDate": int(float(cookie.get("expirationDate") or 0)),
            "name": name,
            "value": value
        })
    return result


def format_cookie_row(cookie: dict[str, Any]) -> str:
    domain = str(cookie["domain"])
    include_subdomains = "FALSE" if cookie.get("hostOnly") else "TRUE"
    if cookie.get("httpOnly") and not domain.startswith("#HttpOnly_"):
        domain = f"#HttpOnly_{domain}"
    return "\t".join([
        domain,
        include_subdomains,
        str(cookie.get("path") or "/"),
        "TRUE" if cookie.get("secure") else "FALSE",
        str(int(cookie.get("expirationDate") or 0)),
        str(cookie["name"]),
        str(cookie.get("value") or "")
    ])
