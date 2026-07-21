from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw, ImageFont


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Génère des figures prêtes à être injectées dans le rapport d'alternance "
            "à partir des sorties de comparaison et des exports FLOOD_LGD."
        )
    )
    parser.add_argument("--comparison-7d-dir", type=Path)
    parser.add_argument("--comparison-30d-dir", type=Path)
    parser.add_argument(
        "--flood-lgd",
        action="append",
        default=[],
        help='Associe un label à un export FLOOD_LGD, au format "label=chemin".',
    )
    parser.add_argument(
        "--copy-figure",
        action="append",
        default=[],
        help='Copie une capture manuelle vers le dossier de sortie, au format "nom=chemin".',
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("docs/alternance_report/generated_figures"),
    )
    return parser.parse_args()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def parse_assignment(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise ValueError(f"Expected name=path, got: {value}")
    name, raw_path = value.split("=", 1)
    name = name.strip()
    if not name:
        raise ValueError(f"Missing name in assignment: {value}")
    return name, Path(raw_path.strip())


def get_font(size: int, bold: bool = False):
    candidates = [
        Path(r"C:\Windows\Fonts\segoeuib.ttf") if bold else Path(r"C:\Windows\Fonts\segoeui.ttf"),
        Path(r"C:\Windows\Fonts\arialbd.ttf") if bold else Path(r"C:\Windows\Fonts\arial.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def read_tabular(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    if suffix in {".csv", ".txt"}:
        try:
            return pd.read_csv(path, sep=";", low_memory=False)
        except Exception:
            return pd.read_csv(path, low_memory=False)
    raise ValueError(f"Unsupported file type: {path}")


def resolve_preferred_file(folder: Path, stem: str) -> Path | None:
    for suffix in [".csv", ".xlsx", ".xls"]:
        candidate = folder / f"{stem}{suffix}"
        if candidate.exists():
            return candidate
    details_dir = folder / "details"
    for suffix in [".csv", ".xlsx", ".xls"]:
        candidate = details_dir / f"{stem}{suffix}"
        if candidate.exists():
            return candidate
    return None


def draw_wrapped_text(draw: ImageDraw.ImageDraw, text: str, font, x: int, y: int, width: int, fill) -> int:
    words = text.split()
    line = ""
    for word in words:
        candidate = word if not line else f"{line} {word}"
        if draw.textlength(candidate, font=font) <= width:
            line = candidate
        else:
            draw.text((x, y), line, font=font, fill=fill)
            y += font.size + 10
            line = word
    if line:
        draw.text((x, y), line, font=font, fill=fill)
        y += font.size + 10
    return y


def find_coverage_row(coverage_df: pd.DataFrame, level: str) -> pd.Series | None:
    level_mask = coverage_df["level"].astype(str).str.lower().eq(level.lower())
    measurement_candidates = coverage_df[level_mask]
    if measurement_candidates.empty:
        return None
    preferred_measurements = ["event", "events", "event_level"]
    for measurement in preferred_measurements:
        measurement_mask = measurement_candidates["measurement"].astype(str).str.lower().eq(measurement)
        if measurement_mask.any():
            return measurement_candidates[measurement_mask].iloc[0]
    return measurement_candidates.iloc[0]


def to_rate(row: pd.Series, matched_col: str, total_col: str) -> float:
    total = float(row[total_col]) if pd.notna(row[total_col]) else 0.0
    matched = float(row[matched_col]) if pd.notna(row[matched_col]) else 0.0
    return 0.0 if total == 0 else matched / total


def create_comparison_figure(rows: list[tuple[str, float, float]], output_path: Path) -> None:
    width, height = 1500, 840
    image = Image.new("RGB", (width, height), (248, 250, 252))
    draw = ImageDraw.Draw(image)

    title_font = get_font(34, bold=True)
    label_font = get_font(22)
    tick_font = get_font(18)
    legend_font = get_font(20)

    draw.text((90, 28), "Comparaison JRC vs GASPAR - synthèse automatique", fill=(15, 23, 42), font=title_font)
    draw.text((90, 68), "Taux de match extraits des fichiers coverage_overview disponibles sur le poste métier", fill=(71, 85, 105), font=label_font)

    chart_x0, chart_y0, chart_x1, chart_y1 = 130, 150, 1420, 690
    chart_h = chart_y1 - chart_y0
    max_pct = max(max(jrc, gaspar) for _, jrc, gaspar in rows) * 100
    max_pct = max(10.0, ((max_pct // 10) + 1) * 10)
    max_pct = min(max_pct, 100.0)

    for pct in range(0, int(max_pct) + 1, 10):
        y = chart_y1 - (pct / max_pct) * chart_h
        draw.line((chart_x0, y, chart_x1, y), fill=(220, 227, 234), width=1)
        draw.text((70, y - 10), f"{pct}%", fill=(100, 116, 139), font=tick_font)

    group_width = 230
    bar_width = 62
    gap_in_group = 34
    group_gap = 75
    start_x = chart_x0 + 40
    colors = {"JRC": (37, 99, 235), "GASPAR": (245, 118, 39)}

    for idx, (label, jrc_rate, gaspar_rate) in enumerate(rows):
        x_base = start_x + idx * (group_width + group_gap)
        for offset, name, rate in [(0, "JRC", jrc_rate), (bar_width + gap_in_group, "GASPAR", gaspar_rate)]:
            x0 = x_base + offset
            x1 = x0 + bar_width
            pct = rate * 100
            y0 = chart_y1 - (pct / max_pct) * chart_h
            draw.rounded_rectangle((x0, y0, x1, chart_y1), radius=10, fill=colors[name])
            value = f"{pct:.1f}%"
            tw = draw.textlength(value, font=tick_font)
            draw.text((x0 + (bar_width - tw) / 2, y0 - 28), value, fill=(15, 23, 42), font=tick_font)

        label_lines = label.replace("Département", "Départ.").split(" / ")
        y = chart_y1 + 16
        for line in label_lines:
            tw = draw.textlength(line, font=tick_font)
            draw.text((x_base + 20 + (bar_width + gap_in_group + bar_width - tw) / 2, y), line, fill=(15, 23, 42), font=tick_font)
            y += 24

    legend_x = 1030
    legend_y = 110
    draw.rounded_rectangle((legend_x, legend_y, legend_x + 320, legend_y + 90), radius=16, fill=(255, 255, 255), outline=(203, 213, 225))
    draw.rectangle((legend_x + 20, legend_y + 24, legend_x + 48, legend_y + 52), fill=colors["JRC"])
    draw.text((legend_x + 62, legend_y + 22), "JRC", fill=(15, 23, 42), font=legend_font)
    draw.rectangle((legend_x + 160, legend_y + 24, legend_x + 188, legend_y + 52), fill=colors["GASPAR"])
    draw.text((legend_x + 202, legend_y + 22), "GASPAR", fill=(15, 23, 42), font=legend_font)

    image.save(output_path)


def normalize_label(label: str) -> str:
    safe = label.strip().lower().replace(" ", "_").replace("-", "_")
    return "".join(ch for ch in safe if ch.isalnum() or ch == "_")


def create_lgd_summary_figure(df: pd.DataFrame, label: str, output_path: Path) -> None:
    width, height = 1600, 900
    image = Image.new("RGB", (width, height), (248, 250, 252))
    draw = ImageDraw.Draw(image)

    title_font = get_font(34, bold=True)
    subtitle_font = get_font(20)
    panel_title_font = get_font(22, bold=True)
    small_font = get_font(18)
    tiny_font = get_font(16)

    draw.text((70, 28), f"FLOOD_LGD - synthèse {label}", fill=(15, 23, 42), font=title_font)
    draw.text((70, 68), "Répartition des sources et chronologie des épisodes à partir du fichier final fourni", fill=(71, 85, 105), font=subtitle_font)

    source_series = (
        df["FLOOD_DATA_SOURCE"].fillna("NA").astype(str).replace({"": "NA"}).value_counts()
        if "FLOOD_DATA_SOURCE" in df.columns
        else pd.Series(dtype="int64")
    )
    area_series = (
        df["FLOOD_DATA_SOURCE_AREA"].fillna("NA").astype(str).replace({"": "NA"}).value_counts()
        if "FLOOD_DATA_SOURCE_AREA" in df.columns
        else pd.Series(dtype="int64")
    )

    year_counts = pd.Series(dtype="int64")
    if "DATE_REF_FLOOD" in df.columns:
        years = pd.to_datetime(df["DATE_REF_FLOOD"], errors="coerce").dropna().dt.year
        if not years.empty:
            year_counts = years.value_counts().sort_index()

    point_counts = pd.Series(dtype="int64")
    if "point_id" in df.columns:
        point_counts = df["point_id"].value_counts()

    panels = [
        (60, 150, 470, 500, "Source retenue point", source_series, (37, 99, 235)),
        (540, 150, 950, 500, "Source retenue area", area_series, (245, 118, 39)),
    ]

    for x0, y0, x1, y1, panel_title, series, color in panels:
        draw.rounded_rectangle((x0, y0, x1, y1), radius=24, fill=(255, 255, 255), outline=(203, 213, 225))
        draw.text((x0 + 18, y0 + 16), panel_title, fill=(15, 23, 42), font=panel_title_font)
        if series.empty:
            draw.text((x0 + 18, y0 + 62), "Colonne absente ou vide.", fill=(100, 116, 139), font=small_font)
            continue

        chart_x0, chart_y0 = x0 + 24, y0 + 90
        chart_x1, chart_y1 = x1 - 24, y1 - 30
        max_value = max(series.max(), 1)
        count = len(series)
        bar_gap = 18
        bar_width = max(28, (chart_x1 - chart_x0 - bar_gap * (count - 1)) / max(count, 1))
        for idx, (name, value) in enumerate(series.items()):
            bx0 = chart_x0 + idx * (bar_width + bar_gap)
            bx1 = bx0 + bar_width
            by0 = chart_y1 - (value / max_value) * (chart_y1 - chart_y0)
            draw.rounded_rectangle((bx0, by0, bx1, chart_y1), radius=8, fill=color)
            label = str(name)
            draw.text((bx0, chart_y1 + 6), label, fill=(15, 23, 42), font=tiny_font)
            draw.text((bx0, by0 - 22), str(int(value)), fill=(15, 23, 42), font=tiny_font)

    x0, y0, x1, y1 = 1020, 150, 1540, 500
    draw.rounded_rectangle((x0, y0, x1, y1), radius=24, fill=(255, 255, 255), outline=(203, 213, 225))
    draw.text((x0 + 18, y0 + 16), "Chronologie des épisodes", fill=(15, 23, 42), font=panel_title_font)
    if year_counts.empty:
        draw.text((x0 + 18, y0 + 62), "DATE_REF_FLOOD absente ou non renseignée.", fill=(100, 116, 139), font=small_font)
    else:
        chart_x0, chart_y0 = x0 + 24, y0 + 90
        chart_x1, chart_y1 = x1 - 24, y1 - 30
        max_value = max(year_counts.max(), 1)
        count = len(year_counts)
        bar_gap = 10
        bar_width = max(18, (chart_x1 - chart_x0 - bar_gap * (count - 1)) / max(count, 1))
        for idx, (year, value) in enumerate(year_counts.items()):
            bx0 = chart_x0 + idx * (bar_width + bar_gap)
            bx1 = bx0 + bar_width
            by0 = chart_y1 - (value / max_value) * (chart_y1 - chart_y0)
            draw.rounded_rectangle((bx0, by0, bx1, chart_y1), radius=6, fill=(15, 118, 110))
            draw.text((bx0, chart_y1 + 6), str(int(year)), fill=(15, 23, 42), font=tiny_font)
            draw.text((bx0, by0 - 22), str(int(value)), fill=(15, 23, 42), font=tiny_font)

    x0, y0, x1, y1 = 60, 560, 1540, 820
    draw.rounded_rectangle((x0, y0, x1, y1), radius=24, fill=(255, 255, 255), outline=(203, 213, 225))
    draw.text((x0 + 18, y0 + 16), "Indicateurs rapides", fill=(15, 23, 42), font=panel_title_font)

    metrics = [
        ("Nombre de lignes", f"{len(df):,}".replace(",", " ")),
        (
            "Points uniques",
            f"{df['point_id'].nunique():,}".replace(",", " ") if "point_id" in df.columns else "N/A",
        ),
        (
            "Épisodes max pour un point",
            str(int(point_counts.max())) if not point_counts.empty else "N/A",
        ),
        (
            "Part FLAG_FLOOD_ADR = 1",
            (
                f"{(pd.to_numeric(df['FLAG_FLOOD_ADR'], errors='coerce').fillna(0).gt(0).mean() * 100):.1f}%"
                if "FLAG_FLOOD_ADR" in df.columns and len(df) > 0
                else "N/A"
            ),
        ),
    ]

    x = x0 + 28
    for label_text, value_text in metrics:
        draw.rounded_rectangle((x, y0 + 70, x + 320, y0 + 190), radius=18, fill=(242, 245, 249), outline=(226, 232, 240))
        draw.text((x + 18, y0 + 92), label_text, fill=(71, 85, 105), font=small_font)
        draw.text((x + 18, y0 + 132), value_text, fill=(15, 23, 42), font=title_font)
        x += 360

    image.save(output_path)


def main() -> None:
    args = parse_args()
    ensure_dir(args.out_dir)

    manifest: dict[str, list[dict[str, str]]] = {"generated": [], "copied": [], "skipped": []}

    comparison_rows: list[tuple[str, float, float]] = []
    for window_label, folder in [("7 jours / Commune", args.comparison_7d_dir), ("30 jours / Commune", args.comparison_30d_dir)]:
        if folder is None:
            continue
        coverage_path = resolve_preferred_file(folder, "coverage_overview")
        if coverage_path is None:
            manifest["skipped"].append({"item": f"comparison_{window_label}", "reason": f"coverage_overview introuvable dans {folder}"})
            continue

        coverage_df = read_tabular(coverage_path)
        required = {"level", "measurement", "jrc_matched", "jrc_total", "gaspar_matched", "gaspar_total"}
        missing = required - set(coverage_df.columns)
        if missing:
            manifest["skipped"].append({"item": f"comparison_{window_label}", "reason": f"Colonnes manquantes dans {coverage_path}: {sorted(missing)}"})
            continue

        commune_row = find_coverage_row(coverage_df, "commune")
        dept_row = find_coverage_row(coverage_df, "department")
        if commune_row is not None:
            label = "7 jours / Commune" if "7 jours" in window_label else "30 jours / Commune"
            comparison_rows.append(
                (
                    label,
                    to_rate(commune_row, "jrc_matched", "jrc_total"),
                    to_rate(commune_row, "gaspar_matched", "gaspar_total"),
                )
            )
        if dept_row is not None:
            label = "7 jours / Département" if "7 jours" in window_label else "30 jours / Département"
            comparison_rows.append(
                (
                    label,
                    to_rate(dept_row, "jrc_matched", "jrc_total"),
                    to_rate(dept_row, "gaspar_matched", "gaspar_total"),
                )
            )

    if comparison_rows:
        output_path = args.out_dir / "jrc_gaspar_comparison_snapshot.png"
        create_comparison_figure(comparison_rows, output_path)
        manifest["generated"].append({"item": "jrc_gaspar_comparison_snapshot", "path": str(output_path)})

    for assignment in args.flood_lgd:
        label, path = parse_assignment(assignment)
        if not path.exists():
            manifest["skipped"].append({"item": label, "reason": f"Fichier introuvable: {path}"})
            continue
        df = read_tabular(path)
        safe_label = normalize_label(label)
        output_path = args.out_dir / f"flood_lgd_source_mix_{safe_label}.png"
        create_lgd_summary_figure(df, label, output_path)
        manifest["generated"].append({"item": label, "path": str(output_path)})

    for assignment in args.copy_figure:
        name, path = parse_assignment(assignment)
        if not path.exists():
            manifest["skipped"].append({"item": name, "reason": f"Capture introuvable: {path}"})
            continue
        image = Image.open(path)
        destination = args.out_dir / f"{name}.png"
        image.save(destination)
        manifest["copied"].append({"item": name, "path": str(destination)})

    manifest_path = args.out_dir / "figure_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Manifest écrit : {manifest_path}")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
