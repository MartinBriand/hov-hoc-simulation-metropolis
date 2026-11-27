"""Unify the GTFS feeds of the Nice study area into one single GTFS feed.

Scope: this script is written for the specific GTFS feeds documented in the README
(the eight transport.data.gouv.fr downloads of November 13, 2026). Some rules are
heuristic and calibrated on this data only: demand-responsive routes are
identified by the "PAD" name prefix of Palmbus. If other feeds are used (other
networks or other download dates), review `FEEDS` and `is_demand_route`
before trusting the output.

Usage:
    uv run python python/merge_gtfs_nice.py --start-date YYYYMMDD --end-date YYYYMMDD
    uv run python python/merge_gtfs_nice.py [--input-dir data/gtfs]
                                            [--output data/gtfs/merge_output/nice_area.zip]

The source zips stay in the input directory; the merged feed is written to a
separate `merge_output` folder, so that original and merged files are easily
told apart.

Steps:
  1. Check that all expected GTFS zip files are present in the input directory.
  2. Compute and print the validity window of every feed (from calendar.txt,
     calendar_dates.txt and feed_info.txt) and their intersection. The
     requested time window must lie inside this intersection: a missing window
     stops the script there (exit 2), a window outside the intersection is
     rejected (exit 1).
  3. Merge the feeds into a single GTFS feed restricted to the requested
     window:
     - every id is namespaced with its network ("zou_prox:...", "dazur:...")
       so that ids remain globally unique,
     - services are restricted to the window: calendars are clipped to the
       window, calendar dates outside are dropped, trips of services that do
       not run inside the window are removed,
     - only scheduled trains and buses are kept (tram, train, bus, trolleybus
       route types): demand-responsive routes (e.g. Palmbus 'Palm à la
       demande') and other vehicle modes are removed, and vendor route
       types are normalized (Lignes d'Azur scheduled village coach lines
       to bus, Transdev trains to train),
     - routes without trips are removed, as well as agencies without routes,
     - `GTFS_SIBR_zou_ferre_datasud.zip` is ignored if present: every journey
       of the ZOU Trains feed is already contained in a merged feed (all TER
       journeys in the ZOU Express feed, the intercity Nice - Marseille line
       in `zou_train_transdev.zip`),
     - trips exported identically by several feeds (the ZOU Express feed
       re-exports the Transdev intercity journeys) are deduplicated:
       the first feed in FEEDS order keeps them,
     - non-standard / per-network files (fares, booking rules, private
       extensions) are dropped and reported,
     - a synthetic feed_info.txt describes the merged feed.
"""

import argparse
import csv
import io
import re
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_DIR = REPO_ROOT / "data" / "gtfs"
DEFAULT_OUTPUT = DEFAULT_INPUT_DIR / "merge_output" / "nice_area.zip"

# Merged GTFS tables (standard files only; anything else is dropped).
MERGED_TABLES = [
    "agency.txt",
    "stops.txt",
    "routes.txt",
    "trips.txt",
    "calendar.txt",
    "calendar_dates.txt",
    "stop_times.txt",
    "frequencies.txt",
    "transfers.txt",
    "shapes.txt",
    "attributions.txt",
]

# Per-feed processing order: trips first, so that mode / window
# filtering and the sets of kept trips / routes / services are known before
# the tables that reference them are written.
PROCESS_ORDER = [
    "stops.txt",
    "trips.txt",
    "routes.txt",
    "calendar.txt",
    "calendar_dates.txt",
    "stop_times.txt",
    "frequencies.txt",
    "transfers.txt",
    "shapes.txt",
    "attributions.txt",
    "agency.txt",
]

