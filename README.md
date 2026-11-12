# hov-hoc-simulation-metropolis
This is a repository to test the impact of a HOC / HOV in a territory. At the time of writing, we are still not sure whether we will choose the territory of Toulouse or Nice.

## Running the project
To run the project, we recommend using uv.

Run `uv sync` and your environment with correct dependencies will be installed and ready to go. Note that you will need a `c` compiler (such as `gcc`) for some dependencies to be built.

Then, you must precede all Python commands by a `uv run` (see `uv` documentation online). Scripts in `scripts` already have the `uv run` prefix and can therefore be executed as such.

### Preparing synthetic population

### Getting OpenStreetMap network

Go to the [Geofabrik website](https://download.geofabrik.de/europe/france/provence-alpes-cote-d-azur.html), click on "raw directory index" (last bullet point), and download `provence-alpes-cote-d-azur-261111.osm.pbf`. Save it in `data/osm`. This is the full map of the "Provence Alpes Côte d'Azur" region (very nice to visit by the way), in which the Nice Survey area is fully contained. Only a portion of the data will be used to build the network.
