import { jsx } from "@oai/artifact-tool/presentation-jsx/jsx-runtime";
import { workflow } from "./deck_content.mjs";
import {
  THEME,
  Background,
  Label,
  Title,
  Panel,
  BodyText,
  SmallText,
  ArrowConnector,
  Footer,
} from "./deck_helpers.mjs";

function ColumnBlock({ slide, ctx, left, top, width, title, items, fill, accent }) {
  Panel({
    slide,
    ctx,
    left,
    top,
    width,
    height: 360,
    fill,
    line: { style: "solid", fill: THEME.line, width: 1 },
    name: title,
  });
  Panel({
    slide,
    ctx,
    left,
    top,
    width,
    height: 8,
    fill: accent,
    line: { style: "solid", fill: THEME.transparent, width: 0 },
    name: `${title}Accent`,
  });
  BodyText({
    slide,
    ctx,
    left: left + 18,
    top: top + 20,
    width: width - 36,
    height: 32,
    text: title,
    size: 23,
    style: { fontSize: 23, bold: true, typeface: ctx.fonts.title, color: THEME.ink },
  });
  items.forEach((item, index) => {
    BodyText({
      slide,
      ctx,
      left: left + 18,
      top: top + 72 + index * 68,
      width: width - 36,
      height: 54,
      text: item,
      size: 18,
      color: THEME.ink,
      lineSpacing: 1.1,
    });
  });
}

export async function slide02(presentation, ctx) {
  const slide = presentation.slides.add();

  jsx(Background, { slide, ctx, variant: "paper" });
  jsx(Label, { slide, ctx, left: 54, top: 42, width: 300, text: "SYSTEM VIEW" });
  jsx(Title, {
    slide,
    ctx,
    left: 54,
    top: 78,
    width: 1120,
    height: 66,
    text: workflow.title,
    size: 34,
  });
  jsx(SmallText, {
    slide,
    ctx,
    left: 54,
    top: 146,
    width: 1020,
    height: 22,
    text: "The same stack now supports raw-data transformation, commune reconciliation, visual comparison, and manual evidence work.",
  });

  ColumnBlock({
    slide,
    ctx,
    left: 54,
    top: 208,
    width: 258,
    title: "Source layer",
    items: workflow.sources,
    fill: "#FBF6ED",
    accent: THEME.coral,
  });
  ColumnBlock({
    slide,
    ctx,
    left: 340,
    top: 208,
    width: 258,
    title: "Harmonization layer",
    items: workflow.harmonization,
    fill: "#EEF3FB",
    accent: THEME.blue,
  });
  ColumnBlock({
    slide,
    ctx,
    left: 626,
    top: 208,
    width: 258,
    title: "Project outputs",
    items: workflow.outputs,
    fill: "#EAF5F3",
    accent: THEME.teal,
  });
  ColumnBlock({
    slide,
    ctx,
    left: 912,
    top: 208,
    width: 258,
    title: "Analyst tools",
    items: workflow.analystTools,
    fill: "#F7F1D9",
    accent: THEME.gold,
  });

  jsx(ArrowConnector, { slide, ctx, left: 314, top: 324, width: 18, color: THEME.coral });
  jsx(ArrowConnector, { slide, ctx, left: 600, top: 324, width: 18, color: THEME.blue });
  jsx(ArrowConnector, { slide, ctx, left: 886, top: 324, width: 18, color: THEME.teal });

  Panel({
    slide,
    ctx,
    left: 54,
    top: 590,
    width: 1116,
    height: 74,
    fill: "#FFFDFC",
    line: { style: "solid", fill: THEME.line, width: 1 },
    name: "Callout",
  });
  BodyText({
    slide,
    ctx,
    left: 78,
    top: 606,
    width: 1070,
    height: 48,
    text: `${workflow.callouts[0]}\n${workflow.callouts[1]}`,
    size: 17,
    color: THEME.ink,
    lineSpacing: 1.1,
  });

  jsx(Footer, {
    slide,
    ctx,
    text: "Built from existing project logic in the France comparison scripts, commune-activity loader, and point-screening workflow.",
  });

  return slide;
}
