# Phase 3 — New mathematical extensions and corrections

All equations below are project extensions; they are **not** equations from Mandal et al. (2025). Energy/route units: kWh, minutes, kilometres, kilograms; temperature in °C. Experimental coefficients are **assumptions**. References at end.

## Idea #1 — physically executable SoC decisions

Original BEFRG stores a rounded-down state `b * rc` and computes station charging from that rounded value. When physical arrival SoC is higher than target, the chosen action is non-executable. Residual energy lost at each grid projection can also cause needless detours.

We replace the rounded route-node state with an exact physical SoC label `s` and keep **only** the station target charge level discrete: `y'_c = ell * B/gamma`. All arcs remain fixed-route and permit at most one station detour. Transitions from each `(k,s)` are:

- Direct: `s' = s - e(v_k,v_{k+1}) > 0`, `increment = d(v_k,v_{k+1})/S`.
- Detour: `a = s - e(v_k,c) >= 0`, choose `ell` with `a < ell*B/gamma <= B`; `s' = ell*B/gamma - e(c,v_{k+1}) > 0`; `increment = (d(v_k,c)+d(c,v_{k+1}))/S + CT(a, ell*B/gamma)`.

The shortest-path label recurrence is

`D_{k+1}(s') = min_{(s, action)->s'} [D_k(s)+increment(s,action)]`.

Only *equal* physical SoC states are merged (numerical key rounded to 11 decimal places, tolerances at most ~1e-9 kWh). The baseline physical label solver makes no nontrivial SoC dominance claim by default. The **optional October 2026 Montoya-validation update** adds dominance pruning **only** for complete Euclidean metrics with nonnegative, monotone charging cost: if a label has more SoC and no greater objective at the same route node, it dominates a lower-SoC label. The triangle inequality guarantees a direct leg never costs more energy/time than a detour when the higher-SoC label would already exceed the lower label’s target charge. This optimization is rejected on sparse/directed distance overrides. On this restricted class, it preserves finite-grid optimality without heuristic beam pruning (up to the existing 11-decimal numeric key). Without optional beam pruning, this is optimal **for the finite set of charge targets and physically executable actions**, but may be slower and use more labels than BEFRG. With `max_labels_per_stage` set, it becomes an explicitly **heuristic** beam search, and `certified_grid_optimal=False`.

The continuous MILP benchmark permits any continuous charge target, so it is a lower bound on this discrete-target solution. A feasible result from our solver may be strictly worse. The per-instance gap is `(T_physical_grid - T_MILP)/T_MILP`, only when the MILP is certified optimal.

## Idea #2 — temperature-aware capacity, HVAC and degradation cost

**User-proposed expression:** `B(T)=B0*(1-alpha*(T_ref-T)^2)`. Dimensionally meaningful with `alpha` measured in degC^-2 but insufficiently realistic: it is symmetric and can be negative; it conflates usable capacity with irreversible aging.

**Project model (constant ambient T for one route):**

`B_use(T,h) = B0 * h * max(f_min, 1 - alpha_c * max(T_ref-T,0)^2 - alpha_h * max(T-T_ref,0)^2)`.

`h` is exogenous state-of-health (0,1], not an evolving state. `f_min` prevents negative capacity. Distinct cold/hot coefficients are an illustrative curve, **not empirical calibration**. Cold performance and HVAC demand are known to impact range; a manufacturer temperature-capacity lookup would be preferable to the quadratic.

**Cabin HVAC (piecewise, kW):**

`P_HVAC(T) = min(P_max, k_heat*max(T_heat-T,0) + k_cool*max(T-T_cool,0))`.

**Per-leg energy (kWh), with S in km/min:**

`e_T(u,w;k) = theta*(L(v_{k+1})+veh_mass)*d(u,w) + P_HVAC(T)*d(u,w)/(60*S)`.

The two legs of a station detour use the **same destination load** as the paper. HVAC energy is counted while traveling only; charger supplies any ancillary power during charging (assumption). The variable `B_use` is a **usable energy capacity**, and the charging target grid is `ell*B_use/gamma`.