# Columns that hold an id and must be namespaced with the feed prefix.
ID_COLUMNS = {
    "agency.txt": {"agency_id"},
    "stops.txt": {"stop_id", "parent_station"},
    "routes.txt": {"route_id", "agency_id"},
    "calendar.txt": {"service_id"},
    "calendar_dates.txt": {"service_id"},
    "trips.txt": {"route_id", "service_id", "trip_id", "shape_id", "block_id"},
    "stop_times.txt": {"trip_id", "stop_id"},
    "frequencies.txt": {"trip_id"},
    "transfers.txt": {
        "from_stop_id",
        "to_stop_id",
        "from_route_id",
        "to_route_id",
        "from_trip_id",
        "to_trip_id",
    },
    "shapes.txt": {"shape_id"},
    "attributions.txt": {"attribution_id", "route_id", "trip_id", "agency_id"},
}

WEEKDAY_COLUMNS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

# Vehicle modes kept in the merged feed: tram (0), train (2), bus (3),
# trolleybus (8). Everything else (ferries, cable cars, demand-responsive
# services, ...) is removed.
KEPT_ROUTE_TYPES = {"0", "2", "3", "8"}

# Vendor route types that actually are scheduled train / bus / coach lines in
# the source feeds, normalized to the GTFS base types: 715 is used by Lignes
# d'Azur for its scheduled village coach lines (C3x-C4x) in the Tinée and Var
# valleys, 100 ("Railway Service") by the Transdev feed for the intercity
# Nice - Marseille line.
NORMALIZED_ROUTE_TYPES = {"715": "3", "100": "2"}


@dataclass(frozen=True)
class FeedSpec:
    """A GTFS zip to merge, and the namespace used for its ids."""

    zip_name: str
    prefix: str
    organizing_authority: str


# The feeds to merge. The order matters for cross-feed deduplication of trips
# (see `merge`): the Transdev feed comes first so that its Nice - Marseille
# intercity journeys win over the copies re-exported by the ZOU Express feed.
FEEDS = [
    FeedSpec("zou_train_transdev.zip", "zou_transdev", "Region, rail (Zou)"),
    FeedSpec("GTFS_sibr_production_zou_proximite.zip", "zou_prox", "Region, prox (Zou)"),
    FeedSpec("GTFS_sibr_production_zou_express.zip", "zou_exp", "Region, express (Zou)"),
    FeedSpec("nice_lignes_dazur.zip", "dazur", "Nice, urban"),
    FeedSpec("envibus.zip", "envibus", "Antibes, local"),
    FeedSpec("palmbus-cannes-fr.zip", "palmbus", "Cannes, local"),
    FeedSpec("urbain_sillages.zip", "sillages", "Grasse, local"),
    FeedSpec("zest.zip", "zest", "Menton, local"),
]

# Present but not merged, on purpose: every journey of the ZOU Trains feed is
# already contained in another merged feed (all TER journeys in the ZOU
# Express feed, the intercity Nice - Marseille line in zou_train_transdev.zip),
# so using it would double count them.
IGNORED_ZIPS = {
    "GTFS_SIBR_zou_ferre_datasud.zip": "journeys already contained in the ZOU Express and Transdev feeds",
}


def journey_key(trip_id: str) -> str:
    """Export-normalized journey id of a trip.

    The ZOU exports differ in two ways: SNCF service-journey ids carry a
    trailing export-batch counter (`SNC:FR:ServiceJourney::SN879387FERRE_13306141`),
    and the Transdev feed writes the intercity journey ids without the `MCN:`
    producer prefix that the ZOU Express feed uses (`17466@2026-12-07` vs
    `MCN:17466@2026-12-07`). Strip both to make the ids comparable across
    feeds.
    """
    return re.sub(r"_[0-9]+$", "", re.sub(r"^MCN:", "", trip_id))


def is_demand_route(short_name: str, long_name: str) -> bool:
    """Tell a demand-responsive route from a scheduled one.

    Demand-responsive services (booked services without a fixed timetable,
    e.g. the 'Palm à la demande' PAD routes of Palmbus) are removed: only
    scheduled trains and buses are kept in the merged feed.
    """
    return (short_name or "").upper().startswith("PAD") or (long_name or "").upper().startswith("PAD")


