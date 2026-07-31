from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "web_images"
OUT.mkdir(exist_ok=True)

W, H = 1800, 1000
NAVY = "#17365D"
BLUE = "#2F75B5"
LIGHT_BLUE = "#DCEAF7"
WATER = "#4FA7D8"
GREEN = "#70AD47"
DARK_GREEN = "#3D7B2B"
SOIL = "#C89F72"
DARK_SOIL = "#8B6544"
GREY = "#6B7280"
LIGHT_GREY = "#F3F6F9"
ORANGE = "#ED7D31"
WHITE = "#FFFFFF"


def font(size, bold=False):
    candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


F_TITLE = font(48, True)
F_SUB = font(33, True)
F_LABEL = font(27, True)
F_TEXT = font(23)
F_SMALL = font(19)


def centered(draw, xy, text, fnt, fill=NAVY):
    x, y = xy
    box = draw.textbbox((0, 0), text, font=fnt)
    draw.text((x - (box[2] - box[0]) / 2, y), text, font=fnt, fill=fill)


def arrow(draw, start, end, color=BLUE, width=12, head=28):
    draw.line([start, end], fill=color, width=width)
    x1, y1 = start
    x2, y2 = end
    dx, dy = x2 - x1, y2 - y1
    length = max((dx * dx + dy * dy) ** 0.5, 1)
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    base_x, base_y = x2 - ux * head, y2 - uy * head
    points = [
        (x2, y2),
        (base_x + px * head * 0.55, base_y + py * head * 0.55),
        (base_x - px * head * 0.55, base_y - py * head * 0.55),
    ]
    draw.polygon(points, fill=color)


def cloud_and_rain(draw, cx, top, rain_bottom, drops=7):
    for dx, dy, r in [(-100, 25, 58), (-35, 0, 72), (40, 18, 62), (100, 34, 48)]:
        draw.ellipse((cx + dx - r, top + dy - r, cx + dx + r, top + dy + r), fill="#D9E2F3", outline=BLUE, width=4)
    draw.rounded_rectangle((cx - 155, top + 15, cx + 155, top + 82), radius=35, fill="#D9E2F3", outline=BLUE, width=4)
    for i in range(drops):
        x = cx - 125 + i * 42
        arrow(draw, (x, top + 100), (x - 7, rain_bottom), color=WATER, width=6, head=17)


def header(draw, title, subtitle):
    centered(draw, (W / 2, 30), title, F_TITLE)
    centered(draw, (W / 2, 92), subtitle, F_TEXT, GREY)
    draw.line((120, 145, W - 120, 145), fill="#C9D6E2", width=3)


def diagram_saturation():
    im = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(im)
    header(d, "Humidité antérieure et saturation du sol", "À pluie identique, la réaction du bassin peut être très différente")
    panels = [(90, 180, 855, 900), (945, 180, 1710, 900)]
    titles = ["SOL SEC OU PEU HUMIDE", "SOL DÉJÀ SATURÉ"]
    for idx, (x1, y1, x2, y2) in enumerate(panels):
        d.rounded_rectangle((x1, y1, x2, y2), radius=28, fill=LIGHT_GREY, outline="#B8C7D6", width=4)
        centered(d, ((x1 + x2) / 2, y1 + 24), titles[idx], F_SUB, DARK_GREEN if idx == 0 else ORANGE)
        ground_y = 475
        d.rectangle((x1 + 30, ground_y, x2 - 30, y2 - 35), fill=SOIL, outline=DARK_SOIL, width=3)
        d.rectangle((x1 + 30, ground_y, x2 - 30, ground_y + 24), fill=GREEN)
        cloud_and_rain(d, (x1 + x2) / 2, 340, 465, drops=6)
        # Soil pores: mostly air on the left, mostly water on the right.
        for row in range(5):
            for col in range(8):
                cx = x1 + 85 + col * 82 + (row % 2) * 22
                cy = 545 + row * 62
                if cx > x2 - 55:
                    continue
                filled = idx == 1 or (row >= 3 and col % 2 == 0)
                d.ellipse((cx - 21, cy - 16, cx + 21, cy + 16), fill=WATER if filled else WHITE, outline=DARK_SOIL, width=3)
        if idx == 0:
            arrow(d, ((x1 + x2) / 2, 500), ((x1 + x2) / 2, 780), color=BLUE, width=16, head=35)
            d.rounded_rectangle((x1 + 75, 785, x2 - 75, 860), radius=18, fill=LIGHT_BLUE)
            centered(d, ((x1 + x2) / 2, 800), "Infiltration et stockage importants", F_LABEL, NAVY)
            d.text((x1 + 52, 510), "Pores contenant\nencore de l’air", font=F_TEXT, fill=DARK_SOIL)
        else:
            arrow(d, (x1 + 305, 500), (x1 + 105, 455), color=ORANGE, width=16, head=35)
            arrow(d, (x2 - 305, 500), (x2 - 105, 455), color=ORANGE, width=16, head=35)
            d.rounded_rectangle((x1 + 65, 785, x2 - 65, 860), radius=18, fill="#FCE4D6")
            centered(d, ((x1 + x2) / 2, 800), "Ruissellement rapide vers le cours d’eau", F_LABEL, "#A64B12")
            d.text((x1 + 55, 510), "Pores déjà\nremplis d’eau", font=F_TEXT, fill=NAVY)
    centered(d, (W / 2, 935), "L’état du sol avant la pluie détermine la quantité d’eau qui peut encore être absorbée.", F_LABEL, NAVY)
    im.save(OUT / "schema_fr_saturation_sol.png", quality=95)


