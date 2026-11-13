* [ ] Make sure the buffer does work well
* [ ] What is the use of buffering urban areas? Is it done correctly (not consistent between parameters and Chambéry example). What is the purpose of saying that a road is "urban"?
* [ ] Why do you say that simulation_ratio does not affect synthetic population once generated?
* [ ] what is the network for pedestrians and bikes? --> is my doing correct?
* [ ] I think you should add default values in parameters definition
* [ ] Should I remove duplicates of network?
* [ ] What is the purpose of "ign" variables?
* [ ] What are joint_travel variables? --> for carpooling I guess?
* [ ] Which model is best?
* [ ] Is my list of available modes correct?
* [ ] Where is the option not to travel?
* [ ] Why is the outside option on the normal network?
* [ ] Define park and ride facilities?
* [ ] Why are Open Trip Planner VOT different from those of normal modal choice.
* [ ] I already have `bicycle_network.forbidden_types`. What is the difference with `osm_bicycle_import.highways`?
* [ ] What happens if I do not ensure that pedestrian or bicycle networks are connected?
* [ ] How to I add bicycle lane and pedestrian for these modes.
* [ ] Why the traffic simulation algorithm does not have its own executable?
* [ ] What is `r5`?
* [ ] In default capacities and default speed limits, am I supposed to tell the toml file for every road type, or is `road` a fallback catch all option?
* [ ] Should i remove duplicates for networks? I mean, am I sure deleting a duplicate for network 1 will not remove it for network 2?
* [ ] What exactly is an HOV lane?
* [ ] What is the interest of having primary and secondary types in road_network (i don’t mean in OSM).
* [ ] Is the backward wave speed the correct way to express the phenomenon?
* [ ] What is the ExponentialThenExponential model?
* [ ] What are nice learning factors?
* [ ] Is it correct to have a learning interval that is the same as the simulation interval?
* [ ] Headway vs PCE VS ridesharing passenger count?
* [ ] What are the zone files?
* [ ] Other TODO in config-nice.toml.
* [ ] Create the gtfs files
