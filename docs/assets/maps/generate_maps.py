# Generates Realmweave map SVGs from the authoritative world coordinates.
# Original work (author: Realmweave project). Output: docs/assets/maps/*.svg
import os

OUT = r"C:\Users\USER\Documents\realmweave\docs\assets\maps"
S, OX, OY = 16, 8, 8
def X(x): return round(OX + x*S, 1)
def Y(y): return round(OY + y*S, 1)

# id, name, x, y, kind  (from backend/realmweave/world.py default_village)
LOCS = [
 ("square","Village Square",32,24,"square"),
 ("tavern","The Gilded Stag",20,18,"tavern"),
 ("tavern_kitchen","Stag Kitchen",16,16,"tavern"),
 ("well","Old Well",32,30,"well"),
 ("stable","Stables",46,20,"stable"),
 ("smithy","Ironbark Smithy",44,30,"smithy"),
 ("field","North Fields",30,6,"field"),
 ("mine","Ironbark Mine",56,32,"mine"),
 ("gate","South Gate",32,44,"gate"),
 ("home_bram","Bram's Room",14,22,"home"),
 ("home_isla","Isla's Cottage",50,14,"home"),
 ("home_toft","Toft's Shack",48,36,"home"),
 ("home_wren","Wren's Loft",24,34,"home"),
 ("home_dora","Dora's House",38,10,"home"),
 ("home_gart","Gart's Hut",58,38,"home"),
]
TREES = [(8,8),(12,40),(52,8),(56,40),(6,26),(58,24),(24,4),(40,46),
         (18,44),(48,4),(2,16),(60,34),(30,48),(34,2)]
ROCKS = [(26,6),(44,42),(58,30),(54,34)]
POND = (12,32)
# main roads (grid coord pairs)
ROADS = [((32,24),(30,6)),((32,24),(32,30)),((32,24),(32,44)),
         ((32,24),(20,18)),((32,24),(46,20)),((32,24),(44,30)),
         ((44,30),(56,32)),((20,18),(16,16)),((32,44),(32,50))]

COL = {"square":"#d9c46b","tavern":"#b98a4a","well":"#5aa0c0","stable":"#8a6d3b",
       "smithy":"#c85a5a","field":"#5ab97a","mine":"#8b93a6","gate":"#d9c46b",
       "home":"#4a5266"}
GLYPH = {"square":"◆","tavern":"☗","well":"♒","stable":"♞",
         "smithy":"⚒","field":"⚘","mine":"⛏","gate":"☷","home":"⌂"}

