"""Перенесення проєкту із запису зустрічі в subjects/<id>/project (2.4).

  python tools/migrate_project.py <папка data> <план.json>            — лише показати, що буде зроблено
  python tools/migrate_project.py <папка data> <план.json> --apply    — виконати
  --root=<папка>  — корінь «Конспекту» для «@root/…» (типово — над tools/)

Нічого не видаляє й не перезаписує: якщо ціль уже є — дія пропускається з попередженням.
meta.json змінюється лише через функції застосунку (lectures.mutate), як і належить.
Шляхи в плані: відносно папки data; «@root/…» — відносно кореня «Конспекту»; «@here/…» — відносно папки плану.
"""
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    data, plan_p = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    apply = "--apply" in sys.argv
    root = Path(next((x.split("=", 1)[1] for x in sys.argv if x.startswith("--root=")), ROOT)).resolve()  # де _to_delete
    os.environ["KONSPEKT_DATA"] = str(data)
    sys.path.insert(0, str(ROOT))
    plan = json.loads(plan_p.read_text(encoding="utf-8"))
    vars_ = plan.get("vars", {})

    def path(s: str) -> Path:
        for k, v in vars_.items():
            s = s.replace("{" + k + "}", v)
        if s.startswith("@root/"):
            return root / s[6:]
        if s.startswith("@here/"):
            return plan_p.parent / s[6:]
        return data / s

    from app import lectures, project, storage  # noqa: E402  (після KONSPEKT_DATA)
    ok = skipped = 0
    for a in plan["actions"]:
        op = a[0]
        if op in ("move", "copy"):
            src, dst = path(a[1]), path(a[2])
            if not src.exists():
                print(f"  ! немає: {a[1]}"); skipped += 1; continue
            if dst.exists():
                print(f"  ! ціль уже є, пропускаю: {a[2]}"); skipped += 1; continue
            print(f"  {op:6} {a[1]}  →  {a[2]}")
            if apply:
                dst.parent.mkdir(parents=True, exist_ok=True)
                (shutil.move if op == "move" else shutil.copy2)(str(src), str(dst))
        elif op == "project_create":
            print(f"  project {a[1]}: «{a[2]}»")
            if apply and not project.exists(a[1]):
                project.create(a[1], a[2])
        elif op == "mkpdf":
            print(f"  mkpdf  {a[1]} → {a[2]}")
            if apply:
                subprocess.run([sys.executable, str(ROOT / "tools" / "mkpdf.py"), str(path(a[1])), str(path(a[2])), a[3], a[4]], check=True)
        elif op == "result_meeting":
            d = path(a[1]) / "output"
            print(f"  result {a[1]}: зустріч без файлів проєкту")
            if apply:
                old = storage.read_json(d / "result.json.bak", {}) or {}
                cur = storage.read_json(d / "result.json", {}) or {}
                res = {**old, "status": "done", "completed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                       "title": a[2], "summary": (old.get("summary") or "") + " " + a[3], "checklist": [],
                       "todos": cur.get("todos") or old.get("todos") or []}
                storage.write_json(d / "result.json", res)
        elif op == "meta_pop":
            print(f"  meta   {a[1]}: прибрати {', '.join(a[2])}")
            if apply:
                lectures.mutate(a[1], lambda m: [m.pop(k, None) for k in a[2]])
        elif op == "log":
            print(f"  log    {a[1]}")
            if apply:
                project.log(a[1], a[2])
        else:
            print(f"  ? невідома дія {op}"); skipped += 1; continue
        ok += 1
    print(f"\n{'Виконано' if apply else 'Буде виконано'}: {ok}, пропущено: {skipped}" + ("" if apply else "  (запустіть з --apply)"))


if __name__ == "__main__":
    main()
