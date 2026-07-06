/*===========================================================================

  ACCLIM - BCEF - Standalone Flood x LGD Category 1 analysis

  WHAT THIS SCRIPT DOES
    1. Imports the two BCEF flood CSV files (establishments + collaterals)
    2. Rebuilds the address-level flood table
    3. Rebuilds the session-level LGD flood aggregation
    4. Runs the Category 1 descriptive analysis:
         - Exposed vs Non-Exposed
         - realised LGD
         - estimated LGD
         - LGD grade distribution
         - IG / NIG shares
         - recovery dynamics
         - correlation between flood indicators and observed LGD

  NOTE
    - This is a new standalone script. It does not modify the existing
      colleague scripts.
    - The original upstream logic is preserved, including:
        * the point_id = '191722' deletion
        * both FLOOD_INT_CUM_DEF_V1 and FLOOD_INT_CUM_DEF_V2
    - The reporting view below defaults to FLOOD_INT_CUM_DEF_V1 so the
      script does not impose a change on the colleague workflow.

===========================================================================*/

options mprint mlogic symbolgen;

/*---------------------------------------------------------------------------
  0. Libraries and parameters
---------------------------------------------------------------------------*/

libname INPUT  "/applis/25182-pumpp/data/car/backtesting/21_TRANSVERSAL/02 - ACCLIM/05 - Phase II/03 - Flood Indicators/00 - Input";
libname OUTPUT "/applis/25182-pumpp/data/car/backtesting/21_TRANSVERSAL/02 - ACCLIM/05 - Phase II/03 - Flood Indicators/01 - Outputs";
libname LGDSRC "/applis/25182-pumpp/data/car/backtesting/21_TRANSVERSAL/02 - ACCLIM/05 - Phase II/01 - Use Case Pilote - Flood - BCeF/01 - Outputs";

/* Import / aggregation parameters */
%let LIBIN      = INPUT;
%let LIBOUT     = OUTPUT;

%let CSV_ETAB   = /applis/25182-pumpp/data/car/backtesting/21_TRANSVERSAL/02 - ACCLIM/05 - Phase II/03 - Flood Indicators/00 - Input/T20_BCeF_Geolocalisation_FLOOD_LGD_with_default_date.csv;
%let CSV_COLL   = /applis/25182-pumpp/data/car/backtesting/21_TRANSVERSAL/02 - ACCLIM/05 - Phase II/03 - Flood Indicators/00 - Input/T20_BCEF_GEOLOC_COLLAT_FLOOD_LGD.csv;

%let ETAB       = T20_ADR_ETAB;
%let COLL       = T20_ADR_COLLAT;
%let ADR        = T20_LGD_ADR_FLOOD_BCEF;
%let LGD        = T20_LGD_BCEF;

%let OUT_ROOT   = T20_LGD_FLOOD_BCEF;
%let KEY        = SESSION_KEY;
%let DT_ENTRY   = DEFAULT_DATE;
%let DT_CLOSE   = CLOSED_DEFAULT_DATE;

%let ZONE       = _AREA;
%let DEPTHSTAT  = MOY;

%let FLOODVAR   = FLAG_FLOOD_ADR&ZONE.;
%let DEPTH      = FLOOD_DEPTH_&DEPTHSTAT.&ZONE.;
%let OUT        = &OUT_ROOT.&ZONE.;

%let H          = 24;
%let W          = 36;
%let HC         = 48;
%let CUTOFF_JRC = '01JAN2015'd;
%let DT_CUT_OFF = '31DEC2024'd;

/* Category 1 reporting parameters */
%let ANALYSIS_DS      = &LIBOUT..&OUT;
%let OUT_PREFIX       = CAT1_BCEF_FLOOD_LGD;
%let MAIN_FLAG        = FLAG_FLOOD_AREA_DEF;
%let REPORT_EST_VAR   = EST_LGD_LATEST;
%let REPORT_GRADE_VAR = LGD_GRADE_LATEST;
%let REPORT_CUM_VAR   = FLOOD_INT_CUM_DEF_V1;
%let IG_MAX_GRADE     = 10;

%let XLSX_OUT         = /applis/25182-pumpp/data/car/backtesting/21_TRANSVERSAL/02 - ACCLIM/05 - Phase II/03 - Flood Indicators/01 - Outputs/CATEGORY1_BCEF_FLOOD_LGD_STANDALONE.xlsx;

%let FLAG_LIST =
    FLAG_FLOOD_AREA_DEF
    FLAG_FLOOD_DEF
    FLAG_JRC_ANY_DEF
    FLAG_GASPAR_ANY_DEF
    FLAG_HANZE_ANY_DEF
    FLAG_FLOOD_COLL_DEF
;

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

/*---------------------------------------------------------------------------
  1. Import helper macro for the two flood CSV files
---------------------------------------------------------------------------*/

