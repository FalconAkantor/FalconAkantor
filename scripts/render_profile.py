"""Genera las animaciones del perfil a partir de data/:

    assets/header.svg         titular tecleado
    assets/neofetch.svg       ventana tipo neofetch (arte ASCII + ficha)
    assets/contributions.svg  mapa de contribuciones del último año

No necesita dependencias: la Action lo ejecuta cada día después de
fetch_contributions.py. GitHub no ejecuta JavaScript en los README, así que
todo el movimiento es SVG puro (SMIL y animaciones CSS) y se reproduce una vez.
"""

import base64
import json
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
DATA = ROOT / "data"

W = 860
MONO = "'JBM',ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace"
ADV = 0.6  # avance de JetBrains Mono, en em

C = {
    "bg": "#0d1117",
    "bar": "#161b22",
    "border": "#30363d",
    "text": "#d9dfe5",
    "dim": "#8b949e",
    "faint": "#484f58",
    "purple": "#b48cff",
    "lilac": "#e3ccff",
    "amber": "#f2a93b",
    "cyan": "#5cc8d6",
    "green": "#52d18e",
    "red": "#ef5b4c",
    "blue": "#6ea8fe",
}
# Color de cada nivel del arte ASCII de data/ascii.json.
# 1-2 = halo, 3-9 = figura (de menos a más densa), 10 = brillo del borde de la capucha.
ART = ["", "#47306e", "#694a9e", "#8a5fd8", "#9a70e6", "#aa82f1", "#ba96f7",
       "#caacfb", "#dac4fd", "#eadcff", "#ffffff"]
HEAT = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

USER, HOST = "nacho", "automariza"
ON_GITHUB_SINCE = date(2024, 7, 28)

INFO = [
    ("SO", "AUTOMARIZA · la R es de Razonamiento"),
    ("Rol", "Desarrollador de IA, automatización y sistemas"),
    ("Uptime", None),  # se calcula
    ("Ubicación", "España"),
    ("Shell", "bash · python · node"),
    ("IA", "YOLO · LLMs · RAG · Ollama · Whisper · OCR"),
    ("Backend", "FastAPI · Flask · Node.js · SQLite"),
    ("Infra", "Docker · Linux · Proxmox · Raspberry Pi"),
    ("Seguridad", "Nmap · Scapy · monitorización de red"),
    ("Bots", "Telegram · WhatsApp · Discord"),
    ("Actividad", None),  # se calcula
    ("Web", "falconakantor.github.io/Portfolio"),
]


# ── piezas comunes ──────────────────────────────────────────────────────────

def f(n: float) -> str:
    return f"{n:.2f}".rstrip("0").rstrip(".")


def fonts_css() -> str:
    out = []
    for weight in (400, 700):
        raw = (ASSETS / "fonts" / f"jetbrains-mono-latin-{weight}-normal.woff2").read_bytes()
        b64 = base64.b64encode(raw).decode()
        out.append(
            f"@font-face{{font-family:'JBM';font-weight:{weight};"
            f"src:url(data:font/woff2;base64,{b64}) format('woff2')}}"
        )
    return "".join(out)


BASE_CSS = (
    f"text{{font-family:{MONO}}}"
    ".b{font-weight:700}"
    ".in{opacity:0;animation:in .45s cubic-bezier(.2,.7,.2,1) forwards}"
    "@keyframes in{from{opacity:0;transform:translateX(-8px)}to{opacity:1;transform:none}}"
    ".fade{opacity:0;animation:fade .6s ease-out forwards}"
    "@keyframes fade{to{opacity:1}}"
    ".blink{animation:blink 1.06s steps(1) infinite}"
    "@keyframes blink{50%{opacity:0}}"
    "@media (prefers-reduced-motion:reduce){*{animation:none!important;opacity:1!important}}"
)


def svg(width: int, height: int, body: str, css: str, label: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{escape(label)}">'
        f"<title>{escape(label)}</title>"
        f"<style>{fonts_css()}{BASE_CSS}{css}</style>"
        f"{body}</svg>\n"
    )


