/*===========================================================================

  BCEF - Category 1 Step 1 enrichment
  Flood indicators vs observed LGD
  Input table: T20_LGD_FLOOD_BCEF

  PURPOSE
    - Use the existing session-level flood table directly
    - Compare the 3 exposure groups already available in EXPO_GROUP:
        * EXPOSED
        * INTERMEDIATE EXPOSURE
        * NON-EXPOSED
    - Study the link between flood indicators and observed LGD
    - Produce ready-to-use tables and plots

  IMPORTANT
    - This script does NOT modify the source table.
    - It creates a new analysis base and output tables.
    - Update the LIBNAME paths and Excel path before running on another PC.

===========================================================================*/

options mprint mlogic symbolgen;

/*---------------------------------------------------------------------------
  0. Libraries and parameters
---------------------------------------------------------------------------*/

/* Update these paths on the target PC */
libname INLIB  "C:\PATH\TO\FOLDER\WITH\INPUT_TABLE";
libname OUTLIB "C:\PATH\TO\OUTPUT_FOLDER";

%let IN_DS        = T20_LGD_FLOOD_BCEF;
%let OUT_PREFIX   = BCEF3G;
%let XLSX_OUT     = C:\PATH\TO\OUTPUT_FOLDER\BCEF_3GROUP_FLOOD_LGD_ANALYSIS.xlsx;
%let IG_MAX_GRADE = 10;

%let CORR_VARS =
    FLAG_FLOOD_AREA_DEF
    FLAG_FLOOD_DEF
    FLAG_JRC_ANY_DEF
    FLAG_GASPAR_ANY_DEF
    FLAG_HANZE_ANY_DEF
    FLAG_FLOOD_COLL_DEF
    NB_FLOOD_DEF
    FLOOD_INT_MAX_DEF
    FLOOD_INT_CUM_DEF_V1
    FLOOD_INT_CUM_DEF_V2
    N_M_LAST_PRE_FLOOD
    RATIO_COLL_FLOODED
;

proc datasets library=work kill nolist;
quit;

/* Clean the main output tables if they already exist */
proc datasets library=OUTLIB nolist;
    delete
        &OUT_PREFIX._BASE
        &OUT_PREFIX._DATA_CHECK
        &OUT_PREFIX._GROUP_COUNTS
        &OUT_PREFIX._MISSINGNESS
        &OUT_PREFIX._DESC_GROUP
        &OUT_PREFIX._RATING_SUMMARY
        &OUT_PREFIX._GRADE_DIST
        &OUT_PREFIX._RATING_DIST
        &OUT_PREFIX._SRC_OVERLAP
        &OUT_PREFIX._FLAG_RATES
        &OUT_PREFIX._CORR_P_ALL
        &OUT_PREFIX._CORR_S_ALL
        &OUT_PREFIX._CORR_P_GRP
        &OUT_PREFIX._CORR_S_GRP
        &OUT_PREFIX._KRUSKAL
        &OUT_PREFIX._RATING_CHISQ
        &OUT_PREFIX._RATING_CROSSTAB
        &OUT_PREFIX._ANOVA_OBS
        &OUT_PREFIX._ANOVA_EST
    ;
quit;

/*---------------------------------------------------------------------------
  1. Build the analysis-ready base from T20_LGD_FLOOD_BCEF
---------------------------------------------------------------------------*/

