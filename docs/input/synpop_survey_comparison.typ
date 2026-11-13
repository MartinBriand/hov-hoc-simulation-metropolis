// Comparison of the synthetic population with the travel survey.
//
// The data is outside of this directory, so compile from the root of the repository with:
//   typst compile --root . docs/input/synpop_survey_comparison.typ

#let survey = json("../../output/synpop/calibration/survey/characteristics.json")
#let synpop = json("../../output/synpop/demand/population/characteristics.json")

// ---------- Number formatting ----------

// 1234567.8 -> "1 234 568"
#let thousands(value) = {
  str(int(calc.round(value))).rev().clusters().chunks(3).map(c => c.join()).join(sym.space.nobreak.narrow).rev()
}

// (2.5, 2) -> "2.50"
#let fixed(value, digits) = {
  let (whole, ..decimals) = str(calc.round(value, digits: digits)).split(".")
  if digits == 0 { return whole }
  whole + "." + ((decimals + ("",)).first() + "0" * digits).slice(0, digits)
}

// (2.5, 1) -> "+2.5"
#let signed(value, digits) = (if value < 0 { "−" } else { "+" }) + fixed(calc.abs(value), digits)

// 30600 -> "8:30" (hours above 24 are on the next day)
#let hhmm(seconds) = {
  let minutes = int(calc.round(seconds / 60))
  let rest = calc.rem(minutes, 60)
  str(calc.quo(minutes, 60)) + ":" + (if rest < 10 { "0" }) + str(rest)
}

#let percent(value) = fixed(value * 100, 1) + " %"

// ---------- Kinds of value: how to show a value, and the survey-synpop difference ----------

#let relative(a, b) = if a == 0 { "–" } else { signed((b / a - 1) * 100, 1) + " %" }
#let points(a, b) = signed((b - a) * 100, 1) + " pp"

#let count = (format: thousands, diff: relative)
#let number(digits) = (format: value => fixed(value, digits), diff: relative)
#let share = (format: percent, diff: points)
#let clock = (format: hhmm, diff: (a, b) => signed((b - a) / 60, 0) + " min")
#let meters-as-km = (format: value => fixed(value / 1000, 2), diff: relative)
#let meters-as-million-km = (format: value => fixed(value / 1e9, 1), diff: relative)

// ---------- Tables ----------

#let panel(title, body, note: none) = block(breakable: false, width: 100%, below: 1.4em)[
  #strong(title)
  #v(-0.4em)
  #body
  #if note != none { text(size: 0.85em, style: "italic", note) }
]

#let header(..cells) = table.header(..cells.pos().map(strong))

// Compares statistics. Each row is (label, path of the statistic in `section`, kind of value).
// With a `section` of `none`, the paths start from the root of the data.
#let stat-table(title, section, rows) = panel(title, table(
  columns: (1fr, 2.6cm, 2.6cm, 2.6cm),
  header([Statistic], [Survey], [Synpop], [Difference]),
  ..rows
    .map(((label, path, kind)) => {
      let full-path = if section == none { path } else { (section, ..path) }
      let a = full-path.fold(survey, (data, key) => data.at(key))
      let b = full-path.fold(synpop, (data, key) => data.at(key))
      (label, (kind.format)(a), (kind.format)(b), (kind.diff)(a, b))
    })
    .flatten(),
))

// Compares two distributions, given as dictionaries of totals by category. `labels` gives the
// categories to show: shares are computed over these categories only. A category which is missing
// from one of the distributions has a total of zero.
#let distribution-table(title, labels, survey-totals, synpop-totals, value: "count", note: none) = {
  let total-of(key, totals) = totals.at(key, default: 0)
  let sum(totals) = labels.keys().map(key => total-of(key, totals)).sum()
  let rows = labels
    .pairs()
    .filter(((key, _)) => total-of(key, survey-totals) + total-of(key, synpop-totals) > 0)
    .map(((key, label)) => {
      let a = total-of(key, survey-totals)
      let b = total-of(key, synpop-totals)
      let share-a = a / sum(survey-totals)
      let share-b = b / sum(synpop-totals)
      (label, thousands(a), thousands(b), percent(share-a), percent(share-b), points(share-a, share-b))
    })
  panel(title, note: note, table(
    columns: (1fr, 2cm, 2cm, 1.6cm, 1.6cm, 2cm),
    header([Category], [Survey #value], [Synpop #value], [Survey share], [Synpop share], [Difference]),
    ..rows.flatten(),
  ))
}

#let category-table(title, section, variable, labels, note: none) = distribution-table(
  title,
  labels,
  survey.at(section).at(variable).counts,
  synpop.at(section).at(variable).counts,
  note: note,
)