%macro import_flood_csv(csv=, out=, adr_type=, clean_name=);

    filename adrcsv "&csv.";
    filename adrclean "%sysfunc(pathname(work))/&clean_name..csv";

    data _null_;
        length _l $32767;
        infile adrcsv lrecl=32767 truncover;
        file   adrclean lrecl=32767;
        input;
        _l = _infile_;
        _n = length(_l);
        if _n >= 2 and char(_l,1) = '"' and char(_l,_n) = '"' then do;
            _l = substr(_l, 2, _n-2);
            _l = tranwrd(_l, '""', '"');
        end;
        put _l;
    run;

    data &out;
        infile adrclean dsd dlm=';' firstobs=2 truncover lrecl=32767;
        input
            point_id               : $20.
            Obligor_ID             : $80.
            Facility_ID            : $80.
            CLOSED_DEFAULT_DATE    : yymmdd10.
            DEFAULT_DATE           : yymmdd10.
            ID_ADR                 : $40.
            TYPE_ADR               : $20.
            Flag_JRC               : 8.
            Flag_GASPAR            : 8.
            Flag_HANZE             : 8.
            FLOOD_DATA_SOURCE      : $8.
            Flag_JRC_AREA          : 8.
            Flag_GASPAR_AREA       : 8.
            Flag_HANZE_AREA        : 8.
            FLOOD_DATA_SOURCE_AREA : $8.
            FLAG_FLOOD_ADR         : 8.
            FLAG_FLOOD_ADR_AREA    : 8.
            DATE_REF_FLOOD         : yymmdd10.
            DATE_END_FLOOD         : yymmdd10.
            FLOOD_DEPTH_MOY        : 12.
            FLOOD_DEPTH_MOY_AREA   : 12.
            FLOOD_DEPTH_MAX        : 12.
            FLOOD_DEPTH_MAX_AREA   : 12.
        ;

        format CLOSED_DEFAULT_DATE DEFAULT_DATE DATE_REF_FLOOD DATE_END_FLOOD ddmmyy10.;

        ID_ADR = compress(ID_ADR, '"');
        if ID_ADR ne '' then TYPE_ADR = "&adr_type";
        else TYPE_ADR = '';
    run;

    filename adrcsv clear;
    filename adrclean clear;

%mend;

/*---------------------------------------------------------------------------
  2. Import BCEF establishments and collaterals
---------------------------------------------------------------------------*/

%import_flood_csv(
    csv=&CSV_ETAB,
    out=&ETAB,
    adr_type=ETABLISSEMENT,
    clean_name=adr_clean_etab
);

%import_flood_csv(
    csv=&CSV_COLL,
    out=&COLL,
    adr_type=COLLATERAL,
    clean_name=adr_clean_coll
);

data &LIBIN..&ADR;
    set &ETAB &COLL;
run;

/*---------------------------------------------------------------------------
  3. Original data quality handling preserved from colleague script
---------------------------------------------------------------------------*/

proc sql;
    create table &LIBOUT..STAT_FLOOD_RECOV as
    select
        TYPE_ADR,
        count(point_id)            as TOT_ADR,
        count(ID_ADR)              as ADR_GEOLOC,
        sum(FLAG_FLOOD_ADR)        as NB_ADR_FLOOD,
        sum(FLAG_FLOOD_ADR_AREA)   as NB_ADR_FLOOD_AREA
    from &LIBIN..&ADR
    group by TYPE_ADR
    ;
quit;

data &LIBIN..&ADR;
    set &LIBIN..&ADR;
    if point_id = '191722' then delete;
run;

/*---------------------------------------------------------------------------
  4. Rebuild the session-level LGD base and join key
---------------------------------------------------------------------------*/

data &LIBIN..&LGD;
    set LGDSRC.t20_manal;
    length SESSION_KEY $40;
    SESSION_KEY = catx("_", Facility_ID, put(DEFAULT_DATE, yymmddn8.));
run;

data &LIBIN..&ADR;
    set &LIBIN..&ADR;
    length SESSION_KEY $40;
    SESSION_KEY = catx("_", Facility_ID, put(DEFAULT_DATE, yymmddn8.));
run;

/*---------------------------------------------------------------------------
  5. Original session aggregation logic
---------------------------------------------------------------------------*/

