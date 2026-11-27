# hov-hoc-simulation-metropolis
This is a repository to test the impact of a HOC / HOV in a territory. At the time of writing, we are still not sure whether we will choose the territory of Toulouse or Nice.

## Setting up the project
To run the project, we recommend using uv.

Run `uv sync` and your environment with correct dependencies will be installed and ready to go. Note that you will need a `c` compiler (such as `gcc`) for some dependencies to be built.

Then, you must precede all Python commands by a `uv run` (see `uv` documentation online). Scripts in `scripts` already have the `uv run` prefix and can therefore be executed as such.


[Typst](https://typst.app/docs/) file should be compiled from the root directory with `typst compile --root . docs/FILE.typ`.

## Repository structure

- `data/` *(not commited)*
  - `emc2-2023-toulouse.zip`: household-travel survey **Not open-data. If you don't have access to it, you can use the [national EMP 2019 survey](https://www.statistiques.developpement-durable.gouv.fr/resultats-detailles-de-lenquete-mobilite-des-personnes-de-2019) as a substitute.**
  - OpenStreetMap data
  - `gtfs/`: GTFS feeds of the transit networks of the study area (see [Getting the GTFS feeds](#getting-the-gtfs-feeds))
- `docs/`: LaTeX and Typst files
- `eqasim/`:
  - `output/`: Generated synthetic population *(not commited)*
  - `config_eqasim.yml`: Eqasim configuration used to generate the synthetic population
- `output/`: Output files, excluding the Eqasim and Pymetropolis output.
- `pymetropolis/`: Configurations and output directories of the Pymetropolis runs.
- `python/`: Various Python scripts.
- `scripts/`: Unix commands to run various processing steps.

## Replicating the complete results

### Preparing synthetic population

Follow the instructions from the [Eqasim-France repository](https://github.com/eqasim-org/eqasim-france).
The Eqasim configuration used to generate the synthetic population is available at [eqasim/config_eqasim.yml](eqasim/config_eqasim.yml).


### Getting the OpenStreetMap network

Go to the [Geofabrik website](https://download.geofabrik.de/europe/france/provence-alpes-cote-d-azur.html), click on "raw directory index" (last bullet point), and download `provence-alpes-cote-d-azur-260101.osm.pbf`. Save it in `data/osm`. This is the full map of the "Provence Alpes Côte d'Azur" region (very nice to visit by the way), in which the Nice Survey area is fully contained. Only a portion of the data will be used to build the network.

### Getting the GTFS feeds

On November 13th, 2026, we downloaded the eight GTFS feeds below from [transport.data.gouv.fr](https://transport.data.gouv.fr) (the French national access point for transport open data), and saved them in `data/gtfs`. Producers overwrite their files on every schedule update, so re-downloading today would give different, possibly incompatible, data. transport.data.gouv.fr offers permalinks to the archived versions of each dataset; the permalinks of the downloaded versions are listed in the table below. We are however not confident that these permalinks will remain valid in the long term, so we will also publish the downloaded archives themselves online at the time of publication. (TODO).

| File | Network | Dataset (transport.data.gouv.fr) | Permalink (archive of Nov 13, 2026) | License |
|---|---|---|---|---|
| `GTFS_sibr_production_zou_proximite.zip` | ZOU ! interurban proximity buses | [Réseau interurbain bus Proximité ZOU !](https://transport.data.gouv.fr/datasets/lignes-des-reseaux-transport-zou-provence-alpes-cote-d-azur-proximite-3-3) | [Link](https://transport-data-gouv-fr-resource-history-prod.cellar-c2.services.clever-cloud.com/82137/82137.20261113.062531.500148.zip) | Licence Ouverte v2 |
| `GTFS_sibr_production_zou_express.zip` | ZOU ! interurban express coaches | [Réseau interurbain Express ZOU !](https://transport.data.gouv.fr/datasets/lignes-des-reseaux-transport-zou-provence-alpes-cote-d-azur-express-3-3) | [Link](https://transport-data-gouv-fr-resource-history-prod.cellar-c2.services.clever-cloud.com/82285/82285.20261113.062843.259248.zip) | Licence Ouverte v2 |
| `zou_train_transdev.zip` | Transdev Rail Sud Intermétropole line (Nice–Marseille) | [Trains régionaux ZOU ! - Transdev Rail Sud Intermétropole](https://transport.data.gouv.fr/datasets/zou) | [Link](https://transport-data-gouv-fr-resource-history-prod.cellar-c2.services.clever-cloud.com/83448/83448.20261112.121740.053528.zip) | Licence Ouverte v2 |
| `nice_lignes_dazur.zip` | Lignes d'Azur (Nice buses and tramways) | [Réseau urbain Lignes d'Azur](https://transport.data.gouv.fr/datasets/donnees-statiques-et-dynamiques-du-reseau-de-transport-lignes-dazur) | [Link](https://transport-data-gouv-fr-resource-history-prod.cellar-c2.services.clever-cloud.com/83178/83178.20261113.002632.563646.zip) | Licence Ouverte v2 |
| `envibus.zip` | Envibus (Antibes, Sophia Antipolis) | [Réseau urbain ENVIBUS](https://transport.data.gouv.fr/datasets/arrets-horaires-et-parcours-theoriques-des-bus-du-reseau-des-transports-publics-envibus) | [Link](https://transport-data-gouv-fr-resource-history-prod.cellar-c2.services.clever-cloud.com/79342/79342.20261113.062521.015918.zip) | **ODbL 1.0** |
| `palmbus-cannes-fr.zip` | Palmbus (Cannes) | [Réseau urbain Palmbus](https://transport.data.gouv.fr/datasets/horaires-theoriques-et-temps-reel-gtfs-gtfs-rt-du-reseau-palmbus-cannes-pays-de-lerins) | [Link](https://transport-data-gouv-fr-resource-history-prod.cellar-c2.services.clever-cloud.com/79420/79420.20261027.070933.430655.zip) | Licence Ouverte v2 |
| `urbain_sillages.zip` | Sillages (Pays de Grasse, urban) _download only urban archive_ | [Réseau urbain et scolaire Sillages](https://transport.data.gouv.fr/datasets/lignes-regulieres-de-transports-sillages-en-pays-de-grasse-urbain-et-scolaire) | [Link](https://transport-data-gouv-fr-resource-history-prod.cellar-c2.services.clever-cloud.com/79822/79822.20260907.141136.542081.zip) | Licence Ouverte v2 |
| `zest.zip` | Zest (Menton, Riviera Française) | [Réseau urbain Zest](https://transport.data.gouv.fr/datasets/horaires-reseau-zest) | [Link](https://transport-data-gouv-fr-resource-history-prod.cellar-c2.services.clever-cloud.com/79559/79559.20261028.085145.915835.zip) | Licence Ouverte v2 |

The license texts are stored in `data/gtfs/licenses/`: `etalab-licence-ouverte-v2.0.{pdf,txt}` for the Licence Ouverte v2 (official text from [Etalab](https://www.etalab.gouv.fr/wp-content/uploads/2017/04/ETALAB-Licence-Ouverte-v2.0.pdf)) and `odbl-10.txt` for the ODbL 1.0 (official plain text from [Open Data Commons](https://opendatacommons.org/licenses/odbl/1-0/)).

Notes:

- You may also encounter the [Trains régionaux ZOU !](https://transport.data.gouv.fr/datasets/trains-zou-en-provence-alpes-cote-dazur) dataset (regional trains, TER) on transport.data.gouv.fr. It is **not** downloaded: all its journeys are already contained in the ZOU Express and Transdev feeds above (the Transdev export being the more complete one for its line).
- The Sillages dataset publishes its urban and its school services as two separate archives; we downloaded the urban one only, and saved it as `urbain_sillages.zip`. Its `SCO_*` / `PVS_*` / `COMP_*` service ids encode calendar variants of the regular urban lines (school term / school holidays / all-year), not school-bus services.

### Merging the GTFS feeds

> **Scope:** `python/merge_gtfs_nice.py` is written for the specific feeds of the table above (downloads of November 13, 2026). Some of its rules — demand-responsive routes identified by the "PAD" name prefix of Palmbus — are heuristics calibrated on this data only. Adapt them before using the script on other GTFS archives.

The eight feeds above are unified into a single GTFS by `python/merge_gtfs_nice.py`, run from the root directory through `uv`:

```
# Don’t execute this command.
# This command is there just to explain the underlying process of the next command which you can execute.
uv run python python/merge_gtfs_nice.py --start-date YYYYMMDD --end-date YYYYMMDD
```

The command above, which is invoked in another command below requires a time window, e.g. `--start-date 20261207 --end-date 20261211` for the study week (Monday December 7th to Friday December 11th, inside the intersection of all feeds). The script checks the given time is within the intersection of the timeframes of the provided gtfs, before merging gtfs in the provided window.

```
./scripts/merge_gtfs_nice.sh
```

The reason why the specific week above was chosen is due to the download date of the gtfs files (November 13th 2026). At that time in France, there were major social movements, including demonstrations and strikes. Consequently, disruptions in public transport could be hidden in the schedules provided by the files. To make sure we were treating public transportation services of a "normal week", we wanted to look far enough to make sure public agencies had no knowledge of a potential service disruption at these dates. However, some roadworks or trainworks already scheduled might still be integreted in the original gtfs files. These works are late in the night though, and our simulation would therefore not suffer much from them.

The merged feed is written to `data/gtfs/merge_output/nice_area.zip`; the `merge_output` folder keeps it separate from the original downloads. `--output` allows another location, `--input-dir`
another source directory. During the merge:

- every id is preserved and namespaced with its network (`zou_prox:...`, `dazur:...`), so that ids remain globally unique;
- services are restricted to the requested window: calendars are clipped, calendar dates outside the window are removed, and trips that do not run in the window are dropped;
- only scheduled trains and buses are kept (tram, train, bus and trolleybus route types): the demand-responsive routes (Palmbus "Palm à la demande") are removed, and the vendor route types are normalized (Lignes d'Azur scheduled village coach lines to bus, Transdev trains to train);
- the trips exported by several feeds are deduplicated (the ZOU Express feed re-exports some of the
  intercity journeys of the Transdev feed), both by journey id and by identical itinerary, the
  Transdev feed having priority;
- routes without trips, agencies without routes and per-network files (fares, private extensions) are dropped; a synthetic `feed_info.txt` describes the merged feed.

### Running the Pymetropolis simulations

*(To be done)*.

## Extra

- `pymetropolis/synpop.toml`: Simple Pymetropolis configuration to import the synthetic population
  and household travel survey and store their characteristics. There is no road network or
  Metropolis simulation. The characteristics files can be compared with
  `docs/input/synpop_survey_comparison.typ`.
- `python/analyse_survey.py`: Python script to print descriptive statistics on ridesharing and
  intermodality from the input household travel survey.
