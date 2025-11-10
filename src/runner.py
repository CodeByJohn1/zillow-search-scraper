import argparse
import json
import logging
import os
import sys
from typing import Any, Iterable, List

# Make sure local imports work even when executed from project root
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from extractors.zillow_parser import (
    ZillowListing,
    parse_zillow_search_results,
)
from outputs.exporters import export_listings

LOGGER = logging.getLogger("zillow_scraper")

def configure_logging(level: str = "INFO") -> None:
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

def load_json_file(path: str) -> Any:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Input file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            LOGGER.debug("Loaded JSON file %s", path)
            return data
        except json.JSONDecodeError as exc:
            raise ValueError(f"Failed to parse JSON file {path}: {exc}") from exc

def extract_raw_listings(data: Any) -> Iterable[dict]:
    """
    Attempt to extract a list of raw listing objects from various
    plausible Zillow JSON structures.
    """
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        # Common patterns for wrapped payloads
        for key in ("results", "listings", "props", "properties"):
            value = data.get(key)
            if isinstance(value, list):
                return value

        # Fallback: try values that look like listings
        listings: List[dict] = []
        for value in data.values():
            if isinstance(value, list) and value and isinstance(value[0], dict):
                listings.extend(value)
        if listings:
            return listings

    raise ValueError("Could not recognize structure of input JSON as Zillow listings.")

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Zillow Search Scraper - parse Zillow search JSON into structured data."
    )
    default_input = os.path.join(
        os.path.dirname(CURRENT_DIR), "data", "input.sample.json"
    )
    default_output_dir = os.path.join(
        os.path.dirname(CURRENT_DIR), "data", "output"
    )

    parser.add_argument(
        "--input",
        "-i",
        default=default_input,
        help=f"Path to input JSON file (default: {default_input})",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        default=default_output_dir,
        help=f"Directory to write output files (default: {default_output_dir})",
    )
    parser.add_argument(
        "--formats",
        "-f",
        nargs="+",
        default=["json", "csv", "html"],
        help="Output formats to generate. Supported: json, csv, html",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL). Default: INFO",
    )

    return parser.parse_args()

def main() -> None:
    args = parse_args()
    configure_logging(args.log_level)

    LOGGER.info("Starting Zillow Search Scraper")
    LOGGER.info("Input file: %s", args.input)
    LOGGER.info("Output directory: %s", args.output_dir)
    LOGGER.info("Output formats: %s", ", ".join(args.formats))

    try:
        raw_data = load_json_file(args.input)
        raw_listings_iter = extract_raw_listings(raw_data)
        listings: List[ZillowListing] = parse_zillow_search_results(raw_listings_iter)
    except Exception as exc:
        LOGGER.error("Failed to parse input data: %s", exc, exc_info=True)
        sys.exit(1)

    if not listings:
        LOGGER.warning("No listings parsed from input data.")
        sys.exit(0)

    LOGGER.info("Parsed %d listings", len(listings))

    try:
        os.makedirs(args.output_dir, exist_ok=True)
        export_listings(listings, args.output_dir, args.formats)
    except Exception as exc:
        LOGGER.error("Failed to export listings: %s", exc, exc_info=True)
        sys.exit(1)

    LOGGER.info("Done. Data exported to %s", args.output_dir)

if __name__ == "__main__":
    main()