data work.bcef3g_base;
    set INLIB.&IN_DS;

    length EXPO_GROUP_ANALYSIS $25 LGD_GRADE_REPORT $40 RATING_BUCKET $8;

    select (upcase(strip(EXPO_GROUP)));
        when ("EXPOSED") do;
            EXPO_GROUP_ORDER    = 1;
            EXPO_GROUP_ANALYSIS = "EXPOSED";
        end;
        when ("INTERMEDIATE EXPOSURE") do;
            EXPO_GROUP_ORDER    = 2;
            EXPO_GROUP_ANALYSIS = "INTERMEDIATE EXPOSURE";
        end;
        when ("NON-EXPOSED") do;
            EXPO_GROUP_ORDER    = 3;
            EXPO_GROUP_ANALYSIS = "NON-EXPOSED";
        end;
        otherwise delete;
    end;

    OBS_LGD_FINAL   = Realised_LGD;
    EST_LGD_REPORT  = LGD_Estimate;
    LGD_GRADE_REPORT = strip(LGD_Grade);

    GRADE_NUM = input(compress(LGD_GRADE_REPORT, , "kd"), ?? best12.);

    if missing(LGD_GRADE_REPORT) or LGD_GRADE_REPORT in ("", ".") then RATING_BUCKET = "NR";
    else if find(upcase(LGD_GRADE_REPORT), "NR", "it") > 0 then RATING_BUCKET = "NR";
    else if find(upcase(LGD_GRADE_REPORT), "NON RATE", "it") > 0 then RATING_BUCKET = "NR";
    else if find(upcase(LGD_GRADE_REPORT), "NIG", "it") > 0 then RATING_BUCKET = "NIG";
    else if find(upcase(LGD_GRADE_REPORT), "NON-INV", "it") > 0 then RATING_BUCKET = "NIG";
    else if find(upcase(LGD_GRADE_REPORT), "NON INVEST", "it") > 0 then RATING_BUCKET = "NIG";
    else if find(upcase(LGD_GRADE_REPORT), "IG", "it") > 0 then RATING_BUCKET = "IG";
    else if not missing(GRADE_NUM) then do;
        if GRADE_NUM <= &IG_MAX_GRADE then RATING_BUCKET = "IG";
        else RATING_BUCKET = "NIG";
    end;
    else RATING_BUCKET = "OTHER";

    format
        OBS_LGD_FINAL
        EST_LGD_REPORT
        FLOOD_INT_CUM_DEF_V1
        FLOOD_INT_CUM_DEF_V2
        FLOOD_INT_MAX_DEF
        NB_FLOOD_DEF
        N_M_LAST_PRE_FLOOD
        RATIO_COLL_FLOODED
        12.4
    ;
run;

proc sort data=work.bcef3g_base;
    by EXPO_GROUP_ORDER EXPO_GROUP_ANALYSIS;
run;

data OUTLIB.&OUT_PREFIX._BASE;
    set work.bcef3g_base;
run;

/*---------------------------------------------------------------------------
  2. Global checks and group counts
---------------------------------------------------------------------------*/

proc sql;
    create table OUTLIB.&OUT_PREFIX._DATA_CHECK as
    select
        count(*)                             as N_ROWS,
        count(distinct EXPO_GROUP_ANALYSIS)  as N_GROUPS,
        sum(not missing(OBS_LGD_FINAL))      as N_WITH_OBS_LGD,
        sum(not missing(EST_LGD_REPORT))     as N_WITH_EST_LGD,
        sum(not missing(LGD_GRADE_REPORT))   as N_WITH_GRADE,
        sum(FLAG_FLOOD_AREA_DEF = 1)         as N_FLAG_FLOOD_AREA_DEF,
        sum(FLAG_FLOOD_DEF = 1)              as N_FLAG_FLOOD_DEF,
        sum(FLAG_JRC_ANY_DEF = 1)            as N_FLAG_JRC_ANY_DEF,
        sum(FLAG_GASPAR_ANY_DEF = 1)         as N_FLAG_GASPAR_ANY_DEF,
        sum(FLAG_HANZE_ANY_DEF = 1)          as N_FLAG_HANZE_ANY_DEF,
        sum(FLAG_FLOOD_COLL_DEF = 1)         as N_FLAG_FLOOD_COLL_DEF
    from work.bcef3g_base
    ;
quit;

proc freq data=work.bcef3g_base noprint;
    tables EXPO_GROUP_ANALYSIS / out=work._group_counts_raw;
run;

data OUTLIB.&OUT_PREFIX._GROUP_COUNTS;
    set work._group_counts_raw;
    length EXPO_GROUP_ORDER 8;
    if EXPO_GROUP_ANALYSIS = "EXPOSED" then EXPO_GROUP_ORDER = 1;
    else if EXPO_GROUP_ANALYSIS = "INTERMEDIATE EXPOSURE" then EXPO_GROUP_ORDER = 2;
    else if EXPO_GROUP_ANALYSIS = "NON-EXPOSED" then EXPO_GROUP_ORDER = 3;
run;

proc sort data=OUTLIB.&OUT_PREFIX._GROUP_COUNTS;
    by EXPO_GROUP_ORDER;
run;

