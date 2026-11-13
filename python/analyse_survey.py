from pathlib import Path

import polars as pl

STD_SURVEY_PATH = Path("output/std_emc2/")


def read_trip_modes():
    """Read legs and construct a trip-level mode from it."""
    legs = pl.read_parquet(STD_SURVEY_PATH / Path("legs.parquet"))
    assert legs.filter(
        pl.col("nb_persons_in_vehicle").is_null(), mode_group="car_driver"
    ).is_empty(), "Variable `nb_persons_in_vehicle` is NULL for some car driver legs."
    mask = pl.col("leg_travel_time").is_null() & pl.col("mode_group").eq("walking")
    n = legs.select(mask.sum()).item()
    if n:
        print(f"Warning. Variable `leg_travel_time` is NULL for {n:,} walking legs.")
        legs = legs.with_columns(pl.col("leg_travel_time").fill_null(0))
    # Add a dedicated mode modality for "car driver with passengers".
    legs = legs.with_columns(
        mode_clean=pl.when(pl.col("nb_persons_in_vehicle") > 1, mode_group="car_driver")
        .then(pl.lit("car_driver_with_passengers"))
        .when(nb_persons_in_vehicle=1, mode_group="car_driver")
        .then(pl.lit("car_driver_alone"))
        .otherwise(pl.col("mode_group").cast(pl.String))
    )
    legs = legs.select(
        "trip_id",
        "leg_id",
        "leg_index",
        "mode",
        "leg_travel_time",
        "leg_euclidean_distance_km",
        "leg_travel_distance_km",
        "car_type",
        "nb_persons_in_vehicle",
        "parking_location",
        "parking_type",
        "parking_search_time",
        "mode_clean",
    ).sort("trip_id", "leg_index")
    # Exclude walking legs with travel time <= 15' (unless it's the only trip leg).
    legs = legs.remove(
        pl.col("mode_clean").eq("walking")
        & pl.col("leg_travel_time").le(15)
        & pl.len().over("trip_id").gt(1)
    )
    # Exclude walking legs with travel time <= 30' when there is a PT leg (walking is part of PT).
    legs = legs.remove(
        pl.col("mode_clean").eq("walking")
        & pl.col("leg_travel_time").le(30)
        & pl.col("mode_clean").eq("public_transit").any().over("trip_id")
    )
    leg_trips = legs.group_by("trip_id").agg(
        "leg_travel_time",
        "leg_euclidean_distance_km",
        modes="mode_clean",
        unique_modes=pl.col("mode_clean").unique().sort(),
    )
    trip_modes = leg_trips.select(
        "trip_id",
        # Only one mode taken.
        trip_mode=pl.when(pl.col("unique_modes").list.len() == 1)
        .then(pl.col("modes").list.first())
        # Walk + PT (> 30' walk).
        .when(unique_modes=["public_transit", "walking"])
        .then(pl.lit("walk_and_ride"))
        # Bicycle + PT.
        .when(unique_modes=["bicycle", "public_transit"])
        .then(pl.lit("bike_and_ride"))
        # Park-and-ride combinations.
        .when(unique_modes=["car_passenger", "public_transit"])
        .then(pl.lit("kiss_and_ride"))
        .when(unique_modes=["car_driver_alone", "public_transit"])
        .then(pl.lit("park_and_ride:alone"))
        .when(unique_modes=["car_driver_with_passengers", "public_transit"])
        .then(pl.lit("park_and_ride:with_passengers"))
        .when(unique_modes=["motorcycle", "public_transit"])
        .then(pl.lit("park_and_ride:motorcycle"))
        # Walk + Car.
        .when(unique_modes=["car_driver_alone", "walking"])
        .then(pl.lit("car_and_walk:driver_alone"))
        .when(unique_modes=["car_driver_with_passengers", "walking"])
        .then(pl.lit("car_and_walk:driver_with_passengers"))
        .when(unique_modes=["car_passenger", "walking"])
        .then(pl.lit("car_and_walk:passenger"))
        # Walk + Bicycle.
        .when(unique_modes=["bicycle", "walking"])
        .then(pl.lit("bicycle_and_walk"))
        # Walk + Motorcycle.
        .when(unique_modes=["motorcycle", "walking"])
        .then(pl.lit("motorcycle_and_walk"))
        .when(pl.col("unique_modes").list.eval(pl.element().str.starts_with("car_")).list.all())
        .then(pl.lit("car_driver_and_passenger"))
        # Other combinations that involve the "other" mode.
        .when(pl.col("unique_modes").list.contains("other"))
        .then(pl.lit("combinations:other"))
        # Other combinations without the "other" mode (e.g., bicycle + car, driver + passenger + PT).
        .otherwise(pl.lit("combinations:complex")),
    )
    # Add number of passengers for car driver with passengers trips.
    trip_modes = trip_modes.join(
        legs.filter(pl.col("nb_persons_in_vehicle") > 1, mode="car:driver")
        .group_by("trip_id")
        # We take the first observed count per trip (in practice, there is only one value per trip).
        .agg(nb_passengers=pl.col("nb_persons_in_vehicle").first() - 1),
        on="trip_id",
        how="left",
    )
    return trip_modes


