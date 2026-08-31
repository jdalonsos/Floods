import { paint, stroke, textStyle } from "@oai/artifact-tool/presentation-jsx";

export const THEME = {
  paper: "#F5F1E8",
  ink: "#0F172A",
  muted: "#5F6675",
  line: "#D7CEC0",
  white: "#FFFFFF",
  coral: "#E45A3C",
  teal: "#0F766E",
  blue: "#3158D3",
  gold: "#D4A72C",
  slate: "#1E293B",
  paleBlue: "#E7EEF9",
  paleTeal: "#E6F4F1",
  paleCoral: "#FCEBE6",
  paleGold: "#F7EFD3",
  transparent: "#00000000",
};

const LABEL_STYLE = textStyle("size: 18px; weight: 700; color: #E45A3C; family: Aptos;");
const TITLE_STYLE = textStyle("size: 34px; weight: 700; color: #0F172A; family: Aptos Display;");
const DARK_TITLE_STYLE = textStyle("size: 44px; weight: 700; color: #F5F1E8; family: Aptos Display;");
const BODY_STYLE = textStyle("size: 19px; color: #0F172A; family: Aptos;");
const SMALL_STYLE = textStyle("size: 14px; color: #5F6675; family: Aptos;");

function applyTextStyle(shape, style = {}) {
  if (!shape?.text || !style) {
    return shape;
  }
  if (style.fontSize !== undefined) shape.text.fontSize = style.fontSize;
  if (style.color !== undefined) shape.text.color = style.color;
  if (style.bold !== undefined) shape.text.bold = Boolean(style.bold);
  if (style.typeface !== undefined) shape.text.typeface = style.typeface;
  if (style.italic !== undefined) shape.text.italic = Boolean(style.italic);
  if (style.alignment !== undefined) shape.text.alignment = style.alignment;
  if (style.lineSpacing !== undefined) shape.text.lineSpacing = style.lineSpacing;
  if (style.wrap !== undefined) shape.text.wrap = style.wrap;
  if (style.underline !== undefined) shape.text.underline = style.underline;
  if (style.autoFit !== undefined) shape.text.autoFit = style.autoFit;
  if (style.insets !== undefined) shape.text.insets = style.insets;
  return shape;
}

function anchorToValign(anchor) {
  if (anchor === 2 || anchor === "middle" || anchor === "center") return "middle";
  if (anchor === 3 || anchor === "bottom") return "bottom";
  return "top";
}

export function Background({ slide, ctx, variant = "paper" }) {
  const fill =
    variant === "dark"
      ? paint("linear(180deg, #101826 0%, #1B2840 100%)")
      : variant === "blue"
        ? paint("linear(180deg, #EEF3FB 0%, #F5F1E8 100%)")
        : THEME.paper;
  return ctx.addShape(slide, {
    left: 0,
    top: 0,
    width: ctx.W,
    height: ctx.H,
    fill,
    line: { style: "solid", fill: THEME.transparent, width: 0 },
    name: "Background",
  });
}

export function AccentBand({ slide, ctx, left = 0, top = 0, width = 12, height = 720, color = THEME.coral }) {
  return ctx.addShape(slide, {
    left,
    top,
    width,
    height,
    fill: color,
    line: { style: "solid", fill: THEME.transparent, width: 0 },
    name: "AccentBand",
  });
}

export function Rule({ slide, ctx, left, top, width, height = 2, color = THEME.line, opacityFill = color }) {
  return ctx.addShape(slide, {
    left,
    top,
    width,
    height,
    fill: opacityFill,
    line: { style: "solid", fill: THEME.transparent, width: 0 },
    name: "Rule",
  });
}

export function Panel({
  slide,
  ctx,
  left,
  top,
  width,
  height,
  fill = THEME.white,
  line = { style: "solid", fill: THEME.line, width: 1 },
  name = "Panel",
}) {
  return ctx.addShape(slide, { left, top, width, height, fill, line, name });
}

export function Label({ slide, ctx, left, top, width, height = 24, text, color = THEME.coral }) {
  const style = { ...LABEL_STYLE, color };
  const shape = ctx.addText(slide, {
    left,
    top,
    width,
    height,
    text,
    fontSize: style.fontSize,
    color: style.color,
    bold: style.bold,
    typeface: style.typeface,
    line: { style: "solid", fill: THEME.transparent, width: 0 },
    fill: THEME.transparent,
    insets: { left: 0, right: 0, top: 0, bottom: 0 },
    name: "Label",
  });
  return applyTextStyle(shape, style);
}

