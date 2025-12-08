# 🧩 Preprocessing JRC Flood Depth Maps by Event  
### Using `preprocess_events.py`

This document explains the purpose and workflow of the script that converts raw JRC WD_MERGE flood depth rasters into **one cleaned, merged raster per flood event**.

---

## 1. Purpose

The original JRC flood depth dataset contains many GeoTIFF tiles (clusters) per event, often split by region or internal tiling.  
Working directly with all these raw files is:

- heavy (many files per event),  
- inconvenient for dashboards and analysis,  
- harder to sample or visualize flood intensity for a specific event.

This script creates **one raster per event**, where:

- all clusters belonging to the same event are **mosaicked** together,
- the merge is done via **pixel-wise maximum flood depth**,
- outputs are optionally **downsampled** for performance,
- outputs are **reprojected to EPSG:4326** for easy web mapping.

The result is a compact, event-based dataset, ideal for Streamlit apps, GIS tools, and further processing.

---

## 2. Required Data

The script expects a directory structure like:

```text
JRC_flood_depth_maps/
    2015/
        WD_MERGE_2015-01-05---2015-01-10_duration_....tif
        WD_MERGE_2015-01-05---2015-01-10_duration_....tif
        WD_MERGE_2015-03-12---2015-03-18_duration_....tif
        ...
    2016/
        ...
    2024/
        ...
```

In the script example, we use:

```python
ROOT_DIR = Path("JRC_flood_depth_maps/2024")
```

so it processes all WD_MERGE rasters for the year **2024**.  
You can point `ROOT_DIR` to any year folder (or the global root) as needed.

Each file is a **WD_MERGE** GeoTIFF with a filename containing the flood event period, e.g.:

```text
WD_MERGE_2024-12-16---2024-12-23_duration_7days_cluster01.tif
```

---

## 3. Output

The script writes one merged raster per event into:

```text
data/events_merged/
    flood_2024-12-16__2024-12-23.tif
    flood_2024-03-05__2024-03-12.tif
    ...
```

Each output file:

- is a **single raster** representing that event,  
- is **downsampled** to a maximum width/height defined by `MAX_SIZE`,  
- has been **cleaned** (nodata and non-positive values → NaN),  
- is **reprojected to EPSG:4326** (by default, via `OUT_CRS`).

You can later filter these events by country and/or merge them into global composites for visualization.

---

## 4. How the Script Works

### Step 1 — Scan all GeoTIFFs

```python
tif_files = find_all_tifs(ROOT_DIR)
```

`find_all_tifs` uses `root.rglob("*.tif")` to recursively collect all GeoTIFF files under the specified root directory.

---

### Step 2 — Group files by flood event

Each WD_MERGE filename encodes the event period in its name:

```text
WD_MERGE_YYYY-MM-DD---YYYY-MM-DD_duration_...
```

The script extracts `(start_date, end_date)` using a regex:

```python
EVENT_PATTERN = re.compile(
    r"WD_MERGE_(\d{4}-\d{2}-\d{2})---(\d{4}-\d{2}-\d{2})_duration_"
)
```

and builds an **event key** like:

```text
"2024-12-16__2024-12-23"
```

Then it groups all matching files into a dictionary:

```python
events[event_key] = [cluster_1.tif, cluster_2.tif, ...]
```

So each key represents **one event** and maps to all its cluster rasters.

---

### Step 3 — Load and mosaic the clusters (`load_and_mosaic`)  

For each event, the script calls:

```python
da_merged = load_and_mosaic(files, max_size=MAX_SIZE)
```

This function performs several steps:

1. **Open all rasters** for the event using `rioxarray.open_rasterio`, squeezing out the band dimension.

2. **Ensure CRS**  
   If the first raster is missing a CRS, it writes a default CRS (`DEFAULT_CRS`, e.g. `EPSG:27704`).

3. **Early downsampling**  
   To avoid memory issues, it checks the size of the first raster and computes a scale factor:

   ```python
   scale = max(ny, nx) / max_size
   ```

   If `scale > 1`, it downsamples each raster using `coarsen(...).mean()` by a factor `ceil(scale)`.

4. **Reproject to a common grid**  
   After downsampling, it picks the first raster as a base and calls:

   ```python
   das_match = [da.rio.reproject_match(base) for da in das]
   ```

   so all rasters share the same resolution, extent, and grid.

5. **Clean nodata and non-flood values**  
   For each raster:

   - nodata values are set to `NaN`,  
   - non-positive values (`<= 0`) are also set to `NaN` (treated as “no flood”).

6. **Merge via pixel-wise maximum**  
   The cleaned rasters are stacked along a new `cluster` dimension:

   ```python
   stack = xr.concat(cleaned, dim="cluster")
   da_merged = stack.max(dim="cluster", skipna=True)
   ```

   The result is a single raster where each pixel represents the **maximum flood depth** found across all clusters for that event.

7. **CRS metadata**  
   The merged raster carries the CRS from the base raster:

   ```python
   da_merged = da_merged.rio.write_crs(base.rio.crs)
   ```

---

### Step 4 — Reproject merged event rasters to `OUT_CRS`

After merging the clusters of an event, the script reprojects the event raster to the target CRS (for web mapping / folium):

```python
da_out = da_merged.rio.reproject(OUT_CRS)
```

By default, `OUT_CRS = "EPSG:4326"`, which is commonly used for lat/lon web maps.

---

### Step 5 — Save one GeoTIFF per event

Each event raster is saved with a name like:

```text
flood_2024-12-16__2024-12-23.tif
```

under `OUT_DIR = data/events_merged`:

```python
da_out.rio.to_raster(
    out_path,
    compress="LZW",
    dtype="float32",
)
```

- `compress="LZW"` keeps files smaller,
- `dtype="float32"` helps reduce disk space while preserving numeric precision.

If an output already exists for an event, it is skipped to avoid recomputation.

---

## 5. Running the Script

From the project root, simply run:

```bash
python preprocess_events.py
```

or, if it lives in `src/data/`:

```bash
python src/data/preprocess_events.py
```

Console output will show:

- how many `.tif` files were found,
- how many unique events were detected,
- progress `[i/total]` per event,
- any errors encountered while processing specific events.

---

## 6. Notes & Tips

- You can change `ROOT_DIR` to process a different year or multiple years.
- You can adjust `MAX_SIZE` if you want higher-resolution outputs (larger rasters) or lighter files (smaller rasters).
- `DEFAULT_CRS` must match the original JRC WD_MERGE CRS. If your metadata says otherwise, update it accordingly.
- If you later filter events by region (e.g., Europe only), it is more efficient to do that on the **merged per-event rasters** rather than raw WD_MERGE tiles.

---

## 7. Recommended Workflow

1. Run **`preprocess_events.py`** → create per-event merged flood rasters in `data/events_merged/`.  
2. (Optional) Run a **country filter script** to keep only events intersecting your area of interest into `data/events_filtered/`.  
3. (Optional) Run **`mergeAllFolder.py`** to create a single global “max flood” raster across all events.  
4. Use these processed rasters in your Streamlit app or any GIS environment.

