import path from "node:path";

import { jsx } from "@oai/artifact-tool/presentation-jsx/jsx-runtime";
import { streamlitApp } from "./deck_content.mjs";
import {
  THEME,
  Background,
  Label,
  Title,
  Panel,
  BodyText,
  SmallText,
  BulletList,
  Footer,
  ImageFrame,
} from "./deck_helpers.mjs";

const GRAND_EST_MAP = path.resolve(process.cwd(), "docs/assets/gaspar_jrc_match_audit/grand_est_2021_q3.png");

export async function slide04(presentation, ctx) {
  const slide = presentation.slides.add();

  jsx(Background, { slide, ctx, variant: "paper" });
  jsx(Label, { slide, ctx, left: 54, top: 42, width: 280, text: "STREAMLIT APP" });
  jsx(Title, {
    slide,
    ctx,
    left: 54,
    top: 78,
    width: 1100,
    height: 66,
    text: streamlitApp.title,
    size: 34,
  });

  Panel({
    slide,
    ctx,
    left: 54,
    top: 180,
    width: 356,
    height: 470,
    fill: "#FFFDFC",
    line: { style: "solid", fill: THEME.line, width: 1 },
    name: "SidebarPanel",
  });
  BodyText({
    slide,
    ctx,
    left: 78,
    top: 204,
    width: 260,
    height: 32,
    text: "What the app now supports",
    size: 22,
    style: { fontSize: 22, bold: true, typeface: ctx.fonts.title, color: THEME.ink },
  });
  jsx(BulletList, {
    slide,
    ctx,
    left: 78,
    top: 252,
    width: 292,
    items: streamlitApp.features,
    rowHeight: 70,
    bulletColor: THEME.coral,
    size: 17,
  });

  Panel({
    slide,
    ctx,
    left: 430,
    top: 180,
    width: 740,
    height: 470,
    fill: "#111827",
    line: { style: "solid", fill: "#202B3C", width: 1 },
    name: "BrowserChrome",
  });
  Panel({
    slide,
    ctx,
    left: 430,
    top: 180,
    width: 740,
    height: 44,
    fill: "#1B2435",
    line: { style: "solid", fill: THEME.transparent, width: 0 },
    name: "BrowserTopBar",
  });
  SmallText({
    slide,
    ctx,
    left: 456,
    top: 194,
    width: 320,
    height: 18,
    text: "Representative comparison view powered by the same commune-activity logic",
    color: "#D7DEE8",
  });

  Panel({
    slide,
    ctx,
    left: 452,
    top: 240,
    width: 190,
    height: 388,
    fill: "#191F2B",
    line: { style: "solid", fill: "#293242", width: 1 },
    name: "MockSidebar",
  });
  const controls = [
    "Display mode: Comparison",
    "Period mode: Month",
    "Year: 2021",
    "Month: 07",
    "Basemap: CartoDB Positron",
    "Departments: on",
    "Diagnostics tab",
  ];
  controls.forEach((label, index) => {
    SmallText({
      slide,
      ctx,
      left: 470,
      top: 260 + index * 48,
      width: 150,
      height: 16,
      text: label,
      color: "#F2F5F9",
    });
    Panel({
      slide,
      ctx,
      left: 470,
      top: 282 + index * 48,
      width: 154,
      height: 16,
      fill: index === 0 ? "#243147" : "#111827",
      line: { style: "solid", fill: "#344154", width: 1 },
      name: `MockControl${index + 1}`,
    });
  });

  await jsx(ImageFrame, {
    slide,
    ctx,
    left: 666,
    top: 240,
    width: 480,
    height: 352,
    path: GRAND_EST_MAP,
    fit: "contain",
    fill: "#FBFBFB",
  });
  Panel({
    slide,
    ctx,
    left: 666,
    top: 604,
    width: 480,
    height: 24,
    fill: "#161F2D",
    line: { style: "solid", fill: THEME.transparent, width: 0 },
    name: "BrowserBottomBar",
  });
  SmallText({
    slide,
    ctx,
    left: 682,
    top: 608,
    width: 440,
    height: 16,
    text: "Comparison classes, filters, aggregated table, filtered rows, and unresolved-row diagnostics are all exposed in the app.",
    color: "#D7DEE8",
  });

  jsx(Footer, {
    slide,
    ctx,
    text: `${streamlitApp.diagnostics[0]} | ${streamlitApp.diagnostics[1]} | Core sources: src/france_commune_activity.py and src/gaspar_jrc_france_map_app.py.`,
  });

  return slide;
}
