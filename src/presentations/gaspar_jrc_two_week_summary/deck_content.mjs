export const overview = {
  title: "Gaspar vs JRC Flood Comparison in France",
  subtitle:
    "Two-week delivery summary: July 2021 comparison, Streamlit diagnostics, national audit, horizon audit, and T20 screening.",
  dateLabel: "Prepared on 2026-06-04",
  highlights: [
    "A France-wide comparison workflow now exists from raw commune rows to map-ready diagnostics.",
    "The July 2021 mismatch has been documented with public evidence from both the Gaspar-only and JRC-only sides.",
    "National commune-level event matching remains low, but department-level matching is materially higher.",
    "The new 2015-2024 horizon audit shows the mismatch recurring across several major flood families.",
    "The T20 point workflow is operational and already tested against processed JRC flood rasters.",
  ],
};

export const workflow = {
  title: "We now have a reusable France comparison stack from raw codes to map-ready communes",
  sources: [
    "Gaspar raw and processed event tables",
    "JRC processed France LAU event table",
    "Old INSEE updates plus current LAU / INSEE lookup",
    "AdminExpress commune polygons",
  ],
  harmonization: [
    "Normalize commune keys to current INSEE communes",
    "Handle old commune codes, LAU links, and Corsica alphanumeric cases",
    "Aggregate activity by date, month, quarter, year, or custom period",
    "Track unresolved rows instead of silently dropping them",
  ],
  outputs: [
    "Bilingual audit documents, horizon audit, and July 2021 evidence note",
    "France comparison tables for 7-day and 30-day windows",
    "Quarter-region manual comparison maps",
    "T20 workbook with point-level JRC flood checks",
  ],
  analystTools: [
    "Streamlit map with Gaspar, JRC, and Comparison modes",
    "Aggregated commune table plus filtered-row diagnostics",
    "Downloadable CSV and HTML map exports",
    "Reproducible scripts for docs and comparison outputs",
  ],
  callouts: [
    "Special-case logic matters: old INSEE updates, LAU reconciliation, and Corsica-style codes such as 2B246 are handled explicitly.",
    "The final visual layer is current AdminExpress commune polygons, while LAU is used in the reconciliation logic.",
  ],
};

export const july2021 = {
  title: "July 2021 shows a real source disagreement, not just a cleaning error",
  activeCommunes: 1671,
  both: 133,
  gasparOnly: 363,
  jrcOnly: 1175,
  gasparEvidence: [
    "Jura and Meuse: Arbois, Lons-le-Saunier, Bletterans, Bar-le-Duc, and Behonne appear in local reporting plus official material.",
    "Seine-et-Marne: Claye-Souilly appears in north-department flood coverage.",
  ],
  jrcEvidence: [
    "Haute-Saone and Ardennes: Autet, Asfeld, and the Sedan area appear in local flood reporting and vigilance context.",
    "Saone-et-Loire: Louhans and the wider corridor have departmental and press evidence.",
  ],
  reading:
    "The mismatch is material in both directions, and public evidence exists for flood impacts on both the Gaspar-only and the JRC-only sides.",
};

export const streamlitApp = {
  title: "The new Streamlit app turns commune matching into a practical visual QA workflow",
  features: [
    "Switch between Gaspar, JRC, and direct Comparison display modes.",
    "Filter by exact date, month, year, quarter, or custom interval.",
    "Inspect active communes, filtered rows, matched rows, and unresolved rows.",
    "Download the current aggregated table as CSV and the current map as HTML.",
    "Use current commune polygons while keeping commune-code diagnostics visible.",
  ],
  diagnostics: [
    "Raw and processed Gaspar inputs are both supported.",
    "Comparison mode separates both-active, Gaspar-only, and JRC-only communes.",
    "Department boundaries are optional overlays derived from commune geometry.",
  ],
};

export const auditStats = {
  title: "National commune-level event match remains low even with a wider time window",
  commune7d: {
    jrcMatched: 66,
    jrcExclusive: 222,
    jrcTotal: 288,
    jrcRate: 22.9,
    gasparMatched: 499,
    gasparExclusive: 3006,
    gasparTotal: 3505,
    gasparRate: 14.2,
  },
  commune30d: {
    jrcMatched: 80,
    jrcExclusive: 208,
    jrcTotal: 288,
    jrcRate: 27.8,
    gasparMatched: 587,
    gasparExclusive: 2918,
    gasparTotal: 3505,
    gasparRate: 16.7,
  },
  department7d: {
    jrcMatched: 125,
    jrcExclusive: 163,
    jrcTotal: 288,
    jrcRate: 43.4,
    gasparMatched: 1488,
    gasparExclusive: 2017,
    gasparTotal: 3505,
    gasparRate: 42.5,
  },
  department30d: {
    jrcMatched: 171,
    jrcExclusive: 117,
    jrcTotal: 288,
    jrcRate: 59.4,
    gasparMatched: 1886,
    gasparExclusive: 1619,
    gasparTotal: 3505,
    gasparRate: 53.8,
  },
  rowCoverage: {
    jrc7d: "2,501 / 64,327 rows = 3.9%",
    gaspar7d: "1,983 / 19,217 rows = 10.3%",
    jrc30d: "3,080 / 64,327 rows = 4.8%",
    gaspar30d: "2,204 / 19,217 rows = 11.5%",
  },
  reading:
    "Department-level rates are materially higher than commune-level rates, which points to commune fragmentation and timing differences rather than a total absence of overlap.",
};

