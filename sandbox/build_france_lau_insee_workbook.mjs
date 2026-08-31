import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const cwd = process.cwd();
const sourceDir = path.join(cwd, "data", "france_lau_insee_documentation");
const csvPath = path.join(sourceDir, "fr_lau_insee_lookup_documentation.csv");
const diagnosticsPath = path.join(sourceDir, "france_insee_match_diagnostics.json");
const historicalCsvPath = path.join(
  sourceDir,
  "fr_old_insee_to_current_mapping.csv",
);
const historicalDiagnosticsPath = path.join(
  sourceDir,
  "france_old_insee_mapping_diagnostics.json",
);
const outputPath = path.join(
  sourceDir,
  "france_lau_insee_nuts3_mapping.xlsx",
);

function parseCsv(text) {
  const rows = [];
  let row = [];
  let value = "";
  let inQuotes = false;

  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    const next = text[i + 1];

    if (ch === '"') {
      if (inQuotes && next === '"') {
        value += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }

    if (ch === "," && !inQuotes) {
      row.push(value);
      value = "";
      continue;
    }

    if ((ch === "\n" || ch === "\r") && !inQuotes) {
      if (ch === "\r" && next === "\n") {
        i += 1;
      }
      row.push(value);
      rows.push(row);
      row = [];
      value = "";
      continue;
    }

    value += ch;
  }

  if (value.length > 0 || row.length > 0) {
    row.push(value);
    rows.push(row);
  }

  if (rows.length > 0 && rows[0][0]?.charCodeAt(0) === 0xfeff) {
    rows[0][0] = rows[0][0].slice(1);
  }

  return rows;
}

function setHeaderStyle(sheet, rangeAddress) {
  const range = sheet.getRange(rangeAddress);
  range.format.fill.color = "#1F4E78";
  range.format.font.color = "#FFFFFF";
  range.format.font.bold = true;
  range.format.wrapText = true;
}

function setTitleStyle(sheet, rangeAddress) {
  const range = sheet.getRange(rangeAddress);
  range.format.font.bold = true;
  range.format.font.size = 16;
  range.format.font.color = "#0F172A";
}

function setSectionStyle(sheet, rangeAddress) {
  const range = sheet.getRange(rangeAddress);
  range.format.font.bold = true;
  range.format.font.size = 12;
  range.format.font.color = "#1F4E78";
}

function writeMatrix(sheet, startRow, startCol, matrix) {
  const range = sheet.getRangeByIndexes(
    startRow,
    startCol,
    matrix.length,
    matrix[0].length,
  );
  range.writeValues(matrix);
}

function setFormulaColumn(sheet, startRow, colIndex, rows, valueIndex) {
  const formulas = rows.map((row) => {
    const raw = row[valueIndex];
    if (raw === null || raw === undefined || raw === "") {
      return [null];
    }
    const escaped = String(raw).replaceAll('"', '""');
    return [`="${escaped}"`];
  });
  sheet.getRangeByIndexes(startRow, colIndex, rows.length, 1).formulas = formulas;
}

function asFixedWidthNumber(value) {
  if (value === null || value === undefined || value === "") {
    return "";
  }
  return Number.parseInt(String(value), 10);
}

const csvText = await fs.readFile(csvPath, "utf8");
const diagnostics = JSON.parse(await fs.readFile(diagnosticsPath, "utf8"));
const historicalCsvText = await fs.readFile(historicalCsvPath, "utf8");
const historicalDiagnostics = JSON.parse(
  await fs.readFile(historicalDiagnosticsPath, "utf8"),
);
const parsed = parseCsv(csvText);
const headers = parsed[0];
const dataRows = parsed.slice(1);
const headerIndex = Object.fromEntries(headers.map((header, idx) => [header, idx]));
const historicalParsed = parseCsv(historicalCsvText);
const historicalHeaders = historicalParsed[0];
const historicalDataRows = historicalParsed.slice(1);
const historicalHeaderIndex = Object.fromEntries(
  historicalHeaders.map((header, idx) => [header, idx]),
);

