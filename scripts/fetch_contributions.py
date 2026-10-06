"""Descarga el calendario público de contribuciones y lo guarda en data/contributions.json.

Lee la misma página HTML que pinta el calendario del perfil, así que no necesita
token ni dependencias. Si GitHub cambia el formato y no se pueden leer los días,
termina con error y no toca el JSON anterior.

    python scripts/fetch_contributions.py [usuario]
"""

import json
import re
import sys
import urllib.request
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "contributions.json"
USER = "FalconAkantor"

COUNT_RE = re.compile(r"^\s*(No|[\d,]+)\s+contributions?\b", re.I)
TOTAL_RE = re.compile(r"([\d,]+)\s+contributions?", re.I)


class CalendarParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.days: dict[str, dict] = {}  # id de la celda -> {date, level}
        self.tooltips: dict[str, str] = {}  # id de la celda -> texto
        self.total_text = ""
        self._tooltip_for: str | None = None
        self._in_total = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "td" and "data-date" in a and "data-level" in a:
            self.days[a.get("id") or a["data-date"]] = {
                "date": a["data-date"],
                "level": int(a["data-level"]),
            }
        elif tag == "tool-tip" and a.get("for"):
            self._tooltip_for = a["for"]
            self.tooltips[self._tooltip_for] = ""
        elif tag == "h2" and a.get("id") == "js-contribution-activity-description":
            self._in_total = True

    def handle_endtag(self, tag):
        if tag == "tool-tip":
            self._tooltip_for = None
        elif tag == "h2":
            self._in_total = False

    def handle_data(self, data):
        if self._tooltip_for:
            self.tooltips[self._tooltip_for] += data
        if self._in_total:
            self.total_text += data


def fetch(user: str) -> str:
    req = urllib.request.Request(
        f"https://github.com/users/{user}/contributions",
        headers={"User-Agent": f"{user}-profile-readme"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def parse(html: str) -> dict:
    p = CalendarParser()
    p.feed(html)

    days = []
    for cell_id, d in p.days.items():
        count = None
        m = COUNT_RE.match(p.tooltips.get(cell_id, ""))
        if m:
            count = 0 if m.group(1).lower() == "no" else int(m.group(1).replace(",", ""))
        date.fromisoformat(d["date"])  # valida el formato
        days.append({"date": d["date"], "level": d["level"], "count": count})
    days.sort(key=lambda d: d["date"])

    if len(days) < 350:
        raise SystemExit(f"Solo se han leído {len(days)} días: ¿ha cambiado el HTML de GitHub?")
    if any(not 0 <= d["level"] <= 4 for d in days):
        raise SystemExit("Nivel de contribución fuera de rango.")

    known = [d["count"] for d in days if d["count"] is not None]
    m = TOTAL_RE.search(p.total_text)
    if m:
        total = int(m.group(1).replace(",", ""))
    elif len(known) == len(days):
        total = sum(known)
    else:
        raise SystemExit("No se ha podido leer el total de contribuciones.")

    return {"total": total, "days": days}


def main() -> None:
    user = sys.argv[1] if len(sys.argv) > 1 else USER
    data = parse(fetch(user))
    data = {
        "user": user,
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        **data,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}: {len(data['days'])} días, {data['total']} contribuciones")


if __name__ == "__main__":
    main()
