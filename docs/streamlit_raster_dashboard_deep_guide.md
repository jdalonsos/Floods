# Deep Guide: How The Streamlit Raster Dashboard Displays Flood TIFFs

This document explains the full display logic of the Streamlit dashboard in plain language.

It is written for cases where you want to understand:

- what happens after you open `src/app.py`
- how the dashboard finds TIFF files
- how a source raster such as `90,000 x 90,000` becomes a smaller preview such as `1,800 x 1,800`
- what `active preview pixels` means
- what `merged preview polygons` means
- why some rasters can look slightly offshore in raster-overlay mode
- why the recent fix changed `Auto` mode behavior

The main code paths are:

- dashboard UI: `src/app.py`
- shared preview engine: `src/flood_preview.py`

## 1. The Main Idea

The original TIFFs are too large to draw directly in a browser.

So the dashboard does **not** do this:

- read the whole TIFF at full resolution
- send all source pixels to the browser
- draw millions or billions of cells one by one

Instead, the dashboard follows a staged workflow:

1. discover the official TIFF files
2. let you choose one file
3. make a small coarse version of the raster to locate the flood
4. read a second, better preview for display
5. choose one of three rendering strategies
6. show the result on a Folium / Leaflet web map inside Streamlit

So the dashboard is really a **smart preview system**, not a naive raster viewer.

## 2. What Happens When You Open The App

When you run:

```bash
streamlit run src/app.py
```

the app does the following:

1. builds the sidebar controls
2. chooses the raster root directory
3. scans the directory for official JRC TIFF filenames
4. creates the year list
5. lets you filter filenames
6. lets you choose a rendering mode and preview settings
7. opens the chosen TIFF only after you select one

The most important thing is:

- the app does **not** load every TIFF into memory
- it first builds an inventory from filenames
- it opens the selected TIFF only when needed

## 3. File Discovery

The dashboard calls `discover_flood_raster_files()` from `src/flood_preview.py`.

That function:

- walks through the raster directories
- keeps only files whose names match the official JRC naming convention
- extracts metadata directly from the filename

Examples of metadata taken from the filename:

- event start date
- event end date
- duration
- flood cluster id
- area values
- centroid latitude / longitude

This means the app can show a useful browser interface before reading the raster contents.

## 4. What Happens After You Pick One TIFF

After you select a file, the Streamlit app calls `load_preview()` in `src/app.py`.

That cached function then calls:

- `read_flood_preview()` in `src/flood_preview.py`

This is the real preview pipeline.

It has two main technical stages:

1. coarse scan of the whole raster
2. detailed preview read of the detected window

## 5. Stage A: Coarse Scan Of The Whole Raster

The coarse scan happens in `find_source_window()`.

The purpose is simple:

- do a cheap first pass
- find where positive flood pixels exist
- avoid expensive full-resolution work when the event is local

The code computes a scale factor using `coarse_max_size`.

Default:

- `coarse_max_size = 1200`

The logic is:

- take the largest raster dimension
- scale it down so that the biggest side is at most `1200`

### Example: `90,000 x 90,000`

Suppose the raster is:

- height = `90,000`
- width = `90,000`

Then:

- `scale = 1200 / 90000 = 0.013333...`
- coarse height = `90000 * 0.013333... = 1200`
- coarse width = `90000 * 0.013333... = 1200`

So the first pass is not `90,000 x 90,000`.

It is only:

- `1,200 x 1,200`

This is much cheaper to read.

### Why This Works

The coarse scan is **not** trying to make a perfect display image.

It is only trying to answer:

> Where in this huge raster is there any flood signal at all?

So a small overview grid is enough for that first question.

### Resampling In The Coarse Scan

The app uses `Resampling.average` with a masked read.

That means each coarse cell summarizes a block of original source cells.

This is important because:

- nodata stays masked
- positive flood depth can still survive into the preview footprint
- the coarse scan remains useful for locating the flood area

## 6. Stage B: Build The Source Window

After the coarse scan, the app finds the rows and columns that still contain flood.

It then converts those coarse positions back into source-raster coordinates.

That gives a bounding window in the original TIFF.

Then it adds some padding around the detected flood so the preview is not cropped too tightly.

Default:

- `source_padding_pixels = 600`

So the logic is:

- detect flood in the coarse grid
- map that location back to the original raster
- enlarge the box a bit
- use that as the detailed source window

### Two Possible Outcomes