// The rows of a numeric variable with a distribution.
#let distribution-rows(variable, kind) = (
  ("Mean", (variable, "mean"), kind),
  ("Minimum", (variable, "min"), kind),
  ("First quartile", (variable, "q1"), kind),
  ("Median", (variable, "median"), kind),
  ("Third quartile", (variable, "q3"), kind),
  ("Maximum", (variable, "max"), kind),
)

// ---------- Labels of the categories ----------

// INSEE grille communale de densité, levels of `DENS7`.
#let densities = (
  "1": "Large urban centers",
  "2": "Intermediate urban centers",
  "3": "Small towns",
  "4": "Urban belts",
  "5": "Rural towns",
  "6": "Dispersed rural",
  "7": "Very dispersed rural",
)
#let urban-types = (
  "central_city": "Central city",
  "suburb": "Suburb",
  "isolated_city": "Isolated city",
  "outside_urban_unit": "Outside urban unit",
)
#let functional-area-types = (
  "11": "Central municipality",
  "12": "Other municipality of the main pole",
  "13": "Municipality of a secondary pole",
  "20": "Commuting belt",
  "30": "Outside functional areas",
)
// Coding of MobiSurvStd, in reverse order of the INSEE coding.
#let functional-area-categories = (
  "1": "Paris",
  "2": "700 000 inhabitants or more",
  "3": "200 000 to 700 000 inhabitants",
  "4": "50 000 to 200 000 inhabitants",
  "5": "Less than 50 000 inhabitants",
)
#let education-levels = (
  "no_studies_or_no_diploma": "No studies or no diploma",
  "primary": "Primary",
  "secondary:no_bac": "Secondary, without baccalauréat",
  "secondary:bac": "Secondary, with baccalauréat",
  "higher:at_most_bac+2": "Higher, at most bac+2",
  "higher:at_least_bac+3": "Higher, at least bac+3",
)
#let professional-activities = (
  "full_time_worker": "Full-time worker",
  "part_time_worker": "Part-time worker",
  "student": "Student",
  "retired": "Retired",
  "under14": "Under 14",
  "other": "Other",
)
// Classes 7 (retired) and 8 (other inactive) are left out as the survey only has workers.
#let socioprofessional-classes = (
  "1": "Farmers",
  "2": "Craftspeople, shopkeepers, business owners",
  "3": "Managers and higher professions",
  "4": "Intermediate professions",
  "5": "Employees",
  "6": "Blue-collar workers",
)
#let purposes = (
  "home": "Home",
  "work": "Work",
  "education": "Education",
  "shopping": "Shopping",
  "task": "Task",
  "leisure": "Leisure",
  "escort": "Escort",
  "other": "Other",
)

// ---------- Document ----------

#set document(title: "Synthetic population and travel survey comparison")
#set page(paper: "a4", margin: 2cm, numbering: "1")
#set text(size: 10pt, number-type: "lining", number-width: "tabular")
#set par(justify: true)
#show table: set par(justify: false)
#show table: set text(hyphenate: false)
#set heading(numbering: "1.")
#show heading.where(level: 1): set block(above: 1.8em, below: 1em)

#set table(
  stroke: none,
  inset: (x: 5pt, y: 3.5pt),
  align: (x, _) => if x == 0 { left } else { right },
  fill: (_, y) => if y == 0 { luma(225) } else if calc.even(y) { luma(245) },
)

#align(center, text(size: 17pt, weight: "bold")[Synthetic population and travel survey comparison])
#v(0.6em)

Survey values are weighted to represent the whole population, from a sample of
#thousands(survey.households.sample_count) households,
#thousands(survey.persons.sample_count) persons,
#thousands(survey.tours.sample_count) tours and
#thousands(survey.trips.sample_count) trips.
The survey is restricted to the households living in the simulation area and the synthetic
population is restricted to the households living in the survey area.
The survey area (Toulouse's urban area) is slightly smaller than the synthetic population area (Toulouse' functional area).

