/*===========================================================================

  ACCLIM - BCEF - Category 1 Step 1
  Flood indicators vs observed LGD

  PURPOSE
    1. Exploit the session-level flood indicators built in T20_LGD_FLOOD_BCEF_AREA
    2. Compare Exposed vs Non-Exposed groups
    3. Study the link between flood indicators and observed LGD
    4. Produce ready-to-use tables for:
         - recovery dynamics
         - average realised LGD
         - mean / median estimated LGD
         - LGD grade distribution
         - % rated IG / % rated NIG

  IMPORTANT MODELING CHOICES
    - Upstream flood aggregation logic is left untouched.
    - Both cumulative intensity metrics are preserved:
        FLOOD_INT_CUM_DEF_V1
        FLOOD_INT_CUM_DEF_V2
      The reporting variable below defaults to V1 so this script does not
      impose a change on the original colleague workflow.
    - Observed LGD used for the descriptive comparison:
        OBS_LGD_FINAL = coalesce(Additional_Realised_LGD,
                                 Realised_LGD_06, ..., Realised_LGD_01)
    - Reported estimated LGD:
        EST_LGD_LATEST = latest non-missing LGD_Estimate_07 -> 01
      You can switch to EST_LGD_DEFAULT if business wants the estimate at default.
    - Reported LGD grade:
        LGD_GRADE_LATEST = latest non-missing LGD_Grade_07 -> 01
    - IG / NIG split:
        if grade is numeric, IG is grade <= &IG_MAX_GRADE.
        Adjust &IG_MAX_GRADE if BCEF uses another cut.

===========================================================================*/

options mprint mlogic symbolgen;

/*---------------------------------------------------------------------------
  0. Parameters
---------------------------------------------------------------------------*/

libname INPUT  "/applis/25182-pumpp/data/car/backtesting/21_TRANSVERSAL/02 - ACCLIM/05 - Phase II/03 - Flood Indicators/00 - Input";
libname OUTPUT "/applis/25182-pumpp/data/car/backtesting/21_TRANSVERSAL/02 - ACCLIM/05 - Phase II/03 - Flood Indicators/01 - Outputs";

%let IN_DS            = OUTPUT.T20_LGD_FLOOD_BCEF_AREA;
%let OUTLIB           = OUTPUT;
%let OUT_PREFIX       = CAT1_BCEF_FLOOD_LGD;

/* Main binary exposure flag for the dedicated Exposed / Non-Exposed view */
%let MAIN_FLAG        = FLAG_FLOOD_AREA_DEF;

/* Report latest estimate by default. Switch to EST_LGD_DEFAULT if needed. */
%let REPORT_EST_VAR   = EST_LGD_LATEST;
%let REPORT_GRADE_VAR = LGD_GRADE_LATEST;
%let REPORT_CUM_VAR   = FLOOD_INT_CUM_DEF_V1;

/* Adjust if BCEF grade mapping uses another IG/NIG threshold */
%let IG_MAX_GRADE     = 10;

/* Optional Excel output */
%let XLSX_OUT         = /applis/25182-pumpp/data/car/backtesting/21_TRANSVERSAL/02 - ACCLIM/05 - Phase II/03 - Flood Indicators/01 - Outputs/CATEGORY1_BCEF_FLOOD_LGD.xlsx;

/* Binary flood definitions to compare */
%let FLAG_LIST =
    FLAG_FLOOD_AREA_DEF
    FLAG_FLOOD_DEF
    FLAG_JRC_ANY_DEF
    FLAG_GASPAR_ANY_DEF
    FLAG_HANZE_ANY_DEF
    FLAG_FLOOD_COLL_DEF
;

/* Variables used in the correlation view */
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
  1. Build the analysis-ready session table
---------------------------------------------------------------------------*/

