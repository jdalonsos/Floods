import { jsx } from "@oai/artifact-tool/presentation-jsx/jsx-runtime";
import { closeout } from "./deck_content.mjs";
import {
  THEME,
  Background,
  Label,
  Title,
  Panel,
  BodyText,
  BulletList,
  Footer,
} from "./deck_helpers.mjs";

export async function slide08(presentation, ctx) {
  const slide = presentation.slides.add();

  jsx(Background, { slide, ctx, variant: "dark" });
  jsx(Label, {
    slide,
    ctx,
    left: 54,
    top: 42,
    width: 360,
    text: "READY NOW / NEXT",
    color: "#F4B39F",
  });
  jsx(Title, {
    slide,
    ctx,
    left: 54,
    top: 78,
    width: 1080,
    height: 66,
    text: closeout.title,
    dark: true,
    size: 38,
  });

  Panel({
    slide,
    ctx,
    left: 54,
    top: 192,
    width: 522,
    height: 408,
    fill: "#F7EFE6",
    line: { style: "solid", fill: THEME.transparent, width: 0 },
    name: "ReadyPanel",
  });
  BodyText({
    slide,
    ctx,
    left: 82,
    top: 218,
    width: 260,
    height: 28,
    text: "Ready today",
    size: 24,
    style: { fontSize: 24, bold: true, typeface: ctx.fonts.title, color: THEME.ink },
  });
  jsx(BulletList, {
    slide,
    ctx,
    left: 82,
    top: 270,
    width: 438,
    items: closeout.ready,
    rowHeight: 78,
    bulletColor: THEME.coral,
    size: 18,
  });

  Panel({
    slide,
    ctx,
    left: 594,
    top: 192,
    width: 576,
    height: 408,
    fill: "#EEF3FB",
    line: { style: "solid", fill: THEME.transparent, width: 0 },
    name: "NextPanel",
  });
  BodyText({
    slide,
    ctx,
    left: 622,
    top: 218,
    width: 260,
    height: 28,
    text: "Best next questions",
    size: 24,
    style: { fontSize: 24, bold: true, typeface: ctx.fonts.title, color: THEME.ink },
  });
  jsx(BulletList, {
    slide,
    ctx,
    left: 622,
    top: 270,
    width: 492,
    items: closeout.next,
    rowHeight: 78,
    bulletColor: THEME.blue,
    size: 18,
  });

  BodyText({
    slide,
    ctx,
    left: 54,
    top: 626,
    width: 1116,
    height: 30,
    text: "Bottom line: the project moved from isolated scripts to a coherent comparison workflow with a reproducible audit trail and analyst-facing map diagnostics.",
    size: 22,
    color: "#F5F1E8",
    style: { fontSize: 22, bold: true, typeface: ctx.fonts.title, color: "#F5F1E8" },
  });

  jsx(Footer, {
    slide,
    ctx,
    dark: true,
    text: "Deliverables shipped this cycle: France comparison app, bilingual audit, July 2021 evidence note, and T20 JRC flood-check workbook.",
  });

  return slide;
}