def read_table(zf: zipfile.ZipFile, name: str) -> tuple[list[str], list[list[str]]] | None:
    member = next((n for n in zf.namelist() if n.split("/")[-1] == name), None)
    if member is None:
        return None
    with zf.open(member) as f:
        text = io.TextIOWrapper(f, encoding="utf-8-sig", newline="")
        rows = list(csv.reader(text))
    if not rows:
        return None
    return rows[0], rows[1:]


def parse_date(yyyymmdd: str) -> date:
    return datetime.strptime(yyyymmdd, "%Y%m%d").date()


def row_record(header: list[str], row: list[str]) -> dict[str, str]:
    return dict(zip(header, row))


def date_window(zf: zipfile.ZipFile) -> tuple[str, str] | None:
    """Validity window of a feed, as [earliest date, latest date]."""
    dates: list[str] = []

    calendar = read_table(zf, "calendar.txt")
    if calendar:
        header, rows = calendar
        start = header.index("start_date")
        end = header.index("end_date")
        dates.extend(row[start] for row in rows if row[start])
        dates.extend(row[end] for row in rows if row[end])

    calendar_dates = read_table(zf, "calendar_dates.txt")
    if calendar_dates:
        header, rows = calendar_dates
        index = header.index("date")
        dates.extend(row[index] for row in rows if row[index])

    if not dates:
        feed_info = read_table(zf, "feed_info.txt")
        if feed_info:
            header, rows = feed_info
            start = header.index("feed_start_date")
            end = header.index("feed_end_date")
            dates.extend(row[start] for row in rows if row[start])
            dates.extend(row[end] for row in rows if row[end])

    if not dates:
        return None
    return min(dates), max(dates)


def service_dates_in_window(
    zf: zipfile.ZipFile, win_start: date, win_end: date
) -> dict[str, set[date]]:
    """For every service of a feed, the dates it runs within the window.

    Weekly patterns come from calendar.txt (clipped to the window), then
    calendar_dates.txt entries inside the window are applied (added or
    removed). Services without a calendar row get their dates from
    calendar_dates.txt only.
    """
    active: dict[str, set[date]] = {}

    calendar = read_table(zf, "calendar.txt")
    if calendar:
        header, rows = calendar
        for row in rows:
            record = row_record(header, row)
            service = record["service_id"]
            run_start = max(parse_date(record["start_date"]), win_start)
            run_end = min(parse_date(record["end_date"]), win_end)
            days = {
                win_start + timedelta(days=offset)
                for offset in range((run_end - run_start).days + 1)
                if record[WEEKDAY_COLUMNS[(win_start + timedelta(days=offset)).weekday()]]
                == "1"
            }
            active[service] = days

    calendar_dates = read_table(zf, "calendar_dates.txt")
    if calendar_dates:
        header, rows = calendar_dates
        for row in rows:
            record = row_record(header, row)
            service = record["service_id"]
            exception_day = parse_date(record["date"])
            if exception_day < win_start or exception_day > win_end:
                continue
            days = active.setdefault(service, set())
            if record["exception_type"] == "2":
                days.discard(exception_day)
            else:
                days.add(exception_day)

    return active


def check_zip_names(input_dir: Path) -> None:
    """Step 1: check the names of the expected zips (exit 1 if any is missing)."""
    expected = [f.zip_name for f in FEEDS]
    missing = [name for name in expected if not (input_dir / name).is_file()]

    print(f"Feeds in {input_dir}:")
    for spec in FEEDS:
        print(
            f"  [ ] {spec.zip_name:<45} {spec.organizing_authority}"
            f" -> merged (prefix '{spec.prefix}:')"
        )
    for path in sorted(input_dir.glob("*.zip")):
        if path.name in IGNORED_ZIPS:
            print(f"  [x] {path.name}: ignored ({IGNORED_ZIPS[path.name]})")
        elif path.name not in expected:
            print(f"  [?] {path.name}: unexpected zip file, ignored.")

    if missing:
        raise SystemExit("Missing GTFS files: " + ", ".join(missing))