data work.cat1_bcef_base;
    set &IN_DS;

    array _flags {*} 
        FLAG_FLOOD_DEF
        FLAG_FLOOD_PRE12
        FLAG_FLOOD_PRE24
        FLAG_FLOOD_AREA_DEF
        FLAG_FLOOD_PRE_24
        FLAG_FLOOD_COLL_DEF
        FLAG_FLOOD_COLL_PRE24
        FLAG_FLOOD_COLL_PRE36
        FLAG_FLOOD_COLL_PRE48
        FLAG_JRC_ANY_DEF
        FLAG_JRC_ANY_PRE24
        FLAG_GASPAR_ANY_DEF
        FLAG_GASPAR_ANY_PRE24
        FLAG_HANZE_ANY_DEF
        FLAG_HANZE_ANY_PRE24
        FLAG_COLLATERAL
        FLAG_COMPL_FLOOD_SOURCES_AT_DEF
        FLAG_COMPL_FLOOD_SOURCES_PRE_24
    ;

    do _i = 1 to dim(_flags);
        if missing(_flags[_i]) then _flags[_i] = 0;
    end;

    /* Observed LGD used for the Category 1 descriptive comparison */
    OBS_LGD_FINAL = coalesce(
        Additional_Realised_LGD,
        Realised_LGD_06,
        Realised_LGD_05,
        Realised_LGD_04,
        Realised_LGD_03,
        Realised_LGD_02,
        Realised_LGD_01
    );

    /* Keep both default-time and latest estimate */
    EST_LGD_DEFAULT = LGD_Estimate_01;
    EST_LGD_LATEST  = coalesce(
        LGD_Estimate_07,
        LGD_Estimate_06,
        LGD_Estimate_05,
        LGD_Estimate_04,
        LGD_Estimate_03,
        LGD_Estimate_02,
        LGD_Estimate_01
    );

    length LGD_GRADE_DEFAULT LGD_GRADE_LATEST $40;

    if strip(vvalue(LGD_Grade_01)) not in ("", ".") then LGD_GRADE_DEFAULT = strip(vvalue(LGD_Grade_01));
    else LGD_GRADE_DEFAULT = "";

    if strip(vvalue(LGD_Grade_07)) not in ("", ".") then LGD_GRADE_LATEST = strip(vvalue(LGD_Grade_07));
    else if strip(vvalue(LGD_Grade_06)) not in ("", ".") then LGD_GRADE_LATEST = strip(vvalue(LGD_Grade_06));
    else if strip(vvalue(LGD_Grade_05)) not in ("", ".") then LGD_GRADE_LATEST = strip(vvalue(LGD_Grade_05));
    else if strip(vvalue(LGD_Grade_04)) not in ("", ".") then LGD_GRADE_LATEST = strip(vvalue(LGD_Grade_04));
    else if strip(vvalue(LGD_Grade_03)) not in ("", ".") then LGD_GRADE_LATEST = strip(vvalue(LGD_Grade_03));
    else if strip(vvalue(LGD_Grade_02)) not in ("", ".") then LGD_GRADE_LATEST = strip(vvalue(LGD_Grade_02));
    else if strip(vvalue(LGD_Grade_01)) not in ("", ".") then LGD_GRADE_LATEST = strip(vvalue(LGD_Grade_01));
    else LGD_GRADE_LATEST = "";

    length RATING_BUCKET $8;
    GRADE_NUM = input(compress(LGD_GRADE_LATEST, , "kd"), best12.);

    if Flag_Non_Rated = 1 then RATING_BUCKET = "NR";
    else if index(upcase(LGD_GRADE_LATEST), "NIG") > 0 then RATING_BUCKET = "NIG";
    else if index(upcase(LGD_GRADE_LATEST), "NON-INV") > 0 then RATING_BUCKET = "NIG";
    else if index(upcase(LGD_GRADE_LATEST), "NON INVEST") > 0 then RATING_BUCKET = "NIG";
    else if index(upcase(LGD_GRADE_LATEST), "IG") > 0 then RATING_BUCKET = "IG";
    else if not missing(GRADE_NUM) then do;
        if GRADE_NUM <= &IG_MAX_GRADE then RATING_BUCKET = "IG";
        else RATING_BUCKET = "NIG";
    end;
    else RATING_BUCKET = "UNK";

    MAIN_EXPOSED    = (&MAIN_FLAG = 1);
    MAIN_EXPO_GROUP = ifc(MAIN_EXPOSED = 1, "Exposed", "Non-Exposed");

    format
        OBS_LGD_FINAL
        EST_LGD_DEFAULT
        EST_LGD_LATEST
        FLOOD_INT_CUM_DEF_V1
        FLOOD_INT_CUM_DEF_V2
        FLOOD_INT_MAX_DEF
        12.4
    ;

    drop _i;
run;

data &OUTLIB..&OUT_PREFIX._BASE;
    set work.cat1_bcef_base;
run;

/*---------------------------------------------------------------------------
  2. Global diagnostics
---------------------------------------------------------------------------*/

