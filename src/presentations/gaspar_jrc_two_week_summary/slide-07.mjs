import { jsx } from "@oai/artifact-tool/presentation-jsx/jsx-runtime";
import { horizonAudit } from "./deck_content.mjs";
import {
  THEME,
  Background,
  Label,
  Title,
  MetricCard,
  Panel,
  BodyText,
  SmallText,
  BulletList,
  Footer,
} from "./deck_helpers.mjs";

export async function slide07(presentation, ctx) {
  const slide = presentation.slides.add();

  jsx(Background, { slide, ctx, variant: "paper" });
  jsx(Label, { slide, ctx, left: 54, top: 42, width: 320, text: "HORIZON AUDIT" });
  jsx(Title, {
    slide,
    ctx,
    left: 54,
    top: 78,
    width: 1120,
    height: 66,
    text: horizonAudit.title,
    size: 33,
  });
  jsx(SmallText, {
    slide,
    ctx,
    left: 54,
    top: 146,
    width: 1060,
    height: 22,
    text: horizonAudit.mainReading,
  });

  jsx(MetricCard, {
    slide,
    ctx,
    left: 54,
    top: 184,
    width: 228,
    height: 112,
    label: "Largest mismatch",
    value: "1,312 communes",
    accent: THEME.blue,
    fill: "#EEF3FB",
  });
  jsx(MetricCard, {
    slide,
    ctx,
    left: 298,
    top: 184,
    width: 228,
    height: 112,
    label: "Strongest Gaspar quarter",
    value: "707 Gaspar only",
    accent: THEME.coral,
    fill: "#FBEEE9",
  });
  jsx(MetricCard, {
    slide,
    ctx,
    left: 542,
    top: 184,
    width: 228,
    height: 112,
    label: "Recent major case",
    value: "1,080 mismatch",
    accent: THEME.teal,
    fill: "#EAF5F3",
  });
  jsx(MetricCard, {
    slide,
    ctx,
    left: 786,
    top: 184,
    width: 384,
    height: 112,
    label: "Coverage horizon",
    value: "2015-Q1 to 2024-Q4",
    accent: THEME.gold,
    fill: "#F7F1D9",
  });

  Panel({
    slide,
    ctx,
    left: 54,
    top: 324,
    width: 636,
    height: 290,
    fill: "#FFFDFC",
    line: { style: "solid", fill: THEME.line, width: 1 },
    name: "TopPeriodsPanel",
  });
  BodyText({
    slide,
    ctx,
    left: 78,
    top: 346,
    width: 260,
    height: 30,
    text: "Top disagreement periods",
    size: 24,
    style: { fontSize: 24, bold: true, typeface: ctx.fonts.title, color: THEME.ink },
  });
  horizonAudit.topPeriods.slice(0, 3).forEach((row, index) => {
    const rowTop = 394 + index * 72;
    BodyText({
      slide,
      ctx,
      left: 78,
      top: rowTop,
      width: 574,
      height: 22,
      text: `${row.label}: ${row.metrics}`,
      size: 18,
      style: { fontSize: 18, bold: true, typeface: ctx.fonts.title, color: THEME.ink },
    });
    SmallText({
      slide,
      ctx,
      left: 78,
      top: rowTop + 30,
      width: 574,
      height: 22,
      text: row.takeaway,
      color: THEME.muted,
    });
  });

  Panel({
    slide,
    ctx,
    left: 714,
    top: 324,
    width: 456,
    height: 290,
    fill: "#F8FBFF",
    line: { style: "solid", fill: THEME.line, width: 1 },
    name: "SupportPanel",
  });
  BodyText({
    slide,
    ctx,
    left: 738,
    top: 346,
    width: 280,
    height: 30,
    text: "Other important flood families",
    size: 24,
    style: { fontSize: 24, bold: true, typeface: ctx.fonts.title, color: THEME.ink },
  });
  jsx(BulletList, {
    slide,
    ctx,
    left: 738,
    top: 396,
    width: 394,
    items: horizonAudit.supportingPeriods,
    rowHeight: 74,
    bulletColor: THEME.gold,
    size: 17,
  });

  Panel({
    slide,
    ctx,
    left: 54,
    top: 636,
    width: 1116,
    height: 30,
    fill: THEME.transparent,
    line: { style: "solid", fill: THEME.transparent, width: 0 },
    name: "ConclusionStrip",
  });
  BodyText({
    slide,
    ctx,
    left: 54,
    top: 636,
    width: 1116,
    height: 26,
    text: "Bottom line: the mismatch is historically persistent and changes shape over time, rather than disappearing once one famous flood is explained.",
    size: 20,
    color: THEME.ink,
    style: { fontSize: 20, bold: true, typeface: ctx.fonts.title, color: THEME.ink },
  });

  jsx(Footer, {
    slide,
    ctx,
    text: "Source: docs/gaspar_jrc_horizon_audit_en.md and ..._fr.md, generated from the region-quarter ranking and mapped manual checks.",
  });

  return slide;
}
