/*===========================================================================
  BCEF - Flood x LGD analysis from T20_LGD_FLOOD_BCEF

  GOAL
    - Compare the 3 existing exposure groups in EXPO_GROUP
    - Study the link between flood indicators and observed LGD
    - Export the main tables and plots to one Excel file

  GROUPS
    - EXPOSED
    - INTERMEDIATE EXPOSURE
    - NON-EXPOSED

  IMPORTANT
    - The source table is not modified.
    - Only update the LIBNAME paths and Excel path before running.
===========================================================================*/

options mprint mlogic symbolgen;

/*---------------------------------------------------------------------------
  0. Paths and parameters
---------------------------------------------------------------------------*/

/* Update these paths on the other PC */
libname INLIB  "C:\PATH\TO\INPUT_FOLDER";
libname OUTLIB "C:\PATH\TO\OUTPUT_FOLDER";

%let IN_DS      = T20_LGD_FLOOD_BCEF;
%let OUT_PREFIX = BCEF3G;
%let XLSX_OUT   = C:\PATH\TO\OUTPUT_FOLDER\BCEF_3GROUP_FLOOD_LGD_ANALYSIS.xlsx;
%let IG_MAX_GRADE = 10;

/* Use V2 as the main cumulative intensity view */
%let MAIN_CUM_VAR = FLOOD_INT_CUM_DEF_V2;

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

/*---------------------------------------------------------------------------
  1. Build a clean analysis base
---------------------------------------------------------------------------*/

data work.base;
    set INLIB.&IN_DS;

    length EXPO_GROUP_STD $25 RATING_BUCKET $8 LGD_GRADE_STD $40;

    EXPO_GROUP_STD = upcase(strip(EXPO_GROUP));
    if EXPO_GROUP_STD not in ("EXPOSED", "INTERMEDIATE EXPOSURE", "NON-EXPOSED") then delete;

    if EXPO_GROUP_STD = "EXPOSED" then EXPO_GROUP_ORD = 1;
    else if EXPO_GROUP_STD = "INTERMEDIATE EXPOSURE" then EXPO_GROUP_ORD = 2;
    else if EXPO_GROUP_STD = "NON-EXPOSED" then EXPO_GROUP_ORD = 3;

    OBS_LGD = Realised_LGD;
    EST_LGD = LGD_Estimate;
    LGD_GRADE_STD = strip(LGD_Grade);
    GRADE_NUM = input(compress(LGD_GRADE_STD, , "kd"), ?? best12.);

    if missing(LGD_GRADE_STD) or LGD_GRADE_STD in ("", ".") then RATING_BUCKET = "NR";
    else if find(upcase(LGD_GRADE_STD), "NIG", "it") > 0 then RATING_BUCKET = "NIG";
    else if find(upcase(LGD_GRADE_STD), "NON-INV", "it") > 0 then RATING_BUCKET = "NIG";
    else if find(upcase(LGD_GRADE_STD), "NON INVEST", "it") > 0 then RATING_BUCKET = "NIG";
    else if find(upcase(LGD_GRADE_STD), "NR", "it") > 0 then RATING_BUCKET = "NR";
    else if find(upcase(LGD_GRADE_STD), "NON RATE", "it") > 0 then RATING_BUCKET = "NR";
    else if find(upcase(LGD_GRADE_STD), "IG", "it") > 0 then RATING_BUCKET = "IG";
    else if not missing(GRADE_NUM) then do;
        if GRADE_NUM <= &IG_MAX_GRADE then RATING_BUCKET = "IG";
        else RATING_BUCKET = "NIG";
    end;
    else RATING_BUCKET = "OTHER";

    format
        OBS_LGD
        EST_LGD
        FLOOD_INT_MAX_DEF
        FLOOD_INT_CUM_DEF_V1
        FLOOD_INT_CUM_DEF_V2
        NB_FLOOD_DEF
        N_M_LAST_PRE_FLOOD
        RATIO_COLL_FLOODED
        12.4
    ;
run;

proc sort data=work.base;
    by EXPO_GROUP_ORD EXPO_GROUP_STD;
run;

data OUTLIB.&OUT_PREFIX._BASE;
    set work.base;
run;

/*---------------------------------------------------------------------------
  2. Business tables
---------------------------------------------------------------------------*/

proc freq data=work.base noprint;
    tables EXPO_GROUP_STD / out=work._group_counts;
    tables EXPO_GROUP_STD * LGD_GRADE_STD / out=work._grade_dist outpct missing;
    tables EXPO_GROUP_STD * RATING_BUCKET / out=work._rating_dist outpct missing;
run;

data OUTLIB.&OUT_PREFIX._GROUP_COUNTS;
    set work._group_counts;
    if EXPO_GROUP_STD = "EXPOSED" then EXPO_GROUP_ORD = 1;
    else if EXPO_GROUP_STD = "INTERMEDIATE EXPOSURE" then EXPO_GROUP_ORD = 2;
    else if EXPO_GROUP_STD = "NON-EXPOSED" then EXPO_GROUP_ORD = 3;
run;

proc sort data=OUTLIB.&OUT_PREFIX._GROUP_COUNTS;
    by EXPO_GROUP_ORD;
run;

proc sql;
    create table OUTLIB.&OUT_PREFIX._GROUP_SUMMARY as
    select
        EXPO_GROUP_ORD,
        EXPO_GROUP_STD,
        count(*)                                 as N_SESSIONS,
        sum(not missing(OBS_LGD))                as N_OBS_LGD,
        sum(not missing(EST_LGD))                as N_EST_LGD,
        mean(OBS_LGD)                            as AVG_OBS_LGD format=12.4,
        median(OBS_LGD)                          as MEDIAN_OBS_LGD format=12.4,
        mean(EST_LGD)                            as AVG_EST_LGD format=12.4,
        median(EST_LGD)                          as MEDIAN_EST_LGD format=12.4,
        mean(FLAG_FLOOD_AREA_DEF)                as PCT_FLAG_FLOOD_AREA_DEF format=percent8.2,
        mean(FLAG_FLOOD_DEF)                     as PCT_FLAG_FLOOD_DEF format=percent8.2,
        mean(FLAG_JRC_ANY_DEF)                   as PCT_FLAG_JRC_ANY_DEF format=percent8.2,
        mean(FLAG_GASPAR_ANY_DEF)                as PCT_FLAG_GASPAR_ANY_DEF format=percent8.2,
        mean(FLAG_HANZE_ANY_DEF)                 as PCT_FLAG_HANZE_ANY_DEF format=percent8.2,
        mean(FLAG_FLOOD_COLL_DEF)                as PCT_FLAG_FLOOD_COLL_DEF format=percent8.2,
        mean(NB_FLOOD_DEF)                       as AVG_NB_FLOOD_DEF format=12.4,
        median(NB_FLOOD_DEF)                     as MEDIAN_NB_FLOOD_DEF format=12.4,
        mean(FLOOD_INT_MAX_DEF)                  as AVG_FLOOD_INT_MAX_DEF format=12.4,
        median(FLOOD_INT_MAX_DEF)                as MEDIAN_FLOOD_INT_MAX_DEF format=12.4,
        mean(FLOOD_INT_CUM_DEF_V1)               as AVG_CUM_V1 format=12.4,
        median(FLOOD_INT_CUM_DEF_V1)             as MEDIAN_CUM_V1 format=12.4,
        mean(FLOOD_INT_CUM_DEF_V2)               as AVG_CUM_V2 format=12.4,
        median(FLOOD_INT_CUM_DEF_V2)             as MEDIAN_CUM_V2 format=12.4,
        mean(N_M_LAST_PRE_FLOOD)                 as AVG_N_M_LAST_PRE_FLOOD format=12.4,
        median(N_M_LAST_PRE_FLOOD)               as MEDIAN_N_M_LAST_PRE_FLOOD format=12.4,
        mean(RATIO_COLL_FLOODED)                 as AVG_RATIO_COLL_FLOODED format=12.4,
        median(RATIO_COLL_FLOODED)               as MEDIAN_RATIO_COLL_FLOODED format=12.4
    from work.base
    group by EXPO_GROUP_ORD, EXPO_GROUP_STD
    order by EXPO_GROUP_ORD
    ;

    create table OUTLIB.&OUT_PREFIX._RATING_SUMMARY as
    select
        EXPO_GROUP_ORD,
        EXPO_GROUP_STD,
        count(*)                                      as N_SESSIONS,
        mean(RATING_BUCKET = "IG")                    as PCT_IG_ALL format=percent8.2,
        mean(RATING_BUCKET = "NIG")                   as PCT_NIG_ALL format=percent8.2,
        mean(RATING_BUCKET = "NR")                    as PCT_NR_ALL format=percent8.2,
        mean(RATING_BUCKET = "OTHER")                 as PCT_OTHER_ALL format=percent8.2,
        case
            when sum(case when RATING_BUCKET in ("IG", "NIG") then 1 else 0 end) > 0
            then sum(case when RATING_BUCKET = "IG" then 1 else 0 end)
               / sum(case when RATING_BUCKET in ("IG", "NIG") then 1 else 0 end)
            else .
        end                                           as PCT_IG_RATED format=percent8.2,
        case
            when sum(case when RATING_BUCKET in ("IG", "NIG") then 1 else 0 end) > 0
            then sum(case when RATING_BUCKET = "NIG" then 1 else 0 end)
               / sum(case when RATING_BUCKET in ("IG", "NIG") then 1 else 0 end)
            else .
        end                                           as PCT_NIG_RATED format=percent8.2
    from work.base
    group by EXPO_GROUP_ORD, EXPO_GROUP_STD
    order by EXPO_GROUP_ORD
    ;
quit;

data OUTLIB.&OUT_PREFIX._GRADE_DIST;
    set work._grade_dist(rename=(PCT_ROW = PCT_IN_GROUP));
    keep EXPO_GROUP_STD LGD_GRADE_STD COUNT PERCENT PCT_IN_GROUP;
run;

data OUTLIB.&OUT_PREFIX._RATING_DIST;
    set work._rating_dist(rename=(PCT_ROW = PCT_IN_GROUP));
    keep EXPO_GROUP_STD RATING_BUCKET COUNT PERCENT PCT_IN_GROUP;
run;

data work._flag_long;
    set work.base;
    length INDICATOR $40 VALUE 8;
    array F[6]
        FLAG_FLOOD_AREA_DEF
        FLAG_FLOOD_DEF
        FLAG_JRC_ANY_DEF
        FLAG_GASPAR_ANY_DEF
        FLAG_HANZE_ANY_DEF
        FLAG_FLOOD_COLL_DEF
    ;
    array N[6] $40 _temporary_
        (
            "FLAG_FLOOD_AREA_DEF",
            "FLAG_FLOOD_DEF",
            "FLAG_JRC_ANY_DEF",
            "FLAG_GASPAR_ANY_DEF",
            "FLAG_HANZE_ANY_DEF",
            "FLAG_FLOOD_COLL_DEF"
        )
    ;
    do I = 1 to dim(F);
        INDICATOR = N[I];
        VALUE = F[I];
        output;
    end;
    keep EXPO_GROUP_ORD EXPO_GROUP_STD INDICATOR VALUE;
run;

proc sql;
    create table OUTLIB.&OUT_PREFIX._FLAG_RATES as
    select
        EXPO_GROUP_ORD,
        EXPO_GROUP_STD,
        INDICATOR,
        mean(VALUE) as RATE format=percent8.2
    from work._flag_long
    group by EXPO_GROUP_ORD, EXPO_GROUP_STD, INDICATOR
    order by INDICATOR, EXPO_GROUP_ORD
    ;