proc sql;
    create table &OUTLIB..&OUT_PREFIX._DATA_CHECK as
    select
        count(*)                                            as N_SESSIONS,
        sum(not missing(OBS_LGD_FINAL))                     as N_WITH_OBS_LGD,
        sum(not missing(EST_LGD_DEFAULT))                   as N_WITH_EST_LGD_DEFAULT,
        sum(not missing(EST_LGD_LATEST))                    as N_WITH_EST_LGD_LATEST,
        sum(&MAIN_FLAG = 1)                                 as N_MAIN_EXPOSED,
        sum(&MAIN_FLAG = 0)                                 as N_MAIN_NON_EXPOSED,
        sum(FLAG_JRC_ANY_DEF = 1)                           as N_JRC_DEF,
        sum(FLAG_GASPAR_ANY_DEF = 1)                        as N_GASPAR_DEF,
        sum(FLAG_HANZE_ANY_DEF = 1)                         as N_HANZE_DEF,
        mean(OBS_LGD_FINAL)                                 as AVG_OBS_LGD format=12.4,
        median(OBS_LGD_FINAL)                               as MEDIAN_OBS_LGD format=12.4,
        mean(&REPORT_EST_VAR)                               as AVG_REPORT_EST_LGD format=12.4,
        median(&REPORT_EST_VAR)                             as MEDIAN_REPORT_EST_LGD format=12.4,
        mean(&REPORT_CUM_VAR)                               as AVG_FLOOD_INT_CUM_DEF format=12.4,
        median(&REPORT_CUM_VAR)                             as MEDIAN_FLOOD_INT_CUM_DEF format=12.4
    from work.cat1_bcef_base
    ;
quit;

/*---------------------------------------------------------------------------
  3. Correlation between flood indicators and observed LGD
---------------------------------------------------------------------------*/

proc corr data=work.cat1_bcef_base pearson nosimple noprint outp=work._corr_p_raw;
    var &CORR_VARS;
    with OBS_LGD_FINAL;
run;

proc corr data=work.cat1_bcef_base spearman nosimple noprint outp=work._corr_s_raw;
    var &CORR_VARS;
    with OBS_LGD_FINAL;
run;

data &OUTLIB..&OUT_PREFIX._CORR_PEARSON;
    length CORR_TYPE $8 INDICATOR $40;
    set work._corr_p_raw;
    where _TYPE_ = "CORR";
    CORR_TYPE = "PEARSON";
    INDICATOR = _NAME_;
    CORR_WITH_OBS_LGD = OBS_LGD_FINAL;
    keep CORR_TYPE INDICATOR CORR_WITH_OBS_LGD;
run;

data &OUTLIB..&OUT_PREFIX._CORR_SPEARMAN;
    length CORR_TYPE $8 INDICATOR $40;
    set work._corr_s_raw;
    where _TYPE_ = "CORR";
    CORR_TYPE = "SPEARMAN";
    INDICATOR = _NAME_;
    CORR_WITH_OBS_LGD = OBS_LGD_FINAL;
    keep CORR_TYPE INDICATOR CORR_WITH_OBS_LGD;
run;

data &OUTLIB..&OUT_PREFIX._CORR_ALL;
    set
        &OUTLIB..&OUT_PREFIX._CORR_PEARSON
        &OUTLIB..&OUT_PREFIX._CORR_SPEARMAN
    ;
run;

/*---------------------------------------------------------------------------
  4. Clean previous outputs if they already exist
---------------------------------------------------------------------------*/

proc datasets library=&OUTLIB nolist;
    delete
        &OUT_PREFIX._SUMMARY_ALL
        &OUT_PREFIX._GRADE_DIST_ALL
        &OUT_PREFIX._RECOVERY_ALL
        &OUT_PREFIX._SIGNAL_ALL
    ;
quit;

/*---------------------------------------------------------------------------
  5. Macro to build the Category 1 outputs for each binary flood definition
---------------------------------------------------------------------------*/