#### Case 1. Small or local flood

If the flood is concentrated in one part of the raster:

- the source window may be much smaller than the full TIFF

Example:

- source raster = `90,000 x 90,000`
- detected flood window = maybe `8,000 x 6,000`

That is good, because the second stage then reads only that smaller part.

#### Case 2. Broad flood footprint

If the flood is spread over a very large area:

- the detected source window can become the whole raster

That is what happened for your example raster.

Your app metrics showed:

- source raster shape: `90,000 x 90,000`
- detailed source window: `90,000 x 90,000`

So the coarse scan did not find a small local box to crop out.

That does **not** mean the algorithm failed.

It simply means:

- the flood footprint was broad enough that the whole raster still mattered

## 7. Stage C: Read The Detailed Preview

After the source window is chosen, the app calls `read_window_preview()`.

This is the step that creates the display preview.

The preview is controlled by:

- `detail_max_size`

Default:

- `detail_max_size = 1800`

The logic is:

- take the source window
- shrink it so the largest side is at most `1800`

### Example: Full Window `90,000 x 90,000`

If the chosen source window is still:

- `90,000 x 90,000`

then:

- `scale = 1800 / 90000 = 0.02`
- output height = `90000 * 0.02 = 1800`
- output width = `90000 * 0.02 = 1800`

So the display preview becomes:

- `1,800 x 1,800`

That is exactly how the app goes from:

- source raster: `90,000 x 90,000`

to:

- display preview: `1,800 x 1,800`

## 8. What One Preview Cell Means

For your raster:

- source width = `90,000`
- preview width = `1,800`

So:

- `90,000 / 1,800 = 50`

That means each preview cell represents about:

- `50 x 50` source cells

In other words:

- one preview cell is a summary of roughly `2,500` original source cells

This is why the preview is fast enough for interactive browsing.

The app is not trying to draw the full scientific raster one cell at a time.

## 9. Why The Preview Does Not Have 3.24 Million Flood Cells

A `1,800 x 1,800` preview contains:

- `3,240,000` total preview cells

But only some of those contain positive flood depth after masking.

The app builds a mask using:

- nodata handling
- the explicit `9999` mask value
- the threshold rule, usually `<= 0 cm`

So many preview cells are discarded because they represent:

- sea
- land with no flood
- masked or nodata areas

That is why your preview had:

- `17,896 active preview pixels`

not:

- `3,240,000 active preview pixels`

## 10. What `Active Preview Pixels` Means

This metric means:

- how many cells in the `1,800 x 1,800` preview still contain visible flood signal after masking

It does **not** mean:

- how many native TIFF cells exist
- how many polygons the browser will finally draw

It is just the count of active cells in the downsampled preview grid.

## 11. The Three Rendering Strategies

Once the preview exists, the dashboard has to decide **how** to draw it on the web map.

Internally, there are three rendering strategies.

### Strategy 1. Exact Native Pixels

This is the most faithful mode.

The app:

- reopens the TIFF
- recovers visible real source cells
- converts each source-cell corner into latitude / longitude
- draws true polygons on the map

This is best for:

- small or sparse floods
- detailed coastline inspection
- high-trust alignment checking

But it can become heavy if the event contains too many cells.

### Strategy 2. Preview-Grid Polygons

This is the main compromise mode.

The app:

- does **not** use all real source cells
- uses the already computed `1,800 x 1,800` preview grid
- turns visible preview cells into polygons

This is still much more geometrically faithful than a single image overlay, because each visible patch is drawn as geometry in map space.

This is the mode that solved your problem.

### Strategy 3. Raster Overlay

This is the fastest mode.

The app:

- converts the preview to one colored image
- reprojects that preview image to `EPSG:4326`
- places the result on the Leaflet map as one image overlay

This is efficient, but it is also the least trustworthy for exact spatial alignment over broad extents.

## 12. What `Merged Preview Polygons` Means

This is the part that usually confuses people.

The preview **does** still have pixels.

But the browser does not always have to draw every preview cell separately.

Suppose one preview row looks like this:

`[blue][blue][blue][empty][green][green]`

Without merging, the browser would draw:

- 5 small polygons

With merging, the browser can draw:

- 1 blue polygon covering the first 3 cells
- 1 green polygon covering the last 2 cells

So:

- 5 active cells

becomes:

- 2 polygons

That is what the app means by **merged preview polygons**.

