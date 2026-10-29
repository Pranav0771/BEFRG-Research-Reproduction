# Phase 4 — Four additional EV charging use cases

> **Provenance: [ours-scaled-down].** All route coordinates, station positions, charging curves, speed, loads, and consumption parameters are **synthetic**, defined in `experiments/phase4.py` and reproduced in `results/phase4/scenario_inputs.json`. These results are **not** observations on real Indian roads, OSM routes, original Montoya instances, or measured battery performance. They were computed with this repository's Phase 3 physical-SoC label DP on 2026-10-28.

## Experimental procedure and guarantee

All scenarios use a *fixed*, closed delivery/service route with depot repeated at the start and end. For each arc, either travel directly or insert **at most one** charger. At stations the solver may charge only to one of `gamma` target levels; route-node SoC is **not floored**. Charging target must be strictly greater than the actual physical arrival SoC. A separate validator replays all actions and checks arrival charge, charge targets, positive SoC at route nodes, travel and charging times, and objective consistency. With no label-beam pruning (the default), the solver returns the optimum **within the finite target-level model**, not a continuous-charging optimum or an EVRP optimum. `--quick` may cap labels and cannot guarantee optimality where pruning is triggered.

The synthetic three-segment charger curves have breakpoints at 0%, 80%, 95%, 100% SoC, with segment charging durations `60*delta_kWh/mean_kW` minutes. These are invented engineering illustrations, not OEM battery charging maps. HVAC energy applies *while driving*, and thermal/aging assumptions are those in `befrg/thermal.py`. The degradation objective is time-equivalent cost, not a prediction of capacity loss. Each route is defined in planar kilometre coordinates and evaluated with Euclidean distances (not measured road-network distances). A fixed pseudoseed is recorded for consistency, but these coordinates are deterministically hand constructed; no randomness is used in defining them.

## Scenarios and executed results

| Scenario | Variant | Route time (min) | Charge (kWh) | Detours | Usable battery (kWh) | Degradation equivalent (min) | Certified / replay valid |
|---|---|---:|---:|---:|---:|---:|---|
| last_mile | mixed_ac_dc | 244.89 | 4.95 | 1 | 10.24 | 0.00 | yes |
| last_mile | ac_only | 357.96 | 5.67 | 2 | 10.24 | 0.00 | yes |
| last_mile | cold_mixed | 347.58 | 10.14 | 4 | 7.36 | 7.55 | yes |
| coach | all_roadside | 612.20 | 270.96 | 3 | 220.00 | 0.00 | yes |
| coach | one_fast_closed | 634.81 | 270.84 | 2 | 220.00 | 0.00 | yes |
| coach | hot_weather | 637.28 | 322.56 | 3 | 214.06 | 7.07 | yes |
| truck | loaded | 815.06 | 451.28 | 3 | 420.00 | 0.00 | yes |
| truck | empty_payload_control | 780.15 | 333.67 | 2 | 420.00 | 0.00 | yes |
| truck | cold_loaded | 913.49 | 568.56 | 3 | 301.88 | 23.46 | yes |
| outage | sparse_one | 336.28 | 14.94 | 1 | 16.00 | 0.00 | yes |
| outage | medium_two | 229.30 | 10.78 | 2 | 16.00 | 0.00 | yes |
| outage | dense_five | 207.67 | 9.15 | 1 | 16.00 | 0.00 | yes |
| outage | dc_mid_outage | 216.73 | 10.88 | 2 | 16.00 | 0.00 | yes |

All values in the table above originate from the executed CSV. The source command was `python -m experiments.phase4 --output results/phase4`. CSV numeric values preserve greater precision than the display table. Total physical route time includes driving and charging, not degradation-equivalent cost; the latter appears separately in `optimized_objective_min`.

## 1. Synthetic Indian urban cargo three-wheeler