export const departmentComparison = {
  title: "At department level, Gaspar and JRC align much more often than they do by commune",
  reading:
    "The gap between commune-level and department-level matching is large in both windows, which suggests that much of the disagreement comes from fine-grained commune allocation and event timing segmentation.",
};

export const horizonAudit = {
  title: "The new 2015-2024 horizon audit shows the mismatch recurring across multiple flood families",
  topPeriods: [
    {
      label: "Grand Est, Q1 2018",
      metrics: "1,312 disagreement communes | 8.4% overlap",
      takeaway: "Largest region-quarter mismatch in the ranking, dominated by a very broad JRC winter-flood corridor.",
    },
    {
      label: "Centre-Val de Loire, Q2 2016",
      metrics: "707 Gaspar only | 22 JRC only",
      takeaway: "Strongest high-activity Gaspar-dominant quarter during the late-May / early-June 2016 flood family.",
    },
    {
      label: "Grand Est, Q2 2024",
      metrics: "1,080 disagreement communes | 9.2% overlap",
      takeaway: "Recent end-of-horizon case where both real flood extent and administrative timing lag may matter.",
    },
    {
      label: "Bourgogne-Franche-Comte, Q1 2018",
      metrics: "1,127 disagreement communes | 9.6% overlap",
      takeaway: "Second-largest mismatch quarter, confirming the 2018 winter corridor beyond Grand Est.",
    },
  ],
  supportingPeriods: [
    "Ile-de-France, Q2 2016: 583 Gaspar-only communes in the same national flood family as Centre-Val de Loire 2016.",
    "PACA, Q4 2019: 305 Gaspar-only communes during the Var and Alpes-Maritimes Mediterranean floods.",
    "Hauts-de-France, Q4 2023: 302 Gaspar-only communes during the Pas-de-Calais and Nord flood sequence.",
  ],
  mainReading:
    "The low match rate is not tied to one famous event. It reappears in different hydrologic settings from 2016 to 2024, with both Gaspar-heavy and JRC-heavy profiles.",
};

export const manualChecks = {
  title: "Mapped manual checks now cover both Gaspar-dominant and JRC-dominant flood families across the horizon",
  cases: [
    {
      label: "Grand Est, Q1 2018",
      metrics: "Both 120 | Gaspar only 48 | JRC only 1,264",
      takeaway:
        "A very wide winter-flood corridor appears in JRC, while Gaspar remains concentrated in a much smaller administrative footprint.",
    },
    {
      label: "Centre-Val de Loire, Q2 2016",
      metrics: "Both 89 | Gaspar only 707 | JRC only 22",
      takeaway:
        "The Loire flood family is heavily recognized in Gaspar, but much less aligned with JRC at commune level.",
    },
    {
      label: "Grand Est, Q2 2024",
      metrics: "Both 110 | Gaspar only 348 | JRC only 732",
      takeaway:
        "A recent case with large disagreement in both directions, consistent with both flood-extent differences and timing effects.",
    },
  ],
};

export const t20 = {
  title: "The T20 rule is operational, but positive local JRC hits are rare in the current sample",
  totalPoints: 49,
  lauMatched: 44,
  unmatched: 5,
  touchedAny: 8,
  positiveHit: 1,
  hitEventCount: 4,
  positiveCase: "Allenjoie (Doubs, 25) is the only positive local case, with four matched event hits from 2018 to 2021.",
  rule: [
    "Map each LAT / LONG point to a French LAU.",
    "Keep only JRC events touching that LAU.",
    "Use full history up to Closed_Default_Date, or Cut_off_Date when needed.",
    "Check local flood pixels in a 40 m point buffer and a 1 km surrounding buffer.",
  ],
  decisionPaths: [
    { label: "LAU not touched in processed JRC events", value: 36, color: "#3158D3" },
    { label: "Touched, but no local flooded pixel above threshold", value: 7, color: "#0F766E" },
    { label: "Point outside LAU polygon", value: 5, color: "#D4A72C" },
    { label: "Positive local flood hit", value: 1, color: "#E45A3C" },
  ],
};

export const closeout = {
  title: "The project now has both a decision tool and a validation backlog",
  ready: [
    "France commune comparison app with map-first diagnostics",
    "Bilingual Gaspar / JRC match audit docs plus the 2015-2024 horizon extension",
    "July 2021 mismatch evidence report with public links",
    "T20 workbook checked against processed JRC flood rasters",
  ],
  next: [
    "Test alternative event-grouping rules using the department-to-commune gap as a benchmark.",
    "Add more quarter-region manual checks where the horizon audit still shows the largest mismatch.",
    "Decide whether to add a LAU-geometry map mode alongside current communes.",
    "Use the same point-screening workflow on additional credit portfolios.",
  ],
};