def esc(s): return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def local_map():
    W, H = OX + 64*S, OY + 50*S
    p = []
    p.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
             f'font-family="Segoe UI,system-ui,sans-serif" role="img" '
             f'aria-label="Local map of Oakhollow village">')
    p.append('<defs>'
      '<radialGradient id="grd" cx="50%" cy="42%" r="70%">'
      '<stop offset="0%" stop-color="#1b2118"/><stop offset="100%" stop-color="#111511"/>'
      '</radialGradient>'
      '<filter id="sh" x="-20%" y="-20%" width="140%" height="140%">'
      '<feDropShadow dx="0" dy="1.5" stdDeviation="1.6" flood-color="#000" flood-opacity="0.5"/>'
      '</filter></defs>')
    p.append(f'<rect width="{W}" height="{H}" fill="#0e1013"/>')
    p.append(f'<rect x="{OX}" y="{OY}" width="{64*S}" height="{48*S}" rx="14" fill="url(#grd)" stroke="#2b3040" stroke-width="2"/>')
    # faint grid every 4 units
    for gx in range(0,65,4):
        p.append(f'<line x1="{X(gx)}" y1="{Y(0)}" x2="{X(gx)}" y2="{Y(48)}" stroke="#ffffff" stroke-opacity="0.03"/>')
    for gy in range(0,49,4):
        p.append(f'<line x1="{X(0)}" y1="{Y(gy)}" x2="{X(64)}" y2="{Y(gy)}" stroke="#ffffff" stroke-opacity="0.03"/>')
    # roads
    for (a,b) in ROADS:
        p.append(f'<line x1="{X(a[0])}" y1="{Y(a[1])}" x2="{X(b[0])}" y2="{Y(b[1])}" '
                 f'stroke="#5a4d2e" stroke-width="7" stroke-linecap="round" stroke-opacity="0.55"/>')
    # pond
    p.append(f'<ellipse cx="{X(POND[0])}" cy="{Y(POND[1])}" rx="34" ry="24" fill="#274b5c" stroke="#5aa0c0" stroke-opacity="0.5"/>')
    p.append(f'<ellipse cx="{X(POND[0])}" cy="{Y(POND[1])}" rx="20" ry="12" fill="#3b6f86" fill-opacity="0.6"/>')
    # rocks
    for (x,y) in ROCKS:
        p.append(f'<circle cx="{X(x)}" cy="{Y(y)}" r="7" fill="#5b6270" stroke="#3a4152"/>')
    # trees
    for (x,y) in TREES:
        p.append(f'<g><line x1="{X(x)}" y1="{Y(y)}" x2="{X(x)}" y2="{Y(y)+7}" stroke="#6b4a2a" stroke-width="3"/>'
                 f'<circle cx="{X(x)}" cy="{Y(y)}" r="10" fill="#2f6b3a"/>'
                 f'<circle cx="{X(x)-3}" cy="{Y(y)-3}" r="6" fill="#3c8049" fill-opacity="0.8"/></g>')
    return p, W, H

def _r(v): return round(v,1)

def icon(kind, cx, cy, s, c):
    dark = "#12151b"; body = "#252a36"; P = []
    def rect(x,y,w,h,fill,stroke="none"):
        return (f'<rect x="{_r(x)}" y="{_r(y)}" width="{_r(w)}" height="{_r(h)}" '
                f'rx="1.5" fill="{fill}" stroke="{stroke}"/>')
    def poly(pts,fill,stroke="none"):
        d=" ".join(f"{_r(a)},{_r(b)}" for a,b in pts)
        return f'<polygon points="{d}" fill="{fill}" stroke="{stroke}"/>'
    if kind in ("home","tavern","smithy","stable"):
        bw,bh = s*1.6, s*1.05
        P.append(rect(cx-bw/2, cy-bh*0.1, bw, bh, body, c))
        P.append(poly([(cx-bw*0.62,cy-bh*0.1),(cx,cy-bh*0.9),(cx+bw*0.62,cy-bh*0.1)], c))
        P.append(rect(cx-s*0.2, cy+bh*0.32, s*0.4, bh*0.58, dark))
        if kind=="tavern":
            P.append(f'<line x1="{_r(cx+bw*0.5)}" y1="{_r(cy-bh*0.1)}" x2="{_r(cx+bw*0.5)}" y2="{_r(cy+bh*0.2)}" stroke="{c}" stroke-width="1.5"/>')
            P.append(f'<circle cx="{_r(cx+bw*0.5)}" cy="{_r(cy+bh*0.32)}" r="{_r(s*0.26)}" fill="{c}"/>')
        if kind=="smithy":
            P.append(poly([(cx-s*0.42,cy+bh*0.02),(cx+s*0.42,cy+bh*0.02),(cx+s*0.24,cy+bh*0.26),(cx-s*0.24,cy+bh*0.26)], c))
        if kind=="stable":
            P.append(f'<path d="M{_r(cx-s*0.38)},{_r(cy+bh*0.45)} a{_r(s*0.38)},{_r(s*0.38)} 0 0 1 {_r(s*0.76)},0 Z" fill="{dark}"/>')
    elif kind=="well":
        P.append(f'<ellipse cx="{_r(cx)}" cy="{_r(cy+s*0.35)}" rx="{_r(s*0.8)}" ry="{_r(s*0.4)}" fill="{body}" stroke="{c}"/>')
        P.append(rect(cx-s*0.72, cy-s*0.9, s*0.16, s*1.25, c))
        P.append(rect(cx+s*0.56, cy-s*0.9, s*0.16, s*1.25, c))
        P.append(poly([(cx-s*0.95,cy-s*0.8),(cx,cy-s*1.2),(cx+s*0.95,cy-s*0.8)], c))
    elif kind=="field":
        for i in range(-2,3):
            xx=cx+i*s*0.44
            P.append(f'<line x1="{_r(xx)}" y1="{_r(cy+s*0.6)}" x2="{_r(xx)}" y2="{_r(cy-s*0.55)}" stroke="{c}" stroke-width="2.4"/>')
            P.append(f'<circle cx="{_r(xx)}" cy="{_r(cy-s*0.62)}" r="{_r(s*0.15)}" fill="{c}"/>')
    elif kind=="mine":
        P.append(poly([(cx-s*0.95,cy+s*0.7),(cx,cy-s*0.95),(cx+s*0.95,cy+s*0.7)], "#3a3f49","#4a5160"))
        P.append(f'<path d="M{_r(cx-s*0.34)},{_r(cy+s*0.7)} a{_r(s*0.34)},{_r(s*0.34)} 0 0 1 {_r(s*0.68)},0 Z" fill="{dark}"/>')
    elif kind=="gate":
        P.append(rect(cx-s*0.78, cy-s*0.7, s*0.34, s*1.5, c))
        P.append(rect(cx+s*0.44, cy-s*0.7, s*0.34, s*1.5, c))
        P.append(rect(cx-s*0.78, cy-s*0.95, s*1.56, s*0.32, c))
    elif kind=="square":
        P.append(poly([(cx,cy-s),(cx+s,cy),(cx,cy+s),(cx-s,cy)], c, "#7a6a2e"))
        P.append(f'<circle cx="{_r(cx)}" cy="{_r(cy)}" r="{_r(s*0.36)}" fill="{body}" stroke="{c}"/>')
        P.append(f'<circle cx="{_r(cx)}" cy="{_r(cy)}" r="{_r(s*0.13)}" fill="{c}"/>')
    return "".join(P)

