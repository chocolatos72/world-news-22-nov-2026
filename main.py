"""Berita 22 — "The World in One Day" (news-image-20261122).

A single 1024x1024 newspaper page summing up Sunday 22 November 2026:
35 stories, 7 regions, 11 pictured cards + 24 more in the list, a world map
with 11 numbered dots, a date-check box and a UTC strip.

Written from scratch for the v4 rewrite (Mon 23 Nov 2026): every line typed
fresh from the approved image and the build notes — no earlier entry code was
read. Stdlib only (zlib + struct): hand-rolled PNG encoder and a 5x7 bitmap
font, because the make.fun sandbox has no Pillow or Matplotlib.

Run:  python3 main.py            -> writes entry-v4.png next to this file
      python3 main.py out.png    -> writes to the given path
Deterministic: two runs produce byte-identical output.
"""

import os
import struct
import sys
import zlib

W = 1024
H = 1024

# ---------------------------------------------------------------- palette
PAPER = (247, 243, 234)      # page background
CARD = (255, 252, 244)       # card / box background
INK = (24, 32, 48)           # near-black text (never pure black)
NAVY = (16, 32, 64)          # dark strip / map label / card border
STRIP = (16, 18, 24)         # top black strip
RED = (178, 34, 34)          # red labels, summary, FRI tag
GOLD = (201, 162, 39)        # gold masthead text
UTCGOLD = (172, 138, 58)     # muted gold for the UTC label
SLATE = (34, 48, 63)         # box body text
GREY = (120, 124, 132)       # footer text
RULEC = (176, 168, 150)      # thin rule lines
UTCDESC = (190, 195, 205)    # UTC descriptions + top-strip right text
WHITE = (255, 255, 255)
ACCENT = (40, 44, 54)        # charcoal accent bar on the date-check box
SEA = (207, 227, 238)        # map sea
LAND = (216, 210, 184)       # map land

# Region colours (also used for card subtitles, list rows, map dots).
REGION = {
    "EUROPE": (31, 78, 156),
    "MIDDLE EAST": (179, 84, 30),
    "ASIA": (46, 125, 79),
    "AMERICAS": (122, 59, 143),
    "AFRICA": (138, 109, 27),
    "OCEANIA": (14, 124, 134),
    "WORLD": (90, 90, 110),
}

# Day tags in the list are coloured by the day the story happened.
TAGCOL = {"SUN": (46, 125, 79), "SAT": (179, 84, 30), "FRI": RED}


# ---------------------------------------------------------------- canvas
class Canvas:
    """A plain RGB byte buffer with small drawing helpers."""

    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.buf = bytearray(w * h * 3)
        r, g, b = bg
        for i in range(0, w * h * 3, 3):
            self.buf[i] = r
            self.buf[i + 1] = g
            self.buf[i + 2] = b

    def px(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.buf[i] = c[0]
            self.buf[i + 1] = c[1]
            self.buf[i + 2] = c[2]

    def get(self, x, y):
        i = (y * self.w + x) * 3
        return (self.buf[i], self.buf[i + 1], self.buf[i + 2])

    def rect(self, x, y, w, h, c):
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.w, x + w)
        y1 = min(self.h, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        r, g, b = c
        for yy in range(y0, y1):
            base = (yy * self.w + x0) * 3
            for xx in range(x1 - x0):
                i = base + xx * 3
                self.buf[i] = r
                self.buf[i + 1] = g
                self.buf[i + 2] = b

    def hline(self, x0, x1, y, c):
        for x in range(max(0, x0), min(self.w, x1 + 1)):
            self.px(x, y, c)

    def vline(self, x, y0, y1, c):
        for y in range(max(0, y0), min(self.h, y1 + 1)):
            self.px(x, y, c)

    def line(self, x0, y0, x1, y1, c):
        """Bresenham line, endpoints inclusive."""
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        x, y = x0, y0
        while True:
            self.px(x, y, c)
            if x == x1 and y == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x += sx
            if e2 <= dx:
                err += dx
                y += sy

    def circle(self, cx, cy, r, c):
        """Filled circle."""
        for yy in range(cy - r, cy + r + 1):
            dx = int((r * r - (yy - cy) * (yy - cy)) ** 0.5) if abs(yy - cy) <= r else 0
            self.hline(cx - dx, cx + dx, yy, c)

    def ellipse(self, cx, cy, rx, ry, c):
        """Filled ellipse."""
        for yy in range(cy - ry, cy + ry + 1):
            dy = (yy - cy) / ry
            dx = int(rx * (1 - dy * dy) ** 0.5) if abs(dy) <= 1 else 0
            self.hline(cx - dx, cx + dx, yy, c)

    def tri(self, pts, c):
        """Filled triangle from three (x, y) points."""
        (x0, y0), (x1, y1), (x2, y2) = pts
        ymin = min(y0, y1, y2)
        ymax = max(y0, y1, y2)
        for y in range(ymin, ymax + 1):
            xs = []
            for (ax, ay), (bx, by) in (((x0, y0), (x1, y1)),
                                       ((x1, y1), (x2, y2)),
                                       ((x2, y2), (x0, y0))):
                if ay == by:
                    continue
                if (y - ay) * (y - by) <= 0 and ay != by:
                    t = (y - ay) / (by - ay)
                    xs.append(ax + t * (bx - ax))
            if len(xs) >= 2:
                self.hline(int(min(xs)), int(max(xs)), y, c)

    def poly(self, pts, c):
        """Filled polygon (scanline, even-odd)."""
        ymin = min(y for _, y in pts)
        ymax = max(y for _, y in pts)
        n = len(pts)
        for y in range(ymin, ymax + 1):
            xs = []
            for i in range(n):
                ax, ay = pts[i]
                bx, by = pts[(i + 1) % n]
                if ay == by:
                    continue
                if (y - ay) * (y - by) < 0 or (y == ay and y < by) or (y == by and y < ay):
                    t = (y - ay) / (by - ay)
                    xs.append(ax + t * (bx - ax))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                self.hline(int(xs[i]), int(xs[i + 1]), y, c)

    def vgrad(self, x, y, w, h, top, bot):
        """Vertical gradient, top colour at y, bottom colour at y+h."""
        for yy in range(h):
            t = yy / max(1, h - 1)
            c = (round(top[0] + (bot[0] - top[0]) * t),
                 round(top[1] + (bot[1] - top[1]) * t),
                 round(top[2] + (bot[2] - top[2]) * t))
            self.hline(x, x + w - 1, y + yy, c)


# ---------------------------------------------------------------- PNG out
def write_png(cv, path):
    """Encode the canvas as an 8-bit RGB PNG (filter 0, one IDAT)."""
    raw = bytearray()
    stride = cv.w * 3
    for y in range(cv.h):
        raw.append(0)
        raw += cv.buf[y * stride:(y + 1) * stride]
    comp = zlib.compress(bytes(raw), 9)

    def chunk(tag, data):
        out = struct.pack(">I", len(data)) + tag + data
        out += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return out

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", comp)
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)


