import { jsx } from "@oai/artifact-tool/presentation-jsx/jsx-runtime";
import { auditStats, departmentComparison } from "./deck_content.mjs";
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

function rateDelta(departmentRate, communeRate) {
  return (departmentRate - communeRate).toFixed(1);
}

function DepartmentWindow({ slide, ctx, left, title, communeStats, departmentStats, accent, fill }) {
  Panel({
    slide,
    ctx,
    left,
    top: 226,
    width: 512,
    height: 344,
    fill,
    line: { style: "solid", fill: THEME.line, width: 1 },
    name: title,
  });
  Panel({
    slide,
    ctx,
    left,
    top: 226,
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
    top: 246,
    width: 260,
    height: 28,
    text: title,
    size: 24,
    style: { fontSize: 24, bold: true, typeface: ctx.fonts.title, color: THEME.ink },
  });
  SmallText({
    slide,
    ctx,
    left: left + 22,
    top: 282,
    width: 440,
    height: 18,
    text: "Same event tables, but matched at department level instead of commune level.",
  });

  ProgressRow({
    slide,
    ctx,
    left: left + 22,
    top: 320,
    width: 468,
    label: `JRC commune (${communeStats.jrcRate.toFixed(1)}%)`,
    value: communeStats.jrcMatched,
    total: communeStats.jrcTotal,
    color: THEME.blue,
  });
  ProgressRow({
    slide,
    ctx,
    left: left + 22,
    top: 372,
    width: 468,
    label: `JRC department (${departmentStats.jrcRate.toFixed(1)}%)`,
    value: departmentStats.jrcMatched,
    total: departmentStats.jrcTotal,
    color: THEME.teal,
    note: `Department view adds ${rateDelta(departmentStats.jrcRate, communeStats.jrcRate)} percentage points for JRC.`,
  });
  ProgressRow({
    slide,
    ctx,
    left: left + 22,
    top: 446,
    width: 468,
    label: `Gaspar commune (${communeStats.gasparRate.toFixed(1)}%)`,
    value: communeStats.gasparMatched,
    total: communeStats.gasparTotal,
    color: "#C76A53",
  });
  ProgressRow({
    slide,
    ctx,
    left: left + 22,
    top: 498,
    width: 468,
    label: `Gaspar department (${departmentStats.gasparRate.toFixed(1)}%)`,
    value: departmentStats.gasparMatched,
    total: departmentStats.gasparTotal,
    color: THEME.coral,
    note: `Department view adds ${rateDelta(departmentStats.gasparRate, communeStats.gasparRate)} percentage points for Gaspar.`,
  });
}

export async function slide06(presentation, ctx) {
  const slide = presentation.slides.add();

  jsx(Background, { slide, ctx, variant: "blue" });
  jsx(Label, { slide, ctx, left: 54, top: 42, width: 360, text: "DEPARTMENT VIEW" });
  jsx(Title, {
    slide,
    ctx,
    left: 54,
    top: 78,
    width: 1120,
    height: 66,
    text: departmentComparison.title,
    size: 34,
  });
  jsx(SmallText, {
    slide,
    ctx,
    left: 54,
    top: 146,
    width: 1070,
    height: 22,
    text: departmentComparison.reading,
  });

  jsx(SmallText, {
    slide,
    ctx,
    left: 54,
    top: 182,
    width: 1116,
    height: 18,
    text:
      `Uplift versus commune level: 7-day JRC +${rateDelta(auditStats.department7d.jrcRate, auditStats.commune7d.jrcRate)} pp, Gaspar +${rateDelta(auditStats.department7d.gasparRate, auditStats.commune7d.gasparRate)} pp | 30-day JRC +${rateDelta(auditStats.department30d.jrcRate, auditStats.commune30d.jrcRate)} pp, Gaspar +${rateDelta(auditStats.department30d.gasparRate, auditStats.commune30d.gasparRate)} pp.`,
  });

  DepartmentWindow({
    slide,
    ctx,
    left: 54,
    title: "7-day window",
    communeStats: auditStats.commune7d,
    departmentStats: auditStats.department7d,
    accent: THEME.coral,
    fill: "#FFFDFC",
  });
  DepartmentWindow({
    slide,
    ctx,
    left: 606,
    title: "30-day window",
    communeStats: auditStats.commune30d,
    departmentStats: auditStats.department30d,
    accent: THEME.blue,
    fill: "#F8FBFF",
  });

  Panel({
    slide,
    ctx,
    left: 54,
    top: 590,
    width: 1116,
    height: 66,
    fill: "#FFFDFC",
    line: { style: "solid", fill: THEME.line, width: 1 },
    name: "InterpretationPanel",
  });
  BodyText({
    slide,
    ctx,
    left: 78,
    top: 606,
    width: 1068,
    height: 34,
    text:
      "Interpretation: once the same episodes are allowed to match at department scale, the overlap rises sharply. The strongest explanation is not 'no common floods', but rather different commune allocation and time slicing inside the same broader events.",
    size: 18,
    color: THEME.ink,
    lineSpacing: 1.1,
  });

  jsx(Footer, {
    slide,
    ctx,
    text: "Source: the same 7-day and 30-day comparison outputs used in the national audit, now read as commune-versus-department contrast.",
  });

  return slide;
}