def buildings(p):
    for (lid,name,x,y,kind) in LOCS:
        c = COL[kind]; home = kind == "home"
        s = 9 if home else (14 if kind=="square" else 12)
        cx, cy = X(x), Y(y)
        p.append(f'<g filter="url(#sh)"><circle cx="{cx}" cy="{cy}" r="{s+6}" '
                 f'fill="#12151b" fill-opacity="0.9" stroke="{c}" stroke-opacity="0.45"/>'
                 + icon(kind, cx, cy, s, c) + '</g>')
        lc = "#9aa0b4" if home else "#e7e8ee"; fs = 10 if home else 12
        p.append(f'<text x="{cx}" y="{cy+s+18}" text-anchor="middle" font-size="{fs}" '
                 f'fill="{lc}" paint-order="stroke" stroke="#0e1013" stroke-width="3" '
                 f'stroke-linejoin="round">{esc(name)}</text>')

def frame(p, W, H, title, sub):
    # title cartouche
    p.append(f'<g><rect x="{OX+10}" y="{OY+8}" width="300" height="46" rx="8" '
             f'fill="#161a22" stroke="#d9c46b" stroke-opacity="0.6"/>'
             f'<text x="{OX+26}" y="{OY+32}" font-size="21" fill="#d9c46b" '
             f'font-weight="700" letter-spacing="1">{esc(title)}</text>'
             f'<text x="{OX+26}" y="{OY+48}" font-size="11" fill="#9aa0b4">{esc(sub)}</text></g>')
    # compass
    ccx, ccy = W-46, 54
    p.append(f'<g transform="translate({ccx},{ccy})">'
             f'<circle r="24" fill="#161a22" stroke="#2b3040"/>'
             f'<polygon points="0,-20 5,0 0,6 -5,0" fill="#c85a5a"/>'
             f'<polygon points="0,20 5,0 0,-6 -5,0" fill="#5a6274"/>'
             f'<text x="0" y="-26" text-anchor="middle" font-size="11" fill="#9aa0b4">N</text></g>')