# ---------------------------------------------------------------- font
# A 5x7 bitmap font, drawn fresh for this rewrite. Each glyph is seven rows;
# each row is a 5-bit number, bit 4 is the leftmost column. Capitals and
# digits use all seven rows; lowercase letters sit on rows 2-6 (x-height),
# with ascenders reaching row 0 and descender tails on row 6.
FONT = {
    "A": (0b01110, 0b10001, 0b10001, 0b11111, 0b10001, 0b10001, 0b10001),
    "B": (0b11110, 0b10001, 0b10001, 0b11110, 0b10001, 0b10001, 0b11110),
    "C": (0b01110, 0b10001, 0b10000, 0b10000, 0b10000, 0b10001, 0b01110),
    "D": (0b11110, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b11110),
    "E": (0b11111, 0b10000, 0b10000, 0b11110, 0b10000, 0b10000, 0b11111),
    "F": (0b11111, 0b10000, 0b10000, 0b11110, 0b10000, 0b10000, 0b10000),
    "G": (0b01110, 0b10001, 0b10000, 0b10111, 0b10001, 0b10001, 0b01111),
    "H": (0b10001, 0b10001, 0b10001, 0b11111, 0b10001, 0b10001, 0b10001),
    "I": (0b01110, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110),
    "J": (0b00111, 0b00010, 0b00010, 0b00010, 0b00010, 0b10010, 0b01100),
    "K": (0b10001, 0b10010, 0b10100, 0b11000, 0b10100, 0b10010, 0b10001),
    "L": (0b10000, 0b10000, 0b10000, 0b10000, 0b10000, 0b10000, 0b11111),
    "M": (0b10001, 0b11011, 0b10101, 0b10101, 0b10001, 0b10001, 0b10001),
    "N": (0b10001, 0b11001, 0b10101, 0b10011, 0b10001, 0b10001, 0b10001),
    "O": (0b01110, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01110),
    "P": (0b11110, 0b10001, 0b10001, 0b11110, 0b10000, 0b10000, 0b10000),
    "Q": (0b01110, 0b10001, 0b10001, 0b10001, 0b10101, 0b10010, 0b01101),
    "R": (0b11110, 0b10001, 0b10001, 0b11110, 0b10100, 0b10010, 0b10001),
    "S": (0b01111, 0b10000, 0b10000, 0b01110, 0b00001, 0b00001, 0b11110),
    "T": (0b11111, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100),
    "U": (0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01110),
    "V": (0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01010, 0b00100),
    "W": (0b10001, 0b10001, 0b10001, 0b10101, 0b10101, 0b10101, 0b01010),
    "X": (0b10001, 0b10001, 0b01010, 0b00100, 0b01010, 0b10001, 0b10001),
    "Y": (0b10001, 0b10001, 0b01010, 0b00100, 0b00100, 0b00100, 0b00100),
    "Z": (0b11111, 0b00001, 0b00010, 0b00100, 0b01000, 0b10000, 0b11111),
    "0": (0b01110, 0b10001, 0b10011, 0b10101, 0b11001, 0b10001, 0b01110),
    "1": (0b00100, 0b01100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110),
    "2": (0b01110, 0b10001, 0b00001, 0b00110, 0b01000, 0b10000, 0b11111),
    "3": (0b11111, 0b00010, 0b00100, 0b00010, 0b00001, 0b10001, 0b01110),
    "4": (0b00010, 0b00110, 0b01010, 0b10010, 0b11111, 0b00010, 0b00010),
    "5": (0b11111, 0b10000, 0b11110, 0b00001, 0b00001, 0b10001, 0b01110),
    "6": (0b00110, 0b01000, 0b10000, 0b11110, 0b10001, 0b10001, 0b01110),
    "7": (0b11111, 0b00001, 0b00010, 0b00100, 0b01000, 0b01000, 0b01000),
    "8": (0b01110, 0b10001, 0b10001, 0b01110, 0b10001, 0b10001, 0b01110),
    "9": (0b01110, 0b10001, 0b10001, 0b01111, 0b00001, 0b00010, 0b01100),
    "a": (0b00000, 0b00000, 0b01110, 0b00001, 0b01111, 0b10001, 0b01111),
    "b": (0b10000, 0b10000, 0b11110, 0b10001, 0b10001, 0b10001, 0b11110),
    "c": (0b00000, 0b00000, 0b01110, 0b10000, 0b10000, 0b10001, 0b01110),
    "d": (0b00001, 0b00001, 0b01111, 0b10001, 0b10001, 0b10001, 0b01111),
    "e": (0b00000, 0b00000, 0b01110, 0b10001, 0b11111, 0b10000, 0b01110),
    "f": (0b00110, 0b01000, 0b01000, 0b11110, 0b01000, 0b01000, 0b01000),
    "g": (0b00000, 0b01111, 0b10001, 0b10001, 0b01111, 0b00001, 0b01110),
    "h": (0b10000, 0b10000, 0b11110, 0b10001, 0b10001, 0b10001, 0b10001),
    "i": (0b00100, 0b00000, 0b01100, 0b00100, 0b00100, 0b00100, 0b01110),
    "j": (0b00010, 0b00000, 0b00110, 0b00010, 0b00010, 0b00010, 0b01100),
    "k": (0b10000, 0b10000, 0b10010, 0b10100, 0b11000, 0b10100, 0b10010),
    "l": (0b01100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110),
    "m": (0b00000, 0b00000, 0b11010, 0b10101, 0b10101, 0b10101, 0b10101),
    "n": (0b00000, 0b00000, 0b11110, 0b10001, 0b10001, 0b10001, 0b10001),
    "o": (0b00000, 0b00000, 0b01110, 0b10001, 0b10001, 0b10001, 0b01110),
    "p": (0b00000, 0b11110, 0b10001, 0b10001, 0b11110, 0b10000, 0b10000),
    "q": (0b00000, 0b01111, 0b10001, 0b10001, 0b01111, 0b00001, 0b00001),
    "r": (0b00000, 0b00000, 0b10110, 0b11001, 0b10000, 0b10000, 0b10000),
    "s": (0b00000, 0b00000, 0b01111, 0b10000, 0b01110, 0b00001, 0b11110),
    "t": (0b00100, 0b00100, 0b11111, 0b00100, 0b00100, 0b00100, 0b00010),
    "u": (0b00000, 0b00000, 0b10001, 0b10001, 0b10001, 0b10011, 0b01101),
    "v": (0b00000, 0b00000, 0b10001, 0b10001, 0b10001, 0b01010, 0b00100),
    "w": (0b00000, 0b00000, 0b10001, 0b10101, 0b10101, 0b10101, 0b01010),
    "x": (0b00000, 0b00000, 0b10001, 0b01010, 0b00100, 0b01010, 0b10001),
    "y": (0b00000, 0b10001, 0b10001, 0b01010, 0b00100, 0b00100, 0b00100),
    "z": (0b00000, 0b00000, 0b11111, 0b00010, 0b00100, 0b01000, 0b11111),
}

FONT.update({
    " ": (0, 0, 0, 0, 0, 0, 0),
    "!": (0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00000, 0b00100),
    '"': (0b01010, 0b01010, 0b01010, 0, 0, 0, 0),
    "#": (0b01010, 0b01010, 0b11111, 0b01010, 0b11111, 0b01010, 0b01010),
    "$": (0b00100, 0b01111, 0b10100, 0b01110, 0b00101, 0b11110, 0b00100),
    "%": (0b11001, 0b11010, 0b00010, 0b00100, 0b01000, 0b01011, 0b10011),
    "&": (0b01100, 0b10010, 0b10100, 0b01000, 0b10101, 0b10010, 0b01101),
    "'": (0b00100, 0b00100, 0b01000, 0, 0, 0, 0),
    "(": (0b00010, 0b00100, 0b01000, 0b01000, 0b01000, 0b00100, 0b00010),
    ")": (0b01000, 0b00100, 0b00010, 0b00010, 0b00010, 0b00100, 0b01000),
    "*": (0, 0b00100, 0b10101, 0b01110, 0b10101, 0b00100, 0),
    "+": (0, 0b00100, 0b00100, 0b11111, 0b00100, 0b00100, 0),
    ",": (0, 0, 0, 0, 0, 0b01100, 0b00100),
    "-": (0, 0, 0, 0b11111, 0, 0, 0),
    ".": (0, 0, 0, 0, 0, 0b01100, 0b01100),
    "/": (0b00001, 0b00010, 0b00010, 0b00100, 0b01000, 0b01000, 0b10000),
    ":": (0, 0b01100, 0b01100, 0, 0b01100, 0b01100, 0),
    ";": (0, 0b01100, 0b01100, 0, 0b01100, 0b00100, 0b01000),
    "<": (0b00010, 0b00100, 0b01000, 0b10000, 0b01000, 0b00100, 0b00010),
    "=": (0, 0, 0b11111, 0, 0b11111, 0, 0),
    ">": (0b01000, 0b00100, 0b00010, 0b00001, 0b00010, 0b00100, 0b01000),
    "?": (0b01110, 0b10001, 0b00001, 0b00110, 0b00100, 0, 0b00100),
    "@": (0b01110, 0b10001, 0b10111, 0b10101, 0b10110, 0b10000, 0b01110),
    "[": (0b01110, 0b01000, 0b01000, 0b01000, 0b01000, 0b01000, 0b01110),
    "]": (0b01110, 0b00010, 0b00010, 0b00010, 0b00010, 0b00010, 0b01110),
    "^": (0b00100, 0b01010, 0b10001, 0, 0, 0, 0),
    "_": (0, 0, 0, 0, 0, 0, 0b11111),
    "`": (0b01000, 0b00100, 0b00010, 0, 0, 0, 0),
    "|": (0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100),
    "~": (0, 0, 0b01001, 0b10110, 0, 0, 0),
    "—": (0, 0, 0, 0b11111, 0, 0, 0),
    "·": (0, 0, 0, 0b01100, 0b01100, 0, 0),
})