const fallbackRows = dataRows.filter(
  (row) => row[headerIndex.match_type] === "fallback_spatial",
);
const lookupRowsForExcel = dataRows.map((row) => {
  const next = [...row];
  for (const idx of [1, 3, 9, 10]) {
    next[idx] = asFixedWidthNumber(next[idx]);
  }
  return next;
});
const fallbackRowsForExcel = fallbackRows.map((row) => {
  const next = [...row];
  for (const idx of [1, 3, 9, 10]) {
    next[idx] = asFixedWidthNumber(next[idx]);
  }
  return next;
});
const lookupDataRowCount = lookupRowsForExcel.length;
const fallbackDataRowCount = fallbackRowsForExcel.length;
const historicalRowsForExcel = historicalDataRows.map((row) => [...row]);
const historicalDataRowCount = historicalRowsForExcel.length;

const workbook = Workbook.create();
const summarySheet = workbook.worksheets.add("Summary");
const lookupSheet = workbook.worksheets.add("Lookup_All");
const fallbackSheet = workbook.worksheets.add("Fallback_81");
const historicalSheet = workbook.worksheets.add("Old_to_Current_INSEE");

summarySheet.getRange("A1:D1").merge();
writeMatrix(summarySheet, 0, 0, [[
  "France LAU -> INSEE commune mapping documentation",
]]);
setTitleStyle(summarySheet, "A1:D1");

writeMatrix(summarySheet, 2, 0, [["Metric", "Value"]]);
setHeaderStyle(summarySheet, "A3:B3");

const summaryMetrics = [
  ["France LAU rows", diagnostics.france_lau_total],
  ["AdminExpress commune rows", diagnostics.adminexpress_communes_total],
  ["Exact matches", diagnostics.exact_code_matches],
  ["Fallback spatial matches", diagnostics.fallback_spatial_matches],
  ["Fallback within matches", diagnostics.spatial_point_within_matches],
  ["Fallback intersects matches", diagnostics.spatial_point_intersects_matches],
  ["Unresolved matches", diagnostics.unresolved_total],
  ["Code changed matches", diagnostics.code_changed_matches],
];
writeMatrix(summarySheet, 3, 0, summaryMetrics);

writeMatrix(summarySheet, 13, 0, [[
  "Example code changes resolved by spatial fallback",
]]);
setSectionStyle(summarySheet, "A14:F14");

const examplesHeader = [
  "Old LAU local code",
  "Matched INSEE code",
  "Eurostat LAU name",
  "AdminExpress commune name",
];
writeMatrix(summarySheet, 14, 0, [examplesHeader]);
setHeaderStyle(summarySheet, "A15:D15");

const exampleRows = diagnostics.code_changed_examples.map((item) => [
  asFixedWidthNumber(item.lau_code_local ?? ""),
  asFixedWidthNumber(item.insee_com ?? ""),
  String(item.lau_name_lau ?? ""),
  String(item.commune_name_adminexpress ?? ""),
]);
if (exampleRows.length > 0) {
  writeMatrix(summarySheet, 15, 0, exampleRows);
  summarySheet
    .getRangeByIndexes(15, 0, exampleRows.length, 2)
    .format.numberFormat = "00000";
  const exampleSourceRows = diagnostics.code_changed_examples.map((item) => [
    String(item.lau_code_local ?? ""),
    String(item.insee_com ?? ""),
  ]);
  setFormulaColumn(summarySheet, 15, 0, exampleSourceRows, 0);
  setFormulaColumn(summarySheet, 15, 1, exampleSourceRows, 1);
}

const historicalTitleRow = 15 + Math.max(exampleRows.length, 1) + 3;
writeMatrix(summarySheet, historicalTitleRow, 0, [[
  "Historical old INSEE commune codes to current commune codes",
]]);
setSectionStyle(
  summarySheet,
  `A${historicalTitleRow + 1}:D${historicalTitleRow + 1}`,
);
writeMatrix(summarySheet, historicalTitleRow + 1, 0, [["Metric", "Value"]]);
setHeaderStyle(
  summarySheet,
  `A${historicalTitleRow + 2}:B${historicalTitleRow + 2}`,
);
const historicalSummaryMetrics = [
  [
    "Historical inactive commune states",
    historicalDiagnostics.historical_commune_states_total,
  ],
  [
    "Rows in old-to-current sheet",
    historicalDiagnostics.historical_output_rows_total,
  ],
  [
    "Unique current matches",
    historicalDiagnostics.unique_current_match_states,
  ],
  [
    "Multiple current matches",
    historicalDiagnostics.multiple_current_match_states,
  ],
  [
    "No current match found",
    historicalDiagnostics.no_current_match_states,
  ],
  [
    "Update-ready rows",
    historicalDiagnostics.update_ready_rows_total,
  ],
  [
    "Distinct current communes referenced",
    historicalDiagnostics.distinct_new_communes_referenced,
  ],
];
writeMatrix(summarySheet, historicalTitleRow + 2, 0, historicalSummaryMetrics);