data OUTLIB.&OUT_PREFIX._MISSINGNESS;
    set work.bcef3g_base end=last;

    retain N_TOTAL 0 MIS1-MIS10 0 NON1-NON10 0;
    array VAR_ARR[10]
        OBS_LGD_FINAL
        EST_LGD_REPORT
        FLAG_FLOOD_AREA_DEF
        FLAG_FLOOD_DEF
        FLOOD_INT_CUM_DEF_V1
        FLOOD_INT_CUM_DEF_V2
        FLOOD_INT_MAX_DEF
        NB_FLOOD_DEF
        N_M_LAST_PRE_FLOOD
        RATIO_COLL_FLOODED
    ;
    array MIS_ARR[10] MIS1-MIS10;
    array NON_ARR[10] NON1-NON10;
    array VAR_NM[10] $40 _temporary_
        (
            "OBS_LGD_FINAL",
            "EST_LGD_REPORT",
            "FLAG_FLOOD_AREA_DEF",
            "FLAG_FLOOD_DEF",
            "FLOOD_INT_CUM_DEF_V1",
            "FLOOD_INT_CUM_DEF_V2",
            "FLOOD_INT_MAX_DEF",
            "NB_FLOOD_DEF",
            "N_M_LAST_PRE_FLOOD",
            "RATIO_COLL_FLOODED"
        )
    ;

    N_TOTAL + 1;
    do _j = 1 to dim(VAR_ARR);
        if missing(VAR_ARR[_j]) then MIS_ARR[_j] + 1;
        else NON_ARR[_j] + 1;
    end;

    if last then do;
        do _j = 1 to dim(VAR_ARR);
            VARIABLE      = VAR_NM[_j];
            N_NON_MISSING = NON_ARR[_j];
            N_MISSING     = MIS_ARR[_j];
            PCT_MISSING   = N_MISSING / N_TOTAL;
            output;
        end;
    end;

    keep VARIABLE N_TOTAL N_NON_MISSING N_MISSING PCT_MISSING;
    format PCT_MISSING percent8.2;
run;

/*---------------------------------------------------------------------------
  3. Descriptive tables by exposure group
---------------------------------------------------------------------------*/

proc sql;
    create table OUTLIB.&OUT_PREFIX._DESC_GROUP as
    select
        EXPO_GROUP_ORDER,
        EXPO_GROUP_ANALYSIS,
        count(*)                                        as N_SESSIONS,
        sum(not missing(OBS_LGD_FINAL))                 as N_OBS_LGD,
        sum(not missing(EST_LGD_REPORT))                as N_EST_LGD,
        mean(OBS_LGD_FINAL)                             as AVG_OBS_LGD format=12.4,
        median(OBS_LGD_FINAL)                           as MEDIAN_OBS_LGD format=12.4,
        mean(EST_LGD_REPORT)                            as AVG_EST_LGD format=12.4,
        median(EST_LGD_REPORT)                          as MEDIAN_EST_LGD format=12.4,
        mean(FLAG_FLOOD_AREA_DEF)                       as PCT_FLAG_FLOOD_AREA_DEF format=percent8.2,
        mean(FLAG_FLOOD_DEF)                            as PCT_FLAG_FLOOD_DEF format=percent8.2,
        mean(FLAG_JRC_ANY_DEF)                          as PCT_FLAG_JRC_ANY_DEF format=percent8.2,
        mean(FLAG_GASPAR_ANY_DEF)                       as PCT_FLAG_GASPAR_ANY_DEF format=percent8.2,
        mean(FLAG_HANZE_ANY_DEF)                        as PCT_FLAG_HANZE_ANY_DEF format=percent8.2,
        mean(FLAG_FLOOD_COLL_DEF)                       as PCT_FLAG_FLOOD_COLL_DEF format=percent8.2,
        mean(NB_FLOOD_DEF)                              as AVG_NB_FLOOD_DEF format=12.4,
        median(NB_FLOOD_DEF)                            as MEDIAN_NB_FLOOD_DEF format=12.4,
        mean(FLOOD_INT_MAX_DEF)                         as AVG_FLOOD_INT_MAX_DEF format=12.4,
        median(FLOOD_INT_MAX_DEF)                       as MEDIAN_FLOOD_INT_MAX_DEF format=12.4,
        mean(FLOOD_INT_CUM_DEF_V1)                      as AVG_FLOOD_INT_CUM_DEF_V1 format=12.4,
        median(FLOOD_INT_CUM_DEF_V1)                    as MEDIAN_FLOOD_INT_CUM_DEF_V1 format=12.4,
        mean(FLOOD_INT_CUM_DEF_V2)                      as AVG_FLOOD_INT_CUM_DEF_V2 format=12.4,
        median(FLOOD_INT_CUM_DEF_V2)                    as MEDIAN_FLOOD_INT_CUM_DEF_V2 format=12.4,
        mean(N_M_LAST_PRE_FLOOD)                        as AVG_N_M_LAST_PRE_FLOOD format=12.4,
        median(N_M_LAST_PRE_FLOOD)                      as MEDIAN_N_M_LAST_PRE_FLOOD format=12.4,
        mean(RATIO_COLL_FLOODED)                        as AVG_RATIO_COLL_FLOODED format=12.4,
        median(RATIO_COLL_FLOODED)                      as MEDIAN_RATIO_COLL_FLOODED format=12.4
    from work.bcef3g_base
    group by EXPO_GROUP_ORDER, EXPO_GROUP_ANALYSIS
    order by EXPO_GROUP_ORDER
    ;
