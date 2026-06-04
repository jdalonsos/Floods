import { jsx } from "@oai/artifact-tool/presentation-jsx/jsx-runtime";
import { overview } from "./deck_content.mjs";
import {
  THEME,
  Background,
  AccentBand,
  Label,
  Title,
  BodyText,
  MetricCard,
  Footer,
  Rule,
} from "./deck_helpers.mjs";

export async function slide01(presentation, ctx) {
  const slide = presentation.slides.add();

  jsx(Background, { slide, ctx, variant: "dark" });
  jsx(AccentBand, { slide, ctx, left: 0, top: 0, width: 18, height: ctx.H, color: THEME.coral });

  jsx(Label, {
    slide,
    ctx,
    left: 58,
    top: 54,
    width: 280,
    text: "TWO-WEEK SUMMARY",
    color: "#F4B39F",
  });
  jsx(Title, {
    slide,
    ctx,
    left: 58,
    top: 94,
    width: 780,
    height: 110,
    text: overview.title,
    dark: true,
    size: 46,
  });
  jsx(BodyText, {
    slide,
    ctx,
    left: 58,
    top: 212,
    width: 650,
    height: 88,
    text: overview.subtitle,
    size: 24,
    color: "#E6ECF5",
    lineSpacing: 1.15,
  });
  jsx(Rule, {
    slide,
    ctx,
    left: 58,
    top: 316,
    width: 760,
    height: 2,
    color: "#314056",
    opacityFill: "#314056",
  });
  jsx(BodyText, {
    slide,
    ctx,
    left: 58,
    top: 340,
    width: 710,
    height: 178,
    text: overview.highlights.join("\n\n"),
    size: 21,
    color: "#E6ECF5",
    lineSpacing: 1.1,
  });

  jsx(MetricCard, {
    slide,
    ctx,
    left: 860,
    top: 108,
    width: 310,
    height: 118,
    label: "Main build",
    value: "France comparison app",
    accent: THEME.coral,
    fill: "#F7EFE6",
  });
  jsx(MetricCard, {
    slide,
    ctx,
    left: 860,
    top: 246,
    width: 148,
    height: 112,
    label: "Audit docs",
    value: "EN + FR",
    accent: THEME.blue,
    fill: "#EEF3FB",
  });
  jsx(MetricCard, {
    slide,
    ctx,
    left: 1022,
    top: 246,
    width: 148,
    height: 112,
    label: "T20 result",
    value: "1 / 49 hit",
    accent: THEME.teal,
    fill: "#EAF5F3",
  });
  jsx(MetricCard, {
    slide,
    ctx,
    left: 860,
    top: 378,
    width: 310,
    height: 140,
    label: "Core finding",
    value: "Commune-level match stays low, but manual checks show real evidence on both sides.",
    accent: THEME.gold,
    fill: "#F7F1D9",
  });

  jsx(Footer, {
    slide,
    ctx,
    dark: true,
    text: `${overview.dateLabel} | Scope: July 2021 comparison, Streamlit viewer, national audit, and T20 point-screening workflow.`,
  });

  return slide;
}
