import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from skimage.morphology import skeletonize

line1 = "Инно"
GAP = 10  # доп. отступ между симфолами
line2 = "2026"
FONT_PATH = "ofont.ru_Buira.ttf"
FONT_SIZE1   = 250
FONT_SIZE2   = 215
LETTER_SPACING = 20  # доп. пикселей между буквами line1
IMG_WIDTH = 800
IMG_HEIGHT = 600
IMG_WIDTH_MM = 80
IMG_HEIGHT_MM = 60
RATIO_X = IMG_WIDTH / IMG_WIDTH_MM *1000 #px/m
RATIO_Y = IMG_HEIGHT / IMG_HEIGHT_MM *1000 #px/m
EPS = 1/1000 #MM

# ---------- рендер буквы ----------
img  = Image.new("RGB", (IMG_WIDTH, IMG_HEIGHT), (255, 255, 255))
draw = ImageDraw.Draw(img)


font1 = ImageFont.truetype(FONT_PATH, FONT_SIZE1)
font2 = ImageFont.truetype(FONT_PATH, FONT_SIZE2)

# Считаем ширину line1 с учётом интервала
widths = [draw.textbbox((0,0), ch, font=font1)[2] for ch in line1]
total_w1 = sum(widths) + LETTER_SPACING * (len(line1) - 1)

bbox2 = draw.textbbox((0, 0), line2, font=font2)
total_w2 = bbox2[2] - bbox2[0]

h1 = draw.textbbox((0,0), line1, font=font1)[3]  # высота первой строки
h2 = bbox2[3] - bbox2[1]

total_h = h1 + GAP + h2
y1 = (IMG_HEIGHT - total_h) // 2
# Рисуем line1 побуквенно
x = (IMG_WIDTH - total_w1) // 2
for ch, w in zip(line1, widths):
    draw.text((x, y1), ch, font=font1, fill=(0, 0, 0))
    x += w + LETTER_SPACING
# Рисуем line2 целиком
x2 = (IMG_WIDTH - total_w2) // 2
draw.text((x2, y1 + h1 + GAP), line2, font=font2, fill=(0, 0, 0))

cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

# ---------- скелетизация ----------
blurred = cv2.GaussianBlur(np.array(img.convert("L")), (5, 5), 0)
skel    = skeletonize((blurred < 200).astype(np.uint8))

# Обрезаем шпоры: 20 раз удаляем точки с единственным соседом
s = skel.copy().astype(np.uint8)
for _ in range(3):
    nbs = sum(np.roll(np.roll(s, dy, 0), dx, 1)
              for dy in (-1,0,1) for dx in (-1,0,1) if (dy,dx) != (0,0))
    s[nbs == 1] = 0
skel = s.astype(bool)

# ---------- скелет → сегменты ----------
s   = skel.astype(np.uint8)
nbs = sum(np.roll(np.roll(s, dy, 0), dx, 1)
          for dy in (-1,0,1) for dx in (-1,0,1) if (dy,dx) != (0,0))

# Концы (1 сосед) и развилки (3+) — узлы; середины (2 соседа) просто проходим
nodes = set(zip(*np.where(skel & ((nbs == 1) | (nbs >= 3)))))

H, W     = skel.shape
visited  = set()
segments = []

for node in nodes:
    for nb in [(node[0]+dy, node[1]+dx)
               for dy in (-1,0,1) for dx in (-1,0,1)
               if (dy,dx) != (0,0) and 0<=node[0]+dy<H and 0<=node[1]+dx<W and skel[node[0]+dy, node[1]+dx]]:
        if frozenset([node, nb]) in visited:
            continue
        # Трассируем путь от node через nb до следующего узла
        path, prev, cur = [node, nb], node, nb
        visited.add(frozenset([prev, cur]))
        while cur not in nodes:
            nxt = [(cur[0]+dy, cur[1]+dx)
                   for dy in (-1,0,1) for dx in (-1,0,1)
                   if (dy,dx) != (0,0) and 0<=cur[0]+dy<H and 0<=cur[1]+dx<W
                   and skel[cur[0]+dy, cur[1]+dx] and (cur[0]+dy, cur[1]+dx) != prev]
            if not nxt or frozenset([cur, nxt[0]]) in visited: break
            prev, cur = cur, nxt[0]
            visited.add(frozenset([prev, cur]))
            path.append(cur)
        segments.append(path)

#? БУКВЫ О
# Петли (буквы О, 0 и т.д.) — точки, не попавшие ни в один сегмент
visited_pts = {pt for seg in segments for pt in seg}
unvisited   = set(zip(*np.where(skel))) - visited_pts

