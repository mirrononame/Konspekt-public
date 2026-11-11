"""Перевірка конспекту перед PDF (2.5): структура за протоколом, обсяг, таблиці, сміття.

  python tools/noteslint.py notes.md --type W|L|P|note [--lang pl]
  (L — інструкція лаби plan.md; note — короткий конспект лаби)

ERR — треба виправити до mkpdf (код виходу 1). WARN — подивитись, але можна лишити.
"""
import re
import sys


def split_row(line: str) -> list[str]:
    """Комірки рядка таблиці: `|` усередині `коду` або як `\\|` не ділить комірку."""
    cells, cur, code, i = [], "", False, 0
    s = line.strip().strip("|")
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s) and s[i + 1] == "|":
            cur += "|"; i += 2; continue
        if ch == "`":
            code = not code
        if ch == "|" and not code:
            cells.append(cur.strip()); cur = ""
        else:
            cur += ch
        i += 1
    cells.append(cur.strip())
    return cells


def section(md: str, title_rx: str) -> str | None:
    m = re.search(rf"^##\s+{title_rx}.*$", md, re.M | re.I)
    if not m:
        return None
    nxt = re.search(r"^##\s", md[m.end():], re.M)
    return md[m.end(): m.end() + nxt.start()] if nxt else md[m.end():]


def items(block: str) -> int:
    return len(re.findall(r"^\s*(?:[-*]|\d+\.)\s+\S", block or "", re.M))


def lint(md: str, typ: str = "W", lang: str = "pl") -> list[tuple[str, str]]:
    out = []
    err = lambda m: out.append(("ERR", m))
    warn = lambda m: out.append(("WARN", m))
    body = re.sub(r"```.*?```", "", md, flags=re.S)  # код не перевіряємо
    h1 = re.findall(r"^# \S", body, re.M)
    if len(h1) != 1:
        err(f"заголовків «# …» має бути один, а є {len(h1)}")
    if not re.search(r"^\*\*Przedmiot:?\*\*", md, re.M):
        warn("немає рядка «**Przedmiot:** … · **Data:** …» під заголовком")
    n = len(md)
    if typ == "W":
        za = section(body, r"Za 1 minut")
        if za is None:
            err("немає розділу «## Za 1 minutę»")
        elif not 4 <= items(za) <= 8:
            warn(f"«Za 1 minutę»: {items(za)} пунктів (треба 5–7)")
        pts = re.findall(r"^(?:#{2,3}\s+\d+\.|\*\*\d+\.)\s", body, re.M)
        if len(pts) < 6:
            err(f"основних пунктів «## N. …» лише {len(pts)} (треба 8–12)")
        zap = len(re.findall(r"Zapami[eę]taj", body, re.I))
        if pts and zap < 0.6 * len(pts):
            warn(f"«Zapamiętaj» лише в {zap} з {len(pts)} пунктів")
        for t, lo, hi in ((r"Typowe pu[lł]apki", 3, 6), (r"Sprawd[zź] si[eę]", 6, 10)):
            b = section(body, t)
            if b is None:
                err(f"немає розділу «## {t.replace(chr(92), '')}»")
            elif not lo <= items(b) <= hi + 2:
                warn(f"«{t.split(chr(92))[0]}…»: {items(b)} пунктів (треба {lo}–{hi})")
        if n < 4000:
            warn(f"конспект короткий ({n} знаків) — перевір, чи нічого не пропущено")
        if n > 13000:
            err(f"конспект задовгий ({n} знаків, межа ~10 тис. = 3–4 сторінки)")
    elif typ == "L":
        for t in (r"Cel w 1 zdaniu", r"Krok po kroku", r"Do oddania"):
            if section(body, t) is None:
                err(f"немає розділу «## {t}»")
        if section(body, r"Typowe b[lł][eę]dy") is None and section(body, r"Ryzyka") is None:
            warn("немає «## Typowe błędy» / «## Ryzyka i pułapki»")
    elif typ == "note":
        if n > 5000:
            warn(f"короткий конспект лаби задовгий ({n} знаків, межа ~1 сторінка): кроки мають бути в plan.md")
    elif typ == "P":
        if section(body, r"Checklista") is None and section(body, r"Uwagi") is None:
            warn("у журналі зустрічі немає ні «Uwagi…», ні «Checklista…»")
        if re.search(r"\b(?:wersja|version)\s*\d|\bR\.?\d\b", body, re.I):
            warn("згадка «wersja N»/«R4»: версії документів — у «Проєкті», не в конспекті зустрічі")
    # таблиці: однакова кількість комірок у кожному рядку
    for tbl in re.findall(r"(?:^\|.*\|\s*$\n?)+", body, re.M):
        rows = [r for r in tbl.strip().split("\n") if not re.match(r"^\|\s*:?-", r)]
        if not rows:
            continue
        w = len(split_row(rows[0]))
        for r in rows[1:]:
            if len(split_row(r)) != w:
                err(f"таблиця розпадеться: рядок має {len(split_row(r))} комірок замість {w}: {r[:60]}…")
                break
    if re.search(r"</?(?:mark|br|span|div|b|i|u)\b", body, re.I):
        err("HTML-теги (<mark>, <br>…) — у PDF вони з'являться як текст")
    if len(re.findall(r"\*\*", body)) % 2:
        err("непарна кількість «**» — десь не закрито жирний")
    if re.search(r"[\U0001F300-\U0001FAFF]", body.replace("🔧", "").replace("⭐", "")):
        warn("емодзі (крім 🔧 і ⭐) у PDF не відобразяться")
    if lang == "pl":
        cyr = len(re.findall(r"[а-яіїєґ]", body, re.I))
        if cyr > 80:
            warn(f"у польському конспекті {cyr} кириличних літер — змішані мови?")
    return out


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(2)
    args = sys.argv[1:]
    typ = args[args.index("--type") + 1] if "--type" in args else "W"
    lang = args[args.index("--lang") + 1] if "--lang" in args else "pl"
    md = open(args[0], encoding="utf-8").read()
    res = lint(md, typ, lang)
    for lvl, msg in res:
        print(f"{lvl:4} {msg}")
    errs = sum(1 for lvl, _ in res if lvl == "ERR")
    print(f"{len(md)} знаків · помилок: {errs}, зауважень: {len(res) - errs}")
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