**Story.** A six-drop cargo delivery route departs from and returns to a fictional urban depot. It has a 10.24-kWh battery, 520-kg unloaded vehicle mass, 185-kg delivery consignment mass, 30-km/h average speed, and a 0.11-kWh/km empty traction assumption. The direct route spans approximately 115.94 km, exceeding the nominal battery's modeled direct-route energy requirement. Two synthetic 3.3-kW AC chargers are available; a third **hypothetical** 25-kW DC charger is added in the mixed scenario. We do **not** claim an actual three-wheeler accepts that DC charger; compatibility, ports, safety and charge acceptance must be verified for a real use case.

The order-of-magnitude battery reference comes from Mahindra Zor Grand documentation (10.24 kWh; about four hours on standard charging): https://mahindra.etgocorp.in/assets/pdf/zor-grand-cargo.pdf . All remaining numerical choices are our scenario design, not derived from this document.

**Results.** AC-only takes **357.96 min**, while mixed access takes **244.89 min**, a modeled **113.07-minute improvement**. At 0°C with reduced usable capacity, HVAC demand and nonzero degradation penalty, physical time rises to **347.58 min**. The cold-model charge total and detour count increase compared with the baseline.

**What this teaches:** When charging power differs dramatically, detour time alone is not enough to select a station. Nonlinear charging and temperature-related energy shortages can dominate the choice. However, the DC-compatibility assumption is unverified and this is not a product-specific operational recommendation.

Figures: `results/phase4/last_mile_comparison.png`, `results/phase4/last_mile_geometry.png`.

## 2. Battery-electric regional coach

**Story.** A fictitious intercity closed loop has six service stops, a 220-kWh battery, 12,000-kg unloaded mass, 66-km/h modeled average speed, and 0.92-kWh/km empty traction consumption. Three roadside charging locations use illustrative 90–150-kW-class input-power curves. Passenger boarding, changing passenger mass, mandatory driver breaks, charging queues and waiting times are **not modeled**; station visits are the only decision points. The zero loads in this case are intentional.

The battery scale is similar to published Skoda PERUN HE electric-bus battery capacity (222 kWh), but no other characteristics are being attributed to that model: https://www.skodagroup.com/reference/electric-bus-with-standard-charging .

**Results.** With all chargers, the route takes **612.20 min**, while closing one high-power roadside station increases it to **634.81 min**. The modeled hot-weather case takes **637.28 min**.

**What this teaches:** On long routes, charger availability can change the chosen charging levels and where the vehicle replenishes energy even without changing customer or stop order. The route does not address bus timetable constraints or real highway topology.

Figures: `results/phase4/coach_comparison.png`, `results/phase4/coach_geometry.png`.

## 3. Heavy-duty electric delivery truck

**Story.** A synthetic 663.66-km closed freight loop visits six delivery sites and delivers 6,100 kg over the tour. An illustrative truck with a 420-kWh battery, 16,000-kg empty mass, 57-km/h travel speed and 1.04-kWh/km empty energy rate can visit four invented 120–250-kW-class DC chargers. The counterfactual retains the same vehicle, charging network, speed and route geometry but sets delivery load to zero. The loaded vs empty comparison isolates the effect of the model's mass-dependent traction energy, not a realistic end-to-end freight cost analysis. Assumed payload capacity is at least 6,100 kg; the `Problem` object does not model axle-load or gross-weight constraints.

Commercial heavy-electric-truck batteries span several hundred kWh, according to Scania's current product specifications: https://www.scania.com/group/en/home/products-and-services/trucks/battery-electric-truck.html . Our 420-kWh battery and load are independent synthetic values.

**Results.** Fully loaded delivery time is **815.06 min**, compared with **780.15 min** with zero deliveries, i.e. **34.91 min** longer. Cold-weather loaded operation takes **913.49 min**.

**What this teaches:** Load-dependent energy consumption creates meaningful differences between freight and lighter-service routes. Thermal derating can compound these effects. However, the paper's mass-linear traction equation is too simplified for validated heavy-truck predictions (no air drag, grades, speed variability or regen).

Figures: `results/phase4/truck_comparison.png`, `results/phase4/truck_geometry.png`.

## 4. Station density and deterministic outage

