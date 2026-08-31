import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE_URL = "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/CEMS-EFAS/European_Satellite-Derived_Flood_Depth_Maps/maps/"
YEARS = list(range(2015, 2025))
OUTPUT_DIR = "JRC_flood_depth_maps"

os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_links(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")
    links = []
    for link in soup.find_all("a"):
        href = link.get("href")
        if href and href.endswith(".tif"):
            links.append(urljoin(url, href))
    return links

print(get_links(BASE_URL))


def download_file(url, dest_folder):
    local_filename = os.path.join(dest_folder, os.path.basename(url))
    if os.path.exists(local_filename):
        print(f"Already downloaded: {local_filename}")
        return
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(local_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    print(f"Downloaded: {local_filename}")


    # Main loop
for year in YEARS:
    year_url = f"{BASE_URL}{year}/"
    print(f"Scanning {year_url}")
    links = get_links(year_url)
    year_folder = os.path.join(OUTPUT_DIR, str(year))
    os.makedirs(year_folder, exist_ok=True)
    for link in links:
        download_file(link, year_folder)

