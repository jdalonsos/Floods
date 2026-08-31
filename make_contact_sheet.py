from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

folder = Path("outputs/rapport_alternance_donnees/qa_hanze2")
files = sorted(folder.glob("page-*.png"))
thumb_w = 320
thumbs = []
for p in files:
    im = Image.open(p).convert("RGB")
    h = round(im.height * thumb_w / im.width)
    im.thumbnail((thumb_w, h))
    thumbs.append((p, im.copy()))
rows = (len(thumbs) + 3) // 4
sheet = Image.new("RGB", (4 * 350, rows * 480), "#D9D9D9")
d = ImageDraw.Draw(sheet)
for i, (p, im) in enumerate(thumbs):
    x = (i % 4) * 350 + 15
    y = (i // 4) * 480 + 35
    sheet.paste(im, (x, y))
    d.text((x, 10 + (i // 4) * 480), p.stem, fill="black")
sheet.save(folder / "contact_sheet.png")
print(len(files))