MISSING = []  # glyphs asked for but not in FONT (must stay empty)


def _cell(unit):
    """Pixels per font cell at the given unit size (glyph is 10*unit tall)."""
    return unit * 10.0 / 7.0


def text_w(text, unit, track=0.0, upper=True):
    """Width in px of text at unit size (advance = 6 cells + track)."""
    if upper:
        text = text.upper()
    cell = _cell(unit)
    adv = 6.0 * cell + track
    return len(text) * adv - track if text else 0.0


def draw_text(cv, x, y, text, unit, colour, bold=False, track=0.0, upper=True):
    """Draw text with its top-left at (x, y). Returns the width drawn.

    Each font pixel becomes a fractional block (nearest-neighbour cells), so
    fractional units stay sharp. Bold draws a second copy shifted by half a
    cell, which keeps the clear gap between letters at >= ~1px.
    """
    if upper:
        text = text.upper()
    cell = _cell(unit)
    adv = 6.0 * cell + track
    cx = float(x)
    for ch in text:
        glyph = FONT.get(ch)
        if glyph is None:
            MISSING.append(ch)
            glyph = FONT["?"]
        _draw_glyph(cv, cx, y, glyph, cell, colour)
        if bold:
            _draw_glyph(cv, cx + max(1.0, cell * 0.5), y, glyph, cell, colour)
        cx += adv
    return cx - x - track if text else 0.0


def _draw_glyph(cv, x, y, glyph, cell, colour):
    for row in range(7):
        bits = glyph[row]
        if not bits:
            continue
        ry0 = int(round(y + row * cell))
        ry1 = int(round(y + (row + 1) * cell))
        for col in range(5):
            if bits & (1 << (4 - col)):
                rx0 = int(round(x + col * cell))
                rx1 = int(round(x + (col + 1) * cell))
                cv.rect(rx0, ry0, max(1, rx1 - rx0), max(1, ry1 - ry0), colour)


def draw_text_centred(cv, cx, y, text, unit, colour, bold=False, track=0.0,
                      upper=True):
    w = text_w(text, unit, track, upper)
    return draw_text(cv, cx - w / 2.0, y, text, unit, colour, bold, track, upper)


def draw_text_right(cv, x1, y, text, unit, colour, bold=False, track=0.0,
                    upper=True):
    w = text_w(text, unit, track, upper)
    return draw_text(cv, x1 - w, y, text, unit, colour, bold, track, upper)


def wrap_lines(text, unit, maxw, track=0.0, upper=True):
    """Greedy word wrap; returns a list of lines that fit maxw."""
    words = text.split(" ")
    lines = []
    cur = ""
    for word in words:
        trial = word if not cur else cur + " " + word
        if text_w(trial, unit, track, upper) <= maxw or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def draw_wrapped(cv, x, y, text, unit, maxw, colour, lh, bold=False,
                 track=0.0, upper=True):
    """Draw wrapped text; returns the y just below the last line."""
    lines = wrap_lines(text, unit, maxw, track, upper)
    for i, line in enumerate(lines):
        draw_text(cv, x, y + i * lh, line, unit, colour, bold, track, upper)
    return y + len(lines) * lh


# ---------------------------------------------------------------- data
# The 11 pictured cards: (number, region, place, title lines, sub lines).
# Titles of the three large cards are one line; small cards have two lines.
# Subtitles are two lines each, drawn in the card's region colour.
MAINS = [
    (1, "EUROPE", "ANTALYA",
     ("COP31 COLLAPSES, NO DEAL",),
     ("NO DEAL ADOPTED; FOSSIL", "FUELS LEFT OUT.")),
    (2, "EUROPE", "GULF OF FINLAND",
     ("SHIP BURNING OFF FINLAND",),
     ("RUSSIAN SHIP ABLAZE AFTER", "DRONE STRIKE.")),
    (3, "MIDDLE EAST", "BAHRAIN",
     ("BAHRAIN SEEKS UN ACTION",),
     ("TEHRAN HIT US BASES;", "TANKERS STRUCK.")),
    (4, "EUROPE", "",
     ("DRONE FLATTENS", "KYIV FLATS"),
     ("14 FEARED TRAPPED;", "186 DRONES LAUNCHED.")),
    (5, "MIDDLE EAST", "",
     ("SUNDAY STRIKES", "KILL TWO"),
     ("AL-MAWASI HIT; RAIN", "FLOODS 70,000 TENTS.")),
    (6, "ASIA", "",
     ("HONG KONG VOTES,", "TURNOUT 97%"),
     ("856 CANDIDATES CHASE", "723 COMMITTEE SEATS.")),
    (7, "ASIA", "",
     ("MINISTER QUITS", "OVER AI"),
     ("EXAM CHAOS DAYS", "BEFORE THE SUNEUNG.")),
    (8, "AMERICAS", "",
     ("VERSTAPPEN WINS", "IN LAS VEGAS"),
     ("3RD VEGAS WIN; NORRIS", "2ND, PIASTRI 3RD.")),
    (9, "OCEANIA", "",
     ("INDIA 720/9", "IN WELLINGTON"),
     ("RECORD TOTAL IN NZ;", "PANT 128, RAHUL 136.")),
    (10, "AMERICAS", "",
     ("RECORD FLOOD", "IN FLORIDA"),
     ("ST JOHNS TOPS 1953;", "CREST DUE SUN.")),
    (11, "MIDDLE EAST", "",
     ("HAMAS SEEKS", "EMERGENCY TALKS"),
     ("MEDIATORS PRESSED;", "AID-VEHICLE STRIKE.")),
]

# The 24 list stories: (number, place, headline, day tag, region).
# Regions are the ones shown in the approved image (Basra and the
# EU-Indonesia deal count as ASIA; the UN "killer robots" item and the
# oil item count as WORLD), so the per-region totals come out at
# EUROPE 10, MIDDLE EAST 8, ASIA 6, AMERICAS 5, AFRICA 2, OCEANIA 2,
# WORLD 2 across all 35 stories.
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

# Region strip counts (must add to 35 with the mains above).
REGIONS = [("EUROPE", 10), ("MIDDLE EAST", 8), ("ASIA", 6), ("AMERICAS", 5),
           ("AFRICA", 2), ("OCEANIA", 2), ("WORLD", 2)]

# The day in UTC: (time, description).
UTC = [("01:00", "HONG KONG VOTES"),
       ("04:00", "VERSTAPPEN WINS F1"),
       ("08:00", "COP31 PLENARY"),
       ("16:30", "LIVERPOOL V MAN UTD"),
       ("17:00", "ATP FINAL")]

# Map dots: (number, lon, lat, region, badge offset dx, dy).
# True positions are the geographic ones; the badge is nudged where two
# badges would collide, with a red leader line back to the true spot.
# Projection: x = 724 + (lon + 180) * 0.72, y = 925 + (78 - lat) * 0.72.
DOTS = [
    (1, 30.7, 36.9, "EUROPE", -28, 27),      # Antalya, COP31
    (2, 27.0, 60.0, "EUROPE", -34, 1),       # Gulf of Finland, Sparta II
    (3, 50.6, 26.2, "MIDDLE EAST", 43, -24),  # Bahrain
    (4, 30.3, 50.8, "EUROPE", -39, 15),      # Dymer, Kyiv region
    (5, 34.2, 31.3, "MIDDLE EAST", 17, 19),   # Al-Mawasi, Gaza
    (6, 114.2, 22.3, "ASIA", -20, -14),      # Hong Kong
    (7, 127.0, 37.6, "ASIA", 19, -13),       # Seoul
    (8, -115.1, 36.2, "AMERICAS", -17, -9),  # Las Vegas
    (9, 174.8, -41.3, "OCEANIA", -6, -12),   # Wellington
    (10, -81.3, 29.5, "AMERICAS", -13, -8),  # St Johns River, Florida
    (11, 34.5, 31.5, "MIDDLE EAST", -12, 25),  # Gaza talks
]

