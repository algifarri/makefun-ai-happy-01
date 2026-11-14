#!/usr/bin/env python3
"""ai-happy-01 entry: "The First Paper Plane".

Draws one warm, joyful image and writes it to /output/entry.png
(or $MAKEFUN_OUTPUT_DIR/entry.png outside the grader's container).

The scene: at golden hour in a flower meadow, a small round robot has just
launched a paper plane for its friends. The plane's looping trail draws a
heart in the sky. A laughing grandmother claps, a child leaps mid-air, and
a little dog jumps with its tongue out - everyone is looking up, delighted.

Pure Python standard library, no network, fully deterministic: the same
bytes come out of every run. The picture is rasterised at 2x and box-
downsampled so edges stay clean at any size.
"""

import math
import os
import struct
import zlib

# ---------------------------------------------------------------- canvas

W = H = 1024          # final image size
SS = 2                # supersampling factor
SW, SH = W * SS, H * SS
fb = bytearray(SW * SH * 3)


def C(hexs):
    """'#RRGGBB' -> (r, g, b)"""
    return (int(hexs[1:3], 16), int(hexs[3:5], 16), int(hexs[5:7], 16))


# palette - one warm golden-hour mood
SKY_TOP = C('#FFB066')
SKY_MID = C('#FFD98F')
SKY_LOW = C('#FFF0BE')
SUN_CORE = C('#FFE066')
SUN_GLOW1 = C('#FFD166')
SUN_GLOW2 = C('#FFC98A')
HILL = C('#9CC24F')
MEADOW = C('#7AB648')
MEADOW_DARK = C('#679E3E')
GRASS = C('#5C9138')
CREAM = C('#FFF9EF')
SHADE = C('#F3E2C4')
CORAL = C('#FF6B4A')
CORAL_DARK = C('#E8503A')
GOLD = C('#FFC93C')
ROSE = C('#E56B6F')
ROSE_DARK = C('#C94F57')
SKIN_G = C('#FFD9B3')      # grandmother
SKIN_C = C('#A06A3B')      # child
HAIR_G = C('#F4F4F8')
HAIR_C = C('#3A2A20')
DARK = C('#4A3226')        # eyes / mouths
MOUTH = C('#7A3B2E')
TONGUE = C('#FF9E9E')
CHEEK = C('#FFB3A0')
WHITE = C('#FFFFFF')
PLANE_SHADE = C('#D9E6F2')
WOOD = C('#B5722F')
DOG = C('#E8A34E')
DOG_DARK = C('#B5722F')
STEEL = C('#8C7B6B')

# ---------------------------------------------------------------- basics


def span(y, x0, x1, c):
    if y < 0 or y >= SH:
        return
    if x0 < 0:
        x0 = 0
    if x1 > SW:
        x1 = SW
    if x1 <= x0:
        return
    i = (y * SW + x0) * 3
    fb[i:i + (x1 - x0) * 3] = bytes(c) * (x1 - x0)


def lerp(a, b, t):
    return (int(a[0] + (b[0] - a[0]) * t + 0.5),
            int(a[1] + (b[1] - a[1]) * t + 0.5),
            int(a[2] + (b[2] - a[2]) * t + 0.5))


def ellipse(cx, cy, rx, ry, c):
    """Filled axis-aligned ellipse; coords in final-image units."""
    cx, cy, rx, ry = cx * SS, cy * SS, rx * SS, ry * SS
    y0, y1 = int(cy - ry), int(cy + ry) + 1
    for y in range(y0, y1):
        t = (y + 0.5 - cy) / ry
        if -1.0 <= t <= 1.0:
            dx = rx * math.sqrt(1.0 - t * t)
            span(y, int(cx - dx), int(cx + dx) + 1, c)


def polygon(points, c):
    """Filled polygon from final-image coords, scanline even-odd."""
    pts = [(x * SS, y * SS) for (x, y) in points]
    ys = [p[1] for p in pts]
    y0, y1 = int(min(ys)), int(max(ys)) + 1
    n = len(pts)
    for y in range(y0, y1):
        yc = y + 0.5
        xs = []
        for i in range(n):
            xa, ya = pts[i]
            xb, yb = pts[(i + 1) % n]
            if (ya <= yc < yb) or (yb <= yc < ya):
                xs.append(xa + (xb - xa) * (yc - ya) / (yb - ya))
        xs.sort()
        for i in range(0, len(xs) - 1, 2):
            span(y, int(xs[i]), int(xs[i + 1]) + 1, c)


