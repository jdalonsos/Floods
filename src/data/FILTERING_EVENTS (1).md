# Filtering Flood Events by Country  
### Using `filter_events_by_country.py`

This document describes the purpose and workflow of the event-filtering script used to extract only the flood rasters relevant for a given geographic region.

## 1. Purpose

After preprocessing the JRC flood depth maps, a large number of merged flood events remain (hundreds or thousands).
Most applications, however, focus only on specific countries. Loading all global events in a dashboard is inefficient, increases memory usage, and slows down interaction.

This script filters the events by checking whether each event’s spatial extent intersects the boundaries of selected countries. Only the relevant events are copied to a filtered folder.

## 2. Required Data

The script expects:

- A directory containing merged flood event raster files (`data/events_merged`).
- A local copy of the Natural Earth Admin 0 country boundaries.  
  Download from:  
  https://www.naturalearthdata.com/downloads/110m-cultural-vectors/

Place the shapefile components (`.shp`, `.shx`, `.dbf`, `.prj`, etc.) inside:

```
data/ne_110m_admin_0_countries/
```

## 3. Output

After execution, the script creates:

```
data/events_filtered/
```

containing only the events intersecting the selected countries.

## 4. How the Script Works

### Step 1 — Load the country boundaries  
The Natural Earth dataset is loaded WGS84 (EPSG:4326).  
The script extracts the geometries of the countries of interest and merges them into a single polygon.

### Step 2 — Iterate over each flood event  
For every raster file in `events_merged`, the script:

1. Reads its geographic bounding box using rasterio.
2. Converts that bounding box into a polygon.
3. Checks whether it intersects the target country geometry.

### Step 3 — Copy matched events  
If the bounding box intersects the selected countries, the file is copied into `events_filtered`.  
Otherwise, it is ignored.

## 5. Running the Script

From the project root:

```
python src/data/filter_events_by_country.py
```

A summary of kept and skipped events is printed after completion.

## 6. Notes

- The method uses bounding-box intersection, which is fast and sufficiently accurate for initial filtering.
- The filtering step should be done once offline to improve dashboard performance.