# Continent outlines as (lon, lat) points, simplified for a 292x90 map.
# Drawn with the same equirectangular projection as the dots.
NORTH_AMERICA = [
    (-168, 66), (-158, 58), (-152, 60), (-140, 60), (-135, 57), (-130, 54),
    (-125, 49), (-124, 42), (-120, 34), (-114, 29), (-110, 24), (-105, 20),
    (-97, 16), (-92, 15), (-86, 12), (-83, 9), (-79, 9), (-81, 13),
    (-84, 16), (-87, 21), (-90, 21), (-91, 19), (-96, 19), (-97, 26),
    (-93, 30), (-89, 30), (-84, 30), (-81, 25), (-80, 32), (-76, 35),
    (-74, 40), (-70, 42), (-68, 45), (-65, 44), (-60, 47), (-55, 47),
    (-60, 52), (-64, 58), (-68, 58), (-72, 62), (-78, 62), (-85, 66),
    (-92, 66), (-95, 69), (-110, 68), (-125, 70), (-140, 70), (-155, 71),
    (-165, 68),
]
GREENLAND = [(-58, 64), (-52, 60), (-43, 60), (-40, 64), (-32, 68),
             (-25, 70), (-22, 74), (-30, 76), (-45, 76), (-58, 74)]
SOUTH_AMERICA = [
    (-79, 9), (-77, 4), (-80, -3), (-81, -6), (-77, -12), (-72, -18),
    (-70, -23), (-70, -30), (-72, -37), (-73, -44), (-74, -50), (-70, -54),
    (-66, -55), (-68, -50), (-65, -45), (-62, -40), (-57, -35), (-52, -32),
    (-48, -28), (-41, -23), (-39, -17), (-35, -9), (-35, -6), (-40, -3),
    (-44, -2), (-50, 0), (-53, 4), (-58, 6), (-62, 9), (-68, 11),
    (-72, 12), (-77, 8),
]
EUROPE = [
    (-10, 36), (-9, 37), (-9, 43), (-2, 44), (-1, 46), (-4, 48), (-2, 50),
    (2, 51), (4, 53), (8, 57), (11, 58), (7, 61), (10, 64), (13, 66),
    (18, 69), (24, 71), (30, 70), (30, 66), (24, 60), (21, 55), (19, 54),
    (14, 54), (10, 57), (8, 55), (3, 53), (0, 50), (-2, 49), (-5, 48),
    (-2, 46), (-1, 43), (-6, 43), (-9, 38),
]
BRITAIN = [(-5, 50), (-3, 53), (-5, 56), (-3, 58), (-1, 57), (0, 53), (-1, 51)]
AFRICA = [
    (-17, 15), (-17, 21), (-15, 27), (-10, 31), (-6, 34), (0, 36), (10, 37),
    (11, 34), (20, 32), (30, 31), (32, 31), (34, 28), (35, 23), (37, 18),
    (40, 15), (43, 12), (48, 11), (51, 12), (48, 6), (42, 0), (40, -5),
    (38, -10), (36, -18), (33, -26), (28, -33), (20, -35), (17, -32),
    (15, -27), (13, -18), (12, -10), (9, -1), (9, 4), (-8, 5), (-13, 8),
    (-17, 12),
]
MADAGASCAR = [(44, -16), (47, -15), (50, -16), (49, -20), (45, -25), (43, -22)]
ASIA = [
    (30, 70), (40, 68), (50, 69), (60, 69), (70, 72), (80, 73), (90, 75),
    (100, 76), (110, 74), (120, 73), (130, 72), (140, 72), (150, 70),
    (158, 66), (162, 60), (158, 56), (155, 60), (150, 60), (145, 60),
    (142, 55), (140, 50), (135, 45), (130, 42), (127, 40), (122, 38),
    (120, 32), (122, 28), (118, 25), (110, 21), (108, 18), (105, 10),
    (103, 8), (100, 8), (98, 10), (95, 15), (92, 18), (90, 22), (88, 22),
    (86, 20), (84, 19), (80, 15), (77, 8), (75, 12), (73, 16), (70, 20),
    (66, 25), (62, 25), (58, 26), (56, 27), (52, 26), (50, 28), (48, 30),
    (44, 29), (42, 27), (40, 28), (38, 30), (36, 36), (33, 36), (30, 36),
    (27, 38), (26, 40), (28, 42), (30, 44), (28, 46), (30, 48), (28, 52),
    (30, 56), (30, 60), (30, 66),
]
AUSTRALIA = [
    (114, -22), (114, -30), (115, -35), (118, -35), (124, -33), (129, -32),
    (132, -32), (135, -35), (138, -35), (140, -38), (145, -38), (150, -37),
    (153, -32), (153, -27), (150, -22), (146, -19), (142, -15), (142, -11),
    (137, -12), (135, -15), (132, -17), (130, -13), (127, -14), (122, -17),
    (118, -20),
]
TASMANIA = [(145, -41), (148, -41), (148, -43), (146, -43)]
NEW_ZEALAND = [
    (167, -45), (170, -42), (173, -41), (175, -38), (177, -38), (175, -40),
    (172, -43), (169, -46),
]
CONTINENTS = [NORTH_AMERICA, GREENLAND, SOUTH_AMERICA, EUROPE, BRITAIN,
              AFRICA, MADAGASCAR, ASIA, AUSTRALIA, TASMANIA, NEW_ZEALAND]


# ---------------------------------------------------------------- scenes
# Each scene draws inside its own box (x, y, w, h). The drawings are simple
# flat shapes — sky, ground, one subject, a few details — in the same style
# as the approved image: no stretched or flattened elements.
def _sky(cv, x, y, w, h, top, bot):
    cv.vgrad(x, y, w, h, top, bot)


def _cloud(cv, x, y, s, c=WHITE):
    cv.ellipse(x, y, int(16 * s), int(6 * s), c)
    cv.ellipse(x + int(12 * s), y - int(3 * s), int(11 * s), int(5 * s), c)
    cv.ellipse(x - int(13 * s), y + int(2 * s), int(10 * s), int(5 * s), c)


def scene_globe(cv, x, y, w, h):
    """Card 1 — COP31: a globe with a judge's gavel."""
    _sky(cv, x, y, w, h, (190, 213, 234), (221, 235, 244))
    _cloud(cv, x + int(w * 0.22), y + int(h * 0.18), 1.0)
    _cloud(cv, x + int(w * 0.82), y + int(h * 0.30), 0.8)
    cv.circle(x + int(w * 0.84), y + int(h * 0.20), 14, (252, 210, 90))
    gx, gy, gr = x + int(w * 0.36), y + int(h * 0.52), 44
    cv.circle(gx, gy, gr, (38, 90, 140))
    cv.ellipse(gx - 18, gy - 14, 13, 8, (46, 125, 79))
    cv.ellipse(gx + 12, gy + 8, 15, 9, (46, 125, 79))
    cv.ellipse(gx + 4, gy - 26, 9, 6, (46, 125, 79))
    # gavel: horizontal head upper-middle, handle down-right, sound block
    cv.rect(x + int(w * 0.45), y + int(h * 0.16), 90, 14, (122, 82, 40))
    cv.rect(x + int(w * 0.45), y + int(h * 0.16), 90, 4, (146, 104, 54))
    cv.line(x + int(w * 0.60), y + int(h * 0.26),
            x + int(w * 0.82), y + int(h * 0.78), (122, 82, 40))
    cv.line(x + int(w * 0.60) + 1, y + int(h * 0.26),
            x + int(w * 0.82) + 1, y + int(h * 0.78), (122, 82, 40))
    cv.rect(x + int(w * 0.68), y + int(h * 0.82), 70, 10, (96, 62, 28))


