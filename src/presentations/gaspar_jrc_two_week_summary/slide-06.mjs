import path from "node:path";

import { jsx } from "@oai/artifact-tool/presentation-jsx/jsx-runtime";
import { manualChecks } from "./deck_content.mjs";
import {
  THEME,
  Background,
  Label,
  Title,
  Panel,
  BodyText,
  SmallText,
  Footer,
  ImageFrame,
} from "./deck_helpers.mjs";

const GRAND_EST_MAP = path.resolve(process.cwd(), "docs/assets/gaspar_jrc_match_audit/grand_est_2021_q3.png");
const BFC_MAP = path.resolve(process.cwd(), "docs/assets/gaspar_jrc_match_audit/bourgogne_franche_comte_2021_q3.png");
const CVL_MAP = path.resolve(process.cwd(), "docs/assets/gaspar_jrc_match_audit/centre_val_de_loire_2016_q2.png");

const mapPaths = [GRAND_EST_MAP, BFC_MAP, CVL_MAP];

export async function slide06(presentation, ctx) {
  const slide = presentation.slides.add();

  jsx(Background, { slide, ctx, variant: "paper" });
  jsx(Label, { slide, ctx, left: 54, top: 42, width: 320, text: "MANUAL CHECKS" });
  jsx(Title, {
    slide,
    ctx,
    left: 54,
    top: 78,
    width: 1120,
    height: 66,
    text: manualChecks.title,
    size: 34,
  });
  jsx(SmallText, {
    slide,
    ctx,
    left: 54,
    top: 146,
    width: 1040,
    height: 22,
    text: "These maps use the same commune-activity logic as the Streamlit app, but focus on quarter-region period overlap rather than event-pair matching.",
  });

  for (let index = 0; index < manualChecks.cases.length; index += 1) {
    const card = manualChecks.cases[index];
    const left = 54 + index * 374;
    Panel({
      slide,
      ctx,
      left,
      top: 196,
      width: 346,
      height: 444,
      fill: "#FFFDFC",
      line: { style: "solid", fill: THEME.line, width: 1 },
      name: `ManualCase${index + 1}`,
    });
    BodyText({
      slide,
      ctx,
      left: left + 18,
      top: 214,
      width: 300,
      height: 30,
      text: card.label,
      size: 22,
      style: { fontSize: 22, bold: true, typeface: ctx.fonts.title, color: THEME.ink },
    });
    SmallText({
      slide,
      ctx,
      left: left + 18,
      top: 248,
      width: 300,
      height: 18,
      text: card.metrics,
      color: index === 0 ? THEME.teal : index === 1 ? THEME.blue : THEME.coral,
    });
    await jsx(ImageFrame, {
      slide,
      ctx,
      left: left + 18,
      top: 282,
      width: 310,
      height: 200,
      path: mapPaths[index],
      fit: "contain",
      fill: "#FBFBFB",
    });
    BodyText({
      slide,
      ctx,
      left: left + 18,
      top: 500,
      width: 310,
      height: 112,
      text: card.takeaway,
      size: 17,
      color: THEME.ink,
      lineSpacing: 1.1,
    });
  }

  jsx(Footer, {
    slide,
    ctx,
    text: "Rendered audit figures live in docs/assets/gaspar_jrc_match_audit and are referenced by the bilingual match-audit report.",
  });

  return slide;
}
