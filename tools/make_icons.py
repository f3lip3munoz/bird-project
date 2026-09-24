"""Generate the app icons (PNG + SVG) for the Libreta de Aves web app.

The icon is a stylised Loica (Leistes loyca) on a perch. All geometry is defined
on a 100x100 grid and shared by the PNG (Pillow) and SVG outputs.

Usage:  python tools/make_icons.py
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parent.parent / "web" / "icons"

BG_TOP, BG_BOTTOM = (34, 110, 84), (18, 66, 51)
CREAM, WING, RED = (246, 239, 226), (214, 196, 163), (214, 69, 58)
BEAK, EYE, PERCH = (242, 165, 65), (22, 34, 29), (122, 86, 52)

BODY = dict(cx=50, cy=58, rx=26, ry=17, rot=-18)
WING_E = dict(cx=45, cy=55, rx=16, ry=8.5, rot=-24)
BREAST = dict(cx=63, cy=58, rx=12, ry=11, rot=0)
HEAD = (68, 40, 12)
EYE_C = (71.5, 38, 2.3)
BEAK_P = [(78.5, 36), (91, 40.5), (78.5, 45)]
TAIL_P = [(29, 60), (9, 71), (13, 63), (7, 56), (28, 52)]
PERCH_L = [(22, 84), (80, 84)]
LEGS = [((49, 73), (47, 84)), ((56, 73), (55, 84))]


def ellipse_poly(cx, cy, rx, ry, rot, n=120):
    a = math.radians(rot)
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x, y = rx * math.cos(t), ry * math.sin(t)
        pts.append((cx + x * math.cos(a) - y * math.sin(a), cy + x * math.sin(a) + y * math.cos(a)))
    return pts


def render_png(size, maskable=False, rounded=True):
    ss = 4
    S = size * ss
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))

    # Vertical gradient background
    grad = Image.new("RGBA", (1, S))
    for y in range(S):
        t = y / (S - 1)
        grad.putpixel((0, y), tuple(int(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * t) for i in range(3)) + (255,))
    grad = grad.resize((S, S))
    mask = Image.new("L", (S, S), 0)
    md = ImageDraw.Draw(mask)
    if rounded and not maskable:
        md.rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * 0.22), fill=255)
    else:
        md.rectangle([0, 0, S, S], fill=255)
    img.paste(grad, (0, 0), mask)

    # Maskable icons keep the bird inside the 80% safe zone
    k = 0.72 if maskable else 0.9
    off = 50 * (1 - k)

    def P(x, y):
        return ((off + x * k) * S / 100, (off + y * k) * S / 100)

    def poly(pts):
        return [P(x, y) for x, y in pts]

    d = ImageDraw.Draw(img)
    w = lambda u: max(1, int(u * k * S / 100))

    d.line(poly(PERCH_L), fill=PERCH, width=w(3.2))
    for a, b in LEGS:
        d.line(poly([a, b]), fill=EYE, width=w(1.8))
    d.polygon(poly(TAIL_P), fill=WING)
    d.polygon(poly(ellipse_poly(**BODY)), fill=CREAM)

    # Red breast clipped to the body
    layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(layer).polygon(poly(ellipse_poly(**BREAST)), fill=RED)
    clip = Image.new("L", (S, S), 0)
    ImageDraw.Draw(clip).polygon(poly(ellipse_poly(**BODY)), fill=255)
    img.paste(layer, (0, 0), Image.composite(layer.split()[3], Image.new("L", (S, S), 0), clip))

    d.polygon(poly(ellipse_poly(**WING_E)), fill=WING)
    hx, hy, hr = HEAD
    d.polygon(poly(ellipse_poly(hx, hy, hr, hr, 0)), fill=CREAM)
    d.polygon(poly(BEAK_P), fill=BEAK)
    ex, ey, er = EYE_C
    d.polygon(poly(ellipse_poly(ex, ey, er, er, 0, 40)), fill=EYE)

    return img.resize((size, size), Image.LANCZOS)


def svg():
    def pts(p):
        return " ".join(f"{x:.2f},{y:.2f}" for x, y in p)

    def ell(e, fill, extra=""):
        return (f'<ellipse cx="{e["cx"]}" cy="{e["cy"]}" rx="{e["rx"]}" ry="{e["ry"]}" '
                f'transform="rotate({e["rot"]} {e["cx"]} {e["cy"]})" fill="{fill}"{extra}/>')

    hex_ = lambda c: "#%02x%02x%02x" % c
    b = BODY
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{hex_(BG_TOP)}"/><stop offset="1" stop-color="{hex_(BG_BOTTOM)}"/></linearGradient>
<clipPath id="body">{ell(BODY, "#000")}</clipPath></defs>
<rect width="100" height="100" rx="22" fill="url(#g)"/>
<g transform="translate(5 5) scale(.9)">
<line x1="22" y1="84" x2="80" y2="84" stroke="{hex_(PERCH)}" stroke-width="3.2" stroke-linecap="round"/>
<path d="M49 73 47 84M56 73 55 84" stroke="{hex_(EYE)}" stroke-width="1.8" stroke-linecap="round"/>
<polygon points="{pts(TAIL_P)}" fill="{hex_(WING)}"/>
{ell(BODY, hex_(CREAM))}
<g clip-path="url(#body)">{ell(BREAST, hex_(RED))}</g>
{ell(WING_E, hex_(WING))}
<circle cx="{HEAD[0]}" cy="{HEAD[1]}" r="{HEAD[2]}" fill="{hex_(CREAM)}"/>
<polygon points="{pts(BEAK_P)}" fill="{hex_(BEAK)}"/>
<circle cx="{EYE_C[0]}" cy="{EYE_C[1]}" r="{EYE_C[2]}" fill="{hex_(EYE)}"/>
</g></svg>
'''


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    render_png(192).save(OUT / "icon-192.png")
    render_png(512).save(OUT / "icon-512.png")
    render_png(512, maskable=True).save(OUT / "maskable-512.png")
    render_png(180, rounded=False).convert("RGB").save(OUT / "apple-touch-icon.png")
    (OUT / "icon.svg").write_text(svg(), encoding="utf-8")
    print("Icons written to", OUT)