def rot_ellipse(cx, cy, rx, ry, deg, c, steps=40):
    t = math.radians(deg)
    ca, sa = math.cos(t), math.sin(t)
    pts = []
    for i in range(steps):
        a = 2.0 * math.pi * i / steps
        ex, ey = rx * math.cos(a), ry * math.sin(a)
        pts.append((cx + ex * ca - ey * sa, cy + ex * sa + ey * ca))
    polygon(pts, c)


def stamp(cx, cy, r, c):
    ellipse(cx, cy, r, r, c)


def thick_line(x0, y0, x1, y1, w, c):
    d = math.hypot(x1 - x0, y1 - y0)
    n = max(2, int(d / (w * 0.22)) + 1)
    for i in range(n):
        t = i / (n - 1)
        ellipse(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, w / 2, w / 2, c)


def arc(cx, cy, r, a0, a1, w, c):
    """Thick arc; angles in degrees, 0 = east, positive clockwise (y down)."""
    n = max(4, int(abs(a1 - a0) / 6) + 1)
    for i in range(n):
        a = math.radians(a0 + (a1 - a0) * i / (n - 1))
        ellipse(cx + r * math.cos(a), cy + r * math.sin(a), w / 2, w / 2, c)


def sector(cx, cy, rx, ry, a0, a1, c, steps=28):
    """Filled pie slice of an ellipse between two angles (degrees)."""
    pts = [(cx, cy)]
    for i in range(steps + 1):
        a = math.radians(a0 + (a1 - a0) * i / steps)
        pts.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
    polygon(pts, c)