def diagram_impermeabilisation():
    im = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(im)
    header(d, "Imperméabilisation des sols et ruissellement", "L’urbanisation modifie la destination de l’eau de pluie")
    panels = [(95, 185, 860, 880), (940, 185, 1705, 880)]
    for idx, (x1, y1, x2, y2) in enumerate(panels):
        d.rounded_rectangle((x1, y1, x2, y2), radius=28, fill=LIGHT_GREY, outline="#B8C7D6", width=4)
        title = "BASSIN VÉGÉTALISÉ" if idx == 0 else "BASSIN TRÈS URBANISÉ"
        centered(d, ((x1 + x2) / 2, y1 + 24), title, F_SUB, DARK_GREEN if idx == 0 else GREY)
        ground_y = 500
        d.rectangle((x1 + 35, ground_y, x2 - 35, y2 - 35), fill=SOIL, outline=DARK_SOIL, width=3)
        if idx == 0:
            d.rectangle((x1 + 35, ground_y - 18, x2 - 35, ground_y + 12), fill=GREEN)
            for tx in [x1 + 150, x1 + 355, x1 + 590]:
                d.rectangle((tx - 12, ground_y - 110, tx + 12, ground_y), fill=DARK_SOIL)
                d.ellipse((tx - 58, ground_y - 170, tx + 58, ground_y - 65), fill=GREEN, outline=DARK_GREEN, width=3)
        else:
            d.polygon([(x1 + 35, ground_y), (x2 - 35, ground_y), (x2 - 35, ground_y + 90), (x1 + 35, ground_y + 65)], fill="#7F8C8D")
            for bx in [x1 + 120, x1 + 360, x1 + 585]:
                d.rectangle((bx, ground_y - 135, bx + 130, ground_y - 10), fill="#B4C6E7", outline=NAVY, width=3)
                d.polygon([(bx - 12, ground_y - 135), (bx + 65, ground_y - 205), (bx + 142, ground_y - 135)], fill="#5B9BD5", outline=NAVY)
        cloud_and_rain(d, (x1 + x2) / 2, 330, 475, drops=6)
        if idx == 0:
            arrow(d, ((x1 + x2) / 2, 525), ((x1 + x2) / 2, 760), color=BLUE, width=18, head=40)
            arrow(d, (x1 + 260, 520), (x1 + 110, 480), color=WATER, width=8, head=22)
            d.rounded_rectangle((x1 + 145, 735, x2 - 145, 845), radius=18, fill="#E2F0D9")
            centered(d, ((x1 + x2) / 2, 752), "Infiltration ≈ 50 %", F_LABEL, NAVY)
            centered(d, ((x1 + x2) / 2, 798), "Ruissellement ≈ 10 %", F_LABEL, DARK_GREEN)
        else:
            arrow(d, (x1 + 230, 520), (x1 + 80, 475), color=ORANGE, width=18, head=40)
            arrow(d, (x2 - 230, 520), (x2 - 80, 475), color=ORANGE, width=18, head=40)
            arrow(d, ((x1 + x2) / 2, 540), ((x1 + x2) / 2, 670), color=BLUE, width=7, head=20)
            d.rounded_rectangle((x1 + 145, 735, x2 - 145, 845), radius=18, fill="#FCE4D6")
            centered(d, ((x1 + x2) / 2, 752), "Infiltration ≈ 15 %", F_LABEL, NAVY)
            centered(d, ((x1 + x2) / 2, 798), "Ruissellement ≈ 55 %", F_LABEL, "#A64B12")
    centered(d, (W / 2, 925), "Les routes, parkings et bâtiments réduisent l’infiltration et accélèrent l’arrivée de l’eau dans les réseaux.", F_LABEL, NAVY)
    im.save(OUT / "schema_fr_impermeabilisation.png", quality=95)


