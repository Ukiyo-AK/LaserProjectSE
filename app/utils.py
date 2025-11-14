import math
from typing import List, Tuple


def color_to_code(color: Tuple[int, int, int]) -> int:
    r, g, b = color
    if r >= g and r >= b:
        return 1
    if g >= r and g >= b:
        return 2
    return 3

def code_to_color(code: int) -> Tuple[int, int, int]:
    if code == 1:
        return (255, 0, 0)
    if code == 2:
        return (0, 255, 0)
    return (0, 0, 255)


def circle_to_points(cen: Tuple[int, int], r: int, s: int = 90) -> List[Tuple[int, int]]:
    cx, cy = cen
    pts = []
    if r <= 0 or s <= 0:
        return pts
    for i in range(s):
        t = 2 * math.pi * (i / s)
        x = int(round(cx + r * math.cos(t)))
        y = int(round(cy + r * math.sin(t)))
        pts.append((x, y))
    
    return pts