def rounded_rect(x0, y0, x1, y1, r, c):
    pts = []
    for (cx, cy, a0) in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0),
                         (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
        for i in range(9):
            a = math.radians(a0 + i * 90 / 8)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    polygon(pts, c)


def heart(cx, cy, s, c):
    """Filled heart; s is the half-width, shape ~2s wide and ~1.9s tall."""
    pts = []
    for i in range(48):
        t = 2.0 * math.pi * i / 48
        hx = 16.0 * math.sin(t) ** 3
        hy = (13.0 * math.cos(t) - 5.0 * math.cos(2 * t)
              - 2.0 * math.cos(3 * t) - math.cos(4 * t))
        pts.append((cx + hx * s / 16.0, cy - hy * s / 16.0))
    polygon(pts, c)


def heart_point(t, cx, cy, s):
    hx = 16.0 * math.sin(t) ** 3
    hy = (13.0 * math.cos(t) - 5.0 * math.cos(2 * t)
          - 2.0 * math.cos(3 * t) - math.cos(4 * t))
    return (cx + hx * s / 16.0, cy - hy * s / 16.0)


def star(cx, cy, r, c):
    pts = []
    for i in range(8):
        a = math.radians(-90 + i * 45)
        rr = r if i % 2 == 0 else r * 0.34
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    polygon(pts, c)


# deterministic scatter (fixed-seed LCG; no library randomness)
_seed = [20261114]


def rnd():
    _seed[0] = (_seed[0] * 1103515245 + 12345) & 0x7FFFFFFF
    return _seed[0] / 0x7FFFFFFF


# ---------------------------------------------------------------- backdrop


def backdrop():
    # sky: per-row gradient, warm at the top melting to cream at the horizon
    for y in range(SH):
        t = y / SH
        if t < 0.45:
            c = lerp(SKY_TOP, SKY_MID, t / 0.45)
        else:
            c = lerp(SKY_MID, SKY_LOW, (t - 0.45) / 0.55)
        span(y, 0, SW, c)
    # sun and its glow, upper left-of-centre
    ellipse(318, 232, 196, 196, SUN_GLOW2)
    ellipse(318, 232, 152, 152, SUN_GLOW1)
    ellipse(318, 232, 106, 106, SUN_CORE)
    # rolling back hill
    hill = [(x, 566 + 26 * math.sin(x / 1024.0 * 2.4 + 0.6)) for x in range(-8, 1033, 16)]
    polygon(hill + [(1032, 1024), (-8, 1024)], HILL)
    # meadow
    med = [(x, 652 + 20 * math.sin(x / 1024.0 * 3.1 + 2.2)) for x in range(-8, 1033, 16)]
    polygon(med + [(1032, 1024), (-8, 1024)], MEADOW)
    # darker front band for depth
    band = [(x, 918 + 14 * math.sin(x / 1024.0 * 2.0 + 1.1)) for x in range(-8, 1033, 16)]
    polygon(band + [(1032, 1024), (-8, 1024)], MEADOW_DARK)


def bunting():
    # two festive strings sagged across the top corners
    flags = [CORAL, GOLD, ROSE, CREAM, CORAL_DARK, GOLD]
    for (x0, y0, x1, y1, sag) in ((0, 26, 512, 118, 64), (512, 118, 1024, 8, 64)):
        prev = None
        n = 40
        for i in range(n + 1):
            t = i / n
            x = x0 + (x1 - x0) * t
            y = y0 + (y1 - y0) * t + sag * 4 * t * (1 - t)
            if prev is not None:
                thick_line(prev[0], prev[1], x, y, 4, WOOD)
            prev = (x, y)
        for i in range(6):
            t = (i + 0.5) / 6
            x = x0 + (x1 - x0) * t
            y = y0 + (y1 - y0) * t + sag * 4 * t * (1 - t)
            polygon([(x - 17, y), (x + 17, y), (x, y + 44)], flags[i % len(flags)])


def plane_and_trail():
    # the plane's loop-the-loop trail: an even dotted heart outline
    cx, cy, s = 500, 278, 168
    steps = 168
    gap = 0.14                     # fraction of the loop left open at the bottom
    for i in range(steps):
        if i % 3:
            continue               # dots, evenly spaced along the curve
        t = math.pi + gap + (2.0 * math.pi - gap * 2) * i / (steps - 1)
        x, y = heart_point(t, cx, cy, s)
        stamp(x, y, 5.5, WHITE)
    # the paper plane itself, top right of the loop, nose up-right
    polygon([(548, 208), (676, 168), (572, 244)], WHITE)          # top wing
    polygon([(548, 208), (572, 244), (606, 218)], PLANE_SHADE)    # fold
    polygon([(606, 218), (676, 168), (636, 244)], C('#EFF6FC'))   # far wing


# ---------------------------------------------------------------- characters


def shadow(cx, cy, rx, ry):
    ellipse(cx, cy, rx, ry, MEADOW_DARK)


def grandmother():
    # laughing grandmother, right side, clapping at the plane
    shadow(795, 912, 118, 16)
    # dress
    polygon([(748, 648), (842, 648), (884, 892), (706, 892)], ROSE)
    polygon([(748, 648), (795, 648), (795, 892), (706, 892)], ROSE_DARK)
    # shoes
    ellipse(742, 904, 30, 12, DARK)
    ellipse(850, 904, 30, 12, DARK)
    # arms up, clapping (sleeves then forearms then hands)
    thick_line(752, 668, 724, 598, 30, ROSE_DARK)
    thick_line(724, 598, 722, 540, 22, SKIN_G)
    thick_line(838, 668, 866, 598, 30, ROSE)
    thick_line(866, 598, 868, 540, 22, SKIN_G)
    ellipse(720, 528, 15, 19, SKIN_G)
    ellipse(870, 528, 15, 19, SKIN_G)
    # head and hair
    ellipse(795, 552, 64, 68, SKIN_G)
    ellipse(795, 500, 66, 40, HAIR_G)
    ellipse(795, 452, 27, 25, HAIR_G)          # bun
    ellipse(795, 520, 67, 30, HAIR_G)          # hairline sweep
    ellipse(795, 556, 60, 60, SKIN_G)          # face again, lower
    # rosy cheeks
    ellipse(752, 586, 15, 10, CHEEK)
    ellipse(838, 586, 15, 10, CHEEK)
    # happy shut eyes (arcs) and round glasses
    arc(772, 556, 13, 180, 360, 6, DARK)
    arc(818, 556, 13, 180, 360, 6, DARK)
    arc(772, 556, 25, 0, 360, 5, WOOD)
    arc(818, 556, 25, 0, 360, 5, WOOD)
    thick_line(797, 552, 793, 552, 5, WOOD)
    # open laughing mouth with tongue
    ellipse(795, 592, 20, 19, MOUTH)
    ellipse(795, 600, 14, 9, TONGUE)
    # collar
    polygon([(766, 640), (824, 640), (795, 672)], CREAM)


def child():
    # small child, left side, caught mid-leap
    shadow(215, 914, 96, 13)
    # legs, bent in the jump
    thick_line(192, 806, 168, 862, 24, SKIN_C)
    thick_line(240, 806, 268, 856, 24, SKIN_C)
    ellipse(164, 872, 22, 11, WHITE)
    ellipse(274, 866, 22, 11, WHITE)
    # shorts and shirt
    polygon([(168, 748), (264, 748), (272, 812), (160, 812)], CORAL)
    rounded_rect(170, 636, 262, 762, 26, GOLD)
    # arms flung wide and up
    thick_line(178, 660, 124, 566, 24, GOLD)
    thick_line(124, 566, 112, 512, 19, SKIN_C)
    ellipse(110, 500, 15, 15, SKIN_C)
    thick_line(254, 660, 306, 560, 24, GOLD)
    thick_line(306, 560, 330, 508, 19, SKIN_C)
    ellipse(334, 496, 15, 15, SKIN_C)
    # head: dark hair cap over warm skin, huge grin
    ellipse(216, 560, 57, 59, SKIN_C)
    ellipse(216, 522, 58, 34, HAIR_C)
    ellipse(190, 498, 12, 11, HAIR_C)   # round curls, not spikes
    ellipse(216, 490, 13, 12, HAIR_C)
    ellipse(242, 498, 12, 11, HAIR_C)
    ellipse(192, 580, 13, 9, CHEEK)
    ellipse(240, 580, 13, 9, CHEEK)
    arc(196, 556, 11, 180, 360, 6, DARK)
    arc(236, 556, 11, 180, 360, 6, DARK)
    sector(216, 578, 24, 20, 15, 165, MOUTH)                # open grin
    polygon([(196, 582), (236, 582), (232, 592), (200, 592)], WHITE)  # teeth
    ellipse(216, 592, 13, 7, TONGUE)


def dog():
    # little golden dog, front left, leaping with its tongue out
    shadow(348, 918, 96, 12)
    thick_line(288, 838, 252, 772, 19, DOG)                 # tail, wagging up
    ellipse(252, 762, 13, 13, DOG)
    rot_ellipse(348, 850, 70, 42, -14, DOG)                 # body
    ellipse(322, 884, 14, 22, DOG)                          # legs
    ellipse(384, 876, 14, 22, DOG)
    ellipse(420, 806, 42, 40, DOG)                          # head
    rot_ellipse(396, 786, 17, 29, 24, DOG_DARK)             # floppy ear
    ellipse(446, 824, 22, 15, C('#FFE3B3'))                 # snout
    ellipse(462, 818, 9, 7, DARK)                           # nose
    polygon([(442, 834), (460, 834), (456, 862), (444, 860)], TONGUE)
    arc(414, 798, 10, 180, 360, 6, DARK)                    # happy eye
    ellipse(430, 782, 5, 5, DARK)                           # second eye dot
    thick_line(306, 824, 364, 860, 14, CORAL)               # collar


def robot():
    # the hero: a small round robot, centre stage, arms up - it just let go
    shadow(512, 916, 128, 16)
    # arms first, so the shoulders tuck under the body
    thick_line(446, 648, 372, 556, 32, CREAM)
    thick_line(372, 556, 356, 492, 26, CREAM)
    ellipse(352, 478, 22, 22, CREAM)
    ellipse(340, 462, 10, 12, CREAM)                        # thumb
    thick_line(578, 648, 650, 548, 32, CREAM)
    thick_line(650, 548, 668, 486, 26, CREAM)
    ellipse(672, 472, 22, 22, CREAM)
    ellipse(684, 456, 10, 12, CREAM)
    # cuffs
    ellipse(382, 540, 20, 20, CORAL)
    ellipse(640, 532, 20, 20, CORAL)
    # legs and boots
    rounded_rect(460, 852, 500, 894, 8, STEEL)
    rounded_rect(524, 852, 564, 894, 8, STEEL)
    rounded_rect(448, 884, 508, 912, 10, CORAL)
    rounded_rect(516, 884, 576, 912, 10, CORAL)
    # body with a soft shaded side and a heart on its chest
    rounded_rect(424, 612, 600, 884, 52, CREAM)
    polygon([(548, 620), (600, 664), (600, 832), (548, 884)], SHADE)
    ellipse(512, 742, 62, 54, C('#FFE8C9'))                 # belly panel
    heart(512, 736, 30, CORAL)
    # scarf: band at the neck and a tail flying to the right
    polygon([(438, 596), (586, 596), (592, 634), (432, 634)], CORAL)
    polygon([(586, 604), (668, 628), (640, 662), (590, 640)], CORAL_DARK)
    # ears
    ellipse(404, 512, 20, 26, CORAL)
    ellipse(620, 512, 20, 26, CORAL)
    # head
    rounded_rect(414, 412, 610, 612, 56, CREAM)
    rounded_rect(436, 434, 588, 590, 42, C('#FFF6E6'))
    # antenna with a gold star
    thick_line(512, 412, 512, 380, 9, STEEL)
    star(512, 362, 21, GOLD)
    # face: shut happy eyes, rosy cheeks, open delighted mouth
    arc(478, 508, 17, 180, 360, 8, DARK)
    arc(546, 508, 17, 180, 360, 8, DARK)
    ellipse(454, 548, 17, 11, CHEEK)
    ellipse(570, 548, 17, 11, CHEEK)
    sector(512, 540, 34, 28, 10, 170, MOUTH)
    ellipse(512, 560, 19, 10, TONGUE)


def foreground():
    # grass tufts scattered over the meadow (deterministic), kept off the cast
    keep_out = [(330, 620, 700, 1024),    # robot and its arms
                (95, 600, 360, 930),      # child
                (685, 600, 905, 930),     # grandmother
                (230, 730, 480, 940)]     # dog
    for _ in range(64):
        x = 20 + rnd() * 984
        y = 700 + rnd() * 300
        if any(a < x < b and c < y < d for (a, c, b, d) in keep_out):
            continue
        for dx in (-7, 0, 7):
            polygon([(x + dx - 4, y), (x + dx + 4, y), (x + dx * 1.6, y - 24 - rnd() * 10)], GRASS)
    # a front row of simple flowers
    cols = [WHITE, CORAL, GOLD, ROSE, C('#FF9E9E')]
    for _ in range(30):
        x = 16 + rnd() * 992
        y = 936 + rnd() * 72
        thick_line(x, y + 16, x, y + 2, 4, GRASS)
        for k in range(5):
            a = 2.0 * math.pi * k / 5
            ellipse(x + 8 * math.cos(a), y + 8 * math.sin(a), 6.5, 6.5, cols[int(rnd() * 5) % 5])
        stamp(x, y, 4.5, GOLD)
    # sparkles and small floating hearts around the celebration
    star(150, 300, 17, WHITE)
    star(884, 268, 20, GOLD)
    star(742, 148, 13, WHITE)
    star(268, 148, 12, GOLD)
    heart(700, 420, 15, ROSE)
    heart(322, 428, 13, CORAL)
    heart(872, 430, 12, CORAL)


# ---------------------------------------------------------------- encode


def downsample():
    out = bytearray(W * H * 3)
    for y in range(H):
        r0 = (2 * y) * SW * 3
        r1 = (2 * y + 1) * SW * 3
        o = y * W * 3
        for x in range(W):
            i0 = r0 + 6 * x
            i1 = r1 + 6 * x
            j = o + 3 * x
            for ch in range(3):
                out[j + ch] = (fb[i0 + ch] + fb[i0 + ch + 3]
                               + fb[i1 + ch] + fb[i1 + ch + 3] + 2) // 4
    return out


_ABS = bytes(b if b < 128 else 256 - b for b in range(256))


def encode_png(px):
    raw = bytearray()
    stride = W * 3
    prev = bytes(stride)
    for y in range(H):
        row = bytes(px[y * stride:(y + 1) * stride])
        sub = bytes((row[i] - (row[i - 3] if i >= 3 else 0)) & 0xFF
                    for i in range(stride))
        up = bytes((row[i] - prev[i]) & 0xFF for i in range(stride))
        best, best_score = (0, row), sum(row.translate(_ABS))
        for tag, cand in ((1, sub), (2, up)):
            score = sum(cand.translate(_ABS))
            if score < best_score:
                best, best_score = (tag, cand), score
        raw.append(best[0])
        raw += best[1]
        prev = row

    def chunk(tag, data):
        return (struct.pack('>I', len(data)) + tag + data
                + struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack('>IIBBBBB', W, H, 8, 2, 0, 0, 0)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr)
            + chunk(b'IDAT', zlib.compress(bytes(raw), 9))
            + chunk(b'IEND', b''))


def main():
    backdrop()
    bunting()
    plane_and_trail()
    grandmother()
    child()
    dog()
    robot()
    foreground()
    data = encode_png(downsample())
    outdir = os.environ.get('MAKEFUN_OUTPUT_DIR', '/output')
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, 'entry.png'), 'wb') as f:
        f.write(data)


if __name__ == '__main__':
    main()