data ADR_EVT;
    set &LIBIN..&ADR;

    bH  = intnx('month', &DT_ENTRY, -&H , 'same');
    bW  = intnx('month', &DT_ENTRY, -&W , 'same');
    b12 = intnx('month', &DT_ENTRY, -12 , 'same');
    b24 = intnx('month', &DT_ENTRY, -24 , 'same');
    b36 = intnx('month', &DT_ENTRY, -36 , 'same');
    bhc = intnx('month', &DT_ENTRY, -&HC, 'same');

    _DT_CLOSE = coalesce(&DT_CLOSE, &DT_CUT_OFF);
    fld  = (&FLOODVAR = 1 and not missing(DATE_REF_FLOOD));
    flda = (FLAG_FLOOD_ADR_AREA = 1 and not missing(DATE_REF_FLOOD));
    coll = (upcase(strip(TYPE_ADR)) = 'COLLATERAL');

    in_def   = (fld and &DT_ENTRY <= DATE_REF_FLOOD <= _DT_CLOSE);
    in_preH  = (fld and bH  <= DATE_REF_FLOOD < &DT_ENTRY);
    in_pre12 = (fld and b12 <= DATE_REF_FLOOD < &DT_ENTRY);
    in_pre24 = (fld and b24 <= DATE_REF_FLOOD < &DT_ENTRY);
    in_preW  = (fld and bW  <= DATE_REF_FLOOD < &DT_ENTRY);
    in_preA  = (fld and DATE_REF_FLOOD < &DT_ENTRY);

    ar_def = (flda and &DT_ENTRY <= DATE_REF_FLOOD <= _DT_CLOSE);

    c_def   = (coll and in_def);
    c_pre24 = (coll and fld and b24 <= DATE_REF_FLOOD < &DT_ENTRY);
    c_pre36 = (coll and fld and b36 <= DATE_REF_FLOOD < &DT_ENTRY);
    c_pre48 = (coll and fld and bhc <= DATE_REF_FLOOD < &DT_ENTRY);
    c_win   = (c_def or c_pre48);

    if in_def  then dep_def  = &DEPTH; else dep_def  = .;
    if in_preH then dep_preH = &DEPTH; else dep_preH = .;
    if c_win   then dep_coll = &DEPTH; else dep_coll = .;

    jrc_def = (Flag_JRC&ZONE.    = 1 and &DT_ENTRY <= DATE_REF_FLOOD <= _DT_CLOSE);
    jrc_pre = (Flag_JRC&ZONE.    = 1 and bH <= DATE_REF_FLOOD < &DT_ENTRY);
    gas_def = (Flag_GASPAR&ZONE. = 1 and &DT_ENTRY <= DATE_REF_FLOOD <= _DT_CLOSE);
    gas_pre = (Flag_GASPAR&ZONE. = 1 and bH <= DATE_REF_FLOOD < &DT_ENTRY);
    han_def = (Flag_HANZE&ZONE.  = 1 and &DT_ENTRY <= DATE_REF_FLOOD <= _DT_CLOSE);
    han_pre = (Flag_HANZE&ZONE.  = 1 and bH <= DATE_REF_FLOOD < &DT_ENTRY);

    if in_def  then d_def  = DATE_REF_FLOOD; else d_def  = .;
    if in_preH then d_preH = DATE_REF_FLOOD; else d_preH = .;
    if in_preA then d_preA = DATE_REF_FLOOD; else d_preA = .;
    if c_def   then d_cdef = DATE_REF_FLOOD; else d_cdef = .;
    if (coll and fld and bhc <= DATE_REF_FLOOD < &DT_ENTRY) then d_cpre = DATE_REF_FLOOD;
    else d_cpre = .;
run;

proc sql;
    create table EVT_DEF as
    select
        &KEY,
        DATE_REF_FLOOD,
        max(dep_def) as DEP_EVT
    from ADR_EVT
    where in_def = 1
    group by &KEY, DATE_REF_FLOOD
    ;
quit;

proc sql;
    create table CUM_V2 as
    select
        &KEY,
        sum(DEP_EVT) as FLOOD_INT_CUM_DEF_V2
    from EVT_DEF
    group by &KEY
    ;
quit;

proc sql;
    create table AGG as
    select
        &KEY,
        min(&DT_ENTRY)                                            as ENTRY_AGG format=ddmmyy10.,
        count(distinct ID_ADR)                                    as NB_ADR,
        count(distinct case when coll then ID_ADR end)            as NB_ADR_COLL,
        max(in_def)                                               as FLAG_FLOOD_DEF,
        max(in_pre12)                                             as FLAG_FLOOD_PRE12,
        max(in_pre24)                                             as FLAG_FLOOD_PRE24,
        max(ar_def)                                               as FLAG_FLOOD_AREA_DEF,
        max(in_preH)                                              as FLAG_FLOOD_PRE_&H.,
        max(in_preW)                                              as FLAG_FLOOD_PRE_W,
        count(distinct case when in_def  then DATE_REF_FLOOD end) as NB_FLOOD_DEF,
        count(distinct case when in_preH then DATE_REF_FLOOD end) as NB_FLOOD_PRE&H.,
        max(dep_def)                                              as FLOOD_INT_MAX_DEF,
        max(dep_preH)                                             as FLOOD_INT_MAX_PRE&H.,
        sum(dep_def)                                              as FLOOD_INT_CUM_DEF_V1,
        min(d_def)                                                as MIN_DEF_DATE format=ddmmyy10.,
        min(d_preH)                                               as MIN_PREH_DATE format=ddmmyy10.,
        max(d_preA)                                               as DATE_LAST_FLOOD_PRE format=ddmmyy10.,
        min(d_cdef)                                               as MIN_CDEF_DATE format=ddmmyy10.,
        min(d_cpre)                                               as MIN_CPRE_DATE format=ddmmyy10.,
        max(c_def)                                                as FLAG_FLOOD_COLL_DEF,
        max(c_pre24)                                              as FLAG_FLOOD_COLL_PRE24,
        max(c_pre36)                                              as FLAG_FLOOD_COLL_PRE36,
        max(c_pre48)                                              as FLAG_FLOOD_COLL_PRE48,
        count(distinct case when c_win then ID_ADR end)           as N_COLL_FLOODED,
        max(dep_coll)                                             as FLOOD_INT_MAX_COLL,
        max(jrc_def)                                              as FLAG_JRC_ANY_DEF,
        max(jrc_pre)                                              as FLAG_JRC_ANY_PRE&H.,
        max(gas_def)                                              as FLAG_GASPAR_ANY_DEF,
        max(gas_pre)                                              as FLAG_GASPAR_ANY_PRE&H.,
        max(han_def)                                              as FLAG_HANZE_ANY_DEF,
        max(han_pre)                                              as FLAG_HANZE_ANY_PRE&H.
    from ADR_EVT
    group by &KEY
    ;