quit;

/*---------------------------------------------------------------------------
  3. Correlations with observed LGD
---------------------------------------------------------------------------*/

data work._corr_base;
    set work.base;
    if not missing(OBS_LGD);
run;

proc sort data=work._corr_base;
    by EXPO_GROUP_ORD EXPO_GROUP_STD;
run;

%macro corr_to_table(method=, bygroup=no, raw=, out=);
    proc corr data=work._corr_base &method nosimple noprint outp=work.&raw;
        %if &bygroup = yes %then %do;
            by EXPO_GROUP_ORD EXPO_GROUP_STD;
        %end;
        var &CORR_VARS;
        with OBS_LGD;
    run;

    data OUTLIB.&OUT_PREFIX._&out;
        length CORR_TYPE $8 INDICATOR $40;
        set work.&raw;
        where _TYPE_ = "CORR";
        CORR_TYPE = upcase("&method");
        INDICATOR = _NAME_;
        CORR_WITH_OBS_LGD = OBS_LGD;
        %if &bygroup = yes %then %do;
            keep EXPO_GROUP_ORD EXPO_GROUP_STD CORR_TYPE INDICATOR CORR_WITH_OBS_LGD;
        %end;
        %else %do;
            keep CORR_TYPE INDICATOR CORR_WITH_OBS_LGD;
        %end;
    run;
%mend;

%corr_to_table(method=pearson,  bygroup=no,  raw=corr_p_all_raw, out=CORR_P_ALL);
%corr_to_table(method=spearman, bygroup=no,  raw=corr_s_all_raw, out=CORR_S_ALL);
%corr_to_table(method=pearson,  bygroup=yes, raw=corr_p_grp_raw, out=CORR_P_GRP);
%corr_to_table(method=spearman, bygroup=yes, raw=corr_s_grp_raw, out=CORR_S_GRP);

/*---------------------------------------------------------------------------
  4. Statistical tests
---------------------------------------------------------------------------*/

ods exclude all;
ods output KruskalWallisTest=OUTLIB.&OUT_PREFIX._KRUSKAL;
proc npar1way data=work.base wilcoxon;
    class EXPO_GROUP_STD;
    var OBS_LGD EST_LGD NB_FLOOD_DEF FLOOD_INT_MAX_DEF FLOOD_INT_CUM_DEF_V1 FLOOD_INT_CUM_DEF_V2;
run;
ods exclude none;

ods exclude all;
ods output ChiSq=OUTLIB.&OUT_PREFIX._RATING_CHISQ
           CrossTabFreqs=OUTLIB.&OUT_PREFIX._RATING_XTAB;
proc freq data=work.base;
    tables EXPO_GROUP_STD * RATING_BUCKET / chisq;
run;
ods exclude none;

/*---------------------------------------------------------------------------
  5. A few plot-ready helper tables
---------------------------------------------------------------------------*/

data work._corr_plot;
    set OUTLIB.&OUT_PREFIX._CORR_S_ALL;
    ABS_CORR = abs(CORR_WITH_OBS_LGD);
run;

proc sort data=work._corr_plot;
    by descending ABS_CORR;
run;

/*---------------------------------------------------------------------------
  6. Excel export
---------------------------------------------------------------------------*/

ods graphics on / reset width=8.5in height=5in imagename="bcef_3group_lgd";
ods excel file="&XLSX_OUT"
    options(embedded_titles="yes" frozen_headers="yes" sheet_interval="none" autofilter="all");

title "Exposure group counts";
ods excel options(sheet_name="01_Group_Counts");
proc print data=OUTLIB.&OUT_PREFIX._GROUP_COUNTS noobs;
run;