def read_trips():
    trips = pl.read_parquet(STD_SURVEY_PATH / Path("trips.parquet"))
    trips = trips.select(
        "trip_id",
        "person_id",
        "household_id",
        "trip_index",
        "home_sequence_index",
        "origin_purpose",
        "origin_purpose_group",
        "origin_escort_purpose",
        "origin_escort_purpose_group",
        "origin_activity_duration",
        "origin_detailed_zone",
        "origin_special_location",
        "destination_purpose",
        "destination_purpose_group",
        "destination_escort_purpose",
        "destination_escort_purpose_group",
        "destination_activity_duration",
        "destination_detailed_zone",
        "destination_special_location",
        "departure_time",
        "arrival_time",
        "travel_time",
        "trip_weekday",
        pl.col("main_mode_group").cast(pl.String),
        "intermodality",
        "trip_perimeter",
        distance="trip_euclidean_distance_km",
    ).sort("person_id", "trip_index")
    # Find shared trips.
    trips = trips.with_columns(
        rounded_departure_time=pl.col("departure_time").truediv(5).round() * 5,
        rounded_arrival_time=pl.col("arrival_time").truediv(5).round() * 5,
        origin_loc=pl.col("origin_special_location").fill_null("origin_detailed_zone"),
        destination_loc=pl.col("destination_special_location").fill_null(
            "destination_detailed_zone"
        ),
    )
    matching_columns = [
        "household_id",
        "origin_loc",
        "destination_loc",
        "trip_weekday",
        "distance",
        "rounded_departure_time",
        "rounded_arrival_time",
    ]
    shared_trips = (
        trips.select("trip_id", "person_id", "main_mode_group", *matching_columns)
        .join(
            trips.select("trip_id", "person_id", "main_mode_group", *matching_columns),
            on=matching_columns,
        )
        .filter(
            pl.col("trip_id") != pl.col("trip_id_right"),
            pl.col("person_id") != pl.col("person_id_right"),
        )
    )
    # Exclude unfeasible mode combinations.
    mode_combinations = pl.DataFrame(
        [
            *((m, m) for m in trips["main_mode_group"].unique()),
            ("car_driver", "car_passenger"),
            ("car_passenger", "car_driver"),
            # Other can include personal transporter (e.g., trottinets).
            ("bicycle", "other"),
            ("other", "bicycle"),
            ("walking", "other"),
            ("other", "walking"),
        ],
        orient="row",
        schema=["main_mode_group", "main_mode_group_right"],
    )
    shared_trips = shared_trips.join(
        mode_combinations, on=["main_mode_group", "main_mode_group_right"], how="semi"
    )
    shared_trips = shared_trips.group_by("trip_id").agg(
        mode=pl.col("main_mode_group").first(),
        shared_persons="person_id_right",
        shared_trips="trip_id_right",
        shared_modes="main_mode_group_right",
    )
    trips = trips.join(shared_trips, on="trip_id", how="left")
    return trips