**Charge-time curve:** Scale each curve breakpoint from nominal charge `z` to `z*B_use/B0` at unchanged elapsed time `x`. This assumes equal C-rate at equal normalized SoC; it omits temperature-triggered charge-power derating and would need battery-specific calibration.

**Degradation proxy:** The user-proposed `C_deg(ΔDoD)=omega*(ΔDoD)^beta` needs an explicit `ΔDoD` definition. Charging **increment fraction** `q=(y'-y)/B_use` is not the same as a cycle depth from a full SoC cycle. We implement

`C_deg(y,y',T) = omega_min * q^beta` where `q >= 0` and `omega_min >= 0`.

`omega_min` has units equivalent minutes; `beta >= 1`. The objective is

`min T_travel + T_charge + sum C_deg`.

The sum belongs in the **action cost** of the exact-SoC label DP, and we report route minutes and penalty separately. Neither electrochemical kinetics, calendar aging, true capacity fade along the tour, SOC-induced calendar degradation, charge C-rate, rainflow DoD cycle depth nor actual battery-life cost is modeled. `beta>1` can perversely favor splitting the same charging energy across multiple events; this objective must be described as a **throughput-related surrogate** pending chemistry-specific fitting, not physical lifetime prediction.

### DP state sufficiency

With fixed temperature `T`, exogenous SOH `h`, deterministic station curves, time-independent traffic and **additive per-charge surrogate costs**, `(route index k, physical SoC s)` remains sufficient: no cycle-history state is needed for this specific proxy. A legitimate electrochemical rainflow cycling cost generally depends on past SoC extrema and would require an expanded state or offline trajectory cost; one cannot silently substitute it into the current Bellman recurrence.

### Added assumptions A25–A35

- **A25:** Constant ambient temperature and constant SOH throughout a route.
- **A26:** Temperature capacity derating is bounded, asymmetric and synthetic; no cell calibration.
- **A27:** HVAC power is piecewise-linear in ambient temperature, not cabin control dynamics.
- **A28:** HVAC consumes battery energy during driving, with no separate charging HVAC drain.
- **A29:** Speed remains the paper's fixed speed, and temperature modifies auxiliary load, not traction efficiency or regeneration.
- **A30:** Charger follows equal normalized-SoC elapsed-time curve at reduced capacity; no cold-charge restriction or throttling.
- **A31:** Degradation term is a *per-charge throughput surrogate*, not an experimentally fitted electrochemical aging law.
- **A32:** Degradation weight is a time-equivalent objective coefficient, not electrical energy or physical duration.
- **A33:** Exact-SoC label search is globally optimal **only** over its discrete-target action space with no beam limit.
- **A34:** Equal SoC labels are merged with numerical tolerance; this is not a mathematically exact real-number implementation.
- **A35:** All Phase 3 coefficient values and all experimental geographic geometries are labeled synthetic; no exact Montoya reproduction is claimed.

### Scientific background (not calibration of our coefficients)

- Mandal et al., *ACM TECS* (2025), https://doi.org/10.1145/3762188 — baseline BEFRG problem, not temperature model.
- U.S. DOE/Argonne National Laboratory, *Impact of Cold Ambient Temperatures and Extreme Conditions on Electric Vehicles*, 2024, https://www.energy.gov/sites/default/files/2024-10/Impact_of_Cold_Ambient_Temperature_on_BEV_Performance_v15_TechEditFinal_12Sep2024__0.pdf .
- NREL System Advisor Model battery temperature/capacity inputs, https://samrepo.nlr.gov/help/battery_storage_fom.html .
- Loew et al., *Economic model predictive control of Li-ion battery cyclic aging via online rainflow-analysis* (2021), https://onlinelibrary.wiley.com/doi/10.1002/est2.228 .
- *A Comprehensive Review on the Characteristics and Modelling of Lithium-ion Battery Ageing*, https://pure.tudelft.nl/ws/portalfiles/portal/115259835/A_Comprehensive_Review_on_the_Characteristics_and_Modelling_of_Lithium_ion_Battery_Ageing.pdf .
