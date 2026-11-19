#!/bin/sh
# Unify the GTFS feeds of the Nice study area, restricted to the week from
# Monday 2026-12-07 to Friday 2026-12-11.
uv run python python/merge_gtfs_nice.py --start-date 20261207 --end-date 20261211