def window(height: int, title: str) -> str:
    return (
        f'<rect x=".5" y=".5" width="{W - 1}" height="{height - 1}" rx="10" '
        f'fill="{C["bg"]}" stroke="{C["border"]}"/>'
        f'<path d="M.5 34.5V10.5A10 10 0 0 1 10.5 .5H{W - 10.5}A10 10 0 0 1 {W - .5} 10.5V34.5Z" '
        f'fill="{C["bar"]}"/>'
        f'<path d="M.5 34.5H{W - .5}" stroke="{C["border"]}"/>'
        f'<circle cx="20" cy="17.5" r="6" fill="#ff5f57"/>'
        f'<circle cx="40" cy="17.5" r="6" fill="#febc2e"/>'
        f'<circle cx="60" cy="17.5" r="6" fill="#28c840"/>'
        f'<text x="{W / 2}" y="22" text-anchor="middle" font-size="12" fill="{C["dim"]}">'
        f"{escape(title)}</text>"
    )


PROMPT_LEN = len(f"{USER}@{HOST}:~$ ")


def prompt(x: float, y: float, size: float) -> str:
    return (
        f'<text x="{f(x)}" y="{f(y)}" font-size="{size}" xml:space="preserve">'
        f'<tspan class="b" fill="{C["purple"]}">{USER}</tspan>'
        f'<tspan fill="{C["dim"]}">@</tspan>'
        f'<tspan class="b" fill="{C["amber"]}">{HOST}</tspan>'
        f'<tspan fill="{C["dim"]}">:</tspan><tspan fill="{C["cyan"]}">~</tspan>'
        f'<tspan fill="{C["text"]}">$ </tspan></text>'
    )


def typed(uid: str, x: float, y: float, content: str, size: float, start: float,
          step: float = 0.055, hide_cursor_after: float | None = None,
          text_attrs: str = "") -> tuple[str, float]:
    """Texto que se escribe letra a letra (un recorte que crece) con cursor de bloque.

    `content` es el interior del <text> y puede llevar <tspan>. Devuelve el SVG
    y el instante en que termina de escribirse. Con `hide_cursor_after`, el
    cursor desaparece ese tiempo después de terminar; si no, se queda parpadeando.
    """
    plain = _strip_tags(content)
    adv = size * ADV
    n = len(plain)
    dur = n * step
    xs = ";".join(f(i * adv) for i in range(n + 1))
    cx = ";".join(f(x + i * adv) for i in range(n + 1))
    key = ";".join(f"{i / n:.4f}" for i in range(n + 1))
    anim = f'begin="{f(start)}s" dur="{f(dur)}s" calcMode="discrete" keyTimes="{key}" fill="freeze"'
    hide = (f'<set attributeName="visibility" to="hidden" begin="{f(start + dur + hide_cursor_after)}s" '
            f'fill="freeze"/>' if hide_cursor_after is not None else "")
    out = (
        f'<clipPath id="{uid}"><rect x="{f(x)}" y="{f(y - size)}" width="0" height="{f(size * 1.4)}">'
        f'<animate attributeName="width" values="{xs}" {anim}/></rect></clipPath>'
        f'<text x="{f(x)}" y="{f(y)}" font-size="{size}" clip-path="url(#{uid})" '
        f'xml:space="preserve" {text_attrs}>{content}</text>'
        f"<g>{hide}"
        f'<rect class="blink" x="{f(x)}" y="{f(y - size * .82)}" width="{f(adv)}" '
        f'height="{f(size * 1.05)}" fill="{C["text"]}" opacity=".8">'
        f'<animate attributeName="x" values="{cx}" {anim}/></rect></g>'
    )
    return out, start + dur


def _strip_tags(s: str) -> str:
    out, inside = [], False
    for ch in s:
        if ch == "<":
            inside = True
        elif ch == ">":
            inside = False
        elif not inside:
            out.append(ch)
    return (
        "".join(out).replace("&amp;", "&").replace("&lt;", "<")
        .replace("&gt;", ">").replace("&quot;", '"').replace("&#x27;", "'")
    )


def dotted(value: str) -> str:
    """Valor con los separadores « · » atenuados."""
    parts = [escape(p) for p in value.split(" · ")]
    return f'<tspan fill="{C["faint"]}"> · </tspan>'.join(parts)


# ── datos ───────────────────────────────────────────────────────────────────

