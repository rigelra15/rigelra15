"""Builds the isometric Activity chart for the profile README from real GitHub contribution data.

Usage: GH_TOKEN=... LOGIN=rigelra15 python3 scripts/activity.py dist
Writes dist/activity-dark.svg and dist/activity-light.svg.
"""
import json
import os
import sys
import urllib.request
from xml.sax.saxutils import escape

import datetime

SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"
W = 1200
# week step (u) and day step (v) in chart units, before scaling to the canvas
U, V = (12.0, 3.5), (-9.0, 6.0)
GAP = 0.8
MAXH = 70.0
THEMES = {
    "dark": dict(bg="#1E1E1E", dots="#343434", edge="#383838", ink="#FFFFFF", muted="#B3B3B3",
                 levels=["#2C2C2C", "#0B4A7A", "#0A78C4", "#0D99FF", "#8AD2FF"]),
    "light": dict(bg="#F5F5F5", dots="#CFCFCF", edge="#D9D9D9", ink="#1E1E1E", muted="#555555",
                  levels=["#E2E2E2", "#BDE0FA", "#79C2F4", "#0D99FF", "#0B6FC2"]),
}
QUERY = ("query($login:String!){user(login:$login){contributionsCollection{contributionCalendar{"
         "totalContributions weeks{contributionDays{date contributionCount}}}}}}")


def fetch(login, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json", "User-Agent": "profile-activity"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data:
        raise SystemExit(data["errors"])
    cal = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    return cal["totalContributions"], cal["weeks"]


def shade(hex_color, f):
    c = hex_color.lstrip("#")
    return "#%02x%02x%02x" % tuple(int(int(c[i:i + 2], 16) * f) for i in (0, 2, 4))


def pt(i, j, du=0.0, dv=0.0):
    return (i * U[0] + j * V[0] + du * U[0] + dv * V[0], i * U[1] + j * V[1] + du * U[1] + dv * V[1])


def render(total, weeks, t):
    cells = []
    for i, w in enumerate(weeks):
        for d in w["contributionDays"]:
            j = (datetime.date.fromisoformat(d["date"]).weekday() + 1) % 7  # Sunday first
            cells.append((i, j, d["contributionCount"], d["date"]))
    counts = [c[2] for c in cells]
    peak = max(counts) or 1
    active = sum(1 for c in counts if c)
    first, last = cells[0][3], cells[-1][3]

    def level(c):
        if not c:
            return 0
        r = c / peak
        return 1 if r <= 0.12 else 2 if r <= 0.3 else 3 if r <= 0.6 else 4

    shapes, xs, ys = [], [], []
    for i, j, c, _ in sorted(cells, key=lambda x: (x[0] * U[1] + x[1] * V[1], x[0])):
        h = 1.5 if not c else 5 + MAXH * (c / peak) ** 0.5
        base = t["levels"][level(c)]
        a, b = pt(i, j), pt(i, j, GAP, 0)
        cc, d = pt(i, j, GAP, GAP), pt(i, j, 0, GAP)
        up = lambda p: (p[0], p[1] - h)
        top = [up(a), up(b), up(cc), up(d)]
        front_v = [d, cc, up(cc), up(d)]      # face toward +day
        front_u = [b, cc, up(cc), up(b)]      # face toward +week
        for pts, col in ((front_v, shade(base, 0.72)), (front_u, shade(base, 0.55)), (top, base)):
            shapes.append((pts, col))
            xs += [p[0] for p in pts]
            ys += [p[1] for p in pts]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    scale = (W - 80) / (maxx - minx)
    top_pad = 150
    H = int(top_pad + (maxy - miny) * scale + 36)
    ox, oy = 40 - minx * scale, top_pad - miny * scale
    poly = "".join(
        '<polygon points="%s" fill="%s"/>' % (" ".join(f"{ox + x * scale:.1f},{oy + y * scale:.1f}" for x, y in pts), col)
        for pts, col in shapes)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t">
<title id="t">{total} GitHub contributions between {first} and {last}, on {active} active days, drawn as a 3D block chart. Busiest day: {peak}.</title>
<defs>
  <pattern id="dot" width="24" height="24" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1.1" fill="{t["dots"]}"/></pattern>
  <clipPath id="f"><rect width="{W}" height="{H}" rx="16"/></clipPath>
</defs>
<g clip-path="url(#f)">
  <rect width="{W}" height="{H}" fill="{t["bg"]}"/>
  <rect width="{W}" height="{H}" fill="url(#dot)"/>
  <text x="40" y="76" font-family="{SANS}" font-size="52" font-weight="800" fill="{t["ink"]}">{total:,}</text>
  <text x="40" y="108" font-family="{SANS}" font-size="22" fill="{t["muted"]}">contributions in the last year, {active} active days</text>
  <g>{poly}</g>
</g>
<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="16" fill="none" stroke="{t["edge"]}"/>
</svg>'''


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "dist"
    os.makedirs(out, exist_ok=True)
    total, weeks = fetch(os.environ["LOGIN"], os.environ["GH_TOKEN"])
    for name, theme in THEMES.items():
        with open(os.path.join(out, f"activity-{name}.svg"), "w") as f:
            f.write(render(total, weeks, theme))
    print("ok", len(weeks), "weeks,", total, "contributions")