quit;

proc sql;
    create table OUTLIB.&OUT_PREFIX._RATING_SUMMARY as
    select
        EXPO_GROUP_ORDER,
        EXPO_GROUP_ANALYSIS,
        count(*)                                     as N_SESSIONS,
        mean(RATING_BUCKET = "IG")                   as PCT_IG_ALL format=percent8.2,
        mean(RATING_BUCKET = "NIG")                  as PCT_NIG_ALL format=percent8.2,
        mean(RATING_BUCKET = "NR")                   as PCT_NR_ALL format=percent8.2,
        mean(RATING_BUCKET = "OTHER")                as PCT_OTHER_ALL format=percent8.2,
        case
            when sum(case when RATING_BUCKET in ("IG", "NIG") then 1 else 0 end) > 0
            then sum(case when RATING_BUCKET = "IG" then 1 else 0 end)
               / sum(case when RATING_BUCKET in ("IG", "NIG") then 1 else 0 end)
            else .
        end                                          as PCT_IG_RATED format=percent8.2,
        case
            when sum(case when RATING_BUCKET in ("IG", "NIG") then 1 else 0 end) > 0
            then sum(case when RATING_BUCKET = "NIG" then 1 else 0 end)
               / sum(case when RATING_BUCKET in ("IG", "NIG") then 1 else 0 end)
            else .
        end                                          as PCT_NIG_RATED format=percent8.2
    from work.bcef3g_base
    group by EXPO_GROUP_ORDER, EXPO_GROUP_ANALYSIS
    order by EXPO_GROUP_ORDER
    ;
quit;

proc freq data=work.bcef3g_base noprint;
    tables EXPO_GROUP_ANALYSIS * LGD_GRADE_REPORT / out=work._grade_raw outpct missing;
    tables EXPO_GROUP_ANALYSIS * RATING_BUCKET / out=work._rating_raw outpct missing;
run;

data OUTLIB.&OUT_PREFIX._GRADE_DIST;
    set work._grade_raw(rename=(PCT_ROW = PCT_IN_GROUP));
    keep EXPO_GROUP_ANALYSIS LGD_GRADE_REPORT COUNT PERCENT PCT_IN_GROUP;
run;

data OUTLIB.&OUT_PREFIX._RATING_DIST;
    set work._rating_raw(rename=(PCT_ROW = PCT_IN_GROUP));
    keep EXPO_GROUP_ANALYSIS RATING_BUCKET COUNT PERCENT PCT_IN_GROUP;
run;

proc freq data=work.bcef3g_base noprint;
    tables EXPO_GROUP_ANALYSIS * FLAG_JRC_ANY_DEF * FLAG_GASPAR_ANY_DEF * FLAG_HANZE_ANY_DEF
        / out=OUTLIB.&OUT_PREFIX._SRC_OVERLAP;
run;