%macro run_flag_analysis(flag=);

    data work._seg;
        set work.cat1_bcef_base;
        length EXPOSURE_DEFINITION $40 EXPOSED_GROUP $12 REPORT_GRADE $40;
        EXPOSURE_DEFINITION = "&flag";
        EXPOSED_GROUP = ifc(&flag = 1, "Exposed", "Non-Exposed");
        REPORT_GRADE = &REPORT_GRADE_VAR;
    run;

    proc sql;
        create table work._summary as
        select
            EXPOSURE_DEFINITION,
            EXPOSED_GROUP,
            count(*) as N_SESSIONS,
            sum(not missing(OBS_LGD_FINAL)) as N_OBS_LGD,
            sum(not missing(&REPORT_EST_VAR)) as N_EST_LGD,
            mean(OBS_LGD_FINAL) as AVG_REALISED_LGD format=12.4,
            median(OBS_LGD_FINAL) as MEDIAN_REALISED_LGD format=12.4,
            mean(&REPORT_EST_VAR) as MEAN_ESTIMATED_LGD format=12.4,
            median(&REPORT_EST_VAR) as MEDIAN_ESTIMATED_LGD format=12.4,
            sum(case when RATING_BUCKET = "IG"  then 1 else 0 end) / count(*) as PCT_IG_ALL format=percent8.2,
            sum(case when RATING_BUCKET = "NIG" then 1 else 0 end) / count(*) as PCT_NIG_ALL format=percent8.2,
            sum(case when RATING_BUCKET = "NR"  then 1 else 0 end) / count(*) as PCT_NR_ALL format=percent8.2,
            case
                when sum(case when RATING_BUCKET in ("IG", "NIG") then 1 else 0 end) > 0
                then sum(case when RATING_BUCKET = "IG" then 1 else 0 end)
                   / sum(case when RATING_BUCKET in ("IG", "NIG") then 1 else 0 end)
            end as PCT_IG_RATED format=percent8.2,
            case
                when sum(case when RATING_BUCKET in ("IG", "NIG") then 1 else 0 end) > 0
                then sum(case when RATING_BUCKET = "NIG" then 1 else 0 end)
                   / sum(case when RATING_BUCKET in ("IG", "NIG") then 1 else 0 end)
            end as PCT_NIG_RATED format=percent8.2
        from work._seg
        group by EXPOSURE_DEFINITION, EXPOSED_GROUP
        ;
    quit;

    proc append base=&OUTLIB..&OUT_PREFIX._SUMMARY_ALL data=work._summary force;
    run;

    proc freq data=work._seg noprint;
        tables EXPOSED_GROUP * REPORT_GRADE / missing out=work._grade outpct;
    run;

    data work._grade;
        length EXPOSURE_DEFINITION $40 EXPOSED_GROUP $12 LGD_GRADE $40;
        set work._grade(rename=(REPORT_GRADE = LGD_GRADE PCT_ROW = PCT_IN_GROUP));
        EXPOSURE_DEFINITION = "&flag";
        keep EXPOSURE_DEFINITION EXPOSED_GROUP LGD_GRADE COUNT PCT_IN_GROUP PERCENT;
    run;

    proc append base=&OUTLIB..&OUT_PREFIX._GRADE_DIST_ALL data=work._grade force;
    run;

    data work._recovery_long;
        set work._seg;
        length METRIC $12;
        array _real[6] Realised_LGD_01-Realised_LGD_06;
        array _est [7] LGD_Estimate_01-LGD_Estimate_07;

        do STAGE = 1 to dim(_real);
            METRIC = "REALISED";
            VALUE  = _real[STAGE];
            if not missing(VALUE) then output;
        end;

        do STAGE = 1 to dim(_est);
            METRIC = "ESTIMATED";
            VALUE  = _est[STAGE];
            if not missing(VALUE) then output;
        end;

        keep EXPOSURE_DEFINITION EXPOSED_GROUP METRIC STAGE VALUE;
    run;

    proc sql;
        create table work._recovery as
        select
            EXPOSURE_DEFINITION,
            EXPOSED_GROUP,
            METRIC,
            STAGE,
            count(*)      as N_OBS,
            mean(VALUE)   as MEAN_VALUE format=12.4,
            median(VALUE) as MEDIAN_VALUE format=12.4
        from work._recovery_long
        group by EXPOSURE_DEFINITION, EXPOSED_GROUP, METRIC, STAGE
        ;
    quit;

    proc append base=&OUTLIB..&OUT_PREFIX._RECOVERY_ALL data=work._recovery force;
    run;

    proc sql;
        create table work._signal as
        select
            "&flag" as EXPOSURE_DEFINITION length=40,
            max(case when EXPOSED_GROUP = "Exposed"     then AVG_REALISED_LGD   end) as EXPOSED_AVG_REALISED_LGD format=12.4,
            max(case when EXPOSED_GROUP = "Non-Exposed" then AVG_REALISED_LGD   end) as NONEXP_AVG_REALISED_LGD format=12.4,
            max(case when EXPOSED_GROUP = "Exposed"     then MEDIAN_REALISED_LGD end) as EXPOSED_MED_REALISED_LGD format=12.4,
            max(case when EXPOSED_GROUP = "Non-Exposed" then MEDIAN_REALISED_LGD end) as NONEXP_MED_REALISED_LGD format=12.4,
            max(case when EXPOSED_GROUP = "Exposed"     then MEDIAN_ESTIMATED_LGD end) as EXPOSED_MED_EST_LGD format=12.4,
            max(case when EXPOSED_GROUP = "Non-Exposed" then MEDIAN_ESTIMATED_LGD end) as NONEXP_MED_EST_LGD format=12.4
        from work._summary
        ;
    quit;

    data work._signal;
        set work._signal;
        DELTA_AVG_REALISED_LGD = EXPOSED_AVG_REALISED_LGD - NONEXP_AVG_REALISED_LGD;
        DELTA_MED_REALISED_LGD = EXPOSED_MED_REALISED_LGD - NONEXP_MED_REALISED_LGD;
        DELTA_MED_EST_LGD      = EXPOSED_MED_EST_LGD      - NONEXP_MED_EST_LGD;

        length SIGNAL_INTERPRETATION $32;
        if DELTA_MED_REALISED_LGD > 0 and DELTA_MED_EST_LGD > 0 then SIGNAL_INTERPRETATION = "Signal";
        else SIGNAL_INTERPRETATION = "No clear signal";
    run;

    proc append base=&OUTLIB..&OUT_PREFIX._SIGNAL_ALL data=work._signal force;
    run;

