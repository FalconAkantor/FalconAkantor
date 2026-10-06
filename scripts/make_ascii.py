"""Convierte assets/src/avatar.jpg en arte ASCII y lo guarda en data/ascii.json.

Solo hace falta ejecutarlo si cambias la imagen de origen (necesita Pillow):

    pip install pillow
    python scripts/make_ascii.py

El resultado lo usa scripts/render_profile.py, que no necesita dependencias.

El avatar es una figura negra sobre un halo morado. Pasado a ASCII tal cual, la
figura sería un hueco; por eso se mide cuánto más oscuro es cada punto que su
entorno: la figura sale rellena de caracteres densos, el halo queda como polvo
de puntos y la parte de abajo se deshace en código binario, como en el original.
"""

import json
import random
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "src" / "avatar.jpg"
OUT = ROOT / "data" / "ascii.json"

COLS = 58
# Una celda de texto monoespaciado es ~1.9 veces más alta que ancha.
CELL_RATIO = 1.9
# Recorte (izq, arriba, der, abajo) sobre la imagen de 416x416: centra la figura.
CROP = (84, 56, 332, 416)

BLUR = 30  # radio del «entorno» con el que se compara cada punto
FIGURE_SCALE = 40  # diferencia de brillo que cuenta como figura del todo
REGION_BLUR, REGION_MIN = 60, 22  # fuera de la zona iluminada no se dibuja nada
FIGURE_RAMP = "-=+*#%@"  # de menos a más denso
BINARY_FROM = 0.62  # a partir de esta altura (0-1) el cuerpo es código binario

# Niveles del JSON (el renderizador les da color):
#   1-2  halo        3-9  figura        10  brillo del borde de la capucha
HALO_CHARS = {1: ".", 2: ":"}


def main() -> None:
    gray = ImageOps.grayscale(Image.open(SRC).convert("RGB")).crop(CROP)
    blur = gray.filter(ImageFilter.GaussianBlur(BLUR))
    darker = ImageChops.subtract(blur, gray)  # max(0, entorno - punto)
    region = gray.filter(ImageFilter.GaussianBlur(REGION_BLUR))

    w, h = gray.size
    rows = round(h / (w / COLS) / CELL_RATIO)
    size = (COLS, rows)
    fig = darker.resize(size, Image.LANCZOS).load()
    lit = region.resize(size, Image.LANCZOS).load()
    lum = gray.resize(size, Image.LANCZOS).load()

    rng = random.Random(1271)  # semilla fija: el resultado es reproducible
    lines, levels = [], []
    for y in range(rows):
        line, lv = [], []
        for x in range(COLS):
            ch, level = " ", 0
            if lit[x, y] >= REGION_MIN:
                d = min(1.0, fig[x, y] / FIGURE_SCALE)
                b = lum[x, y]
                if d > 0.12:
                    i = min(len(FIGURE_RAMP) - 1, int(d ** 0.8 * len(FIGURE_RAMP)))
                    level = 3 + i
                    ch = FIGURE_RAMP[i]
                    if y >= rows * BINARY_FROM:
                        ch = rng.choice("01")
                elif b > 120:
                    level, ch = 10, "*"
                elif b > 60:
                    level, ch = 2, HALO_CHARS[2]
                elif b > 34:
                    level, ch = 1, HALO_CHARS[1]
            line.append(ch)
            lv.append(level)
        # La figura siempre está rodeada de halo: lo oscuro que queda fuera de él
        # en la misma fila es la viñeta del fondo, no la figura.
        halo = [x for x, level in enumerate(lv) if level in (1, 2, 10)]
        for x, level in enumerate(lv):
            if 3 <= level <= 9 and (not halo or not halo[0] < x < halo[-1]):
                line[x], lv[x] = " ", 0
        lv = [format(level, "x") for level in lv]
        text = "".join(line).rstrip()
        lines.append(text)
        levels.append("".join(lv)[: len(text)])

    # Quita filas vacías arriba y abajo.
    while lines and not lines[0].strip():
        lines.pop(0)
        levels.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
        levels.pop()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps({"cols": COLS, "lines": lines, "levels": levels}, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    print(f"{OUT.relative_to(ROOT)}: {COLS}x{len(lines)}")
    for line in lines:
        print(line)


if __name__ == "__main__":
    main()