proc sql;
    create table OUTLIB.&OUT_PREFIX._FLAG_RATES as
    select EXPO_GROUP_ORDER, EXPO_GROUP_ANALYSIS, "FLAG_FLOOD_AREA_DEF" as INDICATOR length=40,
           mean(FLAG_FLOOD_AREA_DEF) as RATE format=percent8.2
    from work.bcef3g_base
    group by EXPO_GROUP_ORDER, EXPO_GROUP_ANALYSIS
    union all
    select EXPO_GROUP_ORDER, EXPO_GROUP_ANALYSIS, "FLAG_FLOOD_DEF" as INDICATOR length=40,
           mean(FLAG_FLOOD_DEF) as RATE format=percent8.2
    from work.bcef3g_base
    group by EXPO_GROUP_ORDER, EXPO_GROUP_ANALYSIS
    union all
    select EXPO_GROUP_ORDER, EXPO_GROUP_ANALYSIS, "FLAG_JRC_ANY_DEF" as INDICATOR length=40,
           mean(FLAG_JRC_ANY_DEF) as RATE format=percent8.2
    from work.bcef3g_base
    group by EXPO_GROUP_ORDER, EXPO_GROUP_ANALYSIS
    union all
    select EXPO_GROUP_ORDER, EXPO_GROUP_ANALYSIS, "FLAG_GASPAR_ANY_DEF" as INDICATOR length=40,
           mean(FLAG_GASPAR_ANY_DEF) as RATE format=percent8.2
    from work.bcef3g_base
    group by EXPO_GROUP_ORDER, EXPO_GROUP_ANALYSIS
    union all
    select EXPO_GROUP_ORDER, EXPO_GROUP_ANALYSIS, "FLAG_HANZE_ANY_DEF" as INDICATOR length=40,
           mean(FLAG_HANZE_ANY_DEF) as RATE format=percent8.2
    from work.bcef3g_base
    group by EXPO_GROUP_ORDER, EXPO_GROUP_ANALYSIS
    union all
    select EXPO_GROUP_ORDER, EXPO_GROUP_ANALYSIS, "FLAG_FLOOD_COLL_DEF" as INDICATOR length=40,
           mean(FLAG_FLOOD_COLL_DEF) as RATE format=percent8.2
    from work.bcef3g_base
    group by EXPO_GROUP_ORDER, EXPO_GROUP_ANALYSIS
    order by EXPO_GROUP_ORDER, INDICATOR
    ;
quit;

/*---------------------------------------------------------------------------
  4. Correlations with observed LGD
---------------------------------------------------------------------------*/

data work._corr_base;
    set work.bcef3g_base;
    if not missing(OBS_LGD_FINAL);
run;

proc sort data=work._corr_base;
    by EXPO_GROUP_ORDER EXPO_GROUP_ANALYSIS;
run;

proc corr data=work._corr_base pearson nosimple noprint outp=work._corr_p_all_raw;
    var &CORR_VARS;
    with OBS_LGD_FINAL;
run;

proc corr data=work._corr_base spearman nosimple noprint outp=work._corr_s_all_raw;
    var &CORR_VARS;
    with OBS_LGD_FINAL;
run;

proc corr data=work._corr_base pearson nosimple noprint outp=work._corr_p_grp_raw;
    by EXPO_GROUP_ORDER EXPO_GROUP_ANALYSIS;
    var &CORR_VARS;
    with OBS_LGD_FINAL;
run;

proc corr data=work._corr_base spearman nosimple noprint outp=work._corr_s_grp_raw;
    by EXPO_GROUP_ORDER EXPO_GROUP_ANALYSIS;
    var &CORR_VARS;
    with OBS_LGD_FINAL;
run;

data OUTLIB.&OUT_PREFIX._CORR_P_ALL;
    length CORR_TYPE $8 INDICATOR $40;
    set work._corr_p_all_raw;
    where _TYPE_ = "CORR";
    CORR_TYPE = "PEARSON";
    INDICATOR = _NAME_;
    CORR_WITH_OBS_LGD = OBS_LGD_FINAL;
    keep CORR_TYPE INDICATOR CORR_WITH_OBS_LGD;
run;

data OUTLIB.&OUT_PREFIX._CORR_S_ALL;
    length CORR_TYPE $8 INDICATOR $40;
    set work._corr_s_all_raw;
    where _TYPE_ = "CORR";
    CORR_TYPE = "SPEARMAN";
    INDICATOR = _NAME_;
    CORR_WITH_OBS_LGD = OBS_LGD_FINAL;
    keep CORR_TYPE INDICATOR CORR_WITH_OBS_LGD;
run;

data OUTLIB.&OUT_PREFIX._CORR_P_GRP;
    length CORR_TYPE $8 INDICATOR $40;
    set work._corr_p_grp_raw;
    where _TYPE_ = "CORR";
    CORR_TYPE = "PEARSON";
    INDICATOR = _NAME_;
    CORR_WITH_OBS_LGD = OBS_LGD_FINAL;
    keep EXPO_GROUP_ORDER EXPO_GROUP_ANALYSIS CORR_TYPE INDICATOR CORR_WITH_OBS_LGD;