def scene_ship(cv, x, y, w, h):
    """Card 2 — Sparta II burning off Finland."""
    _sky(cv, x, y, w, h, (198, 214, 230), (226, 232, 238))
    cv.circle(x + int(w * 0.30), y + int(h * 0.16), 12, (120, 128, 140))
    cv.circle(x + int(w * 0.38), y + int(h * 0.10), 15, (120, 128, 140))
    cv.circle(x + int(w * 0.46), y + int(h * 0.16), 11, (120, 128, 140))
    cv.rect(x + int(w * 0.10), y + int(h * 0.52), 90, 22, (230, 120, 40))
    cv.rect(x + int(w * 0.10), y + int(h * 0.52), 90, 6, (244, 150, 70))
    cv.rect(x + int(w * 0.42), y + int(h * 0.44), 80, 22, (46, 125, 79))
    cv.rect(x + int(w * 0.42), y + int(h * 0.44), 80, 6, (70, 155, 100))
    cv.rect(x + int(w * 0.70), y + int(h * 0.52), 70, 22, (230, 190, 60))
    # fire licking up from the containers
    for fx, fh in ((0.16, 26), (0.28, 34), (0.48, 30), (0.60, 22), (0.76, 26)):
        cv.tri([(x + int(w * fx) - 10, y + int(h * 0.54)),
                (x + int(w * fx), y + int(h * 0.54) - fh),
                (x + int(w * fx) + 10, y + int(h * 0.54))], (240, 120, 20))
        cv.tri([(x + int(w * fx) - 5, y + int(h * 0.54)),
                (x + int(w * fx), y + int(h * 0.54) - fh + 12),
                (x + int(w * fx) + 5, y + int(h * 0.54))], (252, 200, 60))
    # hull + sea
    cv.poly([(x + 6, y + int(h * 0.68)), (x + w - 6, y + int(h * 0.68)),
             (x + w - 30, y + int(h * 0.82)), (x + 30, y + int(h * 0.82))],
            (24, 32, 48))
    cv.vgrad(x, y + int(h * 0.82), w, h - int(h * 0.82), (38, 90, 140),
             (30, 70, 110))
    cv.line(x + 10, y + int(h * 0.86), x + 60, y + int(h * 0.86), WHITE)
    cv.line(x + int(w * 0.55), y + int(h * 0.90), x + int(w * 0.75),
            y + int(h * 0.90), WHITE)
    cv.line(x + int(w * 0.80), y + int(h * 0.86), x + int(w * 0.95),
            y + int(h * 0.86), WHITE)
    # red flag on the stern (right)
    cv.line(x + int(w * 0.88), y + int(h * 0.30), x + int(w * 0.88),
            y + int(h * 0.52), (60, 60, 70))
    cv.tri([(x + int(w * 0.88), y + int(h * 0.30)),
            (x + int(w * 0.88) - 18, y + int(h * 0.34)),
            (x + int(w * 0.88), y + int(h * 0.38))], RED)


def scene_tanker(cv, x, y, w, h):
    """Card 3 — Bahrain: a tanker on a night sea, moon and stars."""
    _sky(cv, x, y, w, h, (13, 21, 45), (15, 24, 50))
    for sx, sy in ((0.08, 0.10), (0.22, 0.22), (0.40, 0.08), (0.55, 0.18),
                   (0.70, 0.07), (0.90, 0.20), (0.95, 0.08)):
        cv.circle(x + int(w * sx), y + int(h * sy), 2, WHITE)
    cv.circle(x + int(w * 0.78), y + int(h * 0.22), 16, (240, 210, 120))
    cv.circle(x + int(w * 0.82), y + int(h * 0.20), 14, (15, 24, 50))
    # green globe, lower right
    gx, gy, gr = x + int(w * 0.86), y + int(h * 0.62), 20
    cv.circle(gx, gy, gr, (46, 125, 79))
    cv.ellipse(gx - 6, gy - 8, 7, 5, (120, 190, 140))
    cv.ellipse(gx + 5, gy + 6, 8, 5, (120, 190, 140))
    # tanker hull
    cv.rect(x + int(w * 0.08), y + int(h * 0.56), int(w * 0.62), 16,
            (30, 70, 110))
    cv.rect(x + int(w * 0.08), y + int(h * 0.50), int(w * 0.20), 12,
            (30, 70, 110))
    cv.rect(x + int(w * 0.62), y + int(h * 0.56), 14, 16, (24, 32, 48))
    for lx in (0.14, 0.24, 0.34, 0.44, 0.54, 0.64):
        cv.circle(x + int(w * lx), y + int(h * 0.60), 2, (252, 210, 90))
    # fire on the tanker deck, two plumes with smoke
    for fx in (0.34, 0.58):
        cv.tri([(x + int(w * fx) - 8, y + int(h * 0.56)),
                (x + int(w * fx), y + int(h * 0.56) - 22),
                (x + int(w * fx) + 8, y + int(h * 0.56))], (240, 120, 20))
        cv.tri([(x + int(w * fx) - 4, y + int(h * 0.56)),
                (x + int(w * fx), y + int(h * 0.56) - 12),
                (x + int(w * fx) + 4, y + int(h * 0.56))], (252, 200, 60))
    cv.circle(x + int(w * 0.34), y + int(h * 0.28), 9, (120, 128, 140))
    cv.circle(x + int(w * 0.58), y + int(h * 0.24), 11, (120, 128, 140))
    cv.circle(x + int(w * 0.46), y + int(h * 0.20), 8, (140, 146, 152))
    cv.vgrad(x, y + int(h * 0.72), w, h - int(h * 0.72), (20, 40, 70),
             (13, 26, 48))
    for lx, ly in ((0.10, 0.78), (0.30, 0.84), (0.55, 0.80), (0.75, 0.88)):
        cv.line(x + int(w * lx), y + int(h * ly), x + int(w * lx) + 34,
                y + int(h * ly), (90, 120, 160))


def scene_building(cv, x, y, w, h):
    """Card 4 — Kyiv: a shelled block of flats, smoke and dust."""
    _sky(cv, x, y, w, h, (150, 158, 168), (200, 200, 196))
    cv.circle(x + int(w * 0.72), y + int(h * 0.20), 16, (120, 128, 140))
    cv.circle(x + int(w * 0.82), y + int(h * 0.12), 13, (140, 146, 152))
    cv.circle(x + int(w * 0.62), y + int(h * 0.12), 11, (120, 128, 140))
    # the block of flats, corner blown off
    cv.rect(x + int(w * 0.14), y + int(h * 0.30), int(w * 0.55), int(h * 0.55),
            (88, 98, 116))
    cv.tri([(x + int(w * 0.14), y + int(h * 0.30)),
            (x + int(w * 0.42), y + int(h * 0.30)),
            (x + int(w * 0.14), y + int(h * 0.52))], (60, 66, 80))
    for wx in range(4):
        for wy in range(3):
            cv.rect(x + int(w * (0.22 + wx * 0.11)), y + int(h * (0.40 + wy * 0.15)),
                    10, 8, (252, 210, 90))
    cv.rect(x + int(w * 0.30), y + int(h * 0.40), 10, 8, (40, 44, 54))
    # rubble at the base
    cv.tri([(x + int(w * 0.08), y + int(h * 0.88)),
            (x + int(w * 0.30), y + int(h * 0.88) - 18),
            (x + int(w * 0.52), y + int(h * 0.88))], (120, 116, 106))
    cv.tri([(x + int(w * 0.48), y + int(h * 0.88)),
            (x + int(w * 0.66), y + int(h * 0.88) - 12),
            (x + int(w * 0.84), y + int(h * 0.88))], (140, 136, 124))
    cv.rect(x, y + int(h * 0.88), w, h - int(h * 0.88), (110, 106, 96))


