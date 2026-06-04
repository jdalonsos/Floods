import { jsx } from "@oai/artifact-tool/presentation-jsx/jsx-runtime";
import { auditStats } from "./deck_content.mjs";
import {
  THEME,
  Background,
  Label,
  Title,
  Panel,
  BodyText,
  SmallText,
  ProgressRow,
  Footer,
} from "./deck_helpers.mjs";

function WindowPanel({ slide, ctx, left, title, stats, fill, accent }) {
  Panel({
    slide,
    ctx,
    left,
    top: 208,
    width: 512,
    height: 396,
    fill,
    line: { style: "solid", fill: THEME.line, width: 1 },
    name: title,
  });
  Panel({
    slide,
    ctx,
    left,
    top: 208,
    width: 512,
    height: 8,
    fill: accent,
    line: { style: "solid", fill: THEME.transparent, width: 0 },
    name: `${title}Accent`,
  });
  BodyText({
    slide,
    ctx,
    left: left + 22,
    top: 228,
    width: 280,
    height: 28,
    text: title,
    size: 24,
    style: { fontSize: 24, bold: true, typeface: ctx.fonts.title, color: THEME.ink },
  });
  SmallText({
    slide,
    ctx,
    left: left + 22,
    top: 264,
    width: 360,
    height: 18,
    text: "Commune-level event matching",
    color: THEME.muted,
  });
  ProgressRow({
    slide,
    ctx,
    left: left + 22,
    top: 296,
    width: 468,
    label: `JRC matched (${stats.jrcRate.toFixed(1)}%)`,
    value: stats.jrcMatched,
    total: stats.jrcTotal,
    color: THEME.blue,
    note: `${stats.jrcExclusive} JRC events remain exclusive under this window.`,
  });
  ProgressRow({
    slide,
    ctx,
    left: left + 22,
    top: 392,
    width: 468,
    label: `Gaspar matched (${stats.gasparRate.toFixed(1)}%)`,
    value: stats.gasparMatched,
    total: stats.gasparTotal,
    color: THEME.coral,
    note: `${stats.gasparExclusive.toLocaleString("en-US")} Gaspar event groups remain exclusive under this window.`,
  });
}

export async function slide05(presentation, ctx) {
  const slide = presentation.slides.add();

  jsx(Background, { slide, ctx, variant: "paper" });
  jsx(Label, { slide, ctx, left: 54, top: 42, width: 280, text: "NATIONAL AUDIT" });
  jsx(Title, {
    slide,
    ctx,
    left: 54,
    top: 78,
    width: 1120,
    height: 66,
    text: auditStats.title,
    size: 34,
  });
  jsx(SmallText, {
    slide,
    ctx,
    left: 54,
    top: 146,
    width: 1050,
    height: 22,
    text: auditStats.reading,
  });

  WindowPanel({
    slide,
    ctx,
    left: 54,
    title: "7-day window",
    stats: auditStats.commune7d,
    fill: "#FFFDFC",
    accent: THEME.coral,
  });
  WindowPanel({
    slide,
    ctx,
    left: 606,
    title: "30-day window",
    stats: auditStats.commune30d,
    fill: "#F8FBFF",
    accent: THEME.blue,
  });

  Panel({
    slide,
    ctx,
    left: 54,
    top: 620,
    width: 1116,
    height: 68,
    fill: "#FFFDFC",
    line: { style: "solid", fill: THEME.line, width: 1 },
    name: "BottomNote",
  });
  BodyText({
    slide,
    ctx,
    left: 78,
    top: 634,
    width: 1068,
    height: 24,
    text:
      `Department-level rates: 7-day JRC ${auditStats.department7d.jrcRate.toFixed(1)}% / Gaspar ${auditStats.department7d.gasparRate.toFixed(1)}%; 30-day JRC ${auditStats.department30d.jrcRate.toFixed(1)}% / Gaspar ${auditStats.department30d.gasparRate.toFixed(1)}%.`,
    size: 19,
    color: THEME.ink,
  });
  SmallText({
    slide,
    ctx,
    left: 78,
    top: 658,
    width: 1068,
    height: 18,
    text:
      `Row coverage: JRC ${auditStats.rowCoverage.jrc7d} then ${auditStats.rowCoverage.jrc30d}; Gaspar ${auditStats.rowCoverage.gaspar7d} then ${auditStats.rowCoverage.gaspar30d}.`,
  });

  jsx(Footer, {
    slide,
    ctx,
    text: "Numbers pulled from data/processed/jrc_gaspar_comparison_flexible_7d and ..._30d using the existing France comparison logic.",
  });

  return slide;
}