def clean_data() -> pl.DataFrame:
    trips = read_trips()
    trip_modes = read_trip_modes()
    trips = trips.join(trip_modes, on="trip_id")
    # Add person weight.
    persons = pl.read_parquet(STD_SURVEY_PATH / Path("persons.parquet"))
    trips = trips.join(persons.select("person_id", weight="sample_weight_surveyed"), on="person_id")
    # Add households information.
    households = pl.read_parquet(STD_SURVEY_PATH / Path("households.parquet"))
    trips = trips.join(
        households.select(
            "household_id",
            fully_surveyed=pl.col("survey_method").eq("face_to_face")
            & pl.col("nb_persons").sub(pl.col("nb_persons_5plus")).eq(0),
        ),
        on="household_id",
    )
    # Restrict to trips within the survey perimeter.
    trips = trips.filter(trip_perimeter="internal")
    return trips


def ridesharing_driver_analysis(trips: pl.DataFrame):
    pl.Config(tbl_rows=25)
    print("Mode shares:")
    print(weighted_shares(trips, "trip_mode"))
    # Analysis of car driver with passengers trips.
    print("=== Car driver with passengers trips ===")
    rs_trips = trips.filter(trip_mode="car_driver_with_passengers")
    mean_nb_passengers = weighted_mean(rs_trips, "nb_passengers")
    dist_mean_nb_passengers = weighted_dist_mean(rs_trips, "nb_passengers")
    print(f"Average number of passengers: {mean_nb_passengers:.4f}")
    print(f"Average number of passengers (weighted by distance): {dist_mean_nb_passengers:.4f}")
    print("Distribution of passenger count:")
    print(weighted_shares(rs_trips, "nb_passengers"))
    fully_surveyed_share = rs_trips["fully_surveyed"].mean()
    print(f"Subsample of trips with fully-surveyed household: {fully_surveyed_share:.2%}")
    share_at_least1 = weighted_mean(
        rs_trips.filter("fully_surveyed"), pl.col("shared_trips").is_not_null()
    )
    dist_share_at_least1 = weighted_dist_mean(
        rs_trips.filter("fully_surveyed"), pl.col("shared_trips").is_not_null()
    )
    share_all = weighted_mean(
        rs_trips.filter("fully_surveyed"),
        pl.col("shared_trips").list.len() == pl.col("nb_passengers"),
    )
    dist_share_all = weighted_dist_mean(
        rs_trips.filter("fully_surveyed"),
        pl.col("shared_trips").list.len() == pl.col("nb_passengers"),
    )
    print(
        f"Share of RS trips with at least one passenger from same household: {share_at_least1:.2%}"
    )
    print(
        "Share of RS trips with at least one passenger from same household (weighted by distance): "
        f"{dist_share_at_least1:.2%}"
    )
    print(f"Share of RS trips with only passengers from same household: {share_all:.2%}")
    print(
        "Share of RS trips with only passengers from same household (weighted by distance): "
        f"{dist_share_all:.2%}"
    )
    print("=== Tour level ===")
    tours = (
        trips.filter("fully_surveyed")
        .sort("trip_id")
        .group_by("person_id", "home_sequence_index")
        .agg(
            weight=pl.col("weight").first(),
            distance=pl.col("distance").sum(),
            modes="trip_mode",
            unique_modes=pl.col("trip_mode").unique(maintain_order=True),
            purposes=pl.concat((pl.col("origin_purpose").first(), pl.col("destination_purpose"))),
            purpose_groups=pl.concat(
                (pl.col("origin_purpose_group").first(), pl.col("destination_purpose_group"))
            ),
            nb_passengers=pl.col("nb_passengers").fill_null(0),
            nb_household_passengers=pl.col("shared_trips").list.len().fill_null(0),
        )
    )
    print("=== Intra-household ridesharing===")
    in_tours = tours.filter(
        pl.col("nb_household_passengers").list.sum().gt(0),
        pl.col("nb_passengers") == pl.col("nb_household_passengers"),
    )
    only_escort_mask = pl.col("purpose_groups").list.unique().list.sort() == ["home", "escort"]
    share_only_escort = weighted_mean(in_tours, only_escort_mask)
    dist_share_only_escort = weighted_dist_mean(in_tours, only_escort_mask)
    print(f"Share of escort-only tours: {share_only_escort:.2%}")
    print(f"Share of escort-only tours (weighted by distance): {dist_share_only_escort:.2%}")
    fully_joint_mask = pl.col("nb_passengers").list.n_unique() == 1
    share_fully_joint = weighted_mean(in_tours, fully_joint_mask & only_escort_mask.not_())
    dist_share_fully_joint = weighted_dist_mean(
        in_tours, fully_joint_mask & only_escort_mask.not_()
    )
    print(f"Share of fully-joint intra-household tours: {share_fully_joint:.2%}")
    print(
        "Share of fully-joint intra-household tours (weighted by distance): "
        f"{dist_share_fully_joint:.2%}"
    )
    has_escort_mask = pl.col("purpose_groups").list.contains("escort")
    share_escort_on_the_way = weighted_mean(
        in_tours, has_escort_mask & fully_joint_mask.not_() & only_escort_mask.not_()
    )
    dist_share_escort_on_the_way = weighted_dist_mean(
        in_tours, has_escort_mask & fully_joint_mask.not_() & only_escort_mask.not_()
    )
    print(f"Share of escort on-the-way tours: {share_escort_on_the_way:.2%}")
    print(
        f"Share of escort on-the-way tours (weighted by distance): {dist_share_escort_on_the_way:.2%}"
    )
    print("=== Out-of-household ridesharing===")
    out_tours = tours.filter(
        pl.col("nb_household_passengers").list.sum().eq(0), pl.col("nb_passengers").list.sum().gt(0)
    )
    only_rs_mask = pl.col("nb_passengers").list.n_unique().eq(1)
    has_work_purpose_mask = pl.col("purpose_groups").list.contains("work")
    share_only_escort = weighted_mean(out_tours, only_escort_mask)
    dist_share_only_escort = weighted_dist_mean(in_tours, only_escort_mask)
    print(f"Share of escort-only tours: {share_only_escort:.2%}")
    print(f"Share of escort-only tours (weighted by distance): {dist_share_only_escort:.2%}")
    share_only_rs = weighted_mean(out_tours, only_rs_mask & only_escort_mask.not_())
    dist_share_only_rs = weighted_dist_mean(out_tours, only_rs_mask & only_escort_mask.not_())
    print(f"Share of fully-joint ridesharing tours: {share_only_rs:.2%}")
    print(
        f"Share of fully-joint ridesharing tours (weighted by distance): {dist_share_only_rs:.2%}"
    )
    share_work_tours = weighted_mean(out_tours, has_work_purpose_mask & only_rs_mask.not_())
    dist_share_work_tours = weighted_dist_mean(
        out_tours, has_work_purpose_mask & only_rs_mask.not_()
    )
    print(f"Share of work tours: {share_work_tours:.2%}")
    print(f"Share of work tours (weighted by distance): {dist_share_work_tours:.2%}")