title "Summary by exposure group";
ods excel options(sheet_name="02_Group_Summary");
proc print data=OUTLIB.&OUT_PREFIX._GROUP_SUMMARY noobs;
run;

title "Rating summary by exposure group";
ods excel options(sheet_name="03_Rating_Summary");
proc print data=OUTLIB.&OUT_PREFIX._RATING_SUMMARY noobs;
run;

title "LGD grade distribution";
ods excel options(sheet_name="04_Grade_Dist");
proc print data=OUTLIB.&OUT_PREFIX._GRADE_DIST noobs;
run;

title "Rating bucket distribution";
ods excel options(sheet_name="05_Rating_Dist");
proc print data=OUTLIB.&OUT_PREFIX._RATING_DIST noobs;
run;

title "Flood flag rates by group";
ods excel options(sheet_name="06_Flag_Rates");
proc print data=OUTLIB.&OUT_PREFIX._FLAG_RATES noobs;
run;

title "Overall Pearson correlations";
ods excel options(sheet_name="07_Corr_P_All");
proc print data=OUTLIB.&OUT_PREFIX._CORR_P_ALL noobs;
run;

title "Overall Spearman correlations";
ods excel options(sheet_name="08_Corr_S_All");
proc print data=OUTLIB.&OUT_PREFIX._CORR_S_ALL noobs;
run;

title "Correlations by exposure group";
ods excel options(sheet_name="09_Corr_By_Group");
proc print data=OUTLIB.&OUT_PREFIX._CORR_S_GRP noobs;
run;

title "Kruskal-Wallis tests";
ods excel options(sheet_name="10_Kruskal");
proc print data=OUTLIB.&OUT_PREFIX._KRUSKAL noobs;
run;

title "Rating chi-square";
ods excel options(sheet_name="11_Rating_ChiSq");
proc print data=OUTLIB.&OUT_PREFIX._RATING_CHISQ noobs;
run;

title "Observed LGD by exposure group";
ods excel options(sheet_name="12_Obs_Box");
proc sgplot data=work.base;
    where not missing(OBS_LGD);
    vbox OBS_LGD / category=EXPO_GROUP_STD;
    xaxis discreteorder=data label="Exposure group";
    yaxis label="Observed LGD";
run;

title "Estimated LGD by exposure group";
ods excel options(sheet_name="13_Est_Box");
proc sgplot data=work.base;
    where not missing(EST_LGD);
    vbox EST_LGD / category=EXPO_GROUP_STD;
    xaxis discreteorder=data label="Exposure group";
    yaxis label="Estimated LGD";
run;

title "Main cumulative intensity vs observed LGD";
ods excel options(sheet_name="14_Cum_Scatter");
proc sgplot data=work.base;
    where not missing(&MAIN_CUM_VAR) and not missing(OBS_LGD);
    scatter x=&MAIN_CUM_VAR y=OBS_LGD / group=EXPO_GROUP_STD transparency=0.35;
    reg x=&MAIN_CUM_VAR y=OBS_LGD / group=EXPO_GROUP_STD nomarkers;
    xaxis label="Flood cumulative intensity";
    yaxis label="Observed LGD";
run;

title "Rating bucket composition";
ods excel options(sheet_name="15_Rating_Bars");
proc sgplot data=OUTLIB.&OUT_PREFIX._RATING_DIST;
    vbarparm category=EXPO_GROUP_STD response=COUNT / group=RATING_BUCKET groupdisplay=stack seglabel;
    xaxis discreteorder=data label="Exposure group";
    yaxis label="Number of sessions";
run;

title "Spearman correlations with observed LGD";
ods excel options(sheet_name="16_Corr_Bars");
proc sgplot data=work._corr_plot;
    hbarparm category=INDICATOR response=CORR_WITH_OBS_LGD;
    refline 0 / axis=x;
    xaxis label="Spearman correlation";
    yaxis discreteorder=data label="Flood indicator";
run;

ods graphics off;
ods excel close;
title;

