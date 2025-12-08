# 🌍 Merging All Flood Events Into a Single Global Raster  
### Using `mergeAllFolder.py`

This document explains the purpose, logic, and usage of the script that merges all preprocessed flood-event rasters into **one global composite flood map**.

---

## 1. Purpose

After running the preprocessing pipeline (`preprocess_events.py`), each flood event becomes its own raster stored inside:

```
data/events_filtered/
```

When visualizing these events in dashboards (e.g., Streamlit), loading dozens or hundreds of event files can be slow and unnecessary.

This script produces:

- **One single raster** representing the **maximum observed flood depth** over *all* events.
- A harmonized **global grid** covering the full spatial extent of all processed events.
- A dataset that is fast to load, easy to inspect, and ideal for global visualizations.

This “all events” map is especially useful for:

- Quick visualization of regions most affected by floods.
- Fast dashboard rendering.
- Machine-learning preprocessing.
- High-level geospatial analysis.

---

## 2. Required Data

The script expects:

- A folder containing **per-event merged flood rasters**, typically created by `preprocess_events.py`.  
  Example:

```
data/events_filtered/
    flood_2024-01-03__2024-01-08.tif
    flood_2024-02-10__2024-02-14.tif
    flood_2024-03-20__2024-03-25.tif
    ...
```

All rasters must:

- Share the **same CRS** (usually `EPSG:4326` after preprocessing),
- Represent flood depth values (positive values for floods, ≤0 / nodata for no-flood).

---

## 3. Output

After execution, the script produces:

```
data/events_filtered/flood_ALL_events.tif
```

This raster:

- Covers the **union of all event extents**, ensuring no flood is accidentally clipped,
- Contains the **pixel-wise maximum flood depth** across all events,
- Uses a controlled resolution (limited by `MAX_SIZE_GLOBAL`),
- Is ready to be used directly in Streamlit or GIS tools.

---

## 4. How the Script Works

### Step 1 — Find all event rasters  
The script scans:

```
data/events_filtered/*.tif
```

excluding the final global output if it already exists.

---

### Step 2 — Determine the **global extent**  
For each event raster:

1. Load bounding box with `rioxarray`.
2. Combine bounds to compute the **minimum bounding box** that covers *all* floods.
3. Extract pixel resolution from the first raster.

This ensures no event is cropped out.

---

### Step 3 — Build a **global grid**  

Using the union of all extents and a resolution constraint (`MAX_SIZE_GLOBAL`), the script computes:

- Output width (number of columns),
- Output height (number of rows),
- Output transform using `rasterio.from_bounds()`.

This defines the **target raster grid** for every event.

---

### Step 4 — Reproject every event onto the global grid  

For each event raster:

1. Reproject it onto the global grid using `rio.reproject()`,
2. Convert nodata values to `NaN`,
3. Set non-positive values (`<=0`) to `NaN` so they do not pollute the merge,
4. Update the global composite:

```
composite = max(composite, event_raster)
```

while ignoring NaNs.

---

### Step 5 — Create and save the final composite raster

The script generates an `xarray.DataArray` with:

- The merged flood depth array,
- Correct spatial coordinates,
- CRS metadata,
- Global affine transform.

It is saved as:

```
data/events_filtered/flood_ALL_events.tif
```

with LZW compression and float32 precision.

---

## 5. Running the Script

From the project root:

```
python src/data/mergeAllFolder.py
```

You will see logs for:

- Global extent computation,
- Grid creation,
- Each merged event raster,
- Final file generation.

---

## 6. Notes

- The merge computes **maximum flood depth** across all events:
  - If multiple floods overlap in a pixel → the deepest one is kept.
  - No-flood pixels remain `NaN`.

- The union-of-extents approach ensures **no flood event is lost** due to cropping.

- If memory becomes a concern, reduce `MAX_SIZE_GLOBAL` to generate a smaller raster.

- This step should be done once, after filtering/preprocessing, to accelerate real-time applications such as dashboards.

---

## 7. Recommended Workflow

1. Run `preprocess_events.py` → creates per-event rasters.  
2. (Optional) Run `filter_events_by_country.py` → keep only relevant regions.  
3. Run **`mergeAllFolder.py`** → produce global merged flood raster.  
4. Use `flood_ALL_events.tif` in Streamlit for fast visualization.

---

## 8. Contact / Support

If you want to extend this pipeline (per-year merges, temporal layers, flood frequencies, hazard indices, ML-ready tensors), feel free to ask!
