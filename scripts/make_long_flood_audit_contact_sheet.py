from pathlib import Path
from PIL import Image, ImageDraw

folder = Path("outputs/long_flood_duration_audit_qa_pass2")
files = sorted(folder.glob("page-*.png"))
thumbs = []
for path in files:
    image = Image.open(path).convert("RGB")
    image.thumbnail((330, 430))
    thumbs.append((path, image.copy()))
sheet = Image.new("RGB", (1050, ((len(thumbs) + 2) // 3) * 470), "#D9D9D9")
draw = ImageDraw.Draw(sheet)
for i, (path, image) in enumerate(thumbs):
    x = (i % 3) * 350 + 10
    y = (i // 3) * 470 + 25
    sheet.paste(image, (x, y))
    draw.text((x, y - 18), path.stem, fill="black")
sheet.save(folder / "contact_sheet.png")
print(folder / "contact_sheet.png")