def ridesharing_passenger_analysis(trips: pl.DataFrame):
    pl.Config(tbl_rows=25)
    persons = pl.read_parquet(STD_SURVEY_PATH / Path("persons.parquet")).with_columns(
        weight="sample_weight_surveyed"
    )
    trips = trips.filter(
        pl.col("trip_mode").is_in(
            ("car_passenger", "kiss_and_ride", "car_driver_and_passenger", "car_and_walk:passenger")
        )
    )
    # Filter: the driver is not from the household.
    trips = trips.filter("fully_surveyed", pl.col("shared_trips").is_null())
    # Non-home purpose.
    trips = trips.with_columns(
        main_purpose=pl.when(destination_purpose_group="home")
        .then("origin_purpose_group")
        .otherwise("destination_purpose_group")
    )
    print("Purpose of passenger trips whose driver is not from the household")
    print(weighted_shares(trips, "main_purpose"))
    persons = persons.join(trips, on="person_id", how="semi")
    print("Minor status for passenger trips whose driver is not from the household")
    print(weighted_shares_persons(persons, pl.col("age").lt(18).alias("minor")))
    print("Driving-license status for passenger trips whose driver is not from the household")
    print(weighted_shares_persons(persons, "has_driving_license"))


def intermodality_analysis(trips: pl.DataFrame):
    pl.Config(tbl_rows=25)
    legs = pl.read_parquet(STD_SURVEY_PATH / Path("legs.parquet"))
    trips = trips.filter(pl.col("trip_mode").str.contains("_and_ride"))
    legs = legs.join(trips.select("trip_id", "weight"), on="trip_id", how="inner")
    print(weighted_shares(trips, "trip_mode"))
    trip_weight = trips["weight"].sum()
    pt_dist = (
        legs.filter(mode_group="public_transit")
        .select((pl.col("leg_euclidean_distance_km") * pl.col("weight")).sum())
        .item()
    )
    non_pt_dist = (
        legs.select((pl.col("leg_euclidean_distance_km") * pl.col("weight")).sum()).item() - pt_dist
    )
    print(f"PT distance of intermodal trips: {pt_dist / trip_weight:.0f} km")
    print(f"Non-PT distance of intermodal trips: {non_pt_dist / trip_weight:.0f} km")
    trips = (
        legs.group_by("trip_id")
        .agg(
            pt_first=pl.col("mode_group")
            .filter(pl.col("mode").ne("walking") | pl.col("leg_travel_time").gt(30))
            .first()
            .eq("public_transit"),
            pt_modes=pl.col("mode").filter(mode_group="public_transit"),
            parking_location=pl.col("parking_location").first(),
        )
        .with_columns(
            access_pt_mode=pl.when("pt_first")
            .then(pl.col("pt_modes").list.first())
            .otherwise(pl.col("pt_modes").list.last())
        )
        .join(trips.select("trip_id", "weight", "distance", "trip_mode"), on="trip_id")
    )
    print("Access PT mode:")
    print(weighted_shares(trips, "access_pt_mode"))
    print("Parking location for park-and-ride:")
    print(
        weighted_shares(
            trips.filter(
                pl.col("pt_first").not_(), pl.col("trip_mode").str.starts_with("park_and_ride")
            ),
            "parking_location",
        )
    )