run;

data OUTLIB.&OUT_PREFIX._CORR_S_GRP;
    length CORR_TYPE $8 INDICATOR $40;
    set work._corr_s_grp_raw;
    where _TYPE_ = "CORR";
    CORR_TYPE = "SPEARMAN";
    INDICATOR = _NAME_;
    CORR_WITH_OBS_LGD = OBS_LGD_FINAL;
    keep EXPO_GROUP_ORDER EXPO_GROUP_ANALYSIS CORR_TYPE INDICATOR CORR_WITH_OBS_LGD;
run;

/*---------------------------------------------------------------------------
  5. Statistical tests across the 3 exposure groups
---------------------------------------------------------------------------*/

ods exclude all;
ods output KruskalWallisTest=OUTLIB.&OUT_PREFIX._KRUSKAL;
proc npar1way data=work.bcef3g_base wilcoxon;
    class EXPO_GROUP_ANALYSIS;
    var
        OBS_LGD_FINAL
        EST_LGD_REPORT
        NB_FLOOD_DEF
        FLOOD_INT_MAX_DEF
        FLOOD_INT_CUM_DEF_V1
        FLOOD_INT_CUM_DEF_V2
        N_M_LAST_PRE_FLOOD
        RATIO_COLL_FLOODED
    ;
run;
ods exclude none;

ods exclude all;
ods output ChiSq=OUTLIB.&OUT_PREFIX._RATING_CHISQ
           CrossTabFreqs=OUTLIB.&OUT_PREFIX._RATING_CROSSTAB;
proc freq data=work.bcef3g_base;
    tables EXPO_GROUP_ANALYSIS * RATING_BUCKET / chisq;
run;
ods exclude none;

ods exclude all;
ods output OverallANOVA=OUTLIB.&OUT_PREFIX._ANOVA_OBS;
proc glm data=work.bcef3g_base;
    where not missing(OBS_LGD_FINAL);
    class EXPO_GROUP_ANALYSIS;
    model OBS_LGD_FINAL = EXPO_GROUP_ANALYSIS;
quit;
ods exclude none;

data OUTLIB.&OUT_PREFIX._ANOVA_OBS;
    length VARIABLE $40;
    set OUTLIB.&OUT_PREFIX._ANOVA_OBS;
    VARIABLE = "OBS_LGD_FINAL";
run;

ods exclude all;
ods output OverallANOVA=OUTLIB.&OUT_PREFIX._ANOVA_EST;
proc glm data=work.bcef3g_base;
    where not missing(EST_LGD_REPORT);
    class EXPO_GROUP_ANALYSIS;
    model EST_LGD_REPORT = EXPO_GROUP_ANALYSIS;
quit;
ods exclude none;

data OUTLIB.&OUT_PREFIX._ANOVA_EST;
    length VARIABLE $40;
    set OUTLIB.&OUT_PREFIX._ANOVA_EST;
    VARIABLE = "EST_LGD_REPORT";
run;

/*---------------------------------------------------------------------------
  6. Helper tables for plots
---------------------------------------------------------------------------*/

data work._corr_s_all_plot;
    set OUTLIB.&OUT_PREFIX._CORR_S_ALL;
    ABS_CORR = abs(CORR_WITH_OBS_LGD);
run;

proc sort data=work._corr_s_all_plot;
    by descending ABS_CORR;
run;

proc sort data=OUTLIB.&OUT_PREFIX._RATING_DIST;
    by EXPO_GROUP_ANALYSIS RATING_BUCKET;
run;

proc sort data=OUTLIB.&OUT_PREFIX._FLAG_RATES;
    by INDICATOR EXPO_GROUP_ORDER;
run;

/*---------------------------------------------------------------------------
  7. Excel export with tables and plots
---------------------------------------------------------------------------*/

ods graphics on / reset width=8.5in height=5in imagename="bcef_3group_flood_lgd";
ods excel file="&XLSX_OUT"
    options(
        embedded_titles="yes"
        frozen_headers="yes"
        sheet_interval="none"
        autofilter="all"
    );

title "BCEF Flood x LGD - Data check";
ods excel options(sheet_name="01_Data_Check");
proc print data=OUTLIB.&OUT_PREFIX._DATA_CHECK noobs;
run;

title "BCEF Flood x LGD - Exposure group counts";
ods excel options(sheet_name="02_Group_Counts");
proc print data=OUTLIB.&OUT_PREFIX._GROUP_COUNTS noobs;
run;