quit;

proc sql;
    create table AGG2 as
    select
        a.*,
        c.FLOOD_INT_CUM_DEF_V2
    from AGG a
    left join CUM_V2 c
        on a.&KEY = c.&KEY
    ;
quit;

data AGG2;
    set AGG2;

    DATE_REF_FLOOD      = coalesce(MIN_DEF_DATE, MIN_PREH_DATE);
    DATE_REF_FLOOD_COLL = coalesce(MIN_CDEF_DATE, MIN_CPRE_DATE);

    if not missing(DATE_LAST_FLOOD_PRE) then
        N_M_LAST_PRE_FLOOD = intck('month', DATE_LAST_FLOOD_PRE, ENTRY_AGG, 'C');

    if NB_ADR_COLL > 0 then RATIO_COLL_FLOODED = N_COLL_FLOODED / NB_ADR_COLL;
run;

proc sql;
    create table T0_SRC as
    select
        e.&KEY,
        e.FLOOD_DATA_SOURCE&ZONE.,
        case upcase(strip(e.FLOOD_DATA_SOURCE&ZONE.))
            when 'JRC'    then 1
            when 'GASPAR' then 2
            when 'HANZE'  then 3
            else 999
        end as RK
    from ADR_EVT e, AGG2 a
    where e.&KEY = a.&KEY
      and not missing(a.DATE_REF_FLOOD)
      and e.DATE_REF_FLOOD = a.DATE_REF_FLOOD
      and e.&FLOODVAR = 1
    ;
quit;

proc sort data=T0_SRC;
    by &KEY RK;
run;

data T0_SRC2(keep=&KEY SOURCE_REF_FLOOD);
    set T0_SRC;
    by &KEY RK;
    if first.&KEY;
    length SOURCE_REF_FLOOD $8;
    SOURCE_REF_FLOOD = FLOOD_DATA_SOURCE&ZONE.;
run;

proc sql;
    create table AGG3 as
    select
        a.*,
        s.SOURCE_REF_FLOOD
    from AGG2 a
    left join T0_SRC2 s
        on a.&KEY = s.&KEY
    ;
quit;

proc sort data=AGG3;
    by &KEY;
run;

proc sort data=&LIBIN..&LGD out=LGD_S;
    by &KEY;
run;

data &LIBOUT..&OUT;
    merge
        LGD_S(in=inL)
        AGG3(in=inA drop=ENTRY_AGG MIN_DEF_DATE MIN_PREH_DATE MIN_CDEF_DATE MIN_CPRE_DATE)
    ;
    by &KEY;
    if inL;

    array _z
        FLAG_FLOOD_DEF
        FLAG_FLOOD_PRE12
        FLAG_FLOOD_PRE24
        FLAG_FLOOD_AREA_DEF
        FLAG_FLOOD_PRE_&H.
        FLAG_FLOOD_PRE_W
        NB_ADR
        NB_ADR_COLL
        NB_FLOOD_DEF
        NB_FLOOD_PRE&H.
        N_COLL_FLOODED
        FLAG_FLOOD_COLL_DEF
        FLAG_FLOOD_COLL_PRE24
        FLAG_FLOOD_COLL_PRE36
        FLAG_FLOOD_COLL_PRE48
        FLAG_JRC_ANY_DEF
        FLAG_JRC_ANY_PRE&H.
        FLAG_GASPAR_ANY_DEF
        FLAG_GASPAR_ANY_PRE&H.
        FLAG_HANZE_ANY_DEF
        FLAG_HANZE_ANY_PRE&H.
    ;

    do _i = 1 to dim(_z);
        if missing(_z[_i]) then _z[_i] = 0;
    end;

    FLAG_COLLATERAL = (NB_ADR_COLL > 0);

    length POSITION_FLOOD $11;
    if      FLAG_FLOOD_PRE_&H. = 1 and FLAG_FLOOD_DEF = 1 then POSITION_FLOOD = 'BOTH';
    else if FLAG_FLOOD_DEF = 1                               then POSITION_FLOOD = 'DURING_ONLY';
    else if FLAG_FLOOD_PRE_&H. = 1                           then POSITION_FLOOD = 'PRE_ONLY';
    else                                                          POSITION_FLOOD = 'NONE';

    length EXPO_GROUP $21;
    if      FLAG_FLOOD_DEF = 1 or FLAG_FLOOD_PRE_&H. = 1 then EXPO_GROUP = 'EXPOSED';
    else if FLAG_FLOOD_PRE_W = 1                          then EXPO_GROUP = 'INTERMEDIATE EXPOSURE';
    else                                                       EXPO_GROUP = 'NON-EXPOSED';

    FLAG_COMPL_FLOOD_SOURCES_AT_DEF = (&DT_ENTRY >= &CUTOFF_JRC);
    FLAG_COMPL_FLOOD_SOURCES_PRE_&H = (intnx('month', &DT_ENTRY, -&H, 'same') >= &CUTOFF_JRC);

    format DATE_REF_FLOOD DATE_REF_FLOOD_COLL DATE_LAST_FLOOD_PRE ddmmyy10.;
    drop FLAG_FLOOD_PRE_W _i;
