import { jsx } from "@oai/artifact-tool/presentation-jsx/jsx-runtime";
import { july2021 } from "./deck_content.mjs";
import {
  THEME,
  Background,
  Label,
  Title,
  BodyText,
  MetricCard,
  Panel,
  SmallText,
  StackedBar,
  Footer,
} from "./deck_helpers.mjs";

export async function slide03(presentation, ctx) {
  const slide = presentation.slides.add();
  const total = july2021.activeCommunes;

  jsx(Background, { slide, ctx, variant: "blue" });
  jsx(Label, { slide, ctx, left: 54, top: 42, width: 360, text: "JULY 2021 DEEP DIVE" });
  jsx(Title, {
    slide,
    ctx,
    left: 54,
    top: 78,
    width: 1120,
    height: 66,
    text: july2021.title,
    size: 34,
  });
  jsx(SmallText, {
    slide,
    ctx,
    left: 54,
    top: 146,
    width: 980,
    height: 22,
    text: july2021.reading,
  });

  jsx(MetricCard, {
    slide,
    ctx,
    left: 54,
    top: 200,
    width: 220,
    height: 112,
    label: "Active communes",
    value: total.toLocaleString("en-US"),
    accent: THEME.slate,
    fill: THEME.white,
  });
  jsx(MetricCard, {
    slide,
    ctx,
    left: 292,
    top: 200,
    width: 168,
    height: 112,
    label: "Both",
    value: july2021.both.toLocaleString("en-US"),
    accent: THEME.teal,
    fill: "#EAF5F3",
  });
  jsx(MetricCard, {
    slide,
    ctx,
    left: 476,
    top: 200,
    width: 168,
    height: 112,
    label: "Gaspar only",
    value: july2021.gasparOnly.toLocaleString("en-US"),
    accent: THEME.coral,
    fill: "#FBEEE9",
  });
  jsx(MetricCard, {
    slide,
    ctx,
    left: 660,
    top: 200,
    width: 168,
    height: 112,
    label: "JRC only",
    value: july2021.jrcOnly.toLocaleString("en-US"),
    accent: THEME.blue,
    fill: "#EEF3FB",
  });

  Panel({
    slide,
    ctx,
    left: 54,
    top: 340,
    width: 774,
    height: 162,
    fill: THEME.white,
    line: { style: "solid", fill: THEME.line, width: 1 },
    name: "StackedBarPanel",
  });
  BodyText({
    slide,
    ctx,
    left: 78,
    top: 360,
    width: 280,
    height: 24,
    text: "France-wide commune activity split in the app",
    size: 21,
    style: { fontSize: 21, bold: true, typeface: ctx.fonts.title, color: THEME.ink },
  });
  jsx(StackedBar, {
    slide,
    ctx,
    left: 78,
    top: 410,
    width: 720,
    height: 42,
    total,
    segments: [
      { value: july2021.both, color: THEME.teal },
      { value: july2021.gasparOnly, color: THEME.coral },
      { value: july2021.jrcOnly, color: THEME.blue },
    ],
  });
  SmallText({
    slide,
    ctx,
    left: 78,
    top: 468,
    width: 210,
    height: 20,
    text: `Both: ${july2021.both} (${((july2021.both / total) * 100).toFixed(1)}%)`,
    color: THEME.teal,
  });
  SmallText({
    slide,
    ctx,
    left: 324,
    top: 468,
    width: 230,
    height: 20,
    text: `Gaspar only: ${july2021.gasparOnly} (${((july2021.gasparOnly / total) * 100).toFixed(1)}%)`,
    color: THEME.coral,
  });
  SmallText({
    slide,
    ctx,
    left: 578,
    top: 468,
    width: 220,
    height: 20,
    text: `JRC only: ${july2021.jrcOnly} (${((july2021.jrcOnly / total) * 100).toFixed(1)}%)`,
    color: THEME.blue,
    align: "right",
  });

  Panel({
    slide,
    ctx,
    left: 854,
    top: 200,
    width: 316,
    height: 302,
    fill: "#FFFDFC",
    line: { style: "solid", fill: THEME.line, width: 1 },
    name: "EvidencePanel",
  });
  BodyText({
    slide,
    ctx,
    left: 878,
    top: 220,
    width: 250,
    height: 28,
    text: "Public evidence found",
    size: 23,
    style: { fontSize: 23, bold: true, typeface: ctx.fonts.title, color: THEME.ink },
  });
  SmallText({
    slide,
    ctx,
    left: 878,
    top: 258,
    width: 250,
    height: 18,
    text: "Gaspar-only side",
    color: THEME.coral,
  });
  BodyText({
    slide,
    ctx,
    left: 878,
    top: 286,
    width: 256,
    height: 108,
    text: "Jura, Meuse, and Claye-Souilly all have press or official support on the Gaspar side.",
    size: 16,
    color: THEME.ink,
    lineSpacing: 1.1,
  });
  SmallText({
    slide,
    ctx,
    left: 878,
    top: 402,
    width: 250,
    height: 18,
    text: "JRC-only side",
    color: THEME.blue,
  });
  BodyText({
    slide,
    ctx,
    left: 878,
    top: 430,
    width: 256,
    height: 108,
    text: "Autet, Asfeld, the Sedan area, and Louhans also have local or departmental evidence on the JRC side.",
    size: 16,
    color: THEME.ink,
    lineSpacing: 1.1,
  });

  Panel({
    slide,
    ctx,
    left: 54,
    top: 528,
    width: 1116,
    height: 126,
    fill: THEME.white,
    line: { style: "solid", fill: THEME.line, width: 1 },
    name: "InterpretationPanel",
  });
  BodyText({
    slide,
    ctx,
    left: 78,
    top: 552,
    width: 1070,
    height: 74,
    text:
      "Interpretation: the July 2021 mismatch is not just an extraction problem. Both sources capture real flood impacts, but they disagree strongly on which communes belong to the same episode and on how widely the flood footprint should extend.",
    size: 21,
    color: THEME.ink,
    lineSpacing: 1.1,
  });

  jsx(Footer, {
    slide,
    ctx,
    text: "Evidence report: docs/july_2021_gaspar_jrc_mismatch_evidence_report.md. Comparison counts from the France Streamlit app for 2021-07.",
  });

  return slide;
}