def report_date_windows(input_dir: Path) -> dict[str, tuple[str, str]]:
    """Step 2: print every feed's window and their intersection."""
    windows: dict[str, tuple[str, str]] = {}
    print("\nValidity windows (calendar.txt / calendar_dates.txt):")
    for spec in FEEDS:
        with zipfile.ZipFile(input_dir / spec.zip_name) as zf:
            window = date_window(zf)
            if window is None:
                raise SystemExit(f"{spec.zip_name}: no calendar data, cannot determine the window")
            windows[spec.zip_name] = window
        print(f"  {spec.zip_name:<45} {window[0]} -> {window[1]}")

    start = max(w[0] for w in windows.values())
    end = min(w[1] for w in windows.values())
    if start <= end:
        print(f"\nIntersection (selections must lie inside): {start} -> {end}")
    else:
        print("\nIntersection: none, no window is covered by all feeds.")
    return windows


def validate_window(windows: dict[str, tuple[str, str]], start: str, end: str) -> tuple[date, date]:
    """Return the requested window as a date pair (exit 1 if invalid)."""
    try:
        start_day = parse_date(start)
        end_day = parse_date(end)
    except ValueError:
        raise SystemExit(f"Bad selection: dates must be YYYYMMDD (got {start}, {end}).")
    if end_day < start_day:
        raise SystemExit(f"Bad selection: end date {end} is before start date {start}.")

    allowed_start = parse_date(max(w[0] for w in windows.values()))
    allowed_end = parse_date(min(w[1] for w in windows.values()))
    if not allowed_start <= start_day <= end_day <= allowed_end:
        raise SystemExit(
            f"Bad selection: {start} -> {end} is not contained in the intersection "
            f"{allowed_start.strftime('%Y%m%d')} -> {allowed_end.strftime('%Y%m%d')} "
            "(see the windows printed above)."
        )
    return start_day, end_day


class MergedTable:
    """One merged GTFS table: union of the columns of every source feed."""

    def __init__(self, name: str, out_dir: Path):
        self.name = name
        self.columns: list[str] = []
        self._seen: set[str] = set()
        self._file = (out_dir / name).open("w", encoding="utf-8", newline="")
        self._writer = csv.writer(self._file, lineterminator="\n")

    def add_columns(self, header: list[str]) -> None:
        new = [c for c in header if c not in self._seen]
        self.columns.extend(new)
        self._seen.update(new)

    def start_writing(self) -> None:
        self._writer.writerow(self.columns)

    def write_rows(self, header: list[str], rows: list[list[str]]) -> None:
        for row in rows:
            record = dict(zip(header, row))
            self._writer.writerow([record.get(c, "") for c in self.columns])

    def close(self) -> None:
        self._file.close()