def load_contributions() -> dict | None:
    path = DATA / "contributions.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def uptime(today: date) -> str:
    months = (today.year - ON_GITHUB_SINCE.year) * 12 + today.month - ON_GITHUB_SINCE.month
    if today.day < ON_GITHUB_SINCE.day:
        months -= 1
    years, months = divmod(months, 12)
    parts = []
    if years:
        parts.append(f"{years} año{'s' if years != 1 else ''}")
    if months or not years:
        parts.append(f"{months} mes{'es' if months != 1 else ''}")
    return ", ".join(parts) + " en GitHub"


def streaks(days: list[dict]) -> tuple[int, int]:
    """(racha actual, mejor racha) en días con al menos una contribución."""
    active = [d["level"] > 0 or (d.get("count") or 0) > 0 for d in days]
    best = run = 0
    for a in active:
        run = run + 1 if a else 0
        best = max(best, run)
    current = 0
    tail = active[:-1] if active and not active[-1] else active  # hoy aún puede llegar
    for a in reversed(tail):
        if not a:
            break
        current += 1
    return current, best


def num(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def plural(n: int, one: str, many: str) -> str:
    return f"{num(n)} {one if n == 1 else many}"


# ── header.svg ──────────────────────────────────────────────────────────────

def render_header() -> str:
    h = 150
    headline = "Construyo sistemas que piensan."
    size = 34
    x = 40
    y = 78
    content = (
        f'<tspan fill="{C["text"]}">Construyo sistemas </tspan>'
        f'<tspan fill="{C["purple"]}">que piensan.</tspan>'
    )
    typing, end = typed("hl", x, y, content, size, start=0.5, step=0.06, text_attrs='class="b"')
    glitch = (
        f'<g clip-path="url(#hl)">'
        f'<text class="b gl r" x="{x}" y="{y}" font-size="{size}" fill="{C["red"]}">{escape(headline)}</text>'
        f'<text class="b gl cy" x="{x}" y="{y}" font-size="{size}" fill="{C["cyan"]}">{escape(headline)}</text>'
        f"</g>"
    )
    brand = "".join(
        f'<tspan fill="{C["amber"]}" class="b">{ch}</tspan>' if i == 6 else ch
        for i, ch in enumerate("AUTOMARIZA")
    )
    sub_y = y + 40
    sub = (
        f'<text class="fade" style="animation-delay:{f(end + .2)}s" x="{x}" y="{sub_y}" '
        f'font-size="14" fill="{C["dim"]}" xml:space="preserve">'
        f'<tspan fill="{C["text"]}" class="b">Nacho</tspan> · <tspan fill="{C["text"]}" class="b">{brand}</tspan>'
        f" — automatización que razona: la <tspan fill=\"{C['amber']}\" class=\"b\">R</tspan>"
        f" es de Razonamiento.</text>"
    )
    css = (
        ".gl{opacity:0;mix-blend-mode:screen}"
        f".gl.r{{animation:glr 5s steps(1) {f(end + 1.2)}s infinite}}"
        f".gl.cy{{animation:glc 5s steps(1) {f(end + 1.2)}s infinite}}"
        "@keyframes glr{0%,86%,100%{opacity:0;transform:none}"
        "87%{opacity:.9;transform:translate(-4px,1px);clip-path:inset(8% 0 58% 0)}"
        "89%{opacity:.9;transform:translate(3px,0);clip-path:inset(55% 0 12% 0)}"
        "91%{opacity:.9;transform:translate(-2px,0);clip-path:inset(30% 0 40% 0)}93%{opacity:0}}"
        "@keyframes glc{0%,86%,100%{opacity:0;transform:none}"
        "87%{opacity:.9;transform:translate(4px,-1px);clip-path:inset(40% 0 30% 0)}"
        "89%{opacity:.9;transform:translate(-3px,1px);clip-path:inset(5% 0 70% 0)}"
        "91%{opacity:.9;transform:translate(2px,0);clip-path:inset(62% 0 6% 0)}93%{opacity:0}}"
    )
    body = (
        "<defs>"
        '<pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse">'
        f'<path d="M24 0H0V24" fill="none" stroke="{C["bar"]}"/></pattern>'
        '<radialGradient id="glow" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" '
        f'gradientTransform="translate({W - 120} 20) scale(420 220)">'
        f'<stop offset="0" stop-color="{C["purple"]}" stop-opacity=".22"/>'
        f'<stop offset="1" stop-color="{C["purple"]}" stop-opacity="0"/></radialGradient>'
        f'<clipPath id="panel"><rect width="{W}" height="{h}" rx="10"/></clipPath>'
        "</defs>"
        f'<g clip-path="url(#panel)">'
        f'<rect width="{W}" height="{h}" fill="{C["bg"]}"/>'
        f'<rect width="{W}" height="{h}" fill="url(#grid)"/>'
        f'<rect width="{W}" height="{h}" fill="url(#glow)"/>'
        f"</g>"
        f'<rect x=".5" y=".5" width="{W - 1}" height="{h - 1}" rx="10" fill="none" stroke="{C["border"]}"/>'
        f"{typing}{glitch}{sub}"
    )
    return svg(W, h, body, css, f"{headline} Nacho · AUTOMARIZA — automatización que razona.")


# ── neofetch.svg ────────────────────────────────────────────────────────────

def render_ascii(x: float, y: float, width: float, start: float, step: float) -> tuple[str, float, float]:
    art = json.loads((DATA / "ascii.json").read_text(encoding="utf-8"))
    adv = width / art["cols"]
    size = adv / ADV
    lh = size * 1.12
    out = []
    for i, (line, levels) in enumerate(zip(art["lines"], art["levels"])):
        if not line.strip():
            continue
        runs: list[list] = []  # [color, texto]
        for ch, lv in zip(line, levels):
            color = ART[int(lv, 16)] if ch != " " else None
            if runs and (color is None or runs[-1][0] == color or runs[-1][0] is None):
                if runs[-1][0] is None:
                    runs[-1][0] = color
                runs[-1][1] += ch
            else:
                runs.append([color, ch])
        spans = "".join(
            f'<tspan fill="{color or ART[1]}">{escape(t)}</tspan>' for color, t in runs
        )
        base = y + i * lh + size * 0.8
        length = len(line) * adv
        uid = f"r{i}"
        out.append(
            f'<clipPath id="{uid}"><rect x="{f(x)}" y="{f(base - size)}" width="0" height="{f(lh + 1)}">'
            f'<animate attributeName="width" from="0" to="{f(length + 1)}" '
            f'begin="{f(start + i * step)}s" dur=".35s" fill="freeze"/></rect></clipPath>'
            f'<text clip-path="url(#{uid})" x="{f(x)}" y="{f(base)}" font-size="{f(size)}" '
            f'textLength="{f(length)}" lengthAdjust="spacingAndGlyphs" xml:space="preserve">{spans}</text>'
        )
    rows = len(art["lines"])
    return "".join(out), rows * lh, start + rows * step + 0.35


ART_W = 300  # ancho del retrato ASCII en la ventana neofetch


def render_neofetch(contrib: dict | None, today: date) -> str:
    size = 13
    lh = 21
    pad = 26
    top = 64

    cmd, typed_end = typed(
        "cmd", pad + PROMPT_LEN * size * ADV, top, f'<tspan fill="{C["text"]}">neofetch</tspan>',
        size, start=0.6, step=0.08, hide_cursor_after=0.25,
    )
    out_start = typed_end + 0.25

    values = dict(INFO)
    values["Uptime"] = uptime(today)
    if contrib:
        values["Actividad"] = plural(contrib["total"], "contribución", "contribuciones") + " en el último año"
    lines = [(k, values[k]) for k, _ in INFO if values[k]]

    ix = 356
    vx = ix + 92
    iy = top + 40
    info = []
    t = out_start + 0.1
    info.append(
        f'<g class="in" style="animation-delay:{f(t)}s">'
        f'<text x="{ix}" y="{iy}" font-size="{size + 1}" class="b">'
        f'<tspan fill="{C["purple"]}">{USER}</tspan><tspan fill="{C["dim"]}">@</tspan>'
        f'<tspan fill="{C["amber"]}">{HOST}</tspan></text>'
        f'<path d="M{ix} {iy + 9}H{ix + len(USER + HOST) * (size + 1) * ADV + (size + 1) * ADV}" '
        f'stroke="{C["faint"]}" stroke-dasharray="5 3"/></g>'
    )
    y = iy + 8
    for k, v in lines:
        y += lh
        t += 0.09
        info.append(
            f'<g class="in" style="animation-delay:{f(t)}s">'
            f'<text x="{ix}" y="{y}" font-size="{size}" class="b" fill="{C["purple"]}">{escape(k)}:</text>'
            f'<text x="{vx}" y="{y}" font-size="{size}" fill="{C["text"]}" xml:space="preserve">{dotted(v)}</text>'
            f"</g>"
        )
    y += lh
    t += 0.12
    blocks = [C["border"], C["red"], C["green"], C["amber"], C["blue"], C["purple"], C["cyan"], C["text"]]
    info.append(
        "".join(
            f'<rect class="in" style="animation-delay:{f(t + i * .05)}s" x="{ix + i * 26}" y="{y - 4}" '
            f'width="24" height="14" rx="2" fill="{c}"/>'
            for i, c in enumerate(blocks)
        )
    )
    info_end = t + len(blocks) * 0.05 + 0.45

    # El retrato se centra en vertical con la ficha.
    info_top, info_bottom = iy - 14, y + 10
    _, art_h, _ = render_ascii(0, 0, ART_W, 0, 0)
    art_y = max(top + 22, info_top + (info_bottom - info_top - art_h) / 2)
    art, art_h, art_end = render_ascii(pad, art_y, ART_W, out_start, 0.045)

    body_bottom = max(art_y + art_h, info_bottom)
    final_y = body_bottom + 34
    end = max(art_end, info_end) + 0.1
    final = (
        f'<g class="fade" style="animation-delay:{f(end)}s">'
        f'{prompt(pad, final_y, size)}'
        f'<rect class="blink" x="{f(pad + PROMPT_LEN * size * ADV)}" y="{f(final_y - size * .82)}" '
        f'width="{f(size * ADV)}" height="{f(size * 1.05)}" fill="{C["text"]}" opacity=".8"/></g>'
    )
    h = int(final_y + 24)
    body = (
        window(h, f"{USER}@{HOST}: ~")
        + prompt(pad, top, size)
        + cmd
        + art
        + "".join(info)
        + final
    )
    return svg(W, h, body, "", f"neofetch de {USER}@{HOST}: " + "; ".join(f"{k}: {v}" for k, v in lines))


# ── contributions.svg ───────────────────────────────────────────────────────

def render_contributions(contrib: dict | None, today: date) -> str:
    if contrib:
        days = contrib["days"]
    else:  # aún sin datos: rejilla vacía hasta la primera ejecución de la Action
        first = today - timedelta(days=364)
        days = [{"date": (first + timedelta(days=i)).isoformat(), "level": 0, "count": 0} for i in range(365)]

    size = 13
    pad = 26
    top = 64
    cmd_text = 'git log --graph --since="1 year ago"'
    cmd, typed_end = typed(
        "cmd", pad + PROMPT_LEN * size * ADV, top, f'<tspan fill="{C["text"]}">{escape(cmd_text)}</tspan>',
        size, start=0.6, step=0.035, hide_cursor_after=0.2,
    )
    start = typed_end + 0.2

    first = date.fromisoformat(days[0]["date"])
    first_sunday = first - timedelta(days=(first.weekday() + 1) % 7)
    pitch, cell = 14.5, 11.5
    gx, gy = 64, top + 46
    weeks = 0

    cells, delays = [], set()
    week_start: dict[int, date] = {}  # primer día visible de cada columna
    for d in days:
        dt = date.fromisoformat(d["date"])
        week = (dt - first_sunday).days // 7
        row = (dt.weekday() + 1) % 7
        weeks = max(weeks, week + 1)
        diag = week + row
        delays.add(diag)
        cells.append(
            f'<rect class="c d{diag}" x="{f(gx + week * pitch)}" y="{f(gy + row * pitch)}" '
            f'width="{cell}" height="{cell}" rx="2.5" fill="{HEAT[d["level"]]}"/>'
        )
        week_start.setdefault(week, dt)

    # Etiqueta de mes en la primera columna de cada mes (sin pisar la anterior).
    month_labels, prev_month, last_week = [], None, -10
    for week in sorted(week_start):
        m = week_start[week].month
        if m != prev_month and week - last_week >= 3:
            month_labels.append((week, MONTHS[m - 1]))
            last_week = week
        prev_month = m

    wave = 0.022
    css = (
        ".c{opacity:0;transform-box:fill-box;transform-origin:center;"
        "animation:pop .5s cubic-bezier(.2,.8,.3,1.35) forwards}"
        "@keyframes pop{from{opacity:0;transform:scale(.2)}to{opacity:1;transform:none}}"
        + "".join(f".d{k}{{animation-delay:{f(start + k * wave)}s}}" for k in sorted(delays))
        + ".ring{opacity:0;animation:ring 2.4s ease-in-out infinite}"
        "@keyframes ring{0%,100%{opacity:0}50%{opacity:.9}}"
    )
    reveal_end = start + max(delays) * wave + 0.5

    labels = "".join(
        f'<text class="fade" style="animation-delay:{f(start)}s" x="{f(gx + w * pitch)}" y="{gy - 9}" '
        f'font-size="10.5" fill="{C["dim"]}">{m}</text>'
        for w, m in month_labels
    )
    labels += "".join(
        f'<text class="fade" style="animation-delay:{f(start)}s" x="{pad}" y="{f(gy + r * pitch + cell - 1.5)}" '
        f'font-size="10.5" fill="{C["dim"]}">{name}</text>'
        for r, name in ((1, "lun"), (3, "mié"), (5, "vie"))
    )

    last = date.fromisoformat(days[-1]["date"])
    lw = (last - first_sunday).days // 7
    lr = (last.weekday() + 1) % 7
    ring = (
        f'<rect class="ring" style="animation-delay:{f(reveal_end)}s" x="{f(gx + lw * pitch - 2)}" '
        f'y="{f(gy + lr * pitch - 2)}" width="{cell + 4}" height="{cell + 4}" rx="4" fill="none" '
        f'stroke="{C["lilac"]}" stroke-width="1.5"/>'
    )

    sy = gy + 7 * pitch + 26
    if contrib:
        current, best = streaks(days)
        stats = (
            f'<tspan class="b" fill="{C["green"]}">{num(contrib["total"])}</tspan>'
            f' {"contribución" if contrib["total"] == 1 else "contribuciones"} en el último año'
            f'<tspan fill="{C["faint"]}"> · </tspan>racha actual: '
            f'<tspan class="b" fill="{C["text"]}">{plural(current, "día", "días")}</tspan>'
            f'<tspan fill="{C["faint"]}"> · </tspan>mejor racha: '
            f'<tspan class="b" fill="{C["text"]}">{plural(best, "día", "días")}</tspan>'
        )
    else:
        stats = "sincronizando contribuciones…"
    stats_svg = (
        f'<text class="fade" style="animation-delay:{f(reveal_end - .3)}s" x="{pad}" y="{f(sy)}" '
        f'font-size="12" fill="{C["dim"]}" xml:space="preserve">{stats}</text>'
    )
    # «menos ■■■■■ más» alineado con el borde derecho de la rejilla (11px → 6.6px por letra).
    legend_w = 44 + 5 * pitch - 3 + 4 + 3 * 11 * ADV
    lx = gx + weeks * pitch - 3 - legend_w
    legend = (
        f'<g class="fade" style="animation-delay:{f(reveal_end - .3)}s">'
        f'<text x="{f(lx)}" y="{f(sy)}" font-size="11" fill="{C["dim"]}">menos</text>'
        + "".join(
            f'<rect x="{f(lx + 44 + i * pitch)}" y="{f(sy - 10)}" width="{cell}" height="{cell}" rx="2.5" fill="{c}"/>'
            for i, c in enumerate(HEAT)
        )
        + f'<text x="{f(lx + 44 + 5 * pitch + 4)}" y="{f(sy)}" font-size="11" fill="{C["dim"]}">más</text></g>'
    )

    h = int(sy + 24)
    body = window(h, "git log — contribuciones") + prompt(pad, top, size) + cmd + labels + "".join(cells) + ring + stats_svg + legend
    label = (
        f"Contribuciones del último año: {contrib['total']}" if contrib else "Contribuciones del último año"
    )
    return svg(W, h, body, css, label)


def main() -> None:
    today = datetime.now(timezone.utc).date()
    contrib = load_contributions()
    outputs = {
        "header.svg": render_header(),
        "neofetch.svg": render_neofetch(contrib, today),
        "contributions.svg": render_contributions(contrib, today),
    }
    for name, content in outputs.items():
        (ASSETS / name).write_text(content, encoding="utf-8")
        print(f"assets/{name}: {len(content.encode()) // 1024} KB")


if __name__ == "__main__":
    main()