The renderer walks across each row, groups consecutive active cells that share the same display color bin, and draws one polygon for that whole run.

So:

- `active preview pixels` = how many preview cells contain flood
- `merged preview polygons` = how many actual shapes the browser must draw after grouping neighboring same-color cells

This second number is a better estimate of browser cost.

## 13. Why The Old `Auto` Mode Was Wrong For Your Raster

Before the fix, `Auto` mostly looked at:

- `active preview pixels`

The old default cutoff was:

- `15,000`

Your raster had:

- `17,896 active preview pixels`

So the app said:

- too many for polygon preview
- fall back to raster overlay

But that was too pessimistic.

Why?

Because your raster did **not** require `17,896` separate browser shapes.

After grouping neighboring same-color preview cells, the estimated browser load was only:

- `16,345 merged preview polygons`

That is a much better number for deciding whether polygon rendering is still practical.

## 14. What The Fix Changed

The recent fix changed two things.

### Change 1. Better metric for `Auto`

Instead of deciding from raw active preview cells alone, `Auto` now estimates:

- how many merged preview polygons the browser would really need to draw

That is more faithful to the real cost of preview-polygon mode.

### Change 2. Higher default polygon budget

The old default budget was:

- `15,000`

The new default budget is:

- `20,000`

This budget is **not** a budget of raw raster cells.

It is a budget of:

- estimated merged preview polygons

For your raster:

- estimated preview polygons = `16,345`

So:

- old budget `15,000` -> app fell back to raster overlay
- new budget `20,000` -> app stays in preview-polygon mode

That is why your map now looks correct.

## 15. Why Raster Overlay Can Look Offshore

This is a display-method issue, not automatically a data issue.

The TIFF is stored in a projected flood CRS.

Leaflet web maps live in web-map coordinate logic.

If you draw the flood as one big image overlay:

- the browser stretches one rectangle in map space
- it is not drawing each flood cell as its own geometry

Even after reprojection, that one-image approach can still drift visually over large extents.

This is especially noticeable:

- near coastlines
- near estuaries
- when the raster covers a broad area

That is why polygon-based rendering is safer when alignment matters.

## 16. The Full Streamlit Display Flow

For one raster, the full display chain is:

1. Streamlit shows the sidebar.
2. You choose the raster root, year, and file.
3. `load_preview()` calls `read_flood_preview()`.
4. `find_source_window()` makes a `1200`-max coarse scan of the whole raster.
5. The app detects which coarse cells still contain flood.
6. Those coarse flood positions are mapped back to source-raster coordinates.
7. A padded source window is created.
8. `read_window_preview()` reads that source window as a `1800`-max detailed preview.
9. The app masks nodata and non-positive flood values.
10. The app computes display range statistics and preview bounds.
11. `build_folium_map()` chooses a rendering strategy:
    - exact native pixels
    - preview-grid polygons
    - raster overlay
12. Folium renders the chosen geometry or image overlay.
13. Streamlit embeds the resulting HTML map in the page.

That is the complete dashboard display process.

## 17. How To Interpret The Main Metrics In The App

### Source raster shape

The real TIFF dimensions.

Example:

- `90,000 x 90,000`

### Detailed crop shape

The dimensions of the downsampled preview used for display.

Example:

- `1,800 x 1,800`

### Active preview pixels

How many preview cells remain visible after masking.

Example:

- `17,896`

### Estimated preview polygons

How many merged preview shapes the browser is expected to draw in preview-polygon mode.

Example:

- `16,345`

### Render mode

What the dashboard actually used:

- `pixels`
- `preview_pixels`
- `raster`
- `raster_fallback`

## 18. Practical Advice

If you want the safest spatial interpretation:

- use `Polygon pixels`

If you want the dashboard to choose automatically:

- use `Auto`

If the browser becomes heavy and you only want a rough qualitative view:

- use `Raster overlay`

If something looks suspiciously offshore:

1. switch from `Auto` to `Polygon pixels`
2. compare against Felt or another viewer
3. only blame the TIFF after checking the rendering mode

## 19. The Short Version

The TIFF is huge, so the dashboard:

- first makes a small search copy
- then makes a smaller display preview
- then chooses how to draw that preview

Your raster looked wrong before because:

- `Auto` fell into the approximate raster-overlay branch too early

It looks right now because:

- the app keeps that raster in the preview-polygon path instead

That means the browser is now drawing real map geometry for the preview, not one stretched image.