while unvisited:
    start     = next(iter(unvisited))
    path      = [start]
    prev, cur = start, next(iter(set([(start[0]+dy, start[1]+dx)
                 for dy in (-1,0,1) for dx in (-1,0,1)
                 if (dy,dx) != (0,0) and skel[start[0]+dy, start[1]+dx]])))
    while cur not in visited_pts:
        path.append(cur)
        visited_pts.add(cur)
        nxt = [(cur[0]+dy, cur[1]+dx)
               for dy in (-1,0,1) for dx in (-1,0,1)
               if (dy,dx) != (0,0) and 0<=cur[0]+dy<H and 0<=cur[1]+dx<W
               and skel[cur[0]+dy, cur[1]+dx] and (cur[0]+dy, cur[1]+dx) != prev]
        if not nxt: break
        prev, cur = cur, nxt[0]
    path.append(path[0])  # замыкаем петлю
    segments.append(path)
    unvisited -= set(path)
#?
# ---------- склейка коротких сегментов ----------
MIN_LEN = 10  # сегменты короче этого порога сливаем с соседним

def merge_segments(segments, min_len):
    from collections import defaultdict

    def try_join(seg, other, endpoint):
        """Стыкует seg к other по точке endpoint.
        Проверяет оба конца other с допуском ±1 пиксель."""
        r2, c2 = endpoint
        for other_end, other_seq in ((other[-1], other), (other[0], other[::-1])):
            r1, c1 = other_end
            if max(abs(r1 - r2), abs(c1 - c2)) > 1:
                continue
            head = other_seq
            tail = seg if endpoint == seg[0] else seg[::-1]
            # Точное совпадение — убираем дублирующую точку стыка
            skip = 1 if (r1, c1) == (r2, c2) else 0
            return head + tail[skip:]
        return None

    # Индекс: точка → индексы сегментов с этим концом
    endpoint_index = defaultdict(list)
    for i, seg in enumerate(segments):
        endpoint_index[seg[0]].append(i)
        endpoint_index[seg[-1]].append(i)

    merged       = [False] * len(segments)
    replacements = {}

    for i, seg in enumerate(segments):
        if merged[i] or len(seg) >= min_len:
            continue

        joined = False
        for endpoint in (seg[0], seg[-1]):
            # Точные кандидаты + соседи ±1 пиксель
            r, c = endpoint
            candidates = {j for dy in range(-1, 2) for dx in range(-1, 2)
                          for j in endpoint_index.get((r+dy, c+dx), [])}
            for j in candidates:
                if j == i or merged[j]:
                    continue
                path = try_join(seg, segments[j], endpoint)
                if path:
                    replacements[j] = path
                    merged[i] = merged[j] = True
                    joined = True
                    break
            if joined:
                break

    return [replacements.get(i, seg) for i, seg in enumerate(segments)
            if not merged[i] or i in replacements]

for _ in range(3):
    segments = merge_segments(segments, MIN_LEN)


print(f"Сегментов: {len(segments)}")
# for i, seg in enumerate(segments):
#     print(f"  [{i}] точек: {len(seg)}  {seg[0]} → {seg[-1]}")


#? Обединение
STITCH_DIST    = 8   # макс. расстояние между концом и началом
STITCH_COS     = 0.7 # минимальный косинус между направлениями (0.8 ≈ 37°)
DIRECTION_PTS  = 8   # по скольким точкам считаем направление

def direction(pts):
    """Вектор от первой к последней точке среди pts."""
    dr = pts[-1][0] - pts[0][0]
    dc = pts[-1][1] - pts[0][1]
    n  = (dr**2 + dc**2) ** 0.5
    return (dr/n, dc/n) if n > 0 else (0, 0)

def cos_sim(a, b):
    return a[0]*b[0] + a[1]*b[1]
def dist(a, b):
    return max(abs(a[0]-b[0]), abs(a[1]-b[1]))
def stitch_segments(segments):
    result = list(segments)
    changed = True
    while changed:
        changed = False
        for i in range(len(result)):
            for j in range(len(result)):
                if i == j:
                    continue
                a, b = result[i], result[j]
                if dist(a[-1], b[0]) <= STITCH_DIST and \
                   cos_sim(direction(a[-DIRECTION_PTS:]), direction(b[:DIRECTION_PTS])) >= STITCH_COS:
                    merged = a + b
                elif dist(a[-1], b[-1]) <= STITCH_DIST and \
                     cos_sim(direction(a[-DIRECTION_PTS:]), direction(b[-DIRECTION_PTS:][::-1])) >= STITCH_COS:
                    merged = a + b[::-1]
                elif dist(a[0], b[-1]) <= STITCH_DIST and \
                     cos_sim(direction(a[:DIRECTION_PTS][::-1]), direction(b[-DIRECTION_PTS:])) >= STITCH_COS:
                    merged = b + a
                elif dist(a[0], b[0]) <= STITCH_DIST and \
                     cos_sim(direction(a[:DIRECTION_PTS][::-1]), direction(b[:DIRECTION_PTS])) >= STITCH_COS:
                    merged = b[::-1] + a
                else:
                    continue
                result = [merged if k == i else v
                          for k, v in enumerate(result) if k != j]
                changed = True
                break
            if changed:
                break
    return result

