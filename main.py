#!/usr/bin/env python3
"""news-image-20261122 -- v6, round 4 (stdlib only).

One 1024x1024 PNG summing up Sunday 22 November 2026 world news:
11 pictured cards + 24 list stories = 35 stories, plus a UTC strip,
a DATE CHECK box and a world map with 11 numbered dots.

v6 (top-5 findings): bold serif masthead date + serif big-card
titles, per-story certainty pills (CONFIRMED green / CLAIM amber)
with a footer legend, and the 6 key numbers on a dark navy band.

No Pillow, no font files: every letter is drawn from the 5x7 bitmap
glyph table below, written by hand for this program (the serif
display type uses a 7x10 table with the same hand-drawn approach).
Output goes to $MAKEFUN_OUTPUT_DIR/entry.png when that variable is
set, otherwise to entry-v6.png next to this file.  Rendering is
fully deterministic.
"""
import os
import struct
import sys
import zlib

W, H = 1024, 1024

# ---------------------------------------------------------------- palette
PAPER = (247, 243, 234)      # warm cream page
CARD = (255, 252, 244)       # card paper
INK = (24, 32, 48)           # near-black navy (never pure black)
NAVY = (16, 32, 64)          # dark strip navy
RED = (178, 34, 34)          # headline red
GOLD = (201, 162, 39)        # masthead gold
UTC_GOLD = (172, 138, 58)    # muted gold for the UTC label
GREY = (120, 124, 132)       # footer grey
RULE = (176, 168, 150)       # thin rule between scene and title
BOXTEXT = (34, 48, 63)       # DATE CHECK body ink
CHARCOAL = (40, 44, 54)      # DATE CHECK accent bar
UTC_DIV = (52, 72, 110)      # UTC column dividers
SEA = (190, 215, 232)        # map sea
LAND = (214, 205, 180)       # map land
WHITE = (255, 255, 255)
SKYLINE = (190, 195, 205)    # UTC description grey

REGION = {
    "EUROPE": (31, 78, 156),
    "MIDDLE EAST": (179, 84, 30),
    "ASIA": (46, 125, 79),
    "AMERICAS": (122, 59, 143),
    "AFRICA": (138, 109, 27),
    "OCEANIA": (14, 124, 134),
    "WORLD": (90, 90, 110),
}
DAYCOL = {"SUN": (46, 125, 79), "SAT": (179, 84, 30), "FRI": (178, 34, 34)}

# ---------------------------------------------------------------- canvas
buf = bytearray(W * H * 3)
_clip = [0, 0, W, H]
MISSING = []


def fill(c):
    r, g, b = c
    buf[0::3] = bytes([r]) * (W * H)
    buf[1::3] = bytes([g]) * (W * H)
    buf[2::3] = bytes([b]) * (W * H)


def set_clip(x0, y0, x1, y1):
    _clip[0] = max(0, x0)
    _clip[1] = max(0, y0)
    _clip[2] = min(W, x1)
    _clip[3] = min(H, y1)


def reset_clip():
    _clip[0], _clip[1], _clip[2], _clip[3] = 0, 0, W, H


def px(x, y, c):
    if _clip[0] <= x < _clip[2] and _clip[1] <= y < _clip[3]:
        i = (y * W + x) * 3
        buf[i], buf[i + 1], buf[i + 2] = c


def rect(x0, y0, x1, y1, c):
    x0 = max(x0, _clip[0]); y0 = max(y0, _clip[1])
    x1 = min(x1, _clip[2]); y1 = min(y1, _clip[3])
    if x1 <= x0 or y1 <= y0:
        return
    r, g, b = c
    for y in range(y0, y1):
        i = (y * W + x0) * 3
        n = (x1 - x0)
        buf[i:i + n * 3] = bytes((r, g, b)) * n


def hline(x0, x1, y, c):
    rect(x0, y, x1, y + 1, c)


def vline(x, y0, y1, c):
    rect(x, y0, x + 1, y1, c)


def vgrad(x0, y0, x1, y1, top, bot):
    """Vertical gradient, 12 bands (deterministic, stdlib only)."""
    h = y1 - y0
    if h <= 0:
        return
    bands = 12
    for k in range(bands):
        ya = y0 + h * k // bands
        yb = y0 + h * (k + 1) // bands
        t = k / max(1, bands - 1)
        c = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3))
        rect(x0, ya, x1, yb, c)


def circle(cx, cy, r, c):
    r = int(round(r))
    if r <= 0:
        return
    for dy in range(-r, r + 1):
        dx = int((r * r - dy * dy) ** 0.5)
        hline(cx - dx, cx + dx + 1, cy + dy, c)


def ellipse(cx, cy, rx, ry, c):
    rx = int(round(rx)); ry = int(round(ry))
    if rx <= 0 or ry <= 0:
        return
    for dy in range(-ry, ry + 1):
        t = 1.0 - (dy * dy) / float(ry * ry)
        dx = int(rx * (t ** 0.5)) if t > 0 else 0
        hline(cx - dx, cx + dx + 1, cy + dy, c)


def ring(cx, cy, r, t, c):
    for k in range(t):
        rr = r - k
        for dy in range(-rr, rr + 1):
            dx = int((rr * rr - dy * dy) ** 0.5)
            px(cx - dx, cy + dy, c)
            px(cx + dx, cy + dy, c)
            px(cx + dx, cy - dy, c)
            px(cx - dx, cy - dy, c)


def line(x0, y0, x1, y1, c):
    dx = abs(x1 - x0); dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        px(x0, y0, c)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy; x0 += sx
        if e2 <= dx:
            err += dx; y0 += sy