title "BCEF Flood x LGD - Missingness";
ods excel options(sheet_name="03_Missingness");
proc print data=OUTLIB.&OUT_PREFIX._MISSINGNESS noobs;
run;

title "BCEF Flood x LGD - Descriptive statistics by EXPO_GROUP";
ods excel options(sheet_name="04_Desc_By_Group");
proc print data=OUTLIB.&OUT_PREFIX._DESC_GROUP noobs;
run;

title "BCEF Flood x LGD - Rating summary by EXPO_GROUP";
ods excel options(sheet_name="05_Rating_Summary");
proc print data=OUTLIB.&OUT_PREFIX._RATING_SUMMARY noobs;
run;

title "BCEF Flood x LGD - LGD grade distribution";
ods excel options(sheet_name="06_Grade_Dist");
proc print data=OUTLIB.&OUT_PREFIX._GRADE_DIST noobs;
run;

title "BCEF Flood x LGD - Rating bucket distribution";
ods excel options(sheet_name="07_Rating_Buckets");
proc print data=OUTLIB.&OUT_PREFIX._RATING_DIST noobs;
run;

title "BCEF Flood x LGD - Flood flag rates by group";
ods excel options(sheet_name="08_Flag_Rates");
proc print data=OUTLIB.&OUT_PREFIX._FLAG_RATES noobs;
run;

title "BCEF Flood x LGD - Source overlap";
ods excel options(sheet_name="09_Source_Overlap");
proc print data=OUTLIB.&OUT_PREFIX._SRC_OVERLAP noobs;
run;

title "BCEF Flood x LGD - Pearson correlation overall";
ods excel options(sheet_name="10_Corr_P_All");
proc print data=OUTLIB.&OUT_PREFIX._CORR_P_ALL noobs;
run;

title "BCEF Flood x LGD - Spearman correlation overall";
ods excel options(sheet_name="11_Corr_S_All");
proc print data=OUTLIB.&OUT_PREFIX._CORR_S_ALL noobs;
run;

title "BCEF Flood x LGD - Pearson correlation by group";
ods excel options(sheet_name="12_Corr_P_Group");
proc print data=OUTLIB.&OUT_PREFIX._CORR_P_GRP noobs;
run;

title "BCEF Flood x LGD - Spearman correlation by group";
ods excel options(sheet_name="13_Corr_S_Group");
proc print data=OUTLIB.&OUT_PREFIX._CORR_S_GRP noobs;
run;

title "BCEF Flood x LGD - Kruskal-Wallis tests";
ods excel options(sheet_name="14_Kruskal");
proc print data=OUTLIB.&OUT_PREFIX._KRUSKAL noobs;
run;

title "BCEF Flood x LGD - ANOVA observed LGD";
ods excel options(sheet_name="15_ANOVA_Obs");
proc print data=OUTLIB.&OUT_PREFIX._ANOVA_OBS noobs;
run;

title "BCEF Flood x LGD - ANOVA estimated LGD";
ods excel options(sheet_name="16_ANOVA_Est");
proc print data=OUTLIB.&OUT_PREFIX._ANOVA_EST noobs;
run;

title "BCEF Flood x LGD - Rating bucket chi-square";
ods excel options(sheet_name="17_Rating_ChiSq");
proc print data=OUTLIB.&OUT_PREFIX._RATING_CHISQ noobs;
run;

title "BCEF Flood x LGD - Rating bucket crosstab";
ods excel options(sheet_name="18_Rating_XTab");
proc print data=OUTLIB.&OUT_PREFIX._RATING_CROSSTAB noobs;
run;

title "BCEF Flood x LGD - Number of sessions by EXPO_GROUP";
ods excel options(sheet_name="19_Counts_Plot");
proc sgplot data=OUTLIB.&OUT_PREFIX._GROUP_COUNTS;
    vbarparm category=EXPO_GROUP_ANALYSIS response=COUNT / datalabel;
    xaxis discreteorder=data label="Exposure group";
    yaxis label="Number of sessions";
run;

title "BCEF Flood x LGD - Observed LGD by EXPO_GROUP";
ods excel options(sheet_name="20_Obs_Box");
proc sgplot data=work.bcef3g_base;
    where not missing(OBS_LGD_FINAL);
    vbox OBS_LGD_FINAL / category=EXPO_GROUP_ANALYSIS;
    xaxis discreteorder=data label="Exposure group";
    yaxis label="Observed LGD";