writeMatrix(lookupSheet, 0, 0, [headers, ...lookupRowsForExcel]);
setHeaderStyle(
  lookupSheet,
  `A1:${String.fromCharCode(64 + headers.length)}1`,
);

writeMatrix(fallbackSheet, 0, 0, [headers, ...fallbackRowsForExcel]);
setHeaderStyle(
  fallbackSheet,
  `A1:${String.fromCharCode(64 + headers.length)}1`,
);
writeMatrix(historicalSheet, 0, 0, [historicalHeaders, ...historicalRowsForExcel]);
setHeaderStyle(
  historicalSheet,
  `A1:${String.fromCharCode(64 + historicalHeaders.length)}1`,
);

summarySheet.freezePanes.freezeRows(1);
lookupSheet.freezePanes.freezeRows(1);
fallbackSheet.freezePanes.freezeRows(1);
historicalSheet.freezePanes.freezeRows(1);

summarySheet.getRange("A:A").format.columnWidthPx = 220;
summarySheet.getRange("B:B").format.columnWidthPx = 120;
summarySheet.getRange("C:D").format.columnWidthPx = 210;
lookupSheet.getRange("A:A").format.columnWidthPx = 150;
lookupSheet.getRange("B:B").format.columnWidthPx = 110;
lookupSheet.getRange("C:C").format.columnWidthPx = 210;
lookupSheet.getRange("D:D").format.columnWidthPx = 110;
lookupSheet.getRange("E:E").format.columnWidthPx = 220;
lookupSheet.getRange("F:G").format.columnWidthPx = 130;
lookupSheet.getRange("H:I").format.columnWidthPx = 120;
lookupSheet.getRange("J:K").format.columnWidthPx = 90;
lookupSheet.getRange("L:L").format.columnWidthPx = 140;
fallbackSheet.getRange("A:A").format.columnWidthPx = 150;
fallbackSheet.getRange("B:B").format.columnWidthPx = 110;
fallbackSheet.getRange("C:C").format.columnWidthPx = 210;
fallbackSheet.getRange("D:D").format.columnWidthPx = 110;
fallbackSheet.getRange("E:E").format.columnWidthPx = 220;
fallbackSheet.getRange("F:G").format.columnWidthPx = 130;
fallbackSheet.getRange("H:I").format.columnWidthPx = 120;
fallbackSheet.getRange("J:K").format.columnWidthPx = 90;
fallbackSheet.getRange("L:L").format.columnWidthPx = 140;
historicalSheet.getRange("A:A").format.columnWidthPx = 105;
historicalSheet.getRange("B:B").format.columnWidthPx = 210;
historicalSheet.getRange("C:D").format.columnWidthPx = 105;
historicalSheet.getRange("E:E").format.columnWidthPx = 105;
historicalSheet.getRange("F:F").format.columnWidthPx = 220;
historicalSheet.getRange("G:G").format.columnWidthPx = 140;
historicalSheet.getRange("H:H").format.columnWidthPx = 220;
historicalSheet.getRange("I:I").format.columnWidthPx = 100;
historicalSheet.getRange("J:J").format.columnWidthPx = 120;
historicalSheet.getRange("K:L").format.columnWidthPx = 90;
historicalSheet.getRange("M:M").format.columnWidthPx = 110;
historicalSheet.getRange("N:N").format.columnWidthPx = 190;
historicalSheet.getRange("O:Q").format.columnWidthPx = 120;

