import { jsx } from "@oai/artifact-tool/presentation-jsx/jsx-runtime";
import { t20 } from "./deck_content.mjs";
import {
  THEME,
  Background,
  Label,
  Title,
  MetricCard,
  Panel,
  BodyText,
  BulletList,
  DecisionBar,
  Footer,
} from "./deck_helpers.mjs";

export async function slide09(presentation, ctx) {
  const slide = presentation.slides.add();

  jsx(Background, { slide, ctx, variant: "paper" });
  jsx(Label, { slide, ctx, left: 54, top: 42, width: 240, text: "T20 CHECK" });
  jsx(Title, {
    slide,
    ctx,
    left: 54,
    top: 78,
    width: 1120,
    height: 66,
    text: t20.title,
    size: 34,
  });

  const cards = [
    { label: "Rows checked", value: t20.totalPoints, accent: THEME.slate, fill: THEME.white },
    { label: "LAU matched", value: t20.lauMatched, accent: THEME.blue, fill: "#EEF3FB" },
    { label: "Any JRC event in LAU", value: t20.touchedAny, accent: THEME.teal, fill: "#EAF5F3" },
    { label: "Positive local hit", value: t20.positiveHit, accent: THEME.coral, fill: "#FBEEE9" },
    { label: "Positive event hits", value: t20.hitEventCount, accent: THEME.gold, fill: "#F7F1D9" },
  ];
  cards.forEach((card, index) => {
    jsx(MetricCard, {
      slide,
      ctx,
      left: 54 + index * 224,
      top: 186,
      width: 204,
      height: 108,
      label: card.label,
      value: String(card.value),
      accent: card.accent,
      fill: card.fill,
    });
  });

  Panel({
    slide,
    ctx,
    left: 54,
    top: 324,
    width: 500,
    height: 302,
    fill: "#FFFDFC",
    line: { style: "solid", fill: THEME.line, width: 1 },
    name: "RulePanel",
  });
  BodyText({
    slide,
    ctx,
    left: 78,
    top: 346,
    width: 280,
    height: 28,
    text: "Applied rule",
    size: 23,
    style: { fontSize: 23, bold: true, typeface: ctx.fonts.title, color: THEME.ink },
  });
  jsx(BulletList, {
    slide,
    ctx,
    left: 78,
    top: 392,
    width: 438,
    items: t20.rule,
    rowHeight: 58,
    bulletColor: THEME.coral,
    size: 17,
  });

  Panel({
    slide,
    ctx,
    left: 578,
    top: 324,
    width: 592,
    height: 302,
    fill: "#FFFDFC",
    line: { style: "solid", fill: THEME.line, width: 1 },
    name: "DecisionPanel",
  });
  BodyText({
    slide,
    ctx,
    left: 602,
    top: 346,
    width: 260,
    height: 28,
    text: "Decision-path breakdown",
    size: 23,
    style: { fontSize: 23, bold: true, typeface: ctx.fonts.title, color: THEME.ink },
  });
  t20.decisionPaths.forEach((row, index) => {
    jsx(DecisionBar, {
      slide,
      ctx,
      left: 602,
      top: 392 + index * 56,
      width: 520,
      label: row.label,
      value: row.value,
      total: t20.totalPoints,
      color: row.color,
    });
  });

  Panel({
    slide,
    ctx,
    left: 54,
    top: 646,
    width: 1116,
    height: 44,
    fill: "#FFFDFC",
    line: { style: "solid", fill: THEME.line, width: 1 },
    name: "CasePanel",
  });
  BodyText({
    slide,
    ctx,
    left: 78,
    top: 658,
    width: 1068,
    height: 22,
    text: `Positive case: ${t20.positiveCase}`,
    size: 18,
    color: THEME.ink,
  });

  jsx(Footer, {
    slide,
    ctx,
    text: "Workbook: data/processed/T20_Anonymised_jrc_flood_check.xlsx. Decision paths show why most rows stay negative even after successful LAU geocoding.",
  });

  return slide;
}
