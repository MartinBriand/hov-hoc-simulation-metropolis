# hov-hoc-simulation-metropolis
This is a repository to test the impact of a HOC / HOV in a territory. At the time of writing, we are still not sure whether we will choose the territory of Toulouse or Nice.

## Running the project
To run the project, we recommend using uv.

Run `uv sync` and your environment with correct dependencies will be installed and ready to go. Note that you will need a `c` compiler (such as `gcc`) for some dependencies to be built.

Then, you must precede all Python commands by a `uv run` (see `uv` documentation online). Scripts in `scripts` already have the `uv run` prefix and can therefore be executed as such.

[Typst](https://typst.app/docs/) file should be compiled from the root directory with
`typst compile --root . docs/FILE.typ`.

## Repository structure

- `data/` *(not commited)*
  - `emc2-2023-toulouse.zip`: household-travel survey **Not open-data. If you don't have access to
    it, you can use the
    [national EMP 2019 survey](https://www.statistiques.developpement-durable.gouv.fr/resultats-detailles-de-lenquete-mobilite-des-personnes-de-2019)
    as a substitute.**
  - OpenStreetMap data
  - GTFS files
- `docs/`: LaTeX and Typst files
- `eqasim/`:
  - `output/`: Generated synthetic population *(not commited)*
  - `config_eqasim.yml`: Eqasim configuration used to generate the synthetic population
- `output/`: Output files, excluding the Eqasim and Pymetropolis output.
- `pymetropolis/`: Configurations and output directories of the Pymetropolis runs.
- `scripts/`: Unix commands to run various processing steps.

## Replicating the complete results

1. Generate the synthetic population.

Follow the instructions from the
[Eqasim-France repository](https://github.com/eqasim-org/eqasim-france).
The Eqasim configuration used to generate the synthetic population is available at
[eqasim/config_eqasim.yml](eqasim/config_eqasim.yml).

2. Pymetropolis run *(To be done)*.

## Extra

- `pymetropolis/synpop.toml`: Simple Pymetropolis configuration to import the synthetic population
  and household travel survey and store their characteristics. There is no road network or
  Metropolis simulation. The characteristics files can be compared with
  `docs/input/synpop_survey_comparison.typ`.