def scene_tents(cv, x, y, w, h):
    """Card 5 — Al-Mawasi: tents in the rain, flood water below."""
    _sky(cv, x, y, w, h, (120, 136, 156), (170, 180, 190))
    cv.circle(x + int(w * 0.20), y + int(h * 0.14), 14, (200, 206, 212))
    cv.circle(x + int(w * 0.70), y + int(h * 0.22), 18, (190, 196, 202))
    # three tents
    for tx, tw, th in ((0.10, 0.26, 0.34), (0.40, 0.30, 0.40), (0.72, 0.22, 0.30)):
        bx = x + int(w * tx)
        by = y + int(h * 0.68)
        cv.tri([(bx, by), (bx + int(w * tw) // 2, by - int(h * th)),
                (bx + int(w * tw), by)], (196, 164, 104))
        cv.tri([(bx + int(w * tw) // 2 - 6, by),
                (bx + int(w * tw) // 2, by - int(h * th)),
                (bx + int(w * tw) // 2 + 6, by)], (160, 128, 76))
    # rain
    for rx in range(0, w, 18):
        cv.line(x + rx, y + int(h * 0.10), x + rx - 6, y + int(h * 0.34),
                (140, 160, 190))
        cv.line(x + rx + 8, y + int(h * 0.40), x + rx + 2, y + int(h * 0.60),
                (140, 160, 190))
    # flood water
    cv.vgrad(x, y + int(h * 0.68), w, h - int(h * 0.68), (60, 110, 130),
             (40, 80, 100))
    for lx in (0.06, 0.30, 0.55, 0.78):
        cv.line(x + int(w * lx), y + int(h * 0.76), x + int(w * lx) + 30,
                y + int(h * 0.76), (150, 190, 210))
    # a figure wading
    fx = x + int(w * 0.52)
    cv.circle(fx, y + int(h * 0.66), 4, (40, 44, 54))
    cv.rect(fx - 3, y + int(h * 0.66) + 4, 6, 12, (40, 44, 54))


def scene_towers(cv, x, y, w, h):
    """Card 6 — Hong Kong: towers with lit windows, red flag on top."""
    _sky(cv, x, y, w, h, (176, 200, 226), (214, 226, 236))
    _cloud(cv, x + int(w * 0.18), y + int(h * 0.16), 0.9)
    _cloud(cv, x + int(w * 0.78), y + int(h * 0.12), 0.8)
    towers = [(0.08, 0.62, 0.20), (0.32, 0.80, 0.20), (0.56, 0.66, 0.18),
              (0.76, 0.52, 0.16)]
    for tx, th, tw in towers:
        bx = x + int(w * tx)
        by = y + h
        cv.rect(bx, by - int(h * th), int(w * tw), int(h * th), (40, 58, 92))
        for wy in range(4):
            for wx in range(2):
                if (wx + wy) % 2 == 0:
                    cv.rect(bx + 6 + wx * 16, by - int(h * th) + 8 + wy * 12,
                            7, 6, (252, 210, 90))
    # red flag on the tallest tower
    fx = x + int(w * 0.42)
    cv.line(fx, y + int(h * 0.06), fx, y + int(h * 0.20), (60, 60, 70))
    cv.rect(fx, y + int(h * 0.06), 22, 12, (200, 30, 30))
    cv.rect(x, y + int(h * 0.92), w, h - int(h * 0.92), (70, 76, 88))


def scene_desk(cv, x, y, w, h):
    """Card 7 — Seoul: a desk with exam papers, pencil, cup and clock."""
    _sky(cv, x, y, w, h, (198, 178, 138), (214, 198, 162))
    # wall clock
    cv.circle(x + int(w * 0.80), y + int(h * 0.20), 14, WHITE)
    cv.circle(x + int(w * 0.80), y + int(h * 0.20), 14, (40, 44, 54))
    cv.circle(x + int(w * 0.80), y + int(h * 0.20), 12, WHITE)
    cv.line(x + int(w * 0.80), y + int(h * 0.20), x + int(w * 0.80) + 6,
            y + int(h * 0.20) - 6, (40, 44, 54))
    cv.line(x + int(w * 0.80), y + int(h * 0.20), x + int(w * 0.80),
            y + int(h * 0.20) - 9, (40, 44, 54))
    # desk
    cv.rect(x, y + int(h * 0.62), w, h - int(h * 0.62), (146, 104, 54))
    cv.rect(x, y + int(h * 0.62), w, 5, (168, 126, 72))
    # papers
    cv.rect(x + int(w * 0.12), y + int(h * 0.42), int(w * 0.34), int(h * 0.22),
            WHITE)
    cv.line(x + int(w * 0.16), y + int(h * 0.48), x + int(w * 0.40),
            y + int(h * 0.48), (120, 124, 132))
    cv.line(x + int(w * 0.16), y + int(h * 0.54), x + int(w * 0.40),
            y + int(h * 0.54), (120, 124, 132))
    cv.rect(x + int(w * 0.50), y + int(h * 0.50), int(w * 0.28), int(h * 0.16),
            (240, 236, 224))
    cv.line(x + int(w * 0.53), y + int(h * 0.56), x + int(w * 0.74),
            y + int(h * 0.56), (120, 124, 132))
    # yellow pencil
    cv.line(x + int(w * 0.16), y + int(h * 0.30), x + int(w * 0.44),
            y + int(h * 0.36), (252, 210, 90))
    cv.line(x + int(w * 0.16), y + int(h * 0.30) + 1, x + int(w * 0.44),
            y + int(h * 0.36) + 1, (252, 210, 90))
    # cup
    cv.rect(x + int(w * 0.84), y + int(h * 0.44), 16, 18, (46, 125, 79))
    cv.rect(x + int(w * 0.84), y + int(h * 0.44), 16, 5, (70, 155, 100))


def scene_race(cv, x, y, w, h):
    """Card 8 — Las Vegas GP: two race cars under a checkered flag."""
    _sky(cv, x, y, w, h, (21, 26, 42), (30, 36, 58))
    for sx, sy in ((0.06, 0.10), (0.30, 0.06), (0.52, 0.14), (0.74, 0.08),
                   (0.92, 0.16), (0.14, 0.26), (0.66, 0.24)):
        cv.circle(x + int(w * sx), y + int(h * sy), 2, WHITE)
    # checkered flag
    fx, fy = x + int(w * 0.44), y + int(h * 0.06)
    for r in range(4):
        for c in range(5):
            if (r + c) % 2 == 0:
                cv.rect(fx + c * 7, fy + r * 7, 7, 7, WHITE)
            else:
                cv.rect(fx + c * 7, fy + r * 7, 7, 7, (24, 32, 48))
    cv.line(fx, fy + 28, fx, fy + 52, (120, 124, 132))
    # road
    cv.rect(x, y + int(h * 0.60), w, h - int(h * 0.60), (40, 44, 54))
    for dx in range(0, w, 34):
        cv.rect(x + dx, y + int(h * 0.78), 18, 4, (252, 210, 90))
    # red car (leader)
    _car(cv, x + int(w * 0.10), y + int(h * 0.52), 86, (200, 30, 30))
    # blue car (chaser)
    _car(cv, x + int(w * 0.58), y + int(h * 0.66), 78, (31, 78, 156))


def _car(cv, x, y, w, colour):
    cv.rect(x, y + 8, w, 12, colour)
    cv.rect(x + 14, y, w - 34, 10, colour)
    cv.rect(x + 18, y + 2, 16, 7, (200, 226, 240))
    cv.circle(x + 16, y + 22, 8, (24, 32, 48))
    cv.circle(x + w - 16, y + 22, 8, (24, 32, 48))
    cv.circle(x + 16, y + 22, 3, (160, 164, 172))
    cv.circle(x + w - 16, y + 22, 3, (160, 164, 172))


def scene_cricket(cv, x, y, w, h):
    """Card 9 — Wellington: a batsman on the green, score 720/9."""
    _sky(cv, x, y, w, h, (120, 170, 100), (150, 195, 130))
    cv.vgrad(x, y + int(h * 0.30), w, h - int(h * 0.30), (46, 125, 79),
             (34, 100, 62))
    # pitch
    cv.rect(x + int(w * 0.42), y + int(h * 0.30), int(w * 0.16), int(h * 0.62),
            (214, 198, 162))
    # batsman: dark helmet and pads, white shirt, on the pitch edge
    bx = x + int(w * 0.46)
    cv.circle(bx, y + int(h * 0.36), 8, (24, 32, 48))
    cv.rect(bx - 6, y + int(h * 0.36) + 8, 12, 24, (255, 252, 244))
    cv.line(bx - 5, y + int(h * 0.36) + 32, bx - 9, y + int(h * 0.72),
            (24, 32, 48))
    cv.line(bx + 5, y + int(h * 0.36) + 32, bx + 9, y + int(h * 0.72),
            (24, 32, 48))
    cv.line(bx + 9, y + int(h * 0.48), bx + 24, y + int(h * 0.68),
            (160, 120, 60))
    cv.line(bx + 9, y + int(h * 0.48) + 1, bx + 24, y + int(h * 0.68) + 1,
            (160, 120, 60))
    # red ball
    cv.circle(x + int(w * 0.74), y + int(h * 0.72), 6, (200, 30, 30))
    # stumps
    for sx in (0.44, 0.47, 0.50):
        cv.line(x + int(w * sx), y + int(h * 0.30), x + int(w * sx),
                y + int(h * 0.30) + 12, (252, 210, 90))
    draw_text(cv, x + int(w * 0.10), y + int(h * 0.12), "720/9", 1.4, WHITE,
              bold=True)


def scene_flood(cv, x, y, w, h):
    """Card 10 — Florida: a flooded house, palm and boat in the rain."""
    _sky(cv, x, y, w, h, (110, 124, 140), (160, 170, 180))
    for rx in range(0, w, 20):
        cv.line(x + rx, y + int(h * 0.06), x + rx - 5, y + int(h * 0.24),
                (140, 160, 190))
    # house
    hx, hy = x + int(w * 0.12), y + int(h * 0.34)
    cv.rect(hx, hy + 18, int(w * 0.42), 26, (240, 232, 210))
    cv.tri([(hx - 6, hy + 18), (hx + int(w * 0.21), hy),
            (hx + int(w * 0.42) + 6, hy + 18)], (230, 120, 40))
    cv.rect(hx + 12, hy + 26, 12, 10, (60, 80, 110))
    cv.rect(hx + int(w * 0.42) - 24, hy + 26, 12, 10, (60, 80, 110))
    # palm tree
    px0 = x + int(w * 0.70)
    cv.line(px0, y + int(h * 0.62), px0 + 4, y + int(h * 0.30), (110, 80, 40))
    for dx, dy in ((-18, -8), (-12, -16), (16, -10), (20, -2), (0, -20)):
        cv.line(px0 + 4, y + int(h * 0.30), px0 + 4 + dx, y + int(h * 0.30) + dy,
                (46, 125, 79))
    # flood water
    cv.vgrad(x, y + int(h * 0.62), w, h - int(h * 0.62), (38, 90, 140),
             (30, 70, 110))
    for lx in (0.05, 0.30, 0.55, 0.80):
        cv.line(x + int(w * lx), y + int(h * 0.72), x + int(w * lx) + 28,
                y + int(h * 0.72), (150, 190, 210))
    # small boat
    cv.poly([(x + int(w * 0.62), y + int(h * 0.78)),
             (x + int(w * 0.82), y + int(h * 0.78)),
             (x + int(w * 0.78), y + int(h * 0.88)),
             (x + int(w * 0.66), y + int(h * 0.88))], (230, 190, 60))
    cv.line(x + int(w * 0.72), y + int(h * 0.78), x + int(w * 0.72),
            y + int(h * 0.66), (60, 60, 70))


def scene_talks(cv, x, y, w, h):
    """Card 11 — Gaza talks: two figures at a table, window, plant."""
    _sky(cv, x, y, w, h, (206, 188, 152), (226, 212, 182))
    # window with mountains
    wx, wy = x + int(w * 0.60), y + int(h * 0.08)
    cv.rect(wx, wy, int(w * 0.32), int(h * 0.40), (150, 190, 220))
    cv.rect(wx, wy, int(w * 0.32), int(h * 0.40), (40, 44, 54))
    cv.rect(wx + 3, wy + 3, int(w * 0.32) - 6, int(h * 0.40) - 6,
            (150, 190, 220))
    cv.tri([(wx + 3, wy + int(h * 0.40) - 3),
            (wx + int(w * 0.10), wy + int(h * 0.16)),
            (wx + int(w * 0.18), wy + int(h * 0.40) - 3)], (90, 110, 130))
    cv.tri([(wx + int(w * 0.12), wy + int(h * 0.40) - 3),
            (wx + int(w * 0.22), wy + int(h * 0.22)),
            (wx + int(w * 0.32) - 3, wy + int(h * 0.40) - 3)], (70, 90, 110))
    cv.line(wx + int(w * 0.16), wy + 3, wx + int(w * 0.16),
            wy + int(h * 0.40) - 3, (40, 44, 54))
    # table
    cv.rect(x, y + int(h * 0.66), w, h - int(h * 0.66), (120, 84, 44))
    cv.rect(x, y + int(h * 0.66), w, 5, (146, 104, 54))
    # documents on the table
    cv.rect(x + int(w * 0.42), y + int(h * 0.60), int(w * 0.20), 10, WHITE)
    cv.rect(x + int(w * 0.66), y + int(h * 0.62), int(w * 0.16), 8,
            (240, 236, 224))
    # two figures
    for fx, suit in ((0.18, (24, 32, 48)), (0.34, (31, 78, 156))):
        fx = x + int(w * fx)
        cv.circle(fx, y + int(h * 0.44), 7, (220, 180, 150))
        cv.rect(fx - 7, y + int(h * 0.44) + 7, 14, 18, suit)
        cv.rect(fx - 2, y + int(h * 0.44) + 7, 4, 12, WHITE)
    # plant, lower left
    cv.rect(x + int(w * 0.06), y + int(h * 0.56), 12, 12, (178, 84, 30))
    for dx, dy in ((-8, -14), (0, -18), (8, -14), (-4, -20), (6, -20)):
        cv.line(x + int(w * 0.06) + 6, y + int(h * 0.56),
                x + int(w * 0.06) + 6 + dx, y + int(h * 0.56) + dy,
                (46, 125, 79))


SCENES = {
    1: scene_globe, 2: scene_ship, 3: scene_tanker, 4: scene_building,
    5: scene_tents, 6: scene_towers, 7: scene_desk, 8: scene_race,
    9: scene_cricket, 10: scene_flood, 11: scene_talks,
}


# ---------------------------------------------------------------- layout
TOP = "THE WORLD IN ONE DAY"
TOP_RIGHT = "35 STORIES · 7 REGIONS · EVERY ONE DATED SUNDAY, 22 NOVEMBER 2026"
DATE = "SUNDAY, 22 NOVEMBER 2026"
SUMMARY = ("COP31 COLLAPSES WITH NO DEAL · SPARTA II STILL BURNING · "
           "BAHRAIN SEEKS UN ACTION ON IRAN")
LIST_TITLE = "ALSO ON SUNDAY, 22 NOVEMBER — 24 MORE STORIES"
FOOTER = ("EUROPE 10 · MIDDLE EAST 8 · ASIA 6 · AMERICAS 5 · AFRICA 2 · "
          "OCEANIA 2 · WORLD 2 · SOURCES: REUTERS, AP, BBC, AL JAZEERA, "
          "F1.COM, CRICBUZZ")

REGION_EDGES = [24, 163, 303, 442, 582, 721, 861, 1000]
UTC_DIVIDERS = [346, 509, 673, 836]      # lighter-navy column dividers
UTC_DIVCOL = (52, 72, 110)
UTC_COL0 = 182                            # first UTC column starts here
UTC_COLW = 163.6                          # each UTC column is this wide

LARGE_X = [24, 352, 680]
SMALL_X = [24, 269, 514, 759]


def draw_segments(cv, x, y, segments, unit, track=0.0, upper=False):
    """Draw a line made of (text, colour, bold) segments, left to right."""
    cx = float(x)
    for text, colour, bold in segments:
        w = draw_text(cv, cx, y, text, unit, colour, bold, track, upper)
        cx += w + track
    return cx - x


def draw_header(cv):
    # top black strip
    cv.rect(0, 0, W, 28, STRIP)
    draw_text(cv, 24, 5, TOP, 1.75, GOLD, bold=True, track=0.65)
    draw_text_right(cv, 998, 14, TOP_RIGHT, 0.8, (205, 210, 215), track=0.45)
    # giant date + red summary + thick rule
    draw_text_centred(cv, 512, 36, DATE, 3.5, INK, bold=True, track=2.9)
    draw_text_centred(cv, 512, 77, SUMMARY, 1.0, RED, track=1.0)
    cv.rect(24, 91, 976, 3, INK)
    # region strip: 7 equal blocks, white bold counts
    for i, (name, count) in enumerate(REGIONS):
        x0 = REGION_EDGES[i]
        x1 = REGION_EDGES[i + 1]
        cv.rect(x0, 99, x1 - x0, 16, REGION[name])
        draw_text_centred(cv, (x0 + x1) / 2.0, 102, "%s %d" % (name, count),
                          1.0, WHITE, bold=True)
    # UTC strip
    cv.rect(24, 120, 976, 38, NAVY)
    draw_text(cv, 24, 133, "THE DAY IN UTC", 1.0, UTCGOLD, track=1.0)
    for dx in UTC_DIVIDERS:
        cv.vline(dx, 125, 152, UTC_DIVCOL)
    for i, (time, desc) in enumerate(UTC):
        cx = UTC_COL0 + UTC_COLW * (i + 0.5)
        draw_text_centred(cv, cx, 124, time, 1.2, WHITE, bold=True, track=0.7)
        draw_text_centred(cv, cx, 140, desc, 0.85, UTCDESC, track=1.0)


def draw_badge(cv, cx, cy, r, number, colour):
    """A region-coloured disc with a white ring and a white bold number."""
    cv.circle(cx, cy, r + 1, WHITE)
    cv.circle(cx, cy, r, colour)
    draw_text_centred(cv, cx, cy - 5, str(number), 1.1, WHITE, bold=True)


def draw_card(cv, num, x, y, w, large):
    _, region, place, titles, subs = MAINS[num - 1]
    colour = REGION[region]
    h = 216 if large else 154
    # card body + navy border on left, right and bottom
    cv.rect(x, y, w, h, CARD)
    cv.vline(x, y, y + h - 1, NAVY)
    cv.vline(x + w - 1, y, y + h - 1, NAVY)
    cv.hline(x, x + w - 1, y + h - 1, NAVY)
    if large:
        head_h = 20
        scene_y, scene_h = y + 21, 135
        rule_y = y + 159
        title_y = y + 167
        sub_y = y + 185
        badge_c = (x + 20, scene_y + 15)
        badge_r = 11
    else:
        head_h = 14
        scene_y, scene_h = y + 15, 68
        rule_y = y + 89
        title_y = y + 94
        sub_y = y + 126
        badge_c = (x + 16, scene_y + 11)
        badge_r = 9
    # header strip first, then its white text on top of it
    cv.rect(x, y, w, head_h, colour)
    if large:
        draw_text(cv, x + 11, y + 6, "%d · %s · %s" % (num, region, place),
                  1.0, WHITE, bold=True, track=0.9)
    else:
        draw_text(cv, x + 8, y + 2, "%d · %s" % (num, region),
                  1.0, WHITE, bold=True)
    SCENES[num](cv, x + 1, scene_y, w - 2, scene_h)
    draw_badge(cv, badge_c[0], badge_c[1], badge_r, num, RED)
    cv.hline(x + 12, x + w - 13, rule_y, RULEC)
    tx = x + 12
    if large:
        draw_text(cv, tx, title_y, titles[0], 1.25, INK, bold=True, track=1.0)
        draw_text(cv, tx, sub_y, subs[0], 1.15, colour, track=1.8)
        draw_text(cv, tx, sub_y + 16, subs[1], 1.15, colour, track=1.8)
    else:
        draw_text(cv, tx, title_y, titles[0], 1.25, INK, bold=True, track=1.0)
        draw_text(cv, tx, title_y + 16, titles[1], 1.25, INK, bold=True,
                  track=1.0)
        draw_text(cv, tx, sub_y, subs[0], 1.0, colour, track=1.8)
        draw_text(cv, tx, sub_y + 13, subs[1], 1.0, colour, track=1.8)


def draw_list(cv):
    draw_text(cv, 24, 707, LIST_TITLE, 1.5, RED, bold=True, track=1.25)
    cv.hline(24, 999, 726, RED)
    for i, (num, place, head, tag, region) in enumerate(LIST):
        col = 0 if i < 12 else 1
        row = i % 12
        y = 728 + row * 14 + 4
        x0 = 24 if col == 0 else 512
        tag_x1 = 496 if col == 0 else 992
        text = "%d. %s — %s" % (num, place, head)
        draw_text(cv, x0, y, text, 0.75, REGION[region])
        draw_text_right(cv, tag_x1, y, "[%s]" % tag, 0.75, TAGCOL[tag])


def project(lon, lat):
    """Map lon/lat to pixels: equal scale, lon -180 at x=724, lat 78 at y=925."""
    return (724 + (lon + 180) * 0.72, 925 + (78 - lat) * 0.72)


def draw_map(cv, x, y, w, h):
    cv.rect(x, y, w, h, SEA)
    for poly_lonlat in CONTINENTS:
        pts = [(int(round(px)), int(round(py)))
               for px, py in (project(lon, lat) for lon, lat in poly_lonlat)]
        cv.poly(pts, LAND)
    # leader lines + dots
    for num, lon, lat, region, dx, dy in DOTS:
        tx, ty = project(lon, lat)
        tx, ty = int(round(tx)), int(round(ty))
        bx, by = tx + dx, ty + dy
        cv.line(bx, by, tx, ty, RED)
        cv.circle(tx, ty, 2, RED)
        draw_badge(cv, bx, by, 11, num, REGION[region])
    # frame: navy left, right and bottom (top is the label strip)
    cv.vline(x, y, y + h - 1, NAVY)
    cv.vline(x + w - 1, y, y + h - 1, NAVY)
    cv.hline(x, x + w - 1, y + h - 1, NAVY)


def draw_bottom(cv):
    # DATE CHECK box
    cv.rect(24, 908, 676, 107, CARD)
    cv.rect(24, 908, 676, 1, NAVY)
    cv.rect(24, 1014, 676, 1, NAVY)
    cv.vline(24, 908, 1014, NAVY)
    cv.vline(699, 908, 1014, NAVY)
    cv.rect(25, 909, 6, 105, ACCENT)
    cv.rect(31, 909, 668, 12, RED)
    draw_text_centred(cv, 364.5, 909, "DATE CHECK", 1.0, WHITE, bold=True,
                      track=0.9)
    cv.rect(31, 975, 668, 13, RED)
    draw_text_centred(cv, 364.5, 976, "HOW WE CHECKED", 1.0, WHITE, bold=True,
                      track=0.3)
    bx = 39
    draw_text(cv, bx, 923,
              "Every story here happened or was first reported Sun 22 Nov "
              "2026 (UTC), to press", 0.8, SLATE, track=1.0, upper=False)
    draw_text(cv, bx, 933, "time 01:00 UTC", 0.8, SLATE, track=1.0,
              upper=False)
    draw_text(cv, bx, 944, "LEFT OUT BECAUSE THEY HAPPENED ON AN EARLIER DAY:",
              0.8, SLATE, track=1.0)
    draw_segments(cv, bx, 954, [
        ("Paris", INK, True), (" (Sat 21)", RED, False),
        (" · ", SLATE, False), ("Rutte", INK, True),
        (" (Sat 21)", RED, False), (" · ", SLATE, False),
        ("Kryvyi Rih", INK, True), (" (Fri 20)", RED, False),
        (" · ", SLATE, False), ("GTA VI", INK, True),
        (" (Fri 20)", RED, False)], 0.8, track=1.0, upper=False)
    draw_segments(cv, bx, 964, [
        ("US stocks", INK, True), (" (Fri 20)", RED, False),
        (" · ", SLATE, False), ("Riemann", INK, True),
        (" (Fri 20)", RED, False)], 0.8, track=1.0, upper=False)
    draw_text(cv, bx, 992,
              "Every story checked against its event date. Sources: Reuters, "
              "AP, BBC, Al Jazeera,", 0.8, SLATE, track=1.0, upper=False)
    draw_text(cv, bx, 1002, "F1.com, Cricbuzz, govt releases.", 0.8, SLATE,
              track=1.0, upper=False)
    # map
    cv.rect(708, 908, 292, 17, NAVY)
    draw_text(cv, 715, 911, "WHERE IT HAPPENED — DOTS 1-11", 1.0, WHITE,
              bold=True, track=0.6)
    draw_map(cv, 708, 925, 292, 90)
    # footer
    draw_text(cv, 24, 1016, FOOTER, 0.7, GREY, track=1.08)


def render():
    cv = Canvas(W, H, PAPER)
    draw_header(cv)
    for i, x in enumerate(LARGE_X):
        draw_card(cv, i + 1, x, 163, 320, large=True)
    for row, y in enumerate((385, 545)):
        for i, x in enumerate(SMALL_X):
            draw_card(cv, 4 + row * 4 + i, x, y, 241, large=False)
    draw_list(cv)
    draw_bottom(cv)
    return cv


def main(argv):
    out = argv[1] if len(argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "entry-v4.png")
    cv = render()
    if MISSING:
        print("MISSING GLYPHS:", sorted(set(MISSING)))
    write_png(cv, out)
    print("wrote", out)


if __name__ == "__main__":
    main(sys.argv)