run;

title "BCEF Flood x LGD - Estimated LGD by EXPO_GROUP";
ods excel options(sheet_name="21_Est_Box");
proc sgplot data=work.bcef3g_base;
    where not missing(EST_LGD_REPORT);
    vbox EST_LGD_REPORT / category=EXPO_GROUP_ANALYSIS;
    xaxis discreteorder=data label="Exposure group";
    yaxis label="Estimated LGD";
run;

title "BCEF Flood x LGD - Observed LGD distribution";
ods excel options(sheet_name="22_Obs_Hist");
proc sgplot data=work.bcef3g_base;
    where not missing(OBS_LGD_FINAL);
    histogram OBS_LGD_FINAL / group=EXPO_GROUP_ANALYSIS transparency=0.45;
    density OBS_LGD_FINAL / group=EXPO_GROUP_ANALYSIS type=kernel;
    xaxis label="Observed LGD";
    yaxis label="Frequency";
run;

title "BCEF Flood x LGD - Estimated LGD distribution";
ods excel options(sheet_name="23_Est_Hist");
proc sgplot data=work.bcef3g_base;
    where not missing(EST_LGD_REPORT);
    histogram EST_LGD_REPORT / group=EXPO_GROUP_ANALYSIS transparency=0.45;
    density EST_LGD_REPORT / group=EXPO_GROUP_ANALYSIS type=kernel;
    xaxis label="Estimated LGD";
    yaxis label="Frequency";
run;

title "BCEF Flood x LGD - Flood cumulative intensity V1 vs observed LGD";
ods excel options(sheet_name="24_Scatter_V1");
proc sgplot data=work.bcef3g_base;
    where not missing(FLOOD_INT_CUM_DEF_V1) and not missing(OBS_LGD_FINAL);
    scatter x=FLOOD_INT_CUM_DEF_V1 y=OBS_LGD_FINAL / group=EXPO_GROUP_ANALYSIS transparency=0.35;
    reg x=FLOOD_INT_CUM_DEF_V1 y=OBS_LGD_FINAL / group=EXPO_GROUP_ANALYSIS nomarkers;
    xaxis label="Flood cumulative intensity V1";
    yaxis label="Observed LGD";
run;

title "BCEF Flood x LGD - Flood cumulative intensity V2 vs observed LGD";
ods excel options(sheet_name="25_Scatter_V2");
proc sgplot data=work.bcef3g_base;
    where not missing(FLOOD_INT_CUM_DEF_V2) and not missing(OBS_LGD_FINAL);
    scatter x=FLOOD_INT_CUM_DEF_V2 y=OBS_LGD_FINAL / group=EXPO_GROUP_ANALYSIS transparency=0.35;
    reg x=FLOOD_INT_CUM_DEF_V2 y=OBS_LGD_FINAL / group=EXPO_GROUP_ANALYSIS nomarkers;
    xaxis label="Flood cumulative intensity V2";
    yaxis label="Observed LGD";
run;

title "BCEF Flood x LGD - Rating bucket composition";
ods excel options(sheet_name="26_Rating_Bars");
proc sgplot data=OUTLIB.&OUT_PREFIX._RATING_DIST;
    vbarparm category=EXPO_GROUP_ANALYSIS response=COUNT / group=RATING_BUCKET groupdisplay=stack seglabel;
    xaxis discreteorder=data label="Exposure group";
    yaxis label="Number of sessions";
run;

title "BCEF Flood x LGD - Flood flag rates by group";
ods excel options(sheet_name="27_Flag_Rates_Plot");
proc sgplot data=OUTLIB.&OUT_PREFIX._FLAG_RATES;
    vbarparm category=INDICATOR response=RATE / group=EXPO_GROUP_ANALYSIS groupdisplay=cluster;
    xaxis discreteorder=data label="Flood indicator";
    yaxis label="Rate" values=(0 to 1 by 0.1);
run;

title "BCEF Flood x LGD - Overall Spearman correlation with observed LGD";
ods excel options(sheet_name="28_Corr_Bars");
proc sgplot data=work._corr_s_all_plot;
    hbarparm category=INDICATOR response=CORR_WITH_OBS_LGD;
    refline 0 / axis=x;
    xaxis label="Spearman correlation with observed LGD";
    yaxis discreteorder=data label="Flood indicator";
run;

ods graphics off;
ods excel close;
title;