def diagram_types_inondation():
    im = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(im)
    header(d, "Les principaux mécanismes d’inondation", "Plusieurs origines peuvent se combiner sur un même territoire")
    # Landscape and groundwater.
    d.polygon([(80, 660), (80, 525), (350, 500), (610, 535), (900, 475), (1220, 525), (1715, 420), (1715, 660)], fill="#D8C3A5", outline=DARK_SOIL)
    d.rectangle((80, 660, 1715, 860), fill=SOIL)
    d.polygon([(80, 755), (430, 720), (780, 750), (1120, 690), (1715, 630), (1715, 860), (80, 860)], fill=LIGHT_BLUE, outline=WATER)
    # Sea and coastal flooding.
    d.rectangle((80, 465, 360, 620), fill=WATER)
    for y in [490, 530, 570]:
        d.arc((90, y - 25, 330, y + 30), 180, 350, fill=WHITE, width=5)
    arrow(d, (215, 450), (410, 500), color=BLUE, width=12, head=30)
    # River and overflow.
    d.polygon([(660, 535), (750, 485), (845, 535), (980, 535), (930, 585), (720, 585)], fill=WATER, outline=BLUE)
    arrow(d, (800, 500), (645, 455), color=BLUE, width=11, head=28)
    arrow(d, (850, 500), (1015, 455), color=BLUE, width=11, head=28)
    # City and surface runoff.
    for bx, by in [(1080, 445), (1240, 420), (1410, 390)]:
        d.rectangle((bx, by, bx + 125, 555), fill="#B4C6E7", outline=NAVY, width=3)
        d.polygon([(bx - 10, by), (bx + 62, by - 70), (bx + 135, by)], fill="#5B9BD5", outline=NAVY)
    cloud_and_rain(d, 1450, 230, 360, drops=5)
    arrow(d, (1550, 520), (1310, 570), color=ORANGE, width=14, head=34)
    arrow(d, (1260, 570), (1040, 590), color=ORANGE, width=14, head=34)
    # Groundwater rise.
    for x in [1160, 1280, 1400]:
        arrow(d, (x, 760), (x, 625), color=WATER, width=10, head=27)
    # Labels.
    labels = [
        (225, 715, "SUBMERSION\nMARINE", "La mer franchit\nle littoral"),
        (785, 715, "DÉBORDEMENT\nDE COURS D’EAU", "La rivière sort\nde son lit"),
        (1185, 190, "RUISSELLEMENT\nPLUVIAL", "L’eau s’écoule\nen surface"),
        (1450, 715, "REMONTÉE\nDE NAPPE", "La nappe atteint\nla surface"),
    ]
    for cx, cy, title, desc in labels:
        d.rounded_rectangle((cx - 175, cy - 12, cx + 175, cy + 128), radius=20, fill=WHITE, outline="#AAB7C4", width=3)
        centered(d, (cx, cy), title, F_LABEL, NAVY)
        centered(d, (cx, cy + 68), desc, F_SMALL, GREY)
    centered(d, (W / 2, 925), "Origine de l’eau + voie de propagation + enjeux exposés = mécanisme d’inondation", F_LABEL, NAVY)
    im.save(OUT / "schema_fr_types_inondation.png", quality=95)


if __name__ == "__main__":
    diagram_saturation()
    diagram_impermeabilisation()
    diagram_types_inondation()
    print("Schémas français créés dans", OUT)