%mend;

%macro run_all_flags;
    %local i flag;
    %do i = 1 %to %sysfunc(countw(&FLAG_LIST));
        %let flag = %scan(&FLAG_LIST, &i);
        %run_flag_analysis(flag=&flag);
    %end;
%mend;

%run_all_flags;

/*---------------------------------------------------------------------------
  6. Main views sorted for reporting
---------------------------------------------------------------------------*/

proc sort data=&OUTLIB..&OUT_PREFIX._SUMMARY_ALL;
    by EXPOSURE_DEFINITION EXPOSED_GROUP;
run;

proc sort data=&OUTLIB..&OUT_PREFIX._GRADE_DIST_ALL;
    by EXPOSURE_DEFINITION EXPOSED_GROUP descending COUNT;
run;

proc sort data=&OUTLIB..&OUT_PREFIX._RECOVERY_ALL;
    by EXPOSURE_DEFINITION METRIC STAGE EXPOSED_GROUP;
run;

proc sort data=&OUTLIB..&OUT_PREFIX._SIGNAL_ALL;
    by EXPOSURE_DEFINITION;
run;

/*---------------------------------------------------------------------------
  7. Optional Excel export
---------------------------------------------------------------------------*/

ods excel file="&XLSX_OUT"
    options(
        embedded_titles="yes"
        frozen_headers="yes"
        sheet_interval="none"
        autofilter="all"
    );

title "BCEF Flood x LGD - Data check";
ods excel options(sheet_name="01_Data_Check");
proc print data=&OUTLIB..&OUT_PREFIX._DATA_CHECK noobs;
run;

title "BCEF Flood x LGD - Correlations with observed LGD";
ods excel options(sheet_name="02_Correlations");
proc print data=&OUTLIB..&OUT_PREFIX._CORR_ALL noobs;
run;

title "BCEF Flood x LGD - Signal table by exposure definition";
ods excel options(sheet_name="03_Signal");
proc print data=&OUTLIB..&OUT_PREFIX._SIGNAL_ALL noobs;
run;

title "BCEF Flood x LGD - Main exposed vs non-exposed summary";
ods excel options(sheet_name="04_Main_Summary");
proc print data=&OUTLIB..&OUT_PREFIX._SUMMARY_ALL noobs;
    where EXPOSURE_DEFINITION = "&MAIN_FLAG";
run;

title "BCEF Flood x LGD - Main LGD grade distribution";
ods excel options(sheet_name="05_Main_Grades");
proc print data=&OUTLIB..&OUT_PREFIX._GRADE_DIST_ALL noobs;
    where EXPOSURE_DEFINITION = "&MAIN_FLAG";
run;

title "BCEF Flood x LGD - Recovery dynamics (main exposure flag)";
ods excel options(sheet_name="06_Recovery");
proc print data=&OUTLIB..&OUT_PREFIX._RECOVERY_ALL noobs;
    where EXPOSURE_DEFINITION = "&MAIN_FLAG";
run;

title "BCEF Flood x LGD - All exposure definitions summary";
ods excel options(sheet_name="07_All_Flags");
proc print data=&OUTLIB..&OUT_PREFIX._SUMMARY_ALL noobs;
run;

ods excel close;
title;