**Story.** On an artificial peri-urban six-drop loop using a 16-kWh delivery van, the allowed charger set is expanded in nested order: one station, two stations, and five stations. A fourth case closes the high-power `dc_mid` station within the five-station network. The same customer order, charging curves of remaining stations, and energy assumptions are used in every comparison. Note: `dc_mid` is a synthetic station label, not a real public charging facility.

**Results.** Route times are **336.28**, **229.30**, and **207.67 min**, respectively. Removing `dc_mid` from the dense network increases time to **216.73 min**.

**What this teaches:** The benefit of adding charging stations is not simply reducing the count of stops; better station power and placement enable different charging choices. With no queues and a nested candidate set, adding stations cannot worsen the exact finite-grid optimal objective. A station outage can increase RT without causing infeasibility.

Figures: `results/phase4/outage_comparison.png`, `results/phase4/outage_geometry.png`.

## Cross-case charging-policy baseline

Each base scenario was additionally solved with full charging (FC) and discrete partial charging (DPC) with the **same** fixed route, charger set, target resolution, and ambient temperature. The exact-SoC solver is used for both. No penalty is active in these baseline comparisons.

| Scenario | FC time (min) | DPC time (min) | Time improvement of DPC (min) |
|---|---:|---:|---:|
| last_mile | 255.13 | 244.89 | 10.24 |
| coach | 694.72 | 612.20 | 82.53 |
| truck | 880.69 | 815.06 | 65.63 |
| outage | 213.53 | 207.67 | 5.87 |

These comparisons are expected to favor or tie DPC because the full-charge action set is contained in the DPC action set. They are an internal model-consistency check, not a field performance claim.

## Reproducibility

```bash
python -m pip install -e '.[test]'
python -m pytest
python -m experiments.phase4 --config configs/phase4.yaml --output results/phase4
# Optional bounded-beam smoke test, not guaranteed optimal if pruning occurs:
python -m experiments.phase4 --quick --output results/phase4_quick
```

Outputs: `use_cases.csv` (all variants), `fc_vs_dpc.csv`, `comparisons.csv`, `policies.json` (action and SoC traces), `scenario_inputs.json`, `run_metadata.json`, eight case-specific PNGs and one cross-case overview. Each CSV contains `provenance=ours-scaled-down` and feasibility/certification flags.

## Explicit Phase 4 assumptions and validity limits

- **A36:** Every scenario has synthetic Euclidean coordinates in km, never real OSM roads or station positions.
- **A37:** Fixed customer/service order and repeated depot; no optimization of customer assignment or depot placement.
- **A38:** Charging hardware is compatible with the vehicle by assumption. Especially the three-wheeler's DC charger is hypothetical and must not be treated as OEM-compatible.
- **A39:** Charging power is piecewise constant by segment with 80%, 95%, 100% breakpoints; charging losses and charger occupancy/queuing are absent.
- **A40:** Temperature is constant throughout a run; capacity derating and HVAC curves are synthetic and uncalibrated.
- **A41:** Battery health is fixed for each route; the degradation penalty is a mathematical surrogate in time-equivalent units, not cumulative SOH prediction.
- **A42:** Coach passenger loads, idle energy, driver rest, depot service, road gradients, regenerative braking, weather-dependent traction and time windows are not modeled.
- **A43:** Freight payload fits the truck by assumption. The paper's mass-linear energy model is used without calibrated resistance terms.
- **A44:** Adding stations is modeled as expanding the existing set with all other inputs fixed; outages remove one station deterministically.
- **A45:** In the exact-SoC solver, the finite charge-target optimum is certified only when no beam pruning occurs. Positivity is tested at original route nodes; zero arrival SoC at a station is allowed.
- **A46:** Very low but positive depot SoC is allowed; no safety reserve or probabilistic robustness is guaranteed.
- **A47:** The study has one deterministic geometry per scenario. These results do not support population statistics, confidence intervals or transport-system generalization.

## Phase 4 verdict

**Executed and internally verified, but synthetic only.** The four new stories are distinct from the Montoya, San Francisco, and Amsterdam paper experiments. Each includes actual solver output, independent physical validation, CSVs and figures. All conclusions describe simulated model behavior only.