lookupSheet.getRange("A:L").format.wrapText = true;
fallbackSheet.getRange("A:L").format.wrapText = true;
historicalSheet.getRange("A:Q").format.wrapText = true;
summarySheet.getRange("A:Z").format.wrapText = true;
summarySheet.getRange("A:B").format.numberFormat = "@";
lookupSheet
  .getRangeByIndexes(1, 1, lookupDataRowCount, 1)
  .format.numberFormat = "00000";
lookupSheet
  .getRangeByIndexes(1, 3, lookupDataRowCount, 1)
  .format.numberFormat = "00000";
lookupSheet
  .getRangeByIndexes(1, 9, lookupDataRowCount, 1)
  .format.numberFormat = "00";
lookupSheet
  .getRangeByIndexes(1, 10, lookupDataRowCount, 1)
  .format.numberFormat = "00";
fallbackSheet
  .getRangeByIndexes(1, 1, fallbackDataRowCount, 1)
  .format.numberFormat = "00000";
fallbackSheet
  .getRangeByIndexes(1, 3, fallbackDataRowCount, 1)
  .format.numberFormat = "00000";
fallbackSheet
  .getRangeByIndexes(1, 9, fallbackDataRowCount, 1)
  .format.numberFormat = "00";
fallbackSheet
  .getRangeByIndexes(1, 10, fallbackDataRowCount, 1)
  .format.numberFormat = "00";
historicalSheet.getRange("A:A").format.numberFormat = "@";
historicalSheet.getRange("E:E").format.numberFormat = "@";
historicalSheet.getRange("G:G").format.numberFormat = "@";
historicalSheet.getRange("I:I").format.numberFormat = "@";
historicalSheet.getRange("K:L").format.numberFormat = "@";

setFormulaColumn(lookupSheet, 1, 1, dataRows, 1);
setFormulaColumn(lookupSheet, 1, 3, dataRows, 3);
setFormulaColumn(lookupSheet, 1, 9, dataRows, 9);
setFormulaColumn(lookupSheet, 1, 10, dataRows, 10);
setFormulaColumn(fallbackSheet, 1, 1, fallbackRows, 1);
setFormulaColumn(fallbackSheet, 1, 3, fallbackRows, 3);
setFormulaColumn(fallbackSheet, 1, 9, fallbackRows, 9);
setFormulaColumn(fallbackSheet, 1, 10, fallbackRows, 10);
setFormulaColumn(
  historicalSheet,
  1,
  historicalHeaderIndex.old_insee_com,
  historicalDataRows,
  historicalHeaderIndex.old_insee_com,
);
setFormulaColumn(
  historicalSheet,
  1,
  historicalHeaderIndex.new_insee_com,
  historicalDataRows,
  historicalHeaderIndex.new_insee_com,
);
setFormulaColumn(
  historicalSheet,
  1,
  historicalHeaderIndex.new_insee_dep,
  historicalDataRows,
  historicalHeaderIndex.new_insee_dep,
);
setFormulaColumn(
  historicalSheet,
  1,
  historicalHeaderIndex.new_insee_reg,
  historicalDataRows,
  historicalHeaderIndex.new_insee_reg,
);

const summaryCheck = await workbook.inspect({
  kind: "table",
  range: "Summary!A1:D60",
  include: "values",
  tableMaxRows: 60,
  tableMaxCols: 4,
});
console.log(summaryCheck.ndjson);

const lookupCheck = await workbook.inspect({
  kind: "table",
  range: "Lookup_All!A1:L8",
  include: "values",
  tableMaxRows: 8,
  tableMaxCols: 12,
});
console.log(lookupCheck.ndjson);

const fallbackCheck = await workbook.inspect({
  kind: "table",
  range: "Fallback_81!A1:L8",
  include: "values",
  tableMaxRows: 8,
  tableMaxCols: 12,
});
console.log(fallbackCheck.ndjson);

const historicalCheck = await workbook.inspect({
  kind: "table",
  range: "Old_to_Current_INSEE!A1:Q8",
  include: "values",
  tableMaxRows: 8,
  tableMaxCols: 17,
});
console.log(historicalCheck.ndjson);

const formulaErrors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 50 },
  summary: "formula error scan",
});
console.log(formulaErrors.ndjson);

const exported = await SpreadsheetFile.exportXlsx(workbook);
await exported.save(outputPath);
console.log(`Saved workbook: ${outputPath}`);