def thick_line(x0, y0, x1, y1, w, c):
    r = max(1, w // 2)
    steps = max(abs(x1 - x0), abs(y1 - y0), 1)
    for k in range(steps + 1):
        x = int(round(x0 + (x1 - x0) * k / steps))
        y = int(round(y0 + (y1 - y0) * k / steps))
        circle(x, y, r, c)


def poly(points, c):
    """Scanline fill of a simple polygon (list of (x, y))."""
    if len(points) < 3:
        return
    ys = [p[1] for p in points]
    for y in range(max(min(ys), _clip[1]), min(max(ys), _clip[3] - 1) + 1):
        xs = []
        n = len(points)
        for i in range(n):
            x0, y0 = points[i]
            x1, y1 = points[(i + 1) % n]
            if (y0 <= y < y1) or (y1 <= y < y0):
                t = (y - y0) / float(y1 - y0)
                xs.append(x0 + t * (x1 - x0))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            hline(int(round(xs[k])), int(round(xs[k + 1])) + 1, y, c)


def tri(x0, y0, x1, y1, x2, y2, c):
    poly([(x0, y0), (x1, y1), (x2, y2)], c)


# ---------------------------------------------------------------- 5x7 font
# Hand-written bitmap glyphs: 7 rows of 5 cells, '1' = ink.
# Uppercase A-Z, lowercase a-z (x-height rows 2-6, ascenders 0-6,
# descenders inside rows 5-6), digits and punctuation.
FONT = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "J": ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "10101", "01010"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "a": ("00000", "00000", "01110", "00001", "01111", "10001", "01111"),
    "b": ("10000", "10000", "11110", "10001", "10001", "10001", "11110"),
    "c": ("00000", "00000", "01110", "10000", "10000", "10001", "01110"),
    "d": ("00001", "00001", "01111", "10001", "10001", "10001", "01111"),
    "e": ("00000", "00000", "01110", "10001", "11111", "10000", "01110"),
    "f": ("00110", "01001", "01000", "11110", "01000", "01000", "01000"),
    "g": ("00000", "01111", "10001", "10001", "01111", "00001", "01110"),
    "h": ("10000", "10000", "11110", "10001", "10001", "10001", "10001"),
    "i": ("00100", "00000", "01100", "00100", "00100", "00100", "01110"),
    "j": ("00010", "00000", "00110", "00010", "00010", "10010", "01100"),
    "k": ("10000", "10000", "10010", "10100", "11000", "10100", "10010"),
    "l": ("01100", "00100", "00100", "00100", "00100", "00100", "01110"),
    "m": ("00000", "00000", "11010", "10101", "10101", "10101", "10101"),
    "n": ("00000", "00000", "11110", "10001", "10001", "10001", "10001"),
    "o": ("00000", "00000", "01110", "10001", "10001", "10001", "01110"),
    "p": ("00000", "00000", "11110", "10001", "10001", "11110", "10000"),
    "q": ("00000", "00000", "01111", "10001", "10001", "01111", "00001"),
    "r": ("00000", "00000", "10110", "11001", "10000", "10000", "10000"),
    "s": ("00000", "00000", "01111", "10000", "01110", "00001", "11110"),
    "t": ("00100", "00100", "11110", "00100", "00100", "00100", "00110"),
    "u": ("00000", "00000", "10001", "10001", "10001", "10011", "01101"),
    "v": ("00000", "00000", "10001", "10001", "10001", "01010", "00100"),
    "w": ("00000", "00000", "10001", "10101", "10101", "10101", "01010"),
    "x": ("00000", "00000", "10001", "01010", "00100", "01010", "10001"),
    "y": ("00000", "00000", "10001", "10001", "01111", "00001", "01110"),
    "z": ("00000", "00000", "11111", "00010", "00100", "01000", "11111"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00110", "01000", "10000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    "6": ("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00010", "01100"),
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    ",": ("00000", "00000", "00000", "00000", "01100", "00100", "01000"),
    ":": ("00000", "01100", "01100", "00000", "01100", "01100", "00000"),
    ";": ("00000", "01100", "01100", "00000", "01100", "00100", "01000"),
    "!": ("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    "?": ("01110", "10001", "00001", "00110", "00100", "00000", "00100"),
    "'": ("00100", "00100", "01000", "00000", "00000", "00000", "00000"),
    '"': ("01010", "01010", "00000", "00000", "00000", "00000", "00000"),
    "-": ("00000", "00000", "00000", "01110", "00000", "00000", "00000"),
    "/": ("00001", "00010", "00010", "00100", "01000", "01000", "10000"),
    "%": ("11001", "11010", "00010", "00100", "01000", "01011", "10011"),
    "$": ("00100", "01111", "10100", "01110", "00101", "11110", "00100"),
    "&": ("01100", "10010", "10100", "01000", "10101", "10010", "01101"),
    "+": ("00000", "00100", "00100", "11111", "00100", "00100", "00000"),
    "=": ("00000", "00000", "11111", "00000", "11111", "00000", "00000"),
    "*": ("00000", "10101", "01110", "10101", "00000", "00000", "00000"),
    "#": ("01010", "01010", "11111", "01010", "11111", "01010", "01010"),
    "@": ("01110", "10001", "10111", "10101", "10110", "10000", "01110"),
    "_": ("00000", "00000", "00000", "00000", "00000", "00000", "11111"),
    "(": ("00010", "00100", "01000", "01000", "01000", "00100", "00010"),
    ")": ("01000", "00100", "00010", "00010", "00010", "00100", "01000"),
    "[": ("01110", "01000", "01000", "01000", "01000", "01000", "01110"),
    "]": ("01110", "00010", "00010", "00010", "00010", "00010", "01110"),
    "<": ("00010", "00100", "01000", "10000", "01000", "00100", "00010"),
    ">": ("01000", "00100", "00010", "00001", "00010", "00100", "01000"),
    "|": ("00100", "00100", "00100", "00100", "00100", "00100", "00100"),
    "\\": ("10000", "01000", "01000", "00100", "00010", "00010", "00001"),
    "\u00b7": ("00000", "00000", "00000", "01100", "01100", "00000", "00000"),
    "\u2019": ("00100", "00100", "01000", "00000", "00000", "00000", "00000"),
    "\u2018": ("00100", "00100", "01000", "00000", "00000", "00000", "00000"),
}

# Dashes and the middle dot map onto drawn glyphs (no missing glyphs).
ALIASES = {"\u2013": "-", "\u2014": "-", "\u00b7": "\u00b7"}


def _glyph(ch):
    if ch in FONT:
        return FONT[ch]
    if ch in ALIASES:
        return FONT[ALIASES[ch]]
    return None


def text_w(s, scale, track=0.0, upper=True):
    if not s:
        return 0.0
    return len(s) * (6 * scale + track) - track


def draw_text(x, y, s, scale, color, bold=False, upper=True, track=0.0):
    """Draw text; (x, y) is the top-left of the glyph box. Returns width."""
    cx = float(x)
    bdx = max(1, int(round(scale * 0.5))) if bold else 0
    for ch in s:
        gch = ch.upper() if (upper and ch.islower()) else ch
        g = _glyph(gch)
        if g is None:
            if ch not in MISSING and ch != " ":
                MISSING.append(ch)
        elif ch != " ":
            for r in range(7):
                row = g[r]
                for col in range(5):
                    if row[col] == "1":
                        x0 = int(round(cx + col * scale))
                        x1 = int(round(cx + (col + 1) * scale))
                        y0 = int(round(y + r * scale))
                        y1 = int(round(y + (r + 1) * scale))
                        if x1 > x0 and y1 > y0:
                            rect(x0, y0, x1, y1, color)
                            if bdx:
                                rect(x0 + bdx, y0, x1 + bdx, y1, color)
        cx += 6 * scale + track
    return cx - x - track if s else 0.0


def draw_centered(cx, y, s, scale, color, bold=False, upper=True, track=0.0):
    w = text_w(s, scale, track, upper)
    draw_text(int(round(cx - w / 2)), y, s, scale, color, bold, upper, track)
    return w


def wrap_words(s, maxw, scale, track=0.0, upper=True):
    """Greedy word wrap; returns a list of lines (strings)."""
    lines, cur = [], ""
    for word in s.split(" "):
        trial = word if not cur else cur + " " + word
        if text_w(trial, scale, track, upper) <= maxw or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


# ---------------------------------------------------------------- serif display type (v6)
# Times-style serif for the masthead date and the 3 big-card titles
# only — the hierarchy the top-5 entries share (giant serif date,
# bold serif lead titles, readable even at thumbnail size). The
# glyphs are the 7x10 table from the round-7/18 serif system (only
# the letters/digits/punctuation the date and the 3 big titles use),
# serifized with 1-cell feet on straight stems and rendered with
# 3x supersampling so edges stay smooth. Everything else keeps the
# sharp 5x7 bitmap font.
_SERIF_SRC = """
A
...#...
..#.#..
..#.#..
.#...#.
.#...#.
.#...#.
#######
.#...#.
#.....#
#.....#

B
######.
#.....#
#.....#
#.....#
######.
#.....#
#.....#
#.....#
#.....#
######.

C
..####.
.#....#
#......
#......
#......
#......
#......
.#.....
.#....#
..####.

D
#####..
#....#.
#.....#
#.....#
#.....#
#.....#
#.....#
#.....#
#....#.
#####..

E
#######
#......
#......
#......
#####..
#......
#......
#......
#......
#######

F
#######
#......
#......
#......
#####..
#......
#......
#......
#......
#......

G
..####.
.#....#
#......
#......
#......
#...###
#.....#
#.....#
.#....#
..####.

H
#.....#
#.....#
#.....#
#.....#
#.....#
#######
#.....#
#.....#
#.....#
#.....#

I
.#####.
...#...
...#...
...#...
...#...
...#...
...#...
...#...
...#...
.#####.

K
#....#.
#...#..
#..#...
#.#....
##.....
#.#....
#..#...
#...#..
#....#.
#.....#

L
#......
#......
#......
#......
#......
#......
#......
#......
#......
#######

M
#.....#
##...##
#.#.#.#
#.#.#.#
#..#..#
#.....#
#.....#
#.....#
#.....#
#.....#

N
#.....#
##....#
#.#...#
#..#..#
#...#.#
#....##
#.....#
#.....#
#.....#
#.....#

O
..###..
.#...#.
#.....#
#.....#
#.....#
#.....#
#.....#
#.....#
.#...#.
..###..

P
######.
#.....#
#.....#
#.....#
######.
#......
#......
#......
#......
#......

R
######.
#.....#
#.....#
#.....#
######.
#.#....
#..#...
#...#..
#....#.
#.....#

S
.#####.
#.....#
#......
#......
.####..
.....#.
......#
#.....#
#.....#
.#####.

T
#######
...#...
...#...
...#...
...#...
...#...
...#...
...#...
...#...
...#...

U
#.....#
#.....#
#.....#
#.....#
#.....#
#.....#
#.....#
#.....#
.#...#.
..###..

V
#.....#
#.....#
#.....#
#.....#
#.....#
#.....#
.#...#.
.#...#.
..#.#..
...#...

Y
#.....#
#.....#
.#...#.
..#.#..
...#...
...#...
...#...
...#...
...#...
...#...

0
..###..
.#...#.
#.....#
#.....#
#.....#
#.....#
#.....#
#.....#
.#...#.
..###..

1
...#...
..##...
...#...
...#...
...#...
...#...
...#...
...#...
...#...
.#####.

2
.####..
#....#.
.....#.
....#..
...#...
..#....
.#.....
#......
#......
#######

3
.####..
#....#.
.....#.
.....#.
..###..
.....#.
.....#.
#....#.
#....#.
.####..

6
..###..
.#.....
#......
#......
#####..
#....#.
#....#.
#....#.
.#...#.
..###..

,
.......
.......
.......
.......
.......
.......
.......
..##...
..##...
.#.....

SPACE
.......
.......
.......
.......
.......
.......
.......
.......
.......
.......
"""


def _parse_serif(src):
    out = {}
    for block in src.strip().split("\n\n"):
        lines = block.split("\n")
        if len(lines) < 11:
            continue
        key = lines[0]
        if key == "SPACE":
            key = " "
        rows = [(r + ".......")[:7] for r in lines[1:11]]
        out[key] = tuple(rows)
    return out


def _serifize(rows):
    # Times-style feet: on the top and bottom rows, extend the ink
    # of a straight vertical stem sideways (only where the next row
    # keeps ink in that column, i.e. a real stem, so round letters
    # like O/C/S keep their curves). Feet are 1 cell each side.
    g = [list(r) for r in rows]
    for r in (0, 9):
        step = 1 if r == 0 else -1
        for c in range(7):
            if g[r][c] != "#":
                continue
            if g[r + step][c] != "#":
                continue
            run = 0
            rr = r
            while 0 <= rr < 10 and g[rr][c] == "#" and run < 3:
                run += 1
                rr += step
            reach = 1
            for d in range(1, reach + 1):
                for cc in (c - d, c + d):
                    if 0 <= cc < 7 and g[r][cc] == ".":
                        g[r][cc] = "#"
    return tuple("".join(r) for r in g)


_SERIF_SANS = _parse_serif(_SERIF_SRC)
SERIF = {k: (_serifize(v) if (("A" <= k <= "Z") or ("0" <= k <= "9"))
                else v)
         for k, v in _SERIF_SANS.items()}

AA_SS = 3  # supersampling factor for smooth (anti-aliased) serif text


def _fallback_serif_glyph(ch):
    # Anything the serif table lacks: stretch the 5x7 glyph into
    # the 7x10 grid (rows and columns nearest-neighbour mapped).
    old = FONT.get(ch)
    if old is None:
        if ch not in MISSING and ch != " ":
            MISSING.append(ch)
        return tuple("......." for _ in range(10))
    rows = []
    for r in range(10):
        orow = old[min(6, r * 7 // 10)]
        rows.append("".join("#" if orow[min(4, c * 5 // 7)] == "1"
                            else "." for c in range(7)))
    return tuple(rows)


def _blit_cov(x, y, gw, gh, cov, c):
    for oy in range(gh):
        yy = y + oy
        if yy < 0 or yy >= H:
            continue
        base = oy * gw
        for ox in range(gw):
            a = cov[base + ox]
            if not a:
                continue
            xx = x + ox
            if xx < 0 or xx >= W:
                continue
            i = (yy * W + xx) * 3
            ia = 255 - a
            buf[i] = (c[0] * a + buf[i] * ia) // 255
            buf[i + 1] = (c[1] * a + buf[i + 1] * ia) // 255
            buf[i + 2] = (c[2] * a + buf[i + 2] * ia) // 255


_SERIF_COV_CACHE = {}


def _serif_cov(ch, unit, bold):
    key = (ch, unit, bold)
    hit = _SERIF_COV_CACHE.get(key)
    if hit is not None:
        return hit
    gl = SERIF.get(ch) or _fallback_serif_glyph(ch)
    # bold 1 (True): one extra 1 px right shift (v6 date/titles).
    # bold 2: two extra shifts — strokes 2 px thicker (v6r2 masthead
    # date, Sari: "ditebelin"). The glyph box grows by the same amount
    # so neighbouring glyphs never overlap.
    gw = int(round(7 * unit)) + (2 if bold == 2 else 1 if bold else 0)
    gh = int(round(10 * unit))
    hw, hh = gw * AA_SS, gh * AA_SS
    sbuf = bytearray(hw * hh)
    shifts = (0, AA_SS, 2 * AA_SS) if bold == 2 else (0, AA_SS) if bold else (0,)
    for r in range(10):
        row = gl[r]
        for col in range(7):
            if row[col] != "#":
                continue
            for sh in shifts:
                x0 = int(round(col * unit * AA_SS)) + sh
                y0 = int(round(r * unit * AA_SS))
                x1 = int(round((col + 1) * unit * AA_SS)) + sh
                y1 = int(round((r + 1) * unit * AA_SS))
                for yy in range(max(0, y0), min(hh, y1)):
                    base = yy * hw
                    for xx in range(max(0, x0), min(hw, x1)):
                        sbuf[base + xx] = 1
    cov = bytearray(gw * gh)
    for oy in range(gh):
        for ox in range(gw):
            s = 0
            for dy in range(AA_SS):
                by = oy * AA_SS + dy
                if by >= hh:
                    break
                base = by * hw
                for dx in range(AA_SS):
                    bx = ox * AA_SS + dx
                    if bx < hw:
                        s += sbuf[base + bx]
            cov[oy * gw + ox] = (s * 255) // (AA_SS * AA_SS)
    res = (gw, gh, cov)
    _SERIF_COV_CACHE[key] = res
    return res


def serif_w(s, unit, bold=False, track=1.0):
    if not s:
        return 0.0
    w = 0.0
    for ch in s:
        gw, _, _ = _serif_cov(ch, unit, bold)
        w += gw + track
    return w - track


def serif_draw(x, y, s, unit, c, bold=False, track=1.0):
    cx = float(x)
    iy = int(round(y))
    for ch in s:
        gw, gh, cov = _serif_cov(ch, unit, bold)
        _blit_cov(int(round(cx)), iy, gw, gh, cov, c)
        cx += gw + track
    return serif_w(s, unit, bold=bold, track=track)


def serif_draw_centered(cx, y, s, unit, c, bold=False, track=1.0):
    w = serif_w(s, unit, bold=bold, track=track)
    serif_draw(int(round(cx - w / 2)), y, s, unit, c, bold=bold, track=track)
    return w


# ---------------------------------------------------------------- PNG out
def write_png(path):
    raw = bytearray()
    for y in range(H):
        raw.append(0)
        raw += buf[y * W * 3:(y + 1) * W * 3]
    comp = zlib.compress(bytes(raw), 6)

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    data = b"\x89PNG\r\n\x1a\n"
    data += chunk(b"IHDR", ihdr)
    data += chunk(b"IDAT", comp)
    data += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(data)
    return len(data)


# ---------------------------------------------------------------- content
# 11 pictured cards.  title: 1 line (big) / 2 lines (small), ALL CAPS bold.
# sub: 2 lines, ALL CAPS, NOT bold, coloured per region (list style).
# strip: header strip text.  region: colour key.
CARDS = [
    dict(n=1, region="EUROPE", strip="1 \u00b7 EUROPE \u00b7 ANTALYA",
         title=["COP31 COLLAPSES, NO DEAL"],
         sub=["NO DEAL ADOPTED; FOSSIL", "FUELS LEFT OUT."]),
    dict(n=2, region="EUROPE", strip="2 \u00b7 EUROPE \u00b7 GULF OF FINLAND",
         title=["SHIP BURNING OFF FINLAND"],
         sub=["RUSSIAN SHIP ABLAZE AFTER", "DRONE STRIKE."]),
    dict(n=3, region="MIDDLE EAST", strip="3 \u00b7 MIDDLE EAST \u00b7 BAHRAIN",
         title=["BAHRAIN SEEKS UN ACTION"],
         sub=["TEHRAN HIT US BASES;", "TANKERS STRUCK."]),
    dict(n=4, region="EUROPE", strip="4 \u00b7 EUROPE", status="CLAIM",
         title=["DRONE FLATTENS", "KYIV FLATS"],
         sub=["14 FEARED TRAPPED;", "186 DRONES LAUNCHED."]),
    dict(n=5, region="MIDDLE EAST", strip="5 \u00b7 MIDDLE EAST", status="CLAIM",
         title=["SUNDAY STRIKES", "KILL TWO"],
         sub=["AL-MAWASI HIT; RAIN", "FLOODS 70,000 TENTS."]),
    dict(n=6, region="ASIA", strip="6 \u00b7 ASIA",
         title=["HONG KONG VOTES,", "TURNOUT 97%"],
         sub=["856 CANDIDATES CHASE", "723 COMMITTEE SEATS."]),
    dict(n=7, region="ASIA", strip="7 \u00b7 ASIA",
         title=["MINISTER QUITS", "OVER AI"],
         sub=["EXAM CHAOS DAYS", "BEFORE THE SUNEUNG."]),
    dict(n=8, region="AMERICAS", strip="8 \u00b7 AMERICAS",
         title=["VERSTAPPEN WINS", "IN LAS VEGAS"],
         sub=["3RD VEGAS WIN; NORRIS", "2ND, PIASTRI 3RD."]),
    dict(n=9, region="OCEANIA", strip="9 \u00b7 OCEANIA",
         title=["INDIA 720/9", "IN WELLINGTON"],
         sub=["RECORD TOTAL IN NZ;", "PANT 128, RAHUL 136."]),
    dict(n=10, region="AMERICAS", strip="10 \u00b7 AMERICAS",
         title=["RECORD FLOOD", "IN FLORIDA"],
         sub=["ST JOHNS TOPS 1953;", "CREST DUE SUN."]),
    dict(n=11, region="MIDDLE EAST", strip="11 \u00b7 MIDDLE EAST",
         title=["HAMAS SEEKS", "EMERGENCY TALKS"],
         sub=["MEDIATORS PRESSED;", "AID-VEHICLE STRIKE."]),
]

# 24 list stories.  Region colours follow the approved design exactly
# (Basra and Brussels are coloured ASIA there, which is what makes the
# header counts EUROPE 10 / MIDDLE EAST 8 / ASIA 6 add up).
LIST = [
    (12, "DENMARK", "EXPELS RUSSIAN ATTACHE OVER 'ASSASSINATION PLOT'", "FRI", "EUROPE"),
    (13, "LONDON", "MAY TELLS PM BURNHAM: 'BREXIT IS DONE, MOVE ON'", "SUN", "EUROPE"),
    (14, "UKRAINE", "186 DRONES LAUNCHED OVERNIGHT; 161 SHOT DOWN", "SUN", "EUROPE"),
    (15, "KYIV", "ZELENSKYY SEEKS LOCAL CEASEFIRES TO FREE 15 VILLAGES", "SAT", "EUROPE"),
    (16, "GAZA", "RAIN FLOODS 70,000 TENTS; PROTESTS OVER DEMOLITIONS", "SUN", "MIDDLE EAST"),
    (17, "WEST BANK", "SETTLER ATTACKS RISE IN OLIVE HARVEST", "SAT", "MIDDLE EAST"),
    (18, "JERUSALEM", "EISENKOT INVITES LIKUD TO UNITY TALKS FROM SUNDAY", "SUN", "MIDDLE EAST"),
    (19, "LEBANON", "AOUN: ISRAEL MUST QUIT 'EVERY INCH' OF LAND", "SAT", "MIDDLE EAST"),
    (20, "MANIPUR", "TOXIC ALCOHOL KILLS 11; 180+ IN HOSPITAL", "SAT", "ASIA"),
    (21, "BASRA", "FIRE AT HARTHA POWER STATION KILLS 4; INJURES 35", "SAT", "ASIA"),
    (22, "NEW DELHI", "NEPAL PM LANDS; SEEKS $2BN; MEETS MODI MONDAY", "SUN", "ASIA"),
    (23, "GENEVA", "UN STATES AGREE 2-YEAR PATH ON 'KILLER ROBOTS'", "SAT", "WORLD"),
    (24, "NIGERIA", "BOAT TOLL RISES TO 24 AFTER FUNERAL-TRIP CAPSIZE", "FRI", "AFRICA"),
    (25, "SOUTH AFRICA", "FLAGS AT HALF-MAST FOR MLAMBO-NGCUKA", "SUN", "AFRICA"),
    (26, "MEXICO", "'EL CHAPO ISIDRO' CAPTURED; 11 KILLED IN RAID", "FRI", "AMERICAS"),
    (27, "BRAZIL", "BOLSONARO IN INTENSIVE CARE AFTER BOWEL BLOCKAGE", "FRI", "AMERICAS"),
    (28, "WASHINGTON", "FBI CRIME DATABASE HACKED; TRUMP: 'NOT GOOD'", "FRI", "AMERICAS"),
    (29, "BRUSSELS", "EU AND INDONESIA SIGN TRADE DEAL AFTER 10 YEARS", "SAT", "ASIA"),
    (30, "OIL", "BRENT $92.57 AFTER HORMUZ TANKER FIRE", "FRI", "WORLD"),
    (31, "RIYADH", "SAUDI JETS HIT HOUTHI TARGETS AFTER MISSILE ALERTS", "SAT", "MIDDLE EAST"),
    (32, "MELBOURNE", "AUSTRALIA EDGE ENGLAND BY 3 WICKETS IN T20", "SAT", "OCEANIA"),
    (33, "ENGLAND", "LEEDS STUN CHELSEA 4-1; ARSENAL HELD 2-2", "SAT", "EUROPE"),
    (34, "LIVERPOOL", "LIVERPOOL ROUT MAN UTD 4-0 IN POCHETTINO DEBUT", "SUN", "EUROPE"),
    (35, "TURIN", "ALCARAZ BEATS ZVEREV 6-2, 7-6(7) FOR ATP TITLE", "SUN", "EUROPE"),
]

UTC_ENTRIES = [
    ("01:00", "HONG KONG VOTES"),
    ("04:00", "VERSTAPPEN WINS F1"),
    ("08:00", "COP31 PLENARY"),
    ("16:30", "LIVERPOOL V MAN UTD"),
    ("17:00", "ATP FINAL"),
]

REGIONS_STRIP = [("EUROPE", 10), ("MIDDLE EAST", 8), ("ASIA", 6),
                 ("AMERICAS", 5), ("AFRICA", 2), ("OCEANIA", 2), ("WORLD", 2)]

RINGKASAN = [("35", "STORIES"), ("186", "DRONES LAUNCHED"),
             ("97%", "HONG KONG TURNOUT"), ("720/9", "INDIA TEST TOTAL"),
             ("14", "FEARED TRAPPED IN DYMER"), ("70,000", "TENTS FLOODED")]

# ---------------------------------------------------------------- header
def draw_header():
    rect(0, 0, W, 28, NAVY)
    draw_text(24, 5, "THE WORLD IN ONE DAY", 2.4, GOLD, bold=True, track=2.6)
    s = "35 STORIES \u00b7 7 REGIONS \u00b7 EVERY ONE DATED SUNDAY, 22 NOVEMBER 2026"
    w = text_w(s, 1.15, 0.5)
    draw_text(int(round(1000 - w)), 14, s, 1.15, (205, 210, 215), track=0.5)
    # v6: masthead date in bold serif (top-5 hierarchy) — 40 px tall,
    # still giant and exactly centred (serif_draw_centered).
    # v6r2 (Sari): thicker + wider tracking — bold 2 (strokes 2 px
    # thicker) and track 3.0. Width 789 px, still one line, centred.
    serif_draw_centered(512, 33, "SUNDAY, 22 NOVEMBER 2026", 4.0, INK,
                        bold=2, track=3.0)
    draw_centered(512, 77,
                  "COP31 COLLAPSES WITH NO DEAL \u00b7 SPARTA II STILL BURNING "
                  "\u00b7 BAHRAIN SEEKS UN ACTION ON IRAN",
                  1.4, RED, bold=True, track=0.85)
    rect(24, 91, 1000, 94, INK)
    # v6: the 6 number columns become a DARK BAND (top-5 anchor:
    # "THE DAY IN NUMBERS" / big-number rows) — dark navy, never
    # pure black, with big bright numbers and small gold labels.
    # Same 6 numbers, same columns; band y 96..146 sits between the
    # masthead rule and the region strip.
    rect(24, 96, 1000, 146, NAVY)
    colw2 = (1000 - 24) / 6.0
    for i, (num, lab) in enumerate(RINGKASAN):
        cx = 24 + colw2 * (i + 0.5)
        draw_centered(cx, 104, num, 2.2, PAPER, bold=True, track=1.0)
        draw_centered(cx, 130, lab, 1.1, GOLD, bold=True, track=0.5)
        if i:
            vline(int(round(24 + colw2 * i)), 100, 142, UTC_DIV)
    # region strip: 7 equal colour blocks
    # Round 30: moved up 10 px (gap below the numbers row tightened).
    x = 24
    bw = (1000 - 24) / 7.0
    for i, (name, cnt) in enumerate(REGIONS_STRIP):
        x0 = int(round(24 + bw * i))
        x1 = int(round(24 + bw * (i + 1)))
        rect(x0, 147, x1, 163, REGION[name])
        draw_centered((x0 + x1) / 2, 150, "%s %d" % (name, cnt), 1.4,
                      WHITE, bold=True, track=1.0)
    # UTC strip (open: no dark block, dark text on cream paper).
    # Round 26: thin navy box frame around the strip (border only, no
    # fill — Sari asked the UTC strip not to be blocked) and colour on
    # the text only: times red bold, descriptions navy.
    # Round 27: a full-width red label bar was added at the top edge
    # of the box. Round 28: that bar COLLIDED with the red times
    # ("08:00" was struck through by the label), so the bar was moved
    # outside the box as a separate strip above it — but Sari said
    # "bukan gitu".
    # Round 29 (Sari): the full-width red strip is GONE. The label
    # "THE DAY IN UTC" is back at the LEFT edge inside the box,
    # wrapped in a small red box exactly around the text (white bold
    # text, small padding — only as wide as the text, not the whole
    # box). The box is back at y 175-213 (round 26 position), so the
    # cards and list below also return to their round-26 geometry
    # (big cards y 219 h 200, small cards y 425/571 h 140, list
    # pitch 13). Times and descriptions are plain BLACK (INK) —
    # no red, no navy.
    # Round 30 (Sari): the outer box frame is GONE — the strip sits
    # frameless on the cream paper. The label is now a RED BLOCK as
    # tall as the strip (y 165-203, after the gap tightening) at the
    # left edge, with generous side padding (18 px, NOT tight around
    # the text) and the label text WHITE bold CENTRED in it (both
    # ways). Correction from Sari: the label text is NOT enlarged —
    # it stays SMALL (scale 1.3, as before); only the block is tall.
    # Times and descriptions stay plain BLACK (INK), centred in
    # their own columns, starting after the label block with a 20 px
    # gap so nothing crowds the label.
    # Gap tightening (Sari, round 30): the gap below the numbers row
    # was too loose, squeezing the bottom — region strip and UTC
    # strip moved up 10 px; the space goes to the cards (big +4,
    # small +1 each row) and the list (pitch 13 -> 13.5). The numbers
    # row itself is UNCHANGED in size (Sari's clarification) — only
    # the gap below it is tighter.
    lab = "THE DAY IN UTC"
    lab_sc = 1.3
    lw = int(round(text_w(lab, lab_sc, 1.0, True)))
    lab_x1 = 24 + lw + 36
    rect(24, 166, lab_x1, 216, RED)
    draw_text(42, 187, lab, lab_sc, WHITE, bold=True, track=1.0)
    col0 = lab_x1 + 20
    colw = (1000 - col0) / 5.0
    for i, (t, d) in enumerate(UTC_ENTRIES):
        cx = col0 + colw * (i + 0.5)
        if i:
            vline(int(round(col0 + colw * i)), 172, 210, UTC_DIV)
        draw_centered(cx, 178, t, 2.0, INK, bold=True, track=1.5)
        draw_centered(cx, 202, d, 1.35, INK, track=0.5)


# ---------------------------------------------------------------- cards
def draw_badge(x, y, n):
    """Red numbered disc at the scene's top-left corner."""
    circle(x, y, 11, (200, 40, 40))
    ring(x, y, 11, 1, (200, 40, 40))
    draw_centered(x, y - 4, str(n), 1.0, WHITE, bold=True)


def draw_card(card, x, y, w, h, scene_h, big):
    rc = REGION[card["region"]]
    rect(x, y, x + w, y + h, CARD)
    rect(x, y, x + w, y + 1, NAVY)
    rect(x, y + h - 1, x + w, y + h, NAVY)
    rect(x, y, x + 1, y + h, NAVY)
    rect(x + w - 1, y, x + w, y + h, NAVY)
    # header strip
    rect(x + 1, y + 1, x + w - 1, y + 17, rc)
    draw_text(x + 12, y + 5, card["strip"], 1.4, WHITE, bold=True, track=1.0)
    # scene
    sx, sy = x + 1, y + 17
    set_clip(sx, sy, sx + w - 2, sy + scene_h)
    SCENES[card["n"]](sx, sy, w - 2, scene_h)
    reset_clip()
    draw_badge(x + 14, sy + 13, card["n"])
    # v6: the pill names the story's certainty (top-5 labels).
    # CONFIRMED for verified/official stories; CLAIM (amber) for
    # reported-but-unverified figures — card 4 "14 feared trapped"
    # (an estimate, rescue ongoing) and card 5 Gaza toll (a single
    # secondary source; the refresh notes flag it provisional).
    # Bottom-right of the scene, as decided in round 24.
    ptxt = card.get("status", "CONFIRMED")
    pcol = (22, 96, 54) if ptxt == "CONFIRMED" else (150, 98, 12)
    # Round 25: pill text 0.85 -> 1.0 (fractional cells dropped strokes,
    # so "CONFIRMED" read as "CON IRMED" at preview); pill widened
    # to fit and height 11 -> 12.
    pw = int(round(text_w(ptxt, 1.0, 0.4, True))) + 10
    ph = 12
    px1 = sx + (w - 2) - 5 - pw
    py1 = sy + scene_h - 5 - ph
    rect(px1, py1, px1 + pw, py1 + ph, pcol)
    rect(px1, py1, px1 + pw, py1 + 1, WHITE)
    rect(px1, py1 + ph - 1, px1 + pw, py1 + ph, WHITE)
    rect(px1, py1, px1 + 1, py1 + ph, WHITE)
    rect(px1 + pw - 1, py1, px1 + pw, py1 + ph, WHITE)
    draw_text(px1 + 5, py1 + 2, ptxt, 1.0, WHITE, bold=True, track=0.4)
    # rule + text zone
    ry = sy + scene_h + 3
    hline(x + 12, x + w - 12, ry, RULE)
    if big:
        ty = ry + 8
        # v6: big-card titles in bold serif (top-5 hierarchy) — 15 px
        # tall at unit 1.5, still one line (longest title 294 px of
        # the 296 px text zone, track 0.8).
        serif_draw(x + 12, ty, card["title"][0], 1.5, INK, bold=True, track=0.8)
        sy2 = ty + 18
        for j, ln in enumerate(card["sub"]):
            draw_text(x + 12, sy2 + j * 16, ln, 1.7, rc, track=1.3)
    else:
        ty = ry + 6
        for j, ln in enumerate(card["title"]):
            draw_text(x + 12, ty + j * 15, ln, 1.75, INK, bold=True, track=1.5)
        sy2 = ty + 31
        for j, ln in enumerate(card["sub"]):
            draw_text(x + 12, sy2 + j * 13, ln, 1.45, rc, track=1.3)


def draw_cards():
    # 3 big cards, row 1 (round 31: the UTC block grew to y 216, so
    # cards start y 222; h 204 -> 196, scene 124 -> 116 — the text
    # zone needs 17+116+3+8+18+32 = 194, so 196 still fits)
    for i, card in enumerate(CARDS[:3]):
        draw_card(card, 24 + i * 328, 222, 320, 196, 116, True)
    # 8 small cards, 2 rows x 4 (h 141, scene 59 — unchanged; row
    # pitch 147 -> 144, rows y 422 / 566, last row ends y 707)
    for r in range(2):
        for c in range(4):
            card = CARDS[3 + r * 4 + c]
            draw_card(card, 24 + c * 245, 422 + r * 144, 241, 141, 59, False)


# ---------------------------------------------------------------- list
def draw_list():
    # Round 31: list moved up 4 px and pitch 14 -> 13 (room taken by
    # the taller numbers row and UTC strip). 13 was the round-29
    # pitch and renders fine.
    # NOTE: pitch must stay an INTEGER — 13.5 put odd rows on half
    # pixels and the rasteriser dropped glyph row 0 on those rows,
    # slicing the list text in half.
    # v6r2 (Sari: "listnya pasin jangan ada kosong dibawah"): pitch
    # 13 -> 14, rows start y 738, font scale 1.0 -> 1.1. Last row
    # y 892, ink 894..902 — 5 px above the DATE CHECK box (y 908),
    # both columns ending on the same line. Scale 1.1 verified
    # against the longest row (row 6 ends x ~451, tag starts 471).
    draw_text(24, 711, "ALSO ON SUNDAY, 22 NOVEMBER \u2014 24 MORE STORIES",
              2.15, RED, bold=True, track=1.2)
    hline(24, 1000, 730, RED)
    for col in range(2):
        x0 = 24 if col == 0 else 512
        tag_right = 500 if col == 0 else 1000
        for i in range(12):
            n, place, head, day, region = LIST[col * 12 + i]
            y = 738 + i * 14
            rc = REGION[region]
            x = x0
            x += draw_text(x, y + 2, "%d." % n, 1.1, INK, bold=True)
            x += draw_text(x, y + 2, " " + place + " \u2013 ", 1.1, rc, bold=True)
            draw_text(x, y + 2, head, 1.1, rc)
            tag = "[%s]" % day
            tw = text_w(tag, 1.1, 0.0)
            draw_text(int(round(tag_right - tw)), y + 2, tag, 1.1,
                      DAYCOL[day], bold=True)


# ---------------------------------------------------------------- bottom
def _unit_lines(units, maxw, scale, track):
    """Wrap units (each a list of (text, color, bold) parts that must stay
    on one line); units are joined with ' \u00b7 ' separators."""
    lines, cur, curw = [], [], 0.0
    sepw = text_w(" \u00b7 ", scale, track)
    for parts in units:
        w = sum(text_w(t, scale, track) for t, _, _ in parts)
        if cur and curw + sepw + w > maxw:
            lines.append(cur)
            cur, curw = [parts], w
        else:
            if cur:
                curw += sepw
            cur.append(parts)
            curw += w
    if cur:
        lines.append(cur)
    return lines


def _draw_unit_line(x, y, units, scale, track):
    cx = float(x)
    for k, parts in enumerate(units):
        if k:
            draw_text(int(round(cx)), y, " \u00b7 ", scale, BOXTEXT,
                      track=track)
            cx += text_w(" \u00b7 ", scale, track)
        for t, col, bold in parts:
            draw_text(int(round(cx)), y, t, scale, col, bold=bold,
                      upper=False, track=track)
            cx += text_w(t, scale, track)


def draw_bottom():
    # ---- DATE CHECK box (24..700, 908..1015)
    rect(24, 908, 700, 1015, CARD)
    rect(24, 908, 700, 909, NAVY)
    rect(24, 1014, 700, 1015, NAVY)
    rect(24, 908, 25, 1015, NAVY)
    rect(699, 908, 700, 1015, NAVY)
    rect(24, 908, 31, 1015, CHARCOAL)
    rect(31, 908, 699, 921, RED)
    draw_centered(365, 911, "DATE CHECK", 1.3, WHITE, bold=True, track=1.0)
    stmt = ("Every story here happened or was first reported Sun 22 Nov 2026 "
            "(UTC), to press time 01:00 UTC")
    for j, ln in enumerate(wrap_words(stmt, 652, 1.28, 0.25, upper=False)):
        draw_text(40, 923 + j * 10, ln, 1.28, BOXTEXT, upper=False, track=0.25)
    draw_text(40, 944, "LEFT OUT BECAUSE THEY HAPPENED ON AN EARLIER DAY:",
              1.15, BOXTEXT, bold=True, track=1.0)
    leftout = ["Paris (Sat 21)", "Rutte (Sat 21)", "Kryvyi Rih (Fri 20)",
               "GTA VI (Fri 20)", "US stocks (Fri 20)", "Riemann (Fri 20)"]
    # names dark bold, dates red; each name+date is one unbreakable unit
    units = []
    for name in leftout:
        nm, dt = name.rsplit(" (", 1)
        units.append([(nm + " ", BOXTEXT, True), ("(" + dt, RED, False)])
    for j, ln in enumerate(_unit_lines(units, 652, 1.15, 1.0)):
        _draw_unit_line(40, 954 + j * 10, ln, 1.15, 1.0)
    rect(31, 975, 699, 988, RED)
    draw_centered(365, 978, "HOW WE CHECKED", 1.3, WHITE, bold=True, track=1.0)
    body = ("Every story checked against its event date. Sources: Reuters, AP, "
            "BBC, Al Jazeera, F1.com, Cricbuzz, govt releases.")
    for j, ln in enumerate(wrap_words(body, 652, 1.2, 0.4, upper=False)):
        draw_text(40, 992 + j * 10, ln, 1.2, BOXTEXT, upper=False, track=0.4)
    # ---- map (708..1000, 908..1015)
    draw_map()
    # ---- footer
    # v6: footer carries the pill legend (region counts already live
    # in the region strip above the UTC strip).
    draw_centered(512, 1015,
                  "CONFIRMED = VERIFIED BY SOURCES \u00b7 CLAIM = REPORTED, "
                  "NOT YET VERIFIED \u00b7 SOURCES: REUTERS \u00b7 AP \u00b7 BBC "
                  "\u00b7 AL JAZEERA \u00b7 F1.COM \u00b7 CRICBUZZ",
                  1.1, GREY, track=0.3)


# ---------------------------------------------------------------- map
MAP_X0, MAP_Y0, MAP_X1, MAP_Y1 = 708, 924, 1000, 1015


def _proj(lon, lat):
    x = MAP_X0 + (lon + 170.0) * (MAP_X1 - MAP_X0) / 350.0
    y = MAP_Y0 + (75.0 - lat) * (MAP_Y1 - MAP_Y0) / 130.0
    return int(round(x)), int(round(y))


NA = [(-168, 66), (-158, 58), (-152, 60), (-140, 60), (-135, 58), (-130, 54),
      (-125, 49), (-124, 42), (-120, 34), (-114, 29), (-110, 24), (-105, 20),
      (-97, 16), (-94, 17), (-90, 14), (-86, 12), (-83, 9), (-80, 8),
      (-79, 9), (-81, 13), (-83, 15), (-87, 16), (-88, 18), (-90, 21),
      (-91, 19), (-96, 19), (-97, 26), (-93, 30), (-89, 30), (-84, 30),
      (-81, 26), (-80, 32), (-76, 35), (-74, 40), (-70, 42), (-68, 45),
      (-65, 44), (-60, 47), (-55, 52), (-60, 55), (-65, 58), (-68, 58),
      (-72, 62), (-78, 62), (-85, 66), (-92, 66), (-95, 69), (-110, 68),
      (-125, 70), (-140, 70), (-155, 71), (-165, 68)]
GREENLAND = [(-45, 60), (-40, 65), (-32, 68), (-22, 70), (-20, 74), (-30, 76),
             (-45, 76), (-55, 74), (-58, 70), (-52, 64)]
SA = [(-80, 9), (-77, 4), (-80, -3), (-81, -6), (-77, -12), (-72, -18),
      (-70, -23), (-70, -30), (-72, -37), (-73, -44), (-74, -50), (-70, -54),
      (-66, -55), (-68, -50), (-65, -45), (-62, -41), (-58, -35), (-52, -32),
      (-48, -28), (-41, -23), (-35, -9), (-35, -6), (-40, -3), (-44, -2),
      (-50, 0), (-53, 4), (-58, 6), (-62, 9), (-68, 11), (-72, 12), (-77, 8)]
AFRICA = [(-6, 35), (-10, 31), (-15, 27), (-17, 21), (-17, 15), (-15, 11),
          (-12, 8), (-8, 4), (-4, 5), (0, 6), (6, 4), (9, 4), (9, 0),
          (12, -2), (13, -10), (12, -18), (14, -22), (16, -28), (20, -35),
          (26, -34), (32, -29), (35, -24), (40, -16), (40, -10), (42, -4),
          (46, -1), (51, 2), (51, 11), (46, 11), (43, 12), (40, 15),
          (38, 18), (37, 22), (34, 28), (32, 31), (30, 32), (25, 32),
          (20, 32), (15, 32), (10, 34), (5, 37), (0, 36)]
EURASIA = [(-10, 36), (-9, 38), (-9, 43), (-2, 44), (-1, 46), (-4, 48),
           (-2, 50), (0, 51), (3, 53), (8, 55), (8, 57), (10, 59), (5, 60),
           (5, 62), (12, 65), (18, 69), (25, 71), (30, 70), (35, 68),
           (40, 68), (45, 68), (55, 69), (65, 69), (75, 72), (85, 74),
           (95, 76), (105, 77), (115, 76), (125, 73), (135, 72), (145, 72),
           (155, 70), (162, 66), (170, 66), (178, 65), (178, 62), (170, 60),
           (162, 60), (158, 56), (162, 52), (158, 50), (155, 48), (150, 45),
           (142, 42), (140, 40), (135, 35), (130, 33), (127, 35), (122, 32),
           (120, 28), (115, 23), (110, 20), (108, 18), (105, 10), (103, 7),
           (100, 8), (98, 12), (95, 16), (92, 21), (89, 22), (86, 20),
           (82, 17), (80, 13), (77, 8), (75, 12), (73, 16), (70, 20),
           (66, 25), (62, 25), (58, 26), (56, 27), (54, 26), (52, 26),
           (50, 29), (48, 30), (50, 26), (48, 24), (44, 22), (40, 20),
           (38, 18), (35, 16), (34, 20), (35, 24), (36, 28), (34, 30),
           (32, 31), (30, 33), (27, 34), (22, 36), (18, 38), (14, 38),
           (12, 40), (10, 38), (8, 37), (4, 37), (0, 36), (-5, 36)]
AUSTRALIA = [(113, -22), (114, -30), (115, -35), (120, -34), (124, -33),
             (129, -32), (132, -32), (135, -35), (138, -35), (140, -38),
             (145, -38), (150, -37), (153, -32), (153, -27), (150, -22),
             (146, -19), (142, -15), (142, -11), (137, -12), (135, -15),
             (132, -12), (130, -13), (126, -14), (122, -17), (118, -20)]
UK = [(-5, 50), (-3, 53), (-5, 56), (-3, 58), (-1, 57), (0, 53), (1, 51)]
MADAGASCAR = [(44, -16), (47, -15), (50, -16), (49, -20), (46, -24), (44, -20)]
JAPAN = [(130, 31), (133, 34), (137, 35), (140, 38), (141, 42), (139, 40),
         (136, 36), (132, 33)]
NZ = [(167, -45), (170, -43), (173, -41), (176, -38), (174, -40), (171, -44)]

# (n, lon, lat, region, badge offset dx, dy)
DOTS = [
    (1, 30.7, 36.9, "EUROPE", -27, 31),
    (2, 24.5, 59.9, "EUROPE", -31, 4),
    (3, 50.6, 26.2, "MIDDLE EAST", 41, -20),
    (4, 30.5, 50.5, "EUROPE", -39, 19),
    (5, 34.5, 31.5, "MIDDLE EAST", 31, 24),
    (6, 114.2, 22.3, "ASIA", -29, -10),
    (7, 127.0, 37.5, "ASIA", 8, -9),
    (8, -115.1, 36.2, "AMERICAS", 0, -5),
    (9, 174.8, -41.3, "OCEANIA", -22, -6),
    (10, -81.0, 28.5, "AMERICAS", 0, -5),
    (11, 34.5, 31.5, "MIDDLE EAST", 2, 30),
]


def draw_map():
    rect(708, 908, 1000, 924, NAVY)
    draw_centered(854, 911, "WHERE IT HAPPENED \u2014 DOTS 1-11", 1.4,
                  WHITE, bold=True, track=1.0)
    set_clip(MAP_X0, MAP_Y0, MAP_X1, MAP_Y1)
    rect(MAP_X0, MAP_Y0, MAP_X1, MAP_Y1, SEA)
    for poly_ll in (NA, GREENLAND, SA, AFRICA, EURASIA, AUSTRALIA, UK,
                    MADAGASCAR, JAPAN, NZ):
        poly([_proj(lon, lat) for lon, lat in poly_ll], LAND)
    # leader lines first, then badges on top
    for n, lon, lat, region, dx, dy in DOTS:
        tx, ty = _proj(lon, lat)
        bx, by = tx + dx, ty + dy
        line(tx, ty, bx, by, RED)
    for n, lon, lat, region, dx, dy in DOTS:
        tx, ty = _proj(lon, lat)
        bx, by = tx + dx, ty + dy
        circle(bx, by, 12, WHITE)
        circle(bx, by, 10, REGION[region])
        draw_centered(bx, by - 4, str(n), 1.0, WHITE, bold=True)
    reset_clip()
    rect(MAP_X0, MAP_Y0, MAP_X1, MAP_Y0 + 1, NAVY)
    rect(MAP_X0, MAP_Y1 - 1, MAP_X1, MAP_Y1, NAVY)
    rect(MAP_X0, MAP_Y0, MAP_X0 + 1, MAP_Y1, NAVY)
    rect(MAP_X1 - 1, MAP_Y0, MAP_X1, MAP_Y1, NAVY)


# ---------------------------------------------------------------- scenes
# Every scene draws only inside its own box (the caller clips to it).
# Positions are fractions of the scene box; radii scale with its height,
# so circles stay circles at any card size.


def scene1(x0, y0, w, h):
    """COP31: globe and gavel under a pale sky."""
    X = lambda f: int(round(x0 + f * w))
    Y = lambda f: int(round(y0 + f * h))
    vgrad(x0, y0, x0 + w, y0 + h, (188, 218, 238), (222, 236, 244))
    ellipse(X(0.12), Y(0.12), 0.09 * w, 0.045 * h, WHITE)
    ellipse(X(0.68), Y(0.10), 0.08 * w, 0.04 * h, WHITE)
    ellipse(X(0.86), Y(0.24), 0.05 * w, 0.03 * h, (240, 244, 248))
    circle(X(0.88), Y(0.16), 0.085 * h, (255, 208, 80))
    circle(X(0.88), Y(0.16), 0.06 * h, (255, 222, 120))
    # globe shadow on the sky
    ellipse(X(0.28), Y(0.88), 0.16 * w, 0.035 * h, (150, 165, 180))
    # globe
    gx, gy, gr = X(0.28), Y(0.52), int(0.34 * h)
    circle(gx, gy, gr, (46, 110, 180))
    circle(gx, gy, int(gr * 0.82), (52, 122, 195))
    ellipse(X(0.24), Y(0.40), 0.09 * h, 0.06 * h, (70, 160, 95))
    ellipse(X(0.33), Y(0.62), 0.075 * h, 0.055 * h, (70, 160, 95))
    ellipse(X(0.34), Y(0.58), 0.05 * h, 0.035 * h, (24, 60, 105))
    ellipse(X(0.22), Y(0.36), 0.045 * h, 0.03 * h, (120, 180, 225))
    ellipse(X(0.30), Y(0.50), 0.03 * h, 0.02 * h, (90, 175, 110))
    # gavel: head, handle, base
    rect(X(0.58), Y(0.28), X(0.84), Y(0.42), (122, 84, 40))
    rect(X(0.58), Y(0.28), X(0.62), Y(0.42), (90, 60, 28))
    rect(X(0.80), Y(0.28), X(0.84), Y(0.42), (90, 60, 28))
    rect(X(0.58), Y(0.33), X(0.84), Y(0.37), (140, 100, 52))
    thick_line(X(0.71), Y(0.42), X(0.60), Y(0.82), 4, (122, 84, 40))
    rect(X(0.54), Y(0.82), X(0.80), Y(0.88), (90, 60, 28))
    rect(X(0.54), Y(0.82), X(0.80), Y(0.84), (140, 100, 52))
    ellipse(X(0.67), Y(0.90), 0.13 * w, 0.02 * h, (150, 165, 180))


def scene2(x0, y0, w, h):
    """Sparta II: cargo ship burning off Finland."""
    X = lambda f: int(round(x0 + f * w))
    Y = lambda f: int(round(y0 + f * h))
    vgrad(x0, y0, x0 + w, y0 + int(0.62 * h), (185, 215, 235), (215, 232, 242))
    vgrad(x0, y0 + int(0.62 * h), x0 + w, y0 + h, (38, 90, 140), (24, 60, 105))
    ellipse(X(0.10), Y(0.12), 0.08 * w, 0.04 * h, WHITE)
    ellipse(X(0.76), Y(0.10), 0.07 * w, 0.035 * h, WHITE)
    # smoke puffs above the flames
    for fx, fy, fr, c in ((0.36, 0.16, 0.055, (150, 150, 155)),
                          (0.44, 0.10, 0.075, (140, 140, 148)),
                          (0.30, 0.12, 0.045, (160, 160, 165)),
                          (0.52, 0.14, 0.05, (150, 150, 155))):
        circle(X(fx), Y(fy), fr * h, c)
    # seagulls
    for bx, by in ((0.58, 0.08), (0.68, 0.06), (0.64, 0.14)):
        line(X(bx) - 5, Y(by), X(bx), Y(by) - 3, (60, 70, 85))
        line(X(bx), Y(by) - 3, X(bx) + 5, Y(by), (60, 70, 85))
    # flames above the containers
    for fx, fy, fs in ((0.37, 0.38, 1.0), (0.55, 0.36, 0.85), (0.70, 0.40, 0.7)):
        tri(X(fx) - int(0.035 * h * fs), Y(fy), X(fx) + int(0.035 * h * fs),
            Y(fy), X(fx), Y(fy) - int(0.14 * h * fs), (255, 110, 20))
        tri(X(fx) - int(0.018 * h * fs), Y(fy), X(fx) + int(0.018 * h * fs),
            Y(fy), X(fx), Y(fy) - int(0.08 * h * fs), (255, 200, 60))
    # containers
    rect(X(0.30), Y(0.40), X(0.42), Y(0.55), (210, 90, 40))
    rect(X(0.30), Y(0.40), X(0.42), Y(0.43), (230, 120, 60))
    rect(X(0.44), Y(0.42), X(0.58), Y(0.55), (40, 120, 70))
    rect(X(0.44), Y(0.42), X(0.58), Y(0.45), (60, 150, 90))
    rect(X(0.60), Y(0.44), X(0.70), Y(0.55), (220, 170, 40))
    # hull
    poly([(X(0.18), Y(0.55)), (X(0.84), Y(0.55)), (X(0.78), Y(0.72)),
          (X(0.24), Y(0.72))], (52, 58, 66))
    rect(X(0.20), Y(0.55), X(0.82), Y(0.58), (70, 78, 88))
    # mast + red flag
    line(X(0.80), Y(0.55), X(0.80), Y(0.30), (40, 44, 54))
    tri(X(0.80), Y(0.30), X(0.80), Y(0.38), X(0.88), Y(0.34), (200, 40, 40))
    # hull reflection + wave lines
    rect(X(0.30), Y(0.74), X(0.70), Y(0.78), (30, 70, 110))
    for wy, wx0, wx1 in ((0.82, 0.10, 0.30), (0.86, 0.55, 0.85),
                         (0.90, 0.20, 0.45), (0.94, 0.60, 0.90),
                         (0.80, 0.75, 0.92)):
        hline(X(wx0), X(wx1), Y(wy), (150, 190, 220))
        hline(X(wx0), X(wx1), Y(wy) + 1, (150, 190, 220))


def scene3(x0, y0, w, h):
    """Bahrain night: tanker in the Strait of Hormuz."""
    X = lambda f: int(round(x0 + f * w))
    Y = lambda f: int(round(y0 + f * h))
    vgrad(x0, y0, x0 + w, y0 + int(0.62 * h), (16, 32, 64), (28, 48, 88))
    vgrad(x0, y0 + int(0.62 * h), x0 + w, y0 + h, (24, 84, 146), (18, 60, 110))
    # stars
    for sx, sy in ((0.06, 0.10), (0.14, 0.22), (0.24, 0.08), (0.34, 0.16),
                   (0.48, 0.06), (0.58, 0.20), (0.66, 0.10), (0.76, 0.26),
                   (0.92, 0.06), (0.08, 0.36), (0.30, 0.30), (0.55, 0.34)):
        px(X(sx), Y(sy), WHITE)
        px(X(sx) + 1, Y(sy), (220, 220, 220))
    # crescent moon
    circle(X(0.88), Y(0.18), 0.07 * h, (255, 220, 110))
    circle(X(0.905), Y(0.16), 0.06 * h, (28, 48, 88))
    # deck lamps with beams
    for lx, ly in ((0.38, 0.38), (0.62, 0.36)):
        line(X(lx), Y(ly), X(lx - 0.06), Y(0.55), (255, 220, 110))
        line(X(lx), Y(ly), X(lx + 0.06), Y(0.55), (255, 220, 110))
        circle(X(lx), Y(ly), 0.035 * h, (255, 230, 130))
        circle(X(lx), Y(ly), 0.02 * h, (255, 245, 180))
    # tanker hull + deck
    rect(X(0.15), Y(0.55), X(0.75), Y(0.68), (40, 44, 54))
    rect(X(0.15), Y(0.55), X(0.75), Y(0.58), (70, 78, 90))
    rect(X(0.70), Y(0.48), X(0.78), Y(0.55), (60, 66, 76))
    tri(X(0.42), Y(0.55), X(0.48), Y(0.55), X(0.45), Y(0.44), (210, 90, 40))
    # horizon lights (far shore)
    for hx in (0.06, 0.09, 0.12):
        circle(X(hx), Y(0.58), 2, (255, 210, 90))
    # green buoy + moonlight shimmer
    circle(X(0.88), Y(0.62), 0.07 * h, (70, 160, 95))
    ellipse(X(0.865), Y(0.60), 0.03 * h, 0.02 * h, (140, 210, 160))
    circle(X(0.95), Y(0.64), 2, (255, 210, 90))
    for sy, sx0, sx1 in ((0.74, 0.80, 0.95), (0.80, 0.84, 0.93),
                         (0.86, 0.86, 0.92), (0.72, 0.20, 0.35)):
        hline(X(sx0), X(sx1), Y(sy), (255, 220, 110))
    for wy, wx0, wx1 in ((0.84, 0.08, 0.30), (0.90, 0.40, 0.70),
                         (0.94, 0.10, 0.45)):
        hline(X(wx0), X(wx1), Y(wy), (120, 170, 205))


def scene4(x0, y0, w, h):
    """Dymer: drone-flattened Kyiv flat, rescue under way."""
    X = lambda f: int(round(x0 + f * w))
    Y = lambda f: int(round(y0 + f * h))
    vgrad(x0, y0, x0 + w, y0 + h, (96, 124, 158), (150, 165, 190))
    ellipse(X(0.55), Y(0.10), 0.10 * w, 0.05 * h, (200, 205, 210))
    ellipse(X(0.80), Y(0.06), 0.07 * w, 0.035 * h, (210, 214, 218))
    # damaged apartment block
    rect(X(0.08), Y(0.15), X(0.34), Y(0.72), (88, 98, 116))
    poly([(X(0.24), Y(0.15)), (X(0.34), Y(0.15)), (X(0.34), Y(0.30)),
          (X(0.29), Y(0.24)), (X(0.26), Y(0.30))], (60, 68, 84))
    # windows: some lit warm, some dark
    for r in range(3):
        for c in range(3):
            wx, wy = X(0.11 + c * 0.08), Y(0.22 + r * 0.15)
            col = (255, 196, 90) if (r + c) % 3 == 0 else (30, 35, 45)
            rect(wx, wy, wx + int(0.04 * w), wy + int(0.08 * h), col)
    # crack down the facade
    line(X(0.20), Y(0.15), X(0.22), Y(0.30), (40, 44, 54))
    line(X(0.22), Y(0.30), X(0.19), Y(0.45), (40, 44, 54))
    line(X(0.19), Y(0.45), X(0.22), Y(0.60), (40, 44, 54))
    # smoke + dust
    for fx, fy, fr, c in ((0.52, 0.18, 0.06, (120, 125, 135)),
                          (0.60, 0.12, 0.05, (135, 140, 148)),
                          (0.46, 0.28, 0.045, (150, 155, 162))):
        circle(X(fx), Y(fy), fr * h, c)
    ellipse(X(0.50), Y(0.66), 0.06 * w, 0.04 * h, (170, 172, 175))
    ellipse(X(0.68), Y(0.70), 0.05 * w, 0.035 * h, (165, 168, 172))
    # rubble slabs
    poly([(X(0.42), Y(0.72)), (X(0.58), Y(0.66)), (X(0.62), Y(0.74)),
          (X(0.46), Y(0.80))], (120, 125, 135))
    poly([(X(0.60), Y(0.74)), (X(0.74), Y(0.70)), (X(0.76), Y(0.78)),
          (X(0.62), Y(0.82))], (105, 110, 120))
    rect(X(0.44), Y(0.80), X(0.56), Y(0.86), (135, 140, 148))
    # bent rebar sticking out of the slabs
    line(X(0.50), Y(0.68), X(0.54), Y(0.52), (60, 60, 66))
    line(X(0.54), Y(0.52), X(0.50), Y(0.44), (60, 60, 66))
    line(X(0.66), Y(0.72), X(0.70), Y(0.58), (60, 60, 66))
    line(X(0.70), Y(0.58), X(0.67), Y(0.50), (60, 60, 66))
    # two flames in the rubble
    for fx, fy, fs in ((0.56, 0.68, 1.0), (0.72, 0.72, 0.7)):
        tri(X(fx) - int(0.02 * h * fs), Y(fy), X(fx) + int(0.02 * h * fs),
            Y(fy), X(fx), Y(fy) - int(0.10 * h * fs), (255, 110, 20))
        tri(X(fx) - int(0.01 * h * fs), Y(fy), X(fx) + int(0.01 * h * fs),
            Y(fy), X(fx), Y(fy) - int(0.06 * h * fs), (255, 200, 60))
    # ground band
    rect(x0, Y(0.86), x0 + w, y0 + h, (70, 78, 90))
    # rescue worker 1 (right, by the slabs)
    _worker(X(0.82), Y(0.52), h, 1.0)
    # rescue worker 2 (left, by the block)
    _worker(X(0.38), Y(0.58), h, 0.85)


def _worker(cx, cy, h, s):
    """Small rescue worker: yellow helmet, orange vest, dark legs."""
    r = int(0.05 * h * s)
    circle(cx, cy, r, (255, 200, 40))
    rect(cx - r, cy + r // 2, cx + r, cy + r, (255, 200, 40))
    circle(cx, cy + int(0.10 * h * s), int(0.035 * h * s), (210, 170, 130))
    rect(cx - int(0.045 * h * s), cy + int(0.13 * h * s),
         cx + int(0.045 * h * s), cy + int(0.30 * h * s), (230, 110, 30))
    rect(cx - int(0.045 * h * s), cy + int(0.19 * h * s),
         cx + int(0.045 * h * s), cy + int(0.22 * h * s), (255, 220, 80))
    line(cx - int(0.02 * h * s), cy + int(0.30 * h * s),
         cx - int(0.03 * h * s), cy + int(0.42 * h * s), (40, 44, 54))
    line(cx + int(0.02 * h * s), cy + int(0.30 * h * s),
         cx + int(0.03 * h * s), cy + int(0.42 * h * s), (40, 44, 54))


def scene5(x0, y0, w, h):
    """Gaza: rain floods the tents at Al-Mawasi."""
    X = lambda f: int(round(x0 + f * w))
    Y = lambda f: int(round(y0 + f * h))
    vgrad(x0, y0, x0 + w, y0 + int(0.42 * h), (96, 128, 172), (150, 170, 200))
    rect(x0, y0, x0 + w, Y(0.22), (70, 95, 140))
    # two storm clouds
    ellipse(X(0.18), Y(0.08), 0.12 * w, 0.05 * h, (60, 70, 90))
    ellipse(X(0.72), Y(0.05), 0.11 * w, 0.045 * h, (60, 70, 90))
    ellipse(X(0.30), Y(0.12), 0.09 * w, 0.04 * h, (90, 100, 120))
    # rain, diagonal
    for rx in range(6, 100, 7):
        line(X(rx / 100.0), Y(0.16), X(rx / 100.0 - 0.02), Y(0.40),
             (120, 160, 210))
    # sand band
    rect(x0, Y(0.42), x0 + w, Y(0.68), (196, 164, 104))
    # three tents with door flaps and guy ropes
    for tx, tw, th in ((0.16, 0.13, 0.24), (0.44, 0.14, 0.22), (0.71, 0.13, 0.24)):
        tri(X(tx - tw), Y(0.68), X(tx + tw), Y(0.68), X(tx), Y(0.68 - th),
            (220, 200, 150))
        tri(X(tx - 0.03), Y(0.68), X(tx + 0.03), Y(0.68),
            X(tx), Y(0.68 - 0.10), (90, 70, 50))
        line(X(tx), Y(0.68 - th), X(tx - tw - 0.04), Y(0.68), (120, 100, 70))
        line(X(tx), Y(0.68 - th), X(tx + tw + 0.04), Y(0.68), (120, 100, 70))
        line(X(tx - tw), Y(0.68), X(tx + tw), Y(0.68), (150, 125, 85))
    # flood water
    vgrad(x0, Y(0.68), x0 + w, y0 + h, (24, 92, 150), (18, 70, 120))
    for wy, wx0, wx1 in ((0.74, 0.05, 0.25), (0.78, 0.55, 0.80),
                         (0.84, 0.10, 0.35), (0.90, 0.60, 0.90),
                         (0.94, 0.20, 0.50)):
        hline(X(wx0), X(wx1), Y(wy), (180, 210, 230))
    # two people wading
    _wader(X(0.30), Y(0.60), h, (40, 70, 140), 1.0)
    _wader(X(0.58), Y(0.58), h, (180, 60, 50), 0.9)
    # floating crate, barrel, plank
    rect(X(0.80), Y(0.72), X(0.88), Y(0.80), (150, 110, 60))
    rect(X(0.80), Y(0.72), X(0.88), Y(0.74), (180, 140, 80))
    rect(X(0.86), Y(0.64), X(0.91), Y(0.72), (140, 70, 60))
    line(X(0.36), Y(0.88), X(0.50), Y(0.84), (160, 120, 70))
    line(X(0.36), Y(0.88), X(0.50), Y(0.84), (160, 120, 70))
    # splashes around the waders
    for sx, sy in ((0.27, 0.72), (0.33, 0.74), (0.55, 0.72), (0.61, 0.74)):
        px(X(sx), Y(sy), WHITE)
        px(X(sx) + 2, Y(sy) - 1, WHITE)


def _wader(cx, cy, h, top, s):
    """Person wading in flood water: head, torso, legs below the line."""
    circle(cx, cy, int(0.035 * h * s), (210, 170, 130))
    rect(cx - int(0.04 * h * s), cy + int(0.04 * h * s),
         cx + int(0.04 * h * s), cy + int(0.16 * h * s), top)
    line(cx - int(0.015 * h * s), cy + int(0.16 * h * s),
         cx - int(0.03 * h * s), cy + int(0.30 * h * s), (50, 50, 60))
    line(cx + int(0.015 * h * s), cy + int(0.16 * h * s),
         cx + int(0.02 * h * s), cy + int(0.30 * h * s), (50, 50, 60))


def scene6(x0, y0, w, h):
    """Hong Kong: Election Committee vote over the harbour."""
    X = lambda f: int(round(x0 + f * w))
    Y = lambda f: int(round(y0 + f * h))
    vgrad(x0, y0, x0 + w, y0 + int(0.72 * h), (84, 140, 200), (165, 198, 230))
    ellipse(X(0.14), Y(0.10), 0.08 * w, 0.04 * h, WHITE)
    ellipse(X(0.80), Y(0.08), 0.06 * w, 0.03 * h, (240, 244, 248))
    # towers, varied heights, lit windows
    towers = [(0.28, 0.34, 0.07), (0.37, 0.26, 0.07), (0.46, 0.30, 0.06),
              (0.54, 0.16, 0.07), (0.63, 0.28, 0.06)]
    for tx, top, tw in towers:
        rect(X(tx), Y(top), X(tx + tw), Y(0.72), (40, 58, 92))
        rect(X(tx), Y(top), X(tx + tw), Y(top + 0.03), (60, 80, 115))
        for r in range(3):
            for c in range(2):
                if (r * 2 + c) % 3 == 0:
                    px(X(tx + 0.015 + c * 0.03), Y(top + 0.08 + r * 0.12),
                       (255, 210, 100))
                    px(X(tx + 0.015 + c * 0.03) + 1, Y(top + 0.08 + r * 0.12),
                       (255, 210, 100))
    # red flag on the tallest tower
    line(X(0.575), Y(0.16), X(0.575), Y(0.08), (40, 44, 54))
    tri(X(0.575), Y(0.08), X(0.575), Y(0.13), X(0.615), Y(0.105), (200, 40, 40))
    # white building with red stripe
    rect(X(0.72), Y(0.42), X(0.88), Y(0.72), (240, 240, 235))
    rect(X(0.72), Y(0.50), X(0.88), Y(0.54), (200, 40, 40))
    for wx in (0.75, 0.80, 0.84):
        rect(X(wx), Y(0.58), X(wx + 0.02), Y(0.66), (60, 80, 110))
    # harbour water + junk boat
    vgrad(x0, Y(0.72), x0 + w, y0 + h, (32, 88, 132), (24, 70, 110))
    for wy, wx0, wx1 in ((0.80, 0.05, 0.30), (0.86, 0.40, 0.70),
                         (0.92, 0.10, 0.45)):
        hline(X(wx0), X(wx1), Y(wy), (170, 200, 220))
    tri(X(0.14), Y(0.78), X(0.20), Y(0.78), X(0.17), Y(0.86), (150, 110, 60))
    tri(X(0.155), Y(0.76), X(0.155), Y(0.88), X(0.20), Y(0.86), (220, 200, 150))
    line(X(0.155), Y(0.76), X(0.155), Y(0.88), (90, 60, 30))


def scene7(x0, y0, w, h):
    """Seoul: the education minister's desk after the AI-cheating row."""
    X = lambda f: int(round(x0 + f * w))
    Y = lambda f: int(round(y0 + f * h))
    vgrad(x0, y0, x0 + w, y0 + int(0.68 * h), (198, 178, 138), (216, 198, 168))
    # framed picture (mountain + sun) on the wall
    rect(X(0.08), Y(0.08), X(0.26), Y(0.34), (90, 60, 28))
    rect(X(0.10), Y(0.10), X(0.24), Y(0.32), (150, 190, 225))
    tri(X(0.10), Y(0.32), X(0.24), Y(0.32), X(0.17), Y(0.16), (60, 130, 70))
    circle(X(0.21), Y(0.15), int(0.03 * h), (255, 210, 90))
    # small framed flag next to it
    rect(X(0.30), Y(0.10), X(0.42), Y(0.26), (90, 60, 28))
    rect(X(0.315), Y(0.115), X(0.405), Y(0.245), WHITE)
    circle(X(0.36), Y(0.18), int(0.03 * h), (200, 40, 40))
    circle(X(0.36), Y(0.18), int(0.015 * h), (40, 70, 160))
    # wall clock
    circle(X(0.88), Y(0.14), int(0.06 * h), WHITE)
    ring(X(0.88), Y(0.14), int(0.06 * h), 1, (60, 60, 66))
    line(X(0.88), Y(0.14), X(0.88), Y(0.10), (40, 44, 54))
    line(X(0.88), Y(0.14), X(0.91), Y(0.16), (40, 44, 54))
    # desk (walnut) with shadow
    rect(x0, Y(0.68), x0 + w, Y(0.72), (90, 60, 28))
    rect(x0, Y(0.72), x0 + w, Y(0.82), (120, 85, 50))
    rect(x0, Y(0.82), x0 + w, y0 + h, (150, 125, 90))
    # paper stack (left)
    rect(X(0.08), Y(0.60), X(0.24), Y(0.68), WHITE)
    rect(X(0.10), Y(0.57), X(0.26), Y(0.65), (235, 235, 228))
    line(X(0.12), Y(0.60), X(0.22), Y(0.60), (150, 150, 145))
    line(X(0.12), Y(0.63), X(0.20), Y(0.63), (150, 150, 145))
    # main document with green check + red line
    rect(X(0.44), Y(0.34), X(0.68), Y(0.68), WHITE)
    rect(X(0.44), Y(0.34), X(0.68), Y(0.36), (200, 200, 195))
    line(X(0.48), Y(0.50), X(0.52), Y(0.56), (40, 140, 60))
    line(X(0.52), Y(0.56), X(0.60), Y(0.42), (40, 140, 60))
    hline(X(0.48), X(0.62), Y(0.60), (200, 40, 40))
    hline(X(0.48), X(0.62), Y(0.63), (200, 40, 40))
    # two pencils + eraser
    thick_line(X(0.30), Y(0.62), X(0.42), Y(0.58), 3, (255, 200, 40))
    thick_line(X(0.70), Y(0.60), X(0.80), Y(0.66), 3, (60, 110, 200))
    rect(X(0.82), Y(0.62), X(0.87), Y(0.67), (230, 130, 140))
    # stamp pad + coffee cup
    rect(X(0.86), Y(0.56), X(0.96), Y(0.62), (200, 40, 40))
    rect(X(0.88), Y(0.58), X(0.94), Y(0.60), (230, 90, 90))
    rect(X(0.74), Y(0.58), X(0.80), Y(0.66), WHITE)
    rect(X(0.80), Y(0.60), X(0.82), Y(0.64), WHITE)


def scene8(x0, y0, w, h):
    """Las Vegas GP: Verstappen wins under the lights."""
    X = lambda f: int(round(x0 + f * w))
    Y = lambda f: int(round(y0 + f * h))
    vgrad(x0, y0, x0 + w, y0 + int(0.55 * h), (20, 28, 48), (45, 60, 90))
    for sx, sy in ((0.08, 0.08), (0.20, 0.14), (0.34, 0.06), (0.48, 0.12),
                   (0.62, 0.06), (0.90, 0.10), (0.96, 0.20), (0.42, 0.20)):
        px(X(sx), Y(sy), WHITE)
    # floodlight poles with glow
    for fx in (0.14, 0.86):
        line(X(fx), Y(0.10), X(fx), Y(0.45), (80, 85, 95))
        circle(X(fx), Y(0.10), int(0.045 * h), (255, 245, 200))
        circle(X(fx), Y(0.10), int(0.025 * h), WHITE)
    # grandstand with crowd dots
    rect(X(0.58), Y(0.12), X(0.96), Y(0.40), (52, 58, 66))
    rect(X(0.58), Y(0.12), X(0.96), Y(0.16), (70, 76, 86))
    for r in range(3):
        for c in range(10):
            col = ((200, 60, 60), (60, 120, 200), (240, 210, 80),
                   (240, 240, 235))[(r + c) % 4]
            px(X(0.60 + c * 0.035), Y(0.22 + r * 0.07), col)
    # checkered flag on a pole
    line(X(0.50), Y(0.18), X(0.50), Y(0.45), (200, 200, 195))
    for r in range(3):
        for c in range(4):
            col = WHITE if (r + c) % 2 == 0 else (20, 20, 26)
            rect(X(0.50 + c * 0.02), Y(0.18 + r * 0.045),
                 X(0.50 + (c + 1) * 0.02), Y(0.18 + (r + 1) * 0.045), col)
    # track
    rect(x0, Y(0.55), x0 + w, Y(0.88), (60, 60, 66))
    hline(x0, x0 + w, Y(0.55), (240, 210, 80))
    hline(x0, x0 + w, Y(0.88), WHITE)
    for dx in range(4, 100, 12):
        hline(X(dx / 100.0), X((dx + 6) / 100.0), Y(0.71), (240, 210, 80))
    # red car (leader) + blue car (chaser)
    _f1car(X(0.16), Y(0.60), w, h, (200, 40, 40), 1.0)
    _f1car(X(0.46), Y(0.64), w, h, (40, 90, 200), 0.85)
    # motion lines
    for my, mx0, mx1 in ((0.62, 0.02, 0.12), (0.68, 0.06, 0.14),
                         (0.66, 0.36, 0.44)):
        hline(X(mx0), X(mx1), Y(my), (200, 200, 195))


def _f1car(cx, cy, w, h, body, s):
    cw, ch = int(0.20 * w * s), int(0.10 * h * s)
    rect(cx, cy, cx + cw, cy + ch, body)
    rect(cx + int(0.06 * w * s), cy - int(0.05 * h * s),
         cx + int(0.12 * w * s), cy, body)
    rect(cx, cy + int(0.03 * h * s), cx + cw, cy + int(0.05 * h * s),
         (240, 240, 235))
    for wx in (0.03, 0.15):
        circle(cx + int(wx * w * s), cy + ch, int(0.035 * h * s), (20, 20, 26))
        circle(cx + int(wx * w * s), cy + ch, int(0.015 * h * s),
               (150, 155, 160))


def scene9(x0, y0, w, h):
    """Wellington: India declare 720/9."""
    X = lambda f: int(round(x0 + f * w))
    Y = lambda f: int(round(y0 + f * h))
    vgrad(x0, y0, x0 + w, y0 + h, (52, 116, 44), (72, 142, 62))
    # outfield boundary rope (drawn first so the pitch and players sit on it)
    ellipse(X(0.50), Y(0.55), 0.30 * w, 0.30 * h, (90, 160, 80))
    ellipse(X(0.50), Y(0.55), 0.28 * w, 0.28 * h, (52, 116, 44))
    # crowd dots along the top
    for c in range(30):
        col = ((220, 220, 210), (200, 60, 60), (60, 110, 200),
               (240, 210, 80))[c % 4]
        px(X(0.03 + c * 0.032), Y(0.04), col)
        px(X(0.03 + c * 0.032), Y(0.07), col)
    # pitch (straw) with creases
    rect(X(0.42), Y(0.10), X(0.58), Y(0.95), (200, 180, 120))
    hline(X(0.42), X(0.58), Y(0.28), WHITE)
    hline(X(0.42), X(0.58), Y(0.82), WHITE)
    hline(X(0.42), X(0.58), Y(0.32), (200, 180, 120))
    # sight screen
    rect(X(0.05), Y(0.30), X(0.12), Y(0.58), (240, 240, 235))
    rect(X(0.05), Y(0.30), X(0.12), Y(0.33), (200, 200, 195))
    # scoreboard
    rect(X(0.70), Y(0.06), X(0.94), Y(0.30), (24, 32, 48))
    draw_text(X(0.72), Y(0.10), "720/9", 1.0, WHITE, bold=True)
    draw_text(X(0.72), Y(0.22), "IND 720/9", 0.55, (200, 205, 210))
    # stumps (yellow) + bails
    for sx in (0.485, 0.50, 0.515):
        vline(X(sx), Y(0.52), Y(0.60), (240, 210, 80))
    # batsman in white, bat raised
    circle(X(0.50), Y(0.44), int(0.035 * h), (210, 170, 130))
    rect(X(0.475), Y(0.48), X(0.525), Y(0.66), WHITE)
    thick_line(X(0.53), Y(0.60), X(0.60), Y(0.78), 3, (150, 110, 60))
    line(X(0.49), Y(0.66), X(0.47), Y(0.82), (240, 240, 235))
    line(X(0.51), Y(0.66), X(0.53), Y(0.82), (240, 240, 235))
    # red ball near the bat
    circle(X(0.62), Y(0.80), int(0.02 * h), (200, 40, 40))
    # wicket-keeper crouched behind the stumps
    circle(X(0.50), Y(0.36), int(0.03 * h), (210, 170, 130))
    rect(X(0.48), Y(0.39), X(0.52), Y(0.48), (40, 44, 54))
    # two fielders
    for fx, fy in ((0.22, 0.42), (0.80, 0.62)):
        circle(X(fx), Y(fy), int(0.03 * h), (210, 170, 130))
        rect(X(fx - 0.02), Y(fy + 0.03), X(fx + 0.02), Y(fy + 0.13),
             (30, 60, 30))
    # field markings
    pass


def scene10(x0, y0, w, h):
    """Florida: St Johns River at a record flood."""
    X = lambda f: int(round(x0 + f * w))
    Y = lambda f: int(round(y0 + f * h))
    vgrad(x0, y0, x0 + w, y0 + int(0.55 * h), (88, 140, 196), (175, 205, 228))
    # storm cloud + rain
    ellipse(X(0.72), Y(0.06), 0.12 * w, 0.05 * h, (60, 70, 90))
    ellipse(X(0.20), Y(0.08), 0.08 * w, 0.035 * h, (120, 130, 145))
    for rx in range(8, 100, 9):
        line(X(rx / 100.0), Y(0.10), X(rx / 100.0 - 0.015), Y(0.34),
             (120, 160, 210))
    # main house (cream, terracotta roof) + smaller house
    rect(X(0.08), Y(0.42), X(0.22), Y(0.62), (225, 210, 180))
    tri(X(0.06), Y(0.42), X(0.24), Y(0.42), X(0.15), Y(0.32), (170, 80, 45))
    rect(X(0.35), Y(0.30), X(0.60), Y(0.62), (240, 225, 190))
    tri(X(0.32), Y(0.30), X(0.63), Y(0.30), X(0.475), Y(0.16), (190, 90, 50))
    rect(X(0.45), Y(0.46), X(0.51), Y(0.62), (120, 85, 50))
    rect(X(0.38), Y(0.38), X(0.43), Y(0.46), (40, 50, 70))
    rect(X(0.54), Y(0.38), X(0.58), Y(0.46), (40, 50, 70))
    # two palm trees
    for tx, ty, s in ((0.68, 0.30, 1.0), (0.26, 0.36, 0.8)):
        line(X(tx), Y(ty + 0.24), X(tx + 0.02 * s), Y(ty), (120, 85, 50))
        for dx, dy in ((-0.06, -0.02), (-0.04, -0.06), (0.0, -0.07),
                       (0.05, -0.05), (0.07, -0.01)):
            line(X(tx + 0.02 * s), Y(ty), X(tx + dx * s), Y(ty + dy * s),
                 (50, 130, 60))
    # flood water with ripples
    vgrad(x0, Y(0.62), x0 + w, y0 + h, (24, 84, 146), (18, 62, 112))
    for wy, wx0, wx1 in ((0.70, 0.05, 0.30), (0.76, 0.55, 0.85),
                         (0.82, 0.10, 0.40), (0.88, 0.45, 0.80),
                         (0.94, 0.15, 0.50)):
        hline(X(wx0), X(wx1), Y(wy), (180, 210, 230))
    # car roof poking out + debris plank
    rect(X(0.28), Y(0.68), X(0.44), Y(0.74), (110, 115, 120))
    rect(X(0.28), Y(0.68), X(0.44), Y(0.70), (150, 155, 160))
    line(X(0.52), Y(0.86), X(0.66), Y(0.82), (160, 120, 70))
    line(X(0.52), Y(0.88), X(0.66), Y(0.84), (160, 120, 70))
    # rescue boat with a person
    rect(X(0.76), Y(0.70), X(0.92), Y(0.78), (200, 40, 40))
    rect(X(0.76), Y(0.70), X(0.92), Y(0.72), (230, 90, 90))
    circle(X(0.84), Y(0.64), int(0.035 * h), (210, 170, 130))
    rect(X(0.815), Y(0.67), X(0.865), Y(0.72), (230, 110, 30))


def scene11(x0, y0, w, h):
    """Emergency talks: Hamas presses the mediators."""
    X = lambda f: int(round(x0 + f * w))
    Y = lambda f: int(round(y0 + f * h))
    vgrad(x0, y0, x0 + w, y0 + int(0.68 * h), (196, 176, 136), (216, 198, 168))
    # hanging lamp
    line(X(0.50), y0, X(0.50), Y(0.16), (60, 60, 66))
    poly([(X(0.44), Y(0.16)), (X(0.56), Y(0.16)), (X(0.53), Y(0.24)),
          (X(0.47), Y(0.24))], (200, 160, 60))
    ellipse(X(0.50), Y(0.26), 0.07 * w, 0.03 * h, (255, 225, 130))
    # wall clock + framed mountain picture
    circle(X(0.14), Y(0.12), int(0.055 * h), WHITE)
    ring(X(0.14), Y(0.12), int(0.055 * h), 1, (60, 60, 66))
    line(X(0.14), Y(0.12), X(0.14), Y(0.08), (40, 44, 54))
    line(X(0.14), Y(0.12), X(0.165), Y(0.14), (40, 44, 54))
    rect(X(0.82), Y(0.08), X(0.95), Y(0.28), (90, 60, 28))
    rect(X(0.835), Y(0.095), X(0.935), Y(0.265), (150, 190, 225))
    tri(X(0.835), Y(0.265), X(0.935), Y(0.265), X(0.885), Y(0.14),
        (60, 130, 70))
    # plant in the corner
    rect(X(0.05), Y(0.56), X(0.11), Y(0.66), (150, 90, 50))
    for dx, dy in ((-0.02, -0.08), (0.0, -0.10), (0.02, -0.08), (0.03, -0.05)):
        line(X(0.08), Y(0.56), X(0.08 + dx), Y(0.56 + dy), (50, 130, 60))
    # table (walnut)
    rect(x0, Y(0.68), x0 + w, Y(0.72), (90, 60, 28))
    rect(x0, Y(0.72), x0 + w, Y(0.82), (120, 85, 50))
    rect(x0, Y(0.82), x0 + w, y0 + h, (150, 125, 90))
    # three figures behind the table, ties, hands on the table
    # heads: bright skin + dark hair cap + thin ring, so they read
    # against the pale wall (old skin (210,170,130) was nearly the
    # same as the wall, so the heads looked missing)
    for fx, suit, tie in ((0.28, (30, 50, 90), (200, 40, 40)),
                          (0.50, (60, 60, 66), (40, 90, 200)),
                          (0.72, (30, 50, 90), (200, 40, 40))):
        hx, hy = X(fx), Y(0.44)
        hr = max(3, int(round(0.055 * h)))
        circle(hx, hy, hr, (235, 196, 150))
        ring(hx, hy, hr, 1, (150, 105, 70))
        # hair: dark cap over the top of the head
        rect(hx - hr, hy - hr, hx + hr + 1, hy - hr // 3, (45, 35, 28))
        # neck
        nw = max(1, hr // 3)
        rect(hx - nw, hy + hr // 2, hx + nw + 1, Y(0.50), (235, 196, 150))
        rect(X(fx - 0.055), Y(0.50), X(fx + 0.055), Y(0.68), suit)
        rect(X(fx - 0.012), Y(0.50), X(fx + 0.012), Y(0.68), WHITE)
        tri(X(fx - 0.014), Y(0.52), X(fx + 0.014), Y(0.52), X(fx), Y(0.64),
            tie)
        ellipse(X(fx), Y(0.70), 0.03 * w, 0.02 * h, (210, 170, 130))
    # nameplate, documents, water glass
    rect(X(0.44), Y(0.72), X(0.58), Y(0.78), WHITE)
    hline(X(0.46), X(0.56), Y(0.75), (60, 60, 66))
    rect(X(0.16), Y(0.70), X(0.28), Y(0.76), (240, 240, 235))
    rect(X(0.76), Y(0.70), X(0.88), Y(0.76), (240, 240, 235))
    rect(X(0.90), Y(0.66), X(0.94), Y(0.74), (180, 210, 225))
    rect(X(0.90), Y(0.66), X(0.94), Y(0.68), (220, 235, 240))


SCENES = {1: scene1, 2: scene2, 3: scene3, 4: scene4, 5: scene5, 6: scene6,
          7: scene7, 8: scene8, 9: scene9, 10: scene10, 11: scene11}


# ---------------------------------------------------------------- main
def main():
    fill(PAPER)
    draw_header()
    draw_cards()
    draw_list()
    draw_bottom()
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR")
    if outdir:
        path = os.path.join(outdir, "entry.png")
    else:
        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(here, "entry-v6.png")
    size = write_png(path)
    if MISSING:
        sys.stderr.write("MISSING glyphs: %r\n" % (MISSING,))
    sys.stderr.write("wrote %s (%d bytes)\n" % (path, size))


if __name__ == "__main__":
    main()