def weighted_mean(df: pl.DataFrame, expr: pl.Expr | str, weight: str = "weight") -> float:
    if isinstance(expr, str):
        expr = pl.col(expr)
    return df.select((expr * pl.col(weight)).sum() / pl.col(weight).sum()).item()


def weighted_dist_mean(
    df: pl.DataFrame,
    expr: pl.Expr | str,
    weight: str = "weight",
    distance: str = "distance",
) -> float:
    if isinstance(expr, str):
        expr = pl.col(expr)
    return df.select(
        (expr * pl.col(weight) * pl.col(distance)).sum() / (pl.col(weight) * pl.col(distance)).sum()
    ).item()


def weighted_shares(
    df: pl.DataFrame,
    expr: pl.Expr | str,
    weight: str = "weight",
    distance: str = "distance",
) -> pl.DataFrame:
    return (
        df.group_by(expr)
        .agg(
            n_obs=pl.len(),
            n_trips=pl.col(weight).sum(),
            distance=(pl.col(weight) * pl.col(distance)).sum(),
        )
        .with_columns(
            share_trips=pl.col("n_trips") / pl.col("n_trips").sum(),
            share_dist=pl.col("distance") / pl.col("distance").sum(),
        )
        .sort("share_trips", descending=True)
    )


def weighted_shares_persons(
    df: pl.DataFrame, expr: pl.Expr | str, weight: str = "weight"
) -> pl.DataFrame:
    return (
        df.group_by(expr)
        .agg(
            n_obs=pl.len(),
            n_persons=pl.col(weight).sum(),
        )
        .with_columns(
            share_persons=pl.col("n_persons") / pl.col("n_persons").sum(),
        )
        .sort("share_persons", descending=True)
    )


def main():
    trips = clean_data()
    ridesharing_driver_analysis(trips)
    ridesharing_passenger_analysis(trips)
    intermodality_analysis(trips)


if __name__ == "__main__":
    main()