run;

/*---------------------------------------------------------------------------
  6. Build the analysis-ready Category 1 base
---------------------------------------------------------------------------*/

data work.cat1_bcef_base;
    set &ANALYSIS_DS;

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

    OBS_LGD_FINAL = coalesce(
        Additional_Realised_LGD,
        Realised_LGD_06,
        Realised_LGD_05,
        Realised_LGD_04,
        Realised_LGD_03,
        Realised_LGD_02,
        Realised_LGD_01
    );

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

data &LIBOUT..&OUT_PREFIX._BASE;
    set work.cat1_bcef_base;
run;

/*---------------------------------------------------------------------------
  7. Category 1 data check
---------------------------------------------------------------------------*/

proc sql;
    create table &LIBOUT..&OUT_PREFIX._DATA_CHECK as
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
  8. Correlations with observed LGD
---------------------------------------------------------------------------*/

proc corr data=work.cat1_bcef_base pearson nosimple noprint outp=work._corr_p_raw;
    var &CORR_VARS;
    with OBS_LGD_FINAL;
run;

proc corr data=work.cat1_bcef_base spearman nosimple noprint outp=work._corr_s_raw;
    var &CORR_VARS;
    with OBS_LGD_FINAL;
run;

data &LIBOUT..&OUT_PREFIX._CORR_PEARSON;
    length CORR_TYPE $8 INDICATOR $40;
    set work._corr_p_raw;
    where _TYPE_ = "CORR";
    CORR_TYPE = "PEARSON";
    INDICATOR = _NAME_;
    CORR_WITH_OBS_LGD = OBS_LGD_FINAL;
    keep CORR_TYPE INDICATOR CORR_WITH_OBS_LGD;
run;

data &LIBOUT..&OUT_PREFIX._CORR_SPEARMAN;
    length CORR_TYPE $8 INDICATOR $40;
    set work._corr_s_raw;
    where _TYPE_ = "CORR";
    CORR_TYPE = "SPEARMAN";
    INDICATOR = _NAME_;
    CORR_WITH_OBS_LGD = OBS_LGD_FINAL;
    keep CORR_TYPE INDICATOR CORR_WITH_OBS_LGD;
run;

data &LIBOUT..&OUT_PREFIX._CORR_ALL;
    set
        &LIBOUT..&OUT_PREFIX._CORR_PEARSON
        &LIBOUT..&OUT_PREFIX._CORR_SPEARMAN
    ;
run;

/*---------------------------------------------------------------------------
  9. Additional descriptive tables and statistical tests
---------------------------------------------------------------------------*/

data &LIBOUT..&OUT_PREFIX._INDICATOR_PREVALENCE;
    set work.cat1_bcef_base end=last;

    retain N_TOTAL 0 CNT1-CNT6 0;
    array FLAG_ARR[6]
        FLAG_FLOOD_AREA_DEF
        FLAG_FLOOD_DEF
        FLAG_JRC_ANY_DEF
        FLAG_GASPAR_ANY_DEF
        FLAG_HANZE_ANY_DEF
        FLAG_FLOOD_COLL_DEF
    ;
    array CNT_ARR[6] CNT1-CNT6;
    array NM_ARR[6] $40 _temporary_
        (
            "FLAG_FLOOD_AREA_DEF",
            "FLAG_FLOOD_DEF",
            "FLAG_JRC_ANY_DEF",
            "FLAG_GASPAR_ANY_DEF",
            "FLAG_HANZE_ANY_DEF",
            "FLAG_FLOOD_COLL_DEF"
        )
    ;

    N_TOTAL + 1;
    do _j = 1 to dim(FLAG_ARR);
        if FLAG_ARR[_j] = 1 then CNT_ARR[_j] + 1;
    end;

    if last then do;
        do _j = 1 to dim(FLAG_ARR);
            INDICATOR  = NM_ARR[_j];
            N_EXPOSED  = CNT_ARR[_j];
            PCT_EXPOSED = N_EXPOSED / N_TOTAL;
            output;
        end;
    end;

    keep INDICATOR N_TOTAL N_EXPOSED PCT_EXPOSED;
    format PCT_EXPOSED percent8.2;
run;

