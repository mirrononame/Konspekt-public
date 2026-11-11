"""Обробник посилання moodlemobile://token=… (викликає Windows після входу в ePortal).

Запуск: pythonw moodle_callback.py <data_dir> "<url>"
Кладе посилання в <data_dir>/eportal_inbox.json — сервер «Конспекту» забере його за ~3 с —
і відкриває застосунок у браузері.
"""
import json
import os
import sys
import time
import webbrowser
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 3:
        return
    data = Path(sys.argv[1])
    url = sys.argv[2]
    if not url.lower().startswith("moodlemobile://"):
        return
    data.mkdir(parents=True, exist_ok=True)
    tmp = data / ".eportal_inbox.json.tmp"
    tmp.write_text(json.dumps({"url": url, "at": time.time()}), encoding="utf-8")
    os.replace(tmp, data / "eportal_inbox.json")
    port = "8765"
    try:
        port = (data / ".port").read_text().strip() or port
    except OSError:
        pass
    webbrowser.open(f"http://127.0.0.1:{port}/#/settings")


if __name__ == "__main__":
    main()
