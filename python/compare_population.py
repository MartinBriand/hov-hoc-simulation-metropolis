from pathlib import Path

import polars as pl

STD_SURVEY_PATH = Path("output/std_emc2_nice/")

PYMETROPOLIS_OUTPUT_PATH = Path("pymetropolis/output-synpop/")

GROUPS = (
    ("Alpes-Maritimes", "dep", "06"),
    ("Var", "dep", "83"),
    # Monaco location can be identified with INSEE code 99070.
    ("Monaco", "insee", "99070"),
)


def read_synpop():
    print("=== Synthetic population ===")
    households = pl.read_parquet(
        PYMETROPOLIS_OUTPUT_PATH / Path("demand/population/households/households.parquet")
    )
    n = len(households)
    print(f"Households: {n:,}")
    persons = pl.read_parquet(
        PYMETROPOLIS_OUTPUT_PATH / Path("demand/population/persons/persons.parquet")
    )
    n = len(persons)
    print(f"Persons: {n:,}")
    trips = pl.read_parquet(
        PYMETROPOLIS_OUTPUT_PATH / Path("demand/population/trips/trips.parquet")
    )
    n = len(trips)
    print(f"Trips: {n:,}")
    dists = pl.read_parquet(
        PYMETROPOLIS_OUTPUT_PATH / Path("demand/population/trips/distances.parquet")
    )
    d = dists["od_distance"].sum() / 1e3
    print(f"Trip distance: {d:,.0f} km")


def counts(df: pl.DataFrame, mask: pl.Expr) -> tuple[int, float] | tuple[int, float, float]:
    weight_col = (
        "sample_weight_surveyed" if "sample_weight_surveyed" in df.columns else "sample_weight"
    )
    df = df.filter(mask)
    n = len(df)
    w = df[weight_col].sum()
    if "trip_euclidean_distance_km" in df.columns:
        d = df.select((pl.col("trip_euclidean_distance_km") * pl.col(weight_col)).sum()).item()
        return n, w, d
    else:
        return n, w


def read_survey():
    households = pl.read_parquet(STD_SURVEY_PATH / Path("households.parquet"))
    print("=== Households ===")
    for name, col, value in GROUPS:
        n, w = counts(households, pl.col(f"home_{col}") == value)
        print(f"{name}: {n:,} obs, {w:,.0f} weight")
    persons = pl.read_parquet(STD_SURVEY_PATH / Path("persons.parquet"))
    persons = persons.join(households, on="household_id")
    print("=== Persons ===")
    for name, col, value in GROUPS:
        n, w = counts(persons, pl.col(f"home_{col}") == value)
        print(f"{name}: {n:,} obs, {w:,.0f} weight")
    trips = pl.read_parquet(STD_SURVEY_PATH / Path("trips.parquet"))
    trips = trips.join(persons, on="person_id")
    print("=== Trips (by residents) ===")
    for name, col, value in GROUPS:
        n, w, d = counts(trips, pl.col(f"home_{col}") == value)
        print(f"Trips of {name} residents: {n:,} obs, {w:,.0f} weight, {d:,.0f} km")
    print("=== Trips (by destination) ===")
    for name, col, value in GROUPS:
        n, w, d = counts(trips, pl.col(f"destination_{col}") == value)
        print(f"Trips to {name}: {n:,} obs, {w:,.0f} weight, {d:,.0f} km")
    for res_name, col, value in GROUPS:
        print(f"=== Trips of {res_name} residents ===")
        res_mask = pl.col(f"home_{col}") == value
        for name, col, value in GROUPS:
            if name == res_name:
                mask = pl.col(f"origin_{col}").eq(value) & pl.col(f"destination_{col}").eq(value)
            else:
                mask = pl.col(f"origin_{col}").eq(value) | pl.col(f"destination_{col}").eq(value)
            n, w, d = counts(trips, res_mask & mask)
            if name == res_name:
                print(f"Trips within {name}: {n:,} obs, {w:,.0f} weight, {d:,.0f} km")
            else:
                print(f"Trips from/to {name}: {n:,} obs, {w:,.0f} weight, {d:,.0f} km")


def main():
    read_synpop()
    read_survey()


if __name__ == "__main__":
    main()
