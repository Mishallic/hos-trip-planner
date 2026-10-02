"""Build the offline place list used to name stops ("Joliet, IL").

Source: GeoNames cities1000 (populated places, CC BY 4.0, https://www.geonames.org).
Keeps towns and cities in the US, Canada and Mexico with a population of at least
1,000 (no neighbourhoods) and writes them as a gzip-compressed TSV: name, region
code, country, lat, lon.

The app only reads the committed file; it never downloads anything at runtime.
Run from backend/ to rebuild:

    python scripts/build_places.py
"""

import argparse
import csv
import gzip
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from planner.providers.regions import region_code  # noqa: E402

CITIES_URL = "https://download.geonames.org/export/dump/cities1000.zip"
ADMIN1_URL = "https://download.geonames.org/export/dump/admin1CodesASCII.txt"
OUTPUT = BACKEND / "planner" / "providers" / "data" / "places_us_ca_mx.tsv.gz"
COUNTRIES = {"US", "CA", "MX"}
MIN_POPULATION = 1000
# Neighbourhoods ("Chicago Loop") and historical, abandoned or destroyed places are not
# what a log remark should name.
SKIP_FEATURE_CODES = {"PPLX", "PPLH", "PPLQ", "PPLW"}
USER_AGENT = "hos-trip-planner/0.1 (+https://github.com/Mishallic/hos-trip-planner)"


def download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def admin1_names(raw: bytes) -> dict[str, str]:
    """ "CA.08" -> "Ontario"."""
    names = {}
    for line in raw.decode("utf-8").splitlines():
        code, name, *_ = line.split("\t")
        names[code] = name
    return names


def places(cities_zip: bytes, admin1: dict[str, str]):
    with (
        zipfile.ZipFile(io.BytesIO(cities_zip)) as archive,
        archive.open("cities1000.txt") as raw,
    ):
        rows = csv.reader(io.TextIOWrapper(raw, "utf-8"), delimiter="\t", quoting=csv.QUOTE_NONE)
        for row in rows:
            name, lat, lon, feature_code, country, admin1_code, population = (
                row[1], row[4], row[5], row[7], row[8], row[10], row[14],
            )  # fmt: skip
            if country not in COUNTRIES or int(population or 0) < MIN_POPULATION:
                continue
            if feature_code in SKIP_FEATURE_CODES:
                continue
            # US admin1 codes are already "TX"; CA and MX use numbers, so go via the name.
            state = admin1_code if country == "US" else admin1.get(f"{country}.{admin1_code}")
            region = region_code(state, country) or ""
            yield name, region, country, round(float(lat), 4), round(float(lon), 4)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cities-zip", type=Path, help="use a downloaded cities1000.zip")
    parser.add_argument("--admin1", type=Path, help="use a downloaded admin1CodesASCII.txt")
    args = parser.parse_args()

    cities_zip = args.cities_zip.read_bytes() if args.cities_zip else download(CITIES_URL)
    admin1 = admin1_names(args.admin1.read_bytes() if args.admin1 else download(ADMIN1_URL))

    rows = sorted(set(places(cities_zip, admin1)), key=lambda r: (r[2], r[1], r[0], r[3]))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    text = "".join("\t".join(map(str, row)) + "\n" for row in rows)
    # mtime=0 keeps the file byte-identical when the data has not changed.
    OUTPUT.write_bytes(gzip.compress(text.encode("utf-8"), compresslevel=9, mtime=0))
    per_country = {c: sum(r[2] == c for r in rows) for c in sorted(COUNTRIES)}
    print(f"{len(rows)} places {per_country} -> {OUTPUT} ({OUTPUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