def scalebar(p, H):
    # 8 grid units bar
    x0 = OX+16; yb = H-24
    p.append(f'<line x1="{x0}" y1="{yb}" x2="{x0+8*S}" y2="{yb}" stroke="#e7e8ee" stroke-width="3"/>')
    for t in (0,8):
        p.append(f'<line x1="{x0+t*S}" y1="{yb-5}" x2="{x0+t*S}" y2="{yb+5}" stroke="#e7e8ee" stroke-width="3"/>')
    p.append(f'<text x="{x0}" y="{yb-9}" font-size="11" fill="#9aa0b4">8 tiles</text>')

def legend(p, W, H):
    items = [("square","Square / gate"),("tavern","Tavern"),("well","Well"),
             ("smithy","Smithy"),("stable","Stable"),("field","Field"),
             ("mine","Mine"),("home","Homes")]
    bx, by = W-214, H-166
    p.append(f'<g><rect x="{bx}" y="{by}" width="196" height="150" rx="8" '
             f'fill="#161a22" stroke="#2b3040"/>'
             f'<text x="{bx+12}" y="{by+20}" font-size="12" fill="#9aa0b4" '
             f'letter-spacing="0.5">LEGEND</text>')
    for i,(k,lbl) in enumerate(items):
        ly = by+38+i*14
        p.append(f'<rect x="{bx+12}" y="{ly-9}" width="12" height="12" rx="3" '
                 f'fill="{COL[k]}" fill-opacity="0.35" stroke="{COL[k]}"/>'
                 f'<text x="{bx+32}" y="{ly}" font-size="11.5" fill="#e7e8ee">{lbl}</text>')
    p.append('</g>')

def build_local():
    p, W, H = local_map()
    buildings(p)
    frame(p, W, H, "Oakhollow", "Local map · top-down village · 15 locations")
    legend(p, W, H)
    scalebar(p, H)
    p.append('</svg>')
    return "\n".join(p)

def build_realm():
    W,H=1024,768; p=[]
    p.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
             f'font-family="Segoe UI,system-ui,sans-serif" role="img" '
             f'aria-label="Regional map of the realm around Oakhollow">')
    p.append('<defs><radialGradient id="rg" cx="50%" cy="45%" r="75%">'
      '<stop offset="0%" stop-color="#1a2028"/><stop offset="100%" stop-color="#0f1216"/>'
      '</radialGradient></defs>')
    p.append(f'<rect width="{W}" height="{H}" fill="#0c0e11"/>')
    p.append(f'<rect x="16" y="16" width="{W-32}" height="{H-32}" rx="16" fill="url(#rg)" stroke="#2b3040" stroke-width="2"/>')
    # Whisperwood (west)
    for (x,y) in [(120,300),(160,360),(110,420),(180,300),(150,470),(210,410),(90,360),(230,340)]:
        p.append(f'<circle cx="{x}" cy="{y}" r="26" fill="#254a30" fill-opacity="0.85"/>')
    p.append('<text x="150" y="250" text-anchor="middle" font-size="15" fill="#5ab97a" font-style="italic">Whisperwood</text>')
    # Highmoor / North Fields (north band)
    p.append('<path d="M300,90 Q520,60 760,110 L740,180 Q520,150 320,175 Z" fill="#3d4a2a" fill-opacity="0.7"/>')
    p.append('<text x="520" y="130" text-anchor="middle" font-size="15" fill="#a9b46b" font-style="italic">Highmoor &amp; the North Fields</text>')
    # Ironbark Hills (east)
    for (x,y,s) in [(820,320,60),(880,380,70),(840,440,55),(900,300,50)]:
        p.append(f'<path d="M{x-s},{y+30} Q{x},{y-s} {x+s},{y+30} Z" fill="#3a3f49" stroke="#4a5160"/>')
    p.append('<text x="870" y="250" text-anchor="middle" font-size="15" fill="#9aa0b4" font-style="italic">Ironbark Hills</text>')
    p.append('<text x="900" y="470" text-anchor="middle" font-size="12" fill="#c85a5a">⛏ Ironbark Mine</text>')
    # Silverrun river
    p.append('<path d="M860,300 C700,360 620,360 512,384 C420,404 300,470 180,560" '
             'fill="none" stroke="#3b6f86" stroke-width="9" stroke-linecap="round" opacity="0.85"/>')
    p.append('<text x="360" y="470" font-size="13" fill="#5aa0c0" font-style="italic" transform="rotate(14 360 470)">Silverrun</text>')
    # Southroad
    p.append('<path d="M512,410 C520,520 512,600 512,720" fill="none" stroke="#5a4d2e" stroke-width="8" stroke-dasharray="2 10" stroke-linecap="round"/>')
    p.append('<text x="524" y="600" font-size="13" fill="#b98a4a" font-style="italic">Southroad</text>')
    return p, W, H

