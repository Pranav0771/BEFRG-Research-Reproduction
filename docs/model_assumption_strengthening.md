# Extension 2: physical assumption strengthening without claiming field calibration

This is an **engineering assumption audit** supported by new genuine-Montoya-geometric sensitivity tests, not by measured battery telemetry. We retain exactly two research extensions.

| Component | In model | Evidence / next real calibration needed |
|---|---|---|
| Temperature derating | Asymmetric bounded quadratic `B_use/B0` vs constant ambient T | Battery chemistry and vehicle-specific discharge capacity tests across T and SoC |
| HVAC | Drive-only power `min(6kW, k_heat*(19-T)_+ + k_cool*(T-27)_+)` | Actual HVAC duty cycle, cabin loads, vehicle heating type, passenger occupancy |
| Charge speed | Original Montoya charging times rescaled at fixed normalized SoC as capacity changes | 2D/3D charge-power-vs-SoC-vs-battery-temperature map; manufacturer charge acceptance and thermal throttling |
| Health | Fixed exogenous SOH multiplier | Time-varying measured SOH and temperatures, validated across cycling history |
| Degradation | Equivalent-minute cost `omega*(Δcharge/B_use)^beta` | Cycling-depth/cycle-history model, observed capacity fade, monetary aging cost and calendar aging |

**Sensitivity setup:** Original Montoya `tc2c320s38cf0.xml` geometry, independent fixed route prefixes n=40/80; ambient T ∈ {0,10,25,40} °C with separate aging and cold-derating sweeps. For this stress test only, cabin coefficients are `heat_kw_per_c = cool_kw_per_c = 0.04`; battery capacity coefficients are `alpha_cold = 0.00045`, `alpha_hot = 0.00012`, SOH default 1, optional .9; cold coefficient multiplied by .5 or 2. Degradation penalty weight 0 or 8 equivalent minutes, beta 1.4. **None of these are fitted from the XML or a measured cell.** Results are in `results/montoya_extension1/thermal_robustness_original_xml.csv` (16/16 independently replay-valid).

**Scientific grounding, not calibration:** U.S. DOE, September 23, 2024, *Impact of Cold Ambient Temperature and Extreme Conditions on Electric Vehicles*, https://www.energy.gov/cmei/vehicles/articles/program-record-impact-cold-ambient-temperature-and-extreme-conditions . Its findings substantiate the relevance of cold cell performance and HVAC to driving energy/range, **not** our numerical coefficients nor a universal capacity-loss function. Real charging power is temperature dependent, unlike the project model. The fixed-temperature, equal-C-rate synthetic assumption is a major potential source of model error.

## Interpretation

These tests answer a limited *conditional* question: given an invented temperature-to-capacity map and ancillary power demand, how would the optimizer's policy change on a known road-network geometry? They do not answer how much a real EV battery degrades per trip, whether Montoya's vehicle would accept the modeled charger at low temperature, or whether the same policy would hold under weather/traffic uncertainty.