data &LIBOUT..&OUT_PREFIX._MISSINGNESS;
    set work.cat1_bcef_base end=last;

    retain N_TOTAL 0 MIS1-MIS8 0 NON1-NON8 0;
    array VAR_ARR[8]
        OBS_LGD_FINAL
        &REPORT_EST_VAR
        &REPORT_CUM_VAR
        FLOOD_INT_CUM_DEF_V2
        FLOOD_INT_MAX_DEF
        NB_FLOOD_DEF
        N_M_LAST_PRE_FLOOD
        RATIO_COLL_FLOODED
    ;
    array MIS_ARR[8] MIS1-MIS8;
    array NON_ARR[8] NON1-NON8;
    array VAR_NM[8] $40 _temporary_
        (
            "OBS_LGD_FINAL",
            "&REPORT_EST_VAR",
            "&REPORT_CUM_VAR",
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

proc freq data=work.cat1_bcef_base noprint;
    where MAIN_EXPO_GROUP in ("Exposed", "Non-Exposed");
    tables MAIN_EXPO_GROUP / out=&LIBOUT..&OUT_PREFIX._MAIN_GROUP_COUNTS;
    tables MAIN_EXPO_GROUP * RATING_BUCKET / out=&LIBOUT..&OUT_PREFIX._RATING_BUCKET_MAIN outpct;
run;

proc freq data=work.cat1_bcef_base noprint;
    where FLAG_FLOOD_AREA_DEF = 1;
    tables FLAG_JRC_ANY_DEF * FLAG_GASPAR_ANY_DEF * FLAG_HANZE_ANY_DEF
        / out=&LIBOUT..&OUT_PREFIX._SOURCE_OVERLAP_MAIN;
run;

ods exclude all;
ods output Summary=&LIBOUT..&OUT_PREFIX._MAIN_GROUP_STATS;
proc means data=work.cat1_bcef_base stackodsoutput n nmiss mean median std min p25 p75 max;
    where MAIN_EXPO_GROUP in ("Exposed", "Non-Exposed");
    class MAIN_EXPO_GROUP;
    var
        OBS_LGD_FINAL
        &REPORT_EST_VAR
        &REPORT_CUM_VAR
        FLOOD_INT_CUM_DEF_V2
        FLOOD_INT_MAX_DEF
        NB_FLOOD_DEF
        N_M_LAST_PRE_FLOOD
        RATIO_COLL_FLOODED
    ;
run;
ods exclude none;

data work._main_group_stats_f;
    set &LIBOUT..&OUT_PREFIX._MAIN_GROUP_STATS;
    where not missing(MAIN_EXPO_GROUP);
run;

data &LIBOUT..&OUT_PREFIX._MAIN_GROUP_STATS;
    set work._main_group_stats_f;
run;

ods exclude all;
ods output Statistics=&LIBOUT..&OUT_PREFIX._TTEST_STATS
           TTests=&LIBOUT..&OUT_PREFIX._TTEST_TESTS
           Equality=&LIBOUT..&OUT_PREFIX._TTEST_EQUALITY;
proc ttest data=work.cat1_bcef_base;
    where MAIN_EXPO_GROUP in ("Exposed", "Non-Exposed");
    class MAIN_EXPO_GROUP;
    var OBS_LGD_FINAL &REPORT_EST_VAR &REPORT_CUM_VAR;
run;
ods exclude none;

ods exclude all;
ods output WilcoxonTest=&LIBOUT..&OUT_PREFIX._WILCOXON_TESTS
           KruskalWallisTest=&LIBOUT..&OUT_PREFIX._KRUSKAL_TESTS;
proc npar1way data=work.cat1_bcef_base wilcoxon;
    where MAIN_EXPO_GROUP in ("Exposed", "Non-Exposed");
    class MAIN_EXPO_GROUP;
    var OBS_LGD_FINAL &REPORT_EST_VAR &REPORT_CUM_VAR;
run;
ods exclude none;

ods exclude all;
ods output ChiSq=&LIBOUT..&OUT_PREFIX._RATING_CHISQ
           CrossTabFreqs=&LIBOUT..&OUT_PREFIX._RATING_CROSSTAB;
proc freq data=work.cat1_bcef_base;
    where MAIN_EXPO_GROUP in ("Exposed", "Non-Exposed");
    tables MAIN_EXPO_GROUP * RATING_BUCKET / chisq;
run;
ods exclude none;

/*---------------------------------------------------------------------------
  10. Clean existing reporting outputs
---------------------------------------------------------------------------*/

proc datasets library=&LIBOUT nolist;
    delete
        &OUT_PREFIX._SUMMARY_ALL
        &OUT_PREFIX._GRADE_DIST_ALL
        &OUT_PREFIX._RECOVERY_ALL
        &OUT_PREFIX._SIGNAL_ALL
    ;
quit;

/*---------------------------------------------------------------------------
  11. Macro for exposed / non-exposed analysis by flood flag
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

    proc append base=&LIBOUT..&OUT_PREFIX._SUMMARY_ALL data=work._summary force;
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

    proc append base=&LIBOUT..&OUT_PREFIX._GRADE_DIST_ALL data=work._grade force;
    run;

    data work._recovery_long;
        set work._seg;
        length METRIC $12;
        array _real[6] Realised_LGD_01-Realised_LGD_06;
        array _est [7] LGD_Estimate_01-LGD_Estimate_07;

        do STAGE = 1 to dim(_real);
            METRIC = "REALISED";
            VALUE = _real[STAGE];
            if not missing(VALUE) then output;
        end;

        do STAGE = 1 to dim(_est);
            METRIC = "ESTIMATED";
            VALUE = _est[STAGE];
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

    proc append base=&LIBOUT..&OUT_PREFIX._RECOVERY_ALL data=work._recovery force;
    run;

    proc sql;
        create table work._signal as
        select
            "&flag" as EXPOSURE_DEFINITION length=40,
            max(case when EXPOSED_GROUP = "Exposed"     then AVG_REALISED_LGD    end) as EXPOSED_AVG_REALISED_LGD format=12.4,
            max(case when EXPOSED_GROUP = "Non-Exposed" then AVG_REALISED_LGD    end) as NONEXP_AVG_REALISED_LGD format=12.4,
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

    proc append base=&LIBOUT..&OUT_PREFIX._SIGNAL_ALL data=work._signal force;
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

proc sort data=&LIBOUT..&OUT_PREFIX._SUMMARY_ALL;
    by EXPOSURE_DEFINITION EXPOSED_GROUP;
run;

proc sort data=&LIBOUT..&OUT_PREFIX._GRADE_DIST_ALL;
    by EXPOSURE_DEFINITION EXPOSED_GROUP descending COUNT;
run;

proc sort data=&LIBOUT..&OUT_PREFIX._RECOVERY_ALL;
    by EXPOSURE_DEFINITION METRIC STAGE EXPOSED_GROUP;
run;

proc sort data=&LIBOUT..&OUT_PREFIX._SIGNAL_ALL;
    by EXPOSURE_DEFINITION;
run;

/*---------------------------------------------------------------------------
  12. Excel export with tables and plots
---------------------------------------------------------------------------*/

ods graphics on / reset width=8.5in height=5in imagename="bcef_flood_lgd";
ods excel file="&XLSX_OUT"
    options(
        embedded_titles="yes"
        frozen_headers="yes"
        sheet_interval="none"
        autofilter="all"
    );

title "BCEF Flood x LGD - Data check";
ods excel options(sheet_name="01_Data_Check");
proc print data=&LIBOUT..&OUT_PREFIX._DATA_CHECK noobs;
run;

title "BCEF Flood x LGD - Flood indicator prevalence";
ods excel options(sheet_name="02_Indicator_Rates");
proc print data=&LIBOUT..&OUT_PREFIX._INDICATOR_PREVALENCE noobs;
run;

title "BCEF Flood x LGD - Key variable missingness";
ods excel options(sheet_name="03_Missingness");
proc print data=&LIBOUT..&OUT_PREFIX._MISSINGNESS noobs;
run;

title "BCEF Flood x LGD - Correlations with observed LGD";
ods excel options(sheet_name="04_Correlations");
proc print data=&LIBOUT..&OUT_PREFIX._CORR_ALL noobs;
run;

title "BCEF Flood x LGD - Main group descriptive statistics";
ods excel options(sheet_name="05_Main_Stats");
proc print data=&LIBOUT..&OUT_PREFIX._MAIN_GROUP_STATS noobs;
run;

title "BCEF Flood x LGD - T test statistics";
ods excel options(sheet_name="06_TTest_Stats");
proc print data=&LIBOUT..&OUT_PREFIX._TTEST_STATS noobs;
run;

title "BCEF Flood x LGD - T test results";
ods excel options(sheet_name="07_TTest_Results");
proc print data=&LIBOUT..&OUT_PREFIX._TTEST_TESTS noobs;
run;

title "BCEF Flood x LGD - Wilcoxon tests";
ods excel options(sheet_name="08_Wilcoxon");
proc print data=&LIBOUT..&OUT_PREFIX._WILCOXON_TESTS noobs;
run;

title "BCEF Flood x LGD - Rating bucket chi-square";
ods excel options(sheet_name="09_Rating_ChiSq");
proc print data=&LIBOUT..&OUT_PREFIX._RATING_CHISQ noobs;
run;

title "BCEF Flood x LGD - Rating bucket cross tab";
ods excel options(sheet_name="10_Rating_Crosstab");
proc print data=&LIBOUT..&OUT_PREFIX._RATING_CROSSTAB noobs;
run;

title "BCEF Flood x LGD - Source overlap among exposed sessions";
ods excel options(sheet_name="11_Source_Overlap");
proc print data=&LIBOUT..&OUT_PREFIX._SOURCE_OVERLAP_MAIN noobs;
run;

title "BCEF Flood x LGD - Signal table by exposure definition";
ods excel options(sheet_name="12_Signal");
proc print data=&LIBOUT..&OUT_PREFIX._SIGNAL_ALL noobs;
run;

title "BCEF Flood x LGD - Main exposed vs non-exposed summary";
ods excel options(sheet_name="13_Main_Summary");
proc print data=&LIBOUT..&OUT_PREFIX._SUMMARY_ALL noobs;
    where EXPOSURE_DEFINITION = "&MAIN_FLAG";
run;

title "BCEF Flood x LGD - Main rating bucket distribution";
ods excel options(sheet_name="14_Rating_Buckets");
proc print data=&LIBOUT..&OUT_PREFIX._RATING_BUCKET_MAIN noobs;
run;

title "BCEF Flood x LGD - Main LGD grade distribution";
ods excel options(sheet_name="15_Main_Grades");
proc print data=&LIBOUT..&OUT_PREFIX._GRADE_DIST_ALL noobs;
    where EXPOSURE_DEFINITION = "&MAIN_FLAG";
run;

title "BCEF Flood x LGD - Recovery dynamics (main exposure flag)";
ods excel options(sheet_name="16_Recovery_Table");
proc print data=&LIBOUT..&OUT_PREFIX._RECOVERY_ALL noobs;
    where EXPOSURE_DEFINITION = "&MAIN_FLAG";
run;

title "BCEF Flood x LGD - All exposure definitions summary";
ods excel options(sheet_name="17_All_Flags");
proc print data=&LIBOUT..&OUT_PREFIX._SUMMARY_ALL noobs;
run;

title "BCEF Flood x LGD - Session count by main exposure group";
ods excel options(sheet_name="18_Counts_Plot");
proc sgplot data=&LIBOUT..&OUT_PREFIX._MAIN_GROUP_COUNTS;
    vbarparm category=MAIN_EXPO_GROUP response=COUNT / datalabel;
    xaxis label="Main exposure group";
    yaxis label="Number of sessions";
run;

title "BCEF Flood x LGD - Observed LGD by main exposure group";
ods excel options(sheet_name="19_Obs_Box");
proc sgplot data=work.cat1_bcef_base;
    where MAIN_EXPO_GROUP in ("Exposed", "Non-Exposed") and not missing(OBS_LGD_FINAL);
    vbox OBS_LGD_FINAL / category=MAIN_EXPO_GROUP;
    xaxis label="Main exposure group";
    yaxis label="Observed LGD";
run;

title "BCEF Flood x LGD - Estimated LGD by main exposure group";
ods excel options(sheet_name="20_Est_Box");
proc sgplot data=work.cat1_bcef_base;
    where MAIN_EXPO_GROUP in ("Exposed", "Non-Exposed") and not missing(&REPORT_EST_VAR);
    vbox &REPORT_EST_VAR / category=MAIN_EXPO_GROUP;
    xaxis label="Main exposure group";
    yaxis label="Estimated LGD";
run;

title "BCEF Flood x LGD - Observed LGD distribution";
ods excel options(sheet_name="21_Obs_Hist");
proc sgplot data=work.cat1_bcef_base;
    where MAIN_EXPO_GROUP in ("Exposed", "Non-Exposed") and not missing(OBS_LGD_FINAL);
    histogram OBS_LGD_FINAL / group=MAIN_EXPO_GROUP transparency=0.45;
    density OBS_LGD_FINAL / group=MAIN_EXPO_GROUP type=kernel;
    xaxis label="Observed LGD";
    yaxis label="Frequency";
run;

title "BCEF Flood x LGD - Estimated LGD distribution";
ods excel options(sheet_name="22_Est_Hist");
proc sgplot data=work.cat1_bcef_base;
    where MAIN_EXPO_GROUP in ("Exposed", "Non-Exposed") and not missing(&REPORT_EST_VAR);
    histogram &REPORT_EST_VAR / group=MAIN_EXPO_GROUP transparency=0.45;
    density &REPORT_EST_VAR / group=MAIN_EXPO_GROUP type=kernel;
    xaxis label="Estimated LGD";
    yaxis label="Frequency";
run;

title "BCEF Flood x LGD - Flood intensity vs observed LGD";
ods excel options(sheet_name="23_Intensity_Scatter");
proc sgplot data=work.cat1_bcef_base;
    where MAIN_EXPO_GROUP in ("Exposed", "Non-Exposed")
      and not missing(&REPORT_CUM_VAR)
      and not missing(OBS_LGD_FINAL);
    scatter x=&REPORT_CUM_VAR y=OBS_LGD_FINAL / group=MAIN_EXPO_GROUP transparency=0.35;
    reg x=&REPORT_CUM_VAR y=OBS_LGD_FINAL / group=MAIN_EXPO_GROUP nomarkers;
    xaxis label="Flood cumulative intensity";
    yaxis label="Observed LGD";
run;

title "BCEF Flood x LGD - Rating bucket composition by group";
ods excel options(sheet_name="24_Rating_Bars");
proc sgplot data=&LIBOUT..&OUT_PREFIX._RATING_BUCKET_MAIN;
    vbarparm category=MAIN_EXPO_GROUP response=COUNT / group=RATING_BUCKET groupdisplay=stack seglabel;
    xaxis label="Main exposure group";
    yaxis label="Number of sessions";
run;

title "BCEF Flood x LGD - Recovery dynamics";
ods excel options(sheet_name="25_Recovery_Plot");
proc sgpanel data=&LIBOUT..&OUT_PREFIX._RECOVERY_ALL;
    where EXPOSURE_DEFINITION = "&MAIN_FLAG";
    panelby METRIC / columns=2 novarname;
    series x=STAGE y=MEAN_VALUE / group=EXPOSED_GROUP markers lineattrs=(thickness=2);
    series x=STAGE y=MEDIAN_VALUE / group=EXPOSED_GROUP markers lineattrs=(pattern=shortdash thickness=2);
    colaxis integer label="Recovery stage";
    rowaxis label="LGD";
run;

ods graphics off;
ods excel close;
title;