export function Title({
  slide,
  ctx,
  left,
  top,
  width,
  height,
  text,
  dark = false,
  size,
}) {
  const style = dark ? { ...DARK_TITLE_STYLE } : { ...TITLE_STYLE };
  if (size) style.fontSize = size;
  const shape = ctx.addText(slide, {
    left,
    top,
    width,
    height,
    text,
    fontSize: style.fontSize,
    color: style.color,
    bold: style.bold,
    typeface: style.typeface,
    line: { style: "solid", fill: THEME.transparent, width: 0 },
    fill: THEME.transparent,
    insets: { left: 0, right: 6, top: 0, bottom: 0 },
    name: "Title",
  });
  return applyTextStyle(shape, style);
}

export function BodyText({
  slide,
  ctx,
  left,
  top,
  width,
  height,
  text,
  size,
  color = THEME.ink,
  align = "left",
  valign = "top",
  lineSpacing,
  fill = THEME.transparent,
  line = { style: "solid", fill: THEME.transparent, width: 0 },
  insets = { left: 0, right: 0, top: 0, bottom: 0 },
  style = {},
  name = "BodyText",
}) {
  const mergedStyle = { ...BODY_STYLE, color, alignment: align, lineSpacing, ...style };
  if (size) mergedStyle.fontSize = size;
  const shape = ctx.addText(slide, {
    left,
    top,
    width,
    height,
    text,
    fontSize: mergedStyle.fontSize,
    color: mergedStyle.color,
    bold: mergedStyle.bold ?? false,
    typeface: mergedStyle.typeface ?? ctx.fonts.body,
    align: mergedStyle.alignment ?? align,
    valign: anchorToValign(mergedStyle.anchor ?? valign),
    fill,
    line,
    insets,
    name,
  });
  return applyTextStyle(shape, mergedStyle);
}

export function SmallText({ slide, ctx, left, top, width, height, text, color = THEME.muted, align = "left" }) {
  return BodyText({
    slide,
    ctx,
    left,
    top,
    width,
    height,
    text,
    size: SMALL_STYLE.fontSize,
    color,
    align,
    style: SMALL_STYLE,
    name: "SmallText",
  });
}

export function MetricCard({
  slide,
  ctx,
  left,
  top,
  width,
  height,
  label,
  value,
  accent = THEME.coral,
  fill = THEME.white,
}) {
  Panel({
    slide,
    ctx,
    left,
    top,
    width,
    height,
    fill,
    line: { style: "solid", fill: THEME.line, width: 1 },
    name: "MetricCard",
  });
  Rule({ slide, ctx, left, top, width, height: 6, color: accent, opacityFill: accent });
  SmallText({
    slide,
    ctx,
    left: left + 18,
    top: top + 18,
    width: width - 36,
    height: 20,
    text: label.toUpperCase(),
    color: THEME.muted,
  });
  BodyText({
    slide,
    ctx,
    left: left + 18,
    top: top + 46,
    width: width - 36,
    height: height - 56,
    text: String(value),
    size: 28,
    color: THEME.ink,
    style: textStyle("size: 28px; weight: 700; family: Aptos Display; color: #0F172A;"),
    name: "MetricValue",
  });
}

export function BulletList({
  slide,
  ctx,
  left,
  top,
  width,
  items,
  rowHeight = 56,
  bulletColor = THEME.coral,
  textColor = THEME.ink,
  size = 18,
}) {
  items.forEach((item, index) => {
    const rowTop = top + index * rowHeight;
    ctx.addShape(slide, {
      left,
      top: rowTop + 8,
      width: 10,
      height: 10,
      fill: bulletColor,
      line: { style: "solid", fill: THEME.transparent, width: 0 },
      name: `Bullet${index + 1}`,
    });
    BodyText({
      slide,
      ctx,
      left: left + 22,
      top: rowTop,
      width: width - 22,
      height: rowHeight - 4,
      text: item,
      size,
      color: textColor,
      lineSpacing: 1.1,
      name: `BulletText${index + 1}`,
    });
  });
}

export function StackedBar({
  slide,
  ctx,
  left,
  top,
  width,
  height,
  segments,
  total,
}) {
  let cursor = left;
  segments.forEach((segment, index) => {
    const segmentWidth = index === segments.length - 1
      ? left + width - cursor
      : Math.max(6, Math.round((segment.value / total) * width));
    ctx.addShape(slide, {
      left: cursor,
      top,
      width: segmentWidth,
      height,
      fill: segment.color,
      line: { style: "solid", fill: THEME.transparent, width: 0 },
      name: `StackedBar${index + 1}`,
    });
    cursor += segmentWidth;
  });
}