segments = stitch_segments(segments)

print(f"Стало сегментов: {len(segments)}")
# for i, seg in enumerate(segments):
#     print(f"  [{i}] точек: {len(seg)}  {seg[0]} → {seg[-1]}")
#?

# ? Сортировка сегментов

import math
def proj(pt):
    r, c = pt
    return c * math.cos(a) + r * math.sin(a)
def sort_key(s):
    r, c = s[0]  # первая точка (уже развёрнуто началом вверх)
    return c * math.cos(a) + r * math.sin(a)  # проекция на повёрнутую ось X

SORT_ANGLE_DEG = 70  # угол наклона по часовой стрелке
a = math.radians(SORT_ANGLE_DEG)
segments = [s if proj(s[0]) <= proj(s[-1]) else s[::-1] for s in segments]

SORT_ANGLE_DEG = 15  # угол наклона по часовой стрелке
a = math.radians(SORT_ANGLE_DEG)
# Y-граница между строками (середина между y1+h1 и y1+h1+gap)
y_split = y1 + h1 + GAP // 2
seg_top = [s for s in segments if min(r for r, c in s) < y_split]
seg_bot = [s for s in segments if min(r for r, c in s) >= y_split]
seg_top.sort(key=sort_key)

print("Дополнительно объединил цифры...")
STITCH_COS     = -0.2
seg_bot = stitch_segments(seg_bot)
seg_bot.sort(key=sort_key)

print(f"Верхние: {len(seg_top)}, нижние: {len(seg_bot)}")
path_segments = seg_top + seg_bot

# path_segments = [s if proj(s[0]) <= proj(s[-1]) else s[::-1] for s in path_segments]
# (row, col) → (x, y)
path_segments = [[(int(c), int(r)) for r, c in seg] for seg in path_segments]#[:11]
# ?


# ---------- визуализация ----------
import matplotlib.pyplot as plt
cmap = plt.cm.rainbow

vis = cv_img.copy()
vis[skel] = (40, 40, 40)

COLOR_STEP = 1
for i, seg in enumerate(path_segments):
    color_f = cmap((i * COLOR_STEP / max(len(path_segments) - 1, 1)) % 1.0)
    color   = tuple(int(c * 255) for c in color_f[2::-1])  # RGB→BGR
    for x, y in seg:
        cv2.circle(vis, (x, y), 2, color, -1)
    cv2.circle(vis, seg[0],  5, (0, 255, 0), -1)
    cv2.circle(vis, seg[-1], 5, (0,   0, 255), -1)


# for i in path_segments[0]:
#     print(f"x = {i[0]}, y = {i[1]}")
# print(len(path_segments[0]), "точек")

path = path_segments
#?
# path_segments[0].reverse()
# path_segments[2].reverse()
# path = [path_segments[2]+path_segments[0], path_segments[1]]
#?
coords_segments = []
last_point = [-100,-100]
for i, segment in enumerate(path):
    coords_segment = []
    for j, point in enumerate(segment):
        point_coords = [point[0]/RATIO_X, point[1]/RATIO_Y]
        if ((point_coords[0]-last_point[0])**2 + (point_coords[1]-last_point[1])**2)**0.5 >= EPS:
            last_point = point_coords.copy()
            coords_segment.append(point_coords)
    coords_segments.append(coords_segment)

print("\nСтало сегментов:", len(coords_segments))
# for i in coords_segments:
#     print(len(i), "точек:")
#     for j in range(0, min(len(i), 3)):
#         print(f"x = {i[j][0]}, y = {i[j][1]}")
#     if len(i) > 10:
#         print("...")
cv2.imshow("Сегменты", vis)
cv2.waitKey(0)

import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(6, 6))
ax.set_aspect("equal")
ax.invert_yaxis()  # ось Y вниз, как на экране
ax.set_xlim(0, IMG_WIDTH_MM / 1000)
ax.set_ylim(IMG_HEIGHT_MM / 1000, 0)  # инвертировано

for seg in coords_segments:
    xs, ys = zip(*seg)
    ax.scatter(xs, ys, s=2)

# for i in range(21):
#     print(len(coords_segments[i]))

import csv
import os
for idx, trajectory in enumerate(coords_segments):
    filename = os.path.join("./", f"trajectory_{idx}.csv")
    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["x", "y"])
        writer.writerows(trajectory)
# plt.tight_layout()
plt.show()
# plt.imsave("f.png", ax)