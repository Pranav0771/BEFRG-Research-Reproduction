# External research data (not redistributed)

## Montoya et al. benchmark
Source: https://www.vrp-rep.org/datasets/item/2016-0020.html
Download the original non-linear charging EVRP benchmark and extract XML files into `data/raw/montoya/`. Example expected filename: `tc1c320s38ct2.xml` (nested folders are supported). The original archive is **not** included in this repository. The independent parser is `befrg.data.read_montoya_xml`.

## San Francisco taxi traces
Source: https://doi.org/10.15783/C7J010 (CRAWDAD EPFL mobility/San Francisco taxis). Put the downloaded archive under `data/raw/crawdad/` and document its checksum. The provided Phase 2 Experiment H is a **synthetic, time-dependent traffic substitute**. The original SUMO/TraCI experiment was **not run**; a controller skeleton is in `simulators/traci_controller.py`.

## OpenStreetMap
For locally configured SUMO experiments, place legally acquired road-network extracts under `data/raw/osm/`. The Phase 4 scenarios do not use OSM; their coordinates are synthetic.

### Important reproducibility qualification
The paper does not fully specify vehicle mass, the coefficient theta, route construction/tie-breaking, or every simulator setting. Using original XML files alone is **insufficient** to guarantee numerical parity with the paper. Document each chosen value. Do not call `--full` results reproduced until these inputs have been aligned and validated.

## New extension validation using these original XMLs

After extracting the needed Montoya XML into `data/raw/montoya`, run:

```bash
python -m experiments.montoya_extension_validation --suite all --output results/my_montoya_extension1
```

This is a matched-tour comparison **within our independently generated route**, not a direct numerical reproduction of the original paper's route. The new `results/montoya_extension1` data in the ZIP are already calculated; source XML remains user-managed and is not redistributed.