def merge(
    input_dir: Path,
    output: Path,
    win_start: date,
    win_end: date,
) -> None:
    """Step 3: merge all feeds into `output`, restricted to the window."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        tables = {name: MergedTable(name, tmp_dir) for name in MERGED_TABLES}

        # First pass: union of the columns per table, then write the headers.
        for spec in FEEDS:
            with zipfile.ZipFile(input_dir / spec.zip_name) as zf:
                for name in MERGED_TABLES:
                    table = read_table(zf, name)
                    if table is not None:
                        tables[name].add_columns(table[0])
        for table in tables.values():
            table.start_writing()

        # Pre-pass: map every journey (normalized trip id, see `journey_key`)
        # to the first feed in FEEDS order that contains it. When several
        # regional feeds export the same physical journey (e.g. ZOU Express
        # re-exports the intercity journeys of the Transdev feed), only the
        # first feed keeps it.
        trip_owner: dict[str, str] = {}
        for spec in FEEDS:
            with zipfile.ZipFile(input_dir / spec.zip_name) as zf:
                trips_table = read_table(zf, "trips.txt")
                if trips_table is None:
                    continue
                header, rows = trips_table
                trip_index = header.index("trip_id")
                for row in rows:
                    trip_owner.setdefault(journey_key(row[trip_index]), spec.prefix)

        # Physical signature of every trip kept so far (route short name,
        # headsign, sequence of stop names and times), claimed by the first
        # feed in FEEDS order. Catches physical duplicates that the journey
        # key misses (same run, different ids).
        claimed_signatures: dict[tuple[str | None, str, tuple[str, ...], tuple[tuple[str | None, str, str], ...]], str] = {}

        stats: list[tuple[str, int, int, int, int, int]] = []
        for spec in FEEDS:
            with zipfile.ZipFile(input_dir / spec.zip_name) as zf:
                standard = {n.split("/")[-1] for n in zf.namelist() if n.endswith(".txt")}
                dropped = sorted(standard - set(MERGED_TABLES) - {"feed_info.txt"})
                if dropped:
                    print(f"Dropping non-merged files from {spec.zip_name}: {', '.join(dropped)}")

                # Load all tables of the feed in memory: the physical
                # signature of a trip is needed while filtering trips.
                feed_tables = {name: read_table(zf, name) for name in MERGED_TABLES}

                stop_names: dict[str, str] = {}
                stops_table = feed_tables["stops.txt"]
                if stops_table is not None:
                    stops_header, stops_rows = stops_table
                    id_index = stops_header.index("stop_id")
                    name_index = stops_header.index("stop_name")
                    stop_names = {row[id_index]: row[name_index] for row in stops_rows}

                route_short: dict[str, str] = {}
                route_agency: dict[str, str] = {}
                dropped_mode_routes: set[str] = set()
                routes_table = feed_tables["routes.txt"]
                if routes_table is not None:
                    routes_header, routes_rows = routes_table
                    id_index = routes_header.index("route_id")
                    short_index = routes_header.index("route_short_name")
                    long_index = routes_header.index("route_long_name")
                    type_index = routes_header.index("route_type")
                    agency_index = routes_header.index("agency_id")
                    for row in routes_rows:
                        route_id = row[id_index]
                        route_short[route_id] = row[short_index]
                        route_agency[route_id] = row[agency_index]
                        kept_mode = row[type_index] in KEPT_ROUTE_TYPES or row[type_index] in NORMALIZED_ROUTE_TYPES
                        if not kept_mode or is_demand_route(row[short_index], row[long_index]):
                            dropped_mode_routes.add(route_id)

                trip_sequences: dict[str, tuple[tuple[str | None, str, str], ...]] = {}
                stop_times_table = feed_tables["stop_times.txt"]
                if stop_times_table is not None:
                    st_header, st_rows = stop_times_table
                    trip_index = st_header.index("trip_id")
                    sequence_index = st_header.index("stop_sequence")
                    by_trip: dict[str, list[list[str]]] = {}
                    for row in st_rows:
                        by_trip.setdefault(row[trip_index], []).append(row)
                    stop_index = st_header.index("stop_id")
                    arrival_index = st_header.index("arrival_time")
                    departure_index = st_header.index("departure_time")
                    for trip_id, trip_rows in by_trip.items():
                        trip_rows.sort(key=lambda row: int(row[sequence_index]))
                        trip_sequences[trip_id] = tuple(
                            (stop_names.get(row[stop_index]), row[arrival_index], row[departure_index])
                            for row in trip_rows
                        )

                active = service_dates_in_window(zf, win_start, win_end)
                kept_trips: set[str] = set()
                kept_routes: set[str] = set()
                kept_services: set[str] = set()
                n_dropped_mode = 0
                n_dropped_window = 0
                n_dropped_duplicate = 0
                n_dropped_physical = 0
                n_routes_dropped_mode = 0
                n_routes_dropped_tripless = 0

                for name in PROCESS_ORDER:
                    table = feed_tables[name]
                    if table is None:
                        continue
                    header, rows = table
                    id_columns = ID_COLUMNS.get(name, set())

                    # Mode filtering, window filtering and cross-feed
                    # deduplication (trips).
                    if name == "trips.txt":
                        service_index = header.index("service_id")
                        trip_index = header.index("trip_id")
                        route_index = header.index("route_id")
                        headsign_index = header.index("trip_headsign") if "trip_headsign" in header else None
                        kept_rows = []
                        for row in rows:
                            if row[route_index] in dropped_mode_routes:
                                n_dropped_mode += 1
                            elif not active.get(row[service_index]):
                                n_dropped_window += 1
                            elif trip_owner.get(journey_key(row[trip_index])) != spec.prefix:
                                n_dropped_duplicate += 1
                            else:
                                sequence = trip_sequences.get(row[trip_index])
                                if sequence is not None:
                                    # Include the active dates of the service:
                                    # the same run at the same times on another
                                    # day (another service) is a distinct trip.
                                    days = tuple(sorted(d.isoformat() for d in active[row[service_index]]))
                                    headsign = row[headsign_index] if headsign_index is not None else ""
                                    signature = (route_short.get(row[route_index]), headsign, days, sequence)
                                    if signature in claimed_signatures:
                                        n_dropped_physical += 1
                                        continue
                                    claimed_signatures[signature] = spec.prefix
                                kept_rows.append(row)
                        rows = kept_rows
                        kept_trips.update(row[trip_index] for row in rows)
                        kept_routes.update(row[route_index] for row in rows)
                        kept_services.update(row[service_index] for row in rows)

                    # Keep only the routes that still carry trips; vendor
                    # types for scheduled coach lines become GTFS bus.
                    if name == "routes.txt":
                        id_index = header.index("route_id")
                        type_index = header.index("route_type")
                        kept = []
                        for row in rows:
                            if row[id_index] in dropped_mode_routes:
                                n_routes_dropped_mode += 1
                                continue
                            if row[id_index] not in kept_routes:
                                n_routes_dropped_tripless += 1
                                continue
                            new_row = list(row)
                            if new_row[type_index] in NORMALIZED_ROUTE_TYPES:
                                new_row[type_index] = NORMALIZED_ROUTE_TYPES[new_row[type_index]]
                            kept.append(new_row)
                        rows = kept

                    # Drop rows that reference removed trips or services.
                    if name in ("stop_times.txt", "frequencies.txt"):
                        trip_index = header.index("trip_id")
                        rows = [row for row in rows if row[trip_index] in kept_trips]
                    if name == "transfers.txt":
                        kept = []
                        for row in rows:
                            record = row_record(header, row)
                            if record.get("from_trip_id") and record["from_trip_id"] not in kept_trips:
                                continue
                            if record.get("to_trip_id") and record["to_trip_id"] not in kept_trips:
                                continue
                            if record.get("from_route_id") and record["from_route_id"] not in kept_routes:
                                continue
                            if record.get("to_route_id") and record["to_route_id"] not in kept_routes:
                                continue
                            kept.append(row)
                        rows = kept
                    if name == "attributions.txt":
                        kept = []
                        for row in rows:
                            record = row_record(header, row)
                            if record.get("trip_id") and record["trip_id"] not in kept_trips:
                                continue
                            if record.get("route_id") and record["route_id"] not in kept_routes:
                                continue
                            kept.append(row)
                        rows = kept
                    if name == "agency.txt":
                        kept_agencies = {route_agency[route_id] for route_id in kept_routes if route_id in route_agency}
                        kept_agencies.discard("")
                        if kept_agencies:
                            id_index = header.index("agency_id")
                            rows = [row for row in rows if row[id_index] in kept_agencies]
                    if name == "calendar.txt":
                        kept = []
                        for row in rows:
                            record = row_record(header, row)
                            if record["service_id"] not in kept_services:
                                continue
                            clipped_row = list(row)
                            start_index = header.index("start_date")
                            end_index = header.index("end_date")
                            clipped_row[start_index] = max(record["start_date"], win_start.strftime("%Y%m%d"))
                            clipped_row[end_index] = min(record["end_date"], win_end.strftime("%Y%m%d"))
                            kept.append(clipped_row)
                        rows = kept
                    if name == "calendar_dates.txt":
                        kept = []
                        for row in rows:
                            record = row_record(header, row)
                            if record["service_id"] not in kept_services:
                                continue
                            if win_start <= parse_date(record["date"]) <= win_end:
                                kept.append(row)
                        rows = kept

                    renamed = [
                        [f"{spec.prefix}:{value}" if column in id_columns and value else value
                         for column, value in zip(header, row)]
                        for row in rows
                    ]
                    tables[name].write_rows(header, renamed)

                parts = []
                if n_dropped_mode:
                    parts.append(f"{n_dropped_mode} demand-mode trips removed")
                if n_dropped_window:
                    parts.append(f"{n_dropped_window} out-of-window trips removed")
                if n_dropped_duplicate:
                    parts.append(f"{n_dropped_duplicate} duplicate trips removed (same journey already merged)")
                if n_dropped_physical:
                    parts.append(f"{n_dropped_physical} duplicate trips removed (same physical run already merged)")
                print(f"{spec.zip_name}: {len(kept_trips)} trips kept" + (" (" + ", ".join(parts) + ")" if parts else ""))
                route_parts = []
                if n_routes_dropped_mode:
                    route_parts.append(f"{n_routes_dropped_mode} demand-mode routes removed")
                if n_routes_dropped_tripless:
                    route_parts.append(f"{n_routes_dropped_tripless} trip-less routes removed")
                if route_parts:
                    print(f"  routes: {len(kept_routes)} kept (" + ", ".join(route_parts) + ")")
                stats.append((spec.zip_name, len(kept_trips), n_dropped_mode, n_dropped_window, n_dropped_duplicate, n_dropped_physical))

        with (tmp_dir / "feed_info.txt").open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, lineterminator="\n")
            writer.writerow(
                ["feed_publisher_name", "feed_publisher_url", "feed_lang", "feed_start_date", "feed_end_date", "feed_version"]
            )
            writer.writerow(
                [
                    "hov-hoc-simulation-metropolis",
                    "https://github.com/MartinBriand/hov-hoc-simulation-metropolis",
                    "fr",
                    win_start.strftime("%Y%m%d"),
                    win_end.strftime("%Y%m%d"),
                    f"merged from {len(FEEDS)} GTFS feeds",
                ]
            )

        for table in tables.values():
            table.close()

        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(tmp_dir.glob("*.txt")):
                zf.write(path, path.name)

    print(f"\nMerged {len(FEEDS)} feeds into {output} (window {win_start} -> {win_end})")
    for zip_name, n_kept, n_mode, n_window, n_duplicate, n_physical in stats:
        parts = []
        if n_mode:
            parts.append(f"{n_mode} demand-mode removed")
        if n_window:
            parts.append(f"{n_window} out-of-window removed")
        if n_duplicate:
            parts.append(f"{n_duplicate} journey duplicates removed")
        if n_physical:
            parts.append(f"{n_physical} physical duplicates removed")
        print(f"  {zip_name:<45} {n_kept} trips" + (" (" + ", ".join(parts) + ")" if parts else ""))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--start-date", help="first day of the time window, YYYYMMDD")
    parser.add_argument("--end-date", help="last day of the time window, YYYYMMDD")
    args = parser.parse_args()

    check_zip_names(args.input_dir)
    windows = report_date_windows(args.input_dir)

    if not args.start_date or not args.end_date:
        print(
            "\nStopped before merging: no time window selected. Re-run with "
            "--start-date YYYYMMDD --end-date YYYYMMDD inside the intersection above."
        )
        raise SystemExit(2)

    start_day, end_day = validate_window(windows, args.start_date, args.end_date)
    merge(args.input_dir, args.output, start_day, end_day)


if __name__ == "__main__":
    main()