export function ProgressRow({
  slide,
  ctx,
  left,
  top,
  width,
  label,
  value,
  total,
  color,
  note,
}) {
  SmallText({
    slide,
    ctx,
    left,
    top,
    width: 230,
    height: 18,
    text: label,
    color: THEME.ink,
  });
  SmallText({
    slide,
    ctx,
    left: left + width - 100,
    top,
    width: 100,
    height: 18,
    text: `${value}/${total}`,
    color: THEME.ink,
    align: "right",
  });
  Panel({
    slide,
    ctx,
    left,
    top: top + 28,
    width,
    height: 14,
    fill: "#EFE7DB",
    line: { style: "solid", fill: THEME.transparent, width: 0 },
    name: "ProgressTrack",
  });
  const activeWidth = Math.max(10, Math.round((value / total) * width));
  Panel({
    slide,
    ctx,
    left,
    top: top + 28,
    width: activeWidth,
    height: 14,
    fill: color,
    line: { style: "solid", fill: THEME.transparent, width: 0 },
    name: "ProgressFill",
  });
  if (note) {
    SmallText({
      slide,
      ctx,
      left,
      top: top + 48,
      width,
      height: 18,
      text: note,
      color: THEME.muted,
    });
  }
}

export function DecisionBar({
  slide,
  ctx,
  left,
  top,
  width,
  label,
  value,
  total,
  color,
}) {
  SmallText({
    slide,
    ctx,
    left,
    top,
    width: 280,
    height: 18,
    text: label,
    color: THEME.ink,
  });
  SmallText({
    slide,
    ctx,
    left: left + width - 40,
    top,
    width: 40,
    height: 18,
    text: String(value),
    color: THEME.ink,
    align: "right",
  });
  Panel({
    slide,
    ctx,
    left,
    top: top + 24,
    width,
    height: 16,
    fill: "#EFE7DB",
    line: { style: "solid", fill: THEME.transparent, width: 0 },
    name: "DecisionTrack",
  });
  Panel({
    slide,
    ctx,
    left,
    top: top + 24,
    width: Math.max(8, Math.round((value / total) * width)),
    height: 16,
    fill: color,
    line: { style: "solid", fill: THEME.transparent, width: 0 },
    name: "DecisionFill",
  });
}

export async function ImageFrame({
  slide,
  ctx,
  left,
  top,
  width,
  height,
  path,
  fit = "contain",
  border = true,
  fill = THEME.white,
}) {
  Panel({
    slide,
    ctx,
    left,
    top,
    width,
    height,
    fill,
    line: border ? { style: "solid", fill: THEME.line, width: 1 } : { style: "solid", fill: THEME.transparent, width: 0 },
    name: "ImageFrame",
  });
  return ctx.addImage(slide, {
    left: left + 8,
    top: top + 8,
    width: width - 16,
    height: height - 16,
    path,
    fit,
    name: "Image",
  });
}

export function Footer({ slide, ctx, text, dark = false }) {
  Rule({
    slide,
    ctx,
    left: 48,
    top: ctx.H - 42,
    width: ctx.W - 96,
    height: 1,
    color: dark ? "#324157" : THEME.line,
    opacityFill: dark ? "#324157" : THEME.line,
  });
  SmallText({
    slide,
    ctx,
    left: 48,
    top: ctx.H - 32,
    width: ctx.W - 96,
    height: 18,
    text,
    color: dark ? "#D6DDE9" : THEME.muted,
  });
}

export function ArrowConnector({ slide, ctx, left, top, width, height = 4, color = THEME.coral }) {
  Panel({
    slide,
    ctx,
    left,
    top,
    width,
    height,
    fill: color,
    line: { style: "solid", fill: THEME.transparent, width: 0 },
    name: "ArrowStem",
  });
  ctx.addShape(slide, {
    left: left + width - 12,
    top: top - 6,
    width: 18,
    height: 16,
    fill: color,
    line: { style: "solid", fill: THEME.transparent, width: 0 },
    geometry: "chevron",
    name: "ArrowHead",
  });
}

export function OutlineBox({ slide, ctx, left, top, width, height, color = THEME.line, fill = THEME.transparent }) {
  return ctx.addShape(slide, {
    left,
    top,
    width,
    height,
    fill,
    line: stroke(`1 ${color}`),
    name: "OutlineBox",
  });
}
