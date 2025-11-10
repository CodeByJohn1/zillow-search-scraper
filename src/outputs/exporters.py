import csv
import json
import logging
import os
from typing import Iterable, List

from extractors.zillow_parser import ZillowListing

LOGGER = logging.getLogger("zillow_scraper.exporters")

SUPPORTED_FORMATS = {"json", "csv", "html"}

def export_to_json(listings: Iterable[ZillowListing], path: str) -> None:
    LOGGER.debug("Exporting %s listings to JSON: %s", len(listings), path)
    data = [l.to_dict() for l in listings]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def export_to_csv(listings: Iterable[ZillowListing], path: str) -> None:
    listings_list: List[ZillowListing] = list(listings)
    if not listings_list:
        LOGGER.warning("No listings to export to CSV.")
        return

    LOGGER.debug("Exporting %s listings to CSV: %s", len(listings_list), path)
    first_dict = listings_list[0].to_dict()
    fieldnames = list(first_dict.keys())

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for listing in listings_list:
            writer.writerow(listing.to_dict())

def export_to_html(listings: Iterable[ZillowListing], path: str) -> None:
    listings_list: List[ZillowListing] = list(listings)
    LOGGER.debug("Exporting %s listings to HTML: %s", len(listings_list), path)

    if not listings_list:
        html = "<html><body><p>No listings available.</p></body></html>"
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        return

    headers = list(listings_list[0].to_dict().keys())
    rows_html = []

    for listing in listings_list:
        row_cells = []
        data = listing.to_dict()
        for h in headers:
            value = data.get(h)
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            row_cells.append(f"<td>{value if value is not None else ''}</td>")
        rows_html.append("<tr>" + "".join(row_cells) + "</tr>")

    table_html = (
        "<table border='1' cellspacing='0' cellpadding='4'>"
        "<thead><tr>"
        + "".join(f"<th>{h}</th>" for h in headers)
        + "</tr></thead>"
        "<tbody>"
        + "".join(rows_html)
        + "</tbody></table>"
    )

    html = (
        "<html><head><meta charset='utf-8'><title>Zillow Listings</title></head>"
        "<body>"
        "<h1>Zillow Listings</h1>"
        f"{table_html}"
        "</body></html>"
    )

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)

def export_listings(
    listings: Iterable[ZillowListing],
    output_dir: str,
    formats: Iterable[str],
) -> None:
    normalized_formats = {fmt.lower() for fmt in formats}
    unsupported = normalized_formats - SUPPORTED_FORMATS
    if unsupported:
        raise ValueError(
            f"Unsupported format(s): {', '.join(sorted(unsupported))}. "
            f"Supported formats: {', '.join(sorted(SUPPORTED_FORMATS))}"
        )

    os.makedirs(output_dir, exist_ok=True)

    if "json" in normalized_formats:
        json_path = os.path.join(output_dir, "zillow_listings.json")
        export_to_json(listings, json_path)
        LOGGER.info("Exported JSON data to %s", json_path)

    # json export consumes the iterator if it's a generator; ensure we have a list
    listings_list: List[ZillowListing] = list(listings)

    if "csv" in normalized_formats:
        csv_path = os.path.join(output_dir, "zillow_listings.csv")
        export_to_csv(listings_list, csv_path)
        LOGGER.info("Exported CSV data to %s", csv_path)

    if "html" in normalized_formats:
        html_path = os.path.join(output_dir, "zillow_listings.html")
        export_to_html(listings_list, html_path)
        LOGGER.info("Exported HTML data to %s", html_path)