def realm_marks(p, W, H):
    # settlements: (x,y,label,major)
    towns=[(512,384,"Oakhollow",True),(512,700,"Aldermere",False),
           (150,430,"Fenwick",False),(880,540,"Stonereach",False)]
    for (x,y,lbl,major) in towns:
        if major:
            p.append(f'<g><polygon points="{x},{y-16} {x+5},{y-5} {x+16},{y-4} {x+7},{y+4} '
                     f'{x+10},{y+15} {x},{y+8} {x-10},{y+15} {x-7},{y+4} {x-16},{y-4} {x-5},{y-5}" '
                     f'fill="#d9c46b" stroke="#7a6a2e"/>'
                     f'<text x="{x}" y="{y+34}" text-anchor="middle" font-size="18" fill="#d9c46b" '
                     f'font-weight="700" paint-order="stroke" stroke="#0c0e11" stroke-width="4">{lbl}</text>'
                     f'<text x="{x}" y="{y+50}" text-anchor="middle" font-size="10" fill="#9aa0b4">the living village</text></g>')
        else:
            p.append(f'<g><circle cx="{x}" cy="{y}" r="6" fill="#9aa0b4" stroke="#e7e8ee"/>'
                     f'<text x="{x}" y="{y+20}" text-anchor="middle" font-size="12" fill="#c9cede" '
                     f'paint-order="stroke" stroke="#0c0e11" stroke-width="3">{lbl}</text></g>')
    # title cartouche
    p.append(f'<g><rect x="30" y="28" width="360" height="52" rx="8" fill="#161a22" '
             f'stroke="#d9c46b" stroke-opacity="0.6"/>'
             f'<text x="48" y="56" font-size="23" fill="#d9c46b" font-weight="700" letter-spacing="1">The Realm of Oakhollow</text>'
             f'<text x="48" y="73" font-size="11" fill="#9aa0b4">Regional map · illustrative lore around the simulated village</text></g>')
    # compass
    p.append(f'<g transform="translate({W-64},76)"><circle r="26" fill="#161a22" stroke="#2b3040"/>'
             f'<polygon points="0,-22 5,0 0,7 -5,0" fill="#c85a5a"/>'
             f'<polygon points="0,22 5,0 0,-7 -5,0" fill="#5a6274"/>'
             f'<text x="0" y="-28" text-anchor="middle" font-size="11" fill="#9aa0b4">N</text></g>')
    p.append(f'<text x="{W-40}" y="{H-30}" text-anchor="end" font-size="10" fill="#6a7080" '
             f'font-style="italic">Oakhollow is the simulated village; neighbors are lore, not yet in-sim.</text>')

def build_realm_full():
    p,W,H = build_realm(); realm_marks(p,W,H); p.append('</svg>'); return "\n".join(p)

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT,"oakhollow-local.svg"),"w",encoding="utf-8").write(build_local())
    open(os.path.join(OUT,"realm-overview.svg"),"w",encoding="utf-8").write(build_realm_full())
    print("wrote", os.listdir(OUT))