Differences are synthetic population minus survey: relative differences (%) for quantities, percentage
points (pp) for shares and minutes for times of day. Shares of a category exclude missing values.

= Overview

#stat-table("Population size", none, (
  ("Households", ("households", "count"), count),
  ("Persons", ("persons", "count"), count),
  ("Tours", ("tours", "count"), count),
  ("Trips", ("trips", "count"), count),
))

= Households

#stat-table("Household characteristics", "households", (
  ("Persons per household", ("nb_persons", "mean"), number(2)),
  ("Driving licenses per household", ("nb_driving_licenses", "mean"), number(2)),
  ("Cars: total", ("nb_cars", "total"), count),
  ("Cars: mean per household", ("nb_cars", "mean"), number(2)),
  ("Cars: share of households with at least one", ("nb_cars", "share_positive"), share),
  ("Motorcycles: total", ("nb_motorcycles", "total"), count),
  ("Motorcycles: mean per household", ("nb_motorcycles", "mean"), number(3)),
  ("Motorcycles: share of households with at least one", ("nb_motorcycles", "share_positive"), share),
  ("Bicycles: total", ("nb_bicycles", "total"), count),
  ("Bicycles: mean per household", ("nb_bicycles", "mean"), number(2)),
  ("Bicycles: share of households with at least one", ("nb_bicycles", "share_positive"), share),
))

#category-table("Home density", "households", "home_density", densities)
#category-table("Home urban type", "households", "home_urban_type", urban-types)
#category-table("Home functional area type", "households", "home_functional_area_type", functional-area-types)
#category-table("Home functional area category", "households", "home_functional_area_category", functional-area-categories)

= Persons

#stat-table("Person characteristics", "persons", (
  ("Share of women", ("woman", "share"), share),
  ("Share with a driving license", ("has_driving_license", "share"), share),
  ("Share with a public-transit subscription", ("has_public_transit_subscription", "share"), share),
  ("Trips per person", ("nb_trips", "mean"), number(2)),
))
#stat-table("Age (years)", "persons", distribution-rows("age", number(1)))

#category-table("Education level", "persons", "education_level", education-levels)
#category-table("Professional activity", "persons", "professional_activity", professional-activities)
#category-table(
  "Socioprofessional class",
  "persons",
  "socioprofessional_class",
  socioprofessional-classes,
  note: [Workers only: the shares of the synthetic population are recomputed over classes 1 to 6.],
)

= Tours

#stat-table("Tour characteristics", "tours", (("Trips per tour", ("nb_trips", "mean"), number(2)),))

= Trips

#stat-table("Origin-destination distance (km, as the crow flies)", "trips", (
  ("Total (million km)", ("od_distance", "total"), meters-as-million-km),
  ..distribution-rows("od_distance", meters-as-km),
))
#stat-table("Departure time", "trips", distribution-rows("departure_time", clock))
#stat-table("Arrival time", "trips", distribution-rows("arrival_time", clock))

#category-table("Origin purpose", "trips", "origin_purpose_group", purposes)
#category-table("Destination purpose", "trips", "destination_purpose_group", purposes)

#let hours-by-purpose(data) = {
  data.trips.activity_durations.pairs().map(((purpose, duration)) => (purpose, duration.total / 3600)).to-dict()
}
#distribution-table(
  "Total activity duration by purpose (hours)",
  purposes,
  hours-by-purpose(survey),
  hours-by-purpose(synpop),
  value: "hours",
)

#category-table("Origin density", "trips", "origin_density", densities)
#category-table("Destination density", "trips", "destination_density", densities)
#category-table("Origin urban type", "trips", "origin_urban_type", urban-types)
#category-table("Destination urban type", "trips", "destination_urban_type", urban-types)
#category-table("Origin functional area type", "trips", "origin_functional_area_type", functional-area-types)
#category-table("Destination functional area type", "trips", "destination_functional_area_type", functional-area-types)
#category-table("Origin functional area category", "trips", "origin_functional_area_category", functional-area-categories)
#category-table("Destination functional area category", "trips", "destination_functional_area_category", functional-area-categories)
