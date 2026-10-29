# Consolidated assumptions register (A01–A55)

These assumptions are explicit research-reproduction decisions, not necessarily statements about the authors’ implementation. See the corresponding phase reports for context.

- **A01** — All fixed-route nodes, including return depot, must have strictly positive discrete SoC. The paper's literal unguarded zero state can be explored with `strict_positive=False`.
- **A02** — B divided by gamma and Gamma creates the two grids; widths are not rounded and battery capacity is exactly represented.
- **A03** — Curve segments require increasing charge and time breakpoints; station curve capacity equals B.
- **A04** — The DP's model SoC is floored after each original route arc. Actual SoC must be replayed independently, and may lead to different charging times or invalid no-op charge targets.
- **A05** — Benchmark vehicle mass and theta are omitted in the paper. Default `veh_mass=1000 kg` and `theta=0.125/1000` kWh/(km·kg) match empty-vehicle rate 0.125 kWh/km, NOT the paper's unknown calibration.
- **A06** — `cheapest_insertion` is Solomon-*inspired*, NOT a reproduction of unspecified SIH logic. No time windows or service times in BEFRG objective.
- **A07** — Montoya uses Euclidean distances in kilometres, retaining double precision.
- **A08** — Station type curves are read from source XML; no station-type reallocation.
- **A09** — At most one station detour per original route arc; no station-to-station travel.
- **A10** — Zero SoC at a charging station is permitted; positive SoC required at original route nodes.
- **A11** — Ties prefer direct action, then station input order, then smaller target.
- **A12** — Figure 2(b) does not specify distances between all node-station pairs. Running example only allows six specified directed arcs. Hence its optimum is for a *sparse interpretation* and cannot establish the optimal policy for an unstated complete graph.
- **A13** — Traffic dependence and predictive online planning are not implemented in Phase 1.
- **A14** — All benchmark customer demands default to one kg (paper's assigned unit loads).
- **A15** — Timing, memory and benchmark comparisons are future Phase 2 tasks; none are claimed here.
- **A16** — Depot occurs at both beginning and end of route, and both positions count as route nodes.
- **A17** — Every Phase 2 synthetic experiment uses fixed seed 20251028 and a deliberate empty-vehicle energy stress multiplier of 2.0.
- **A18** — Synthetic customer subsets are prefixes of the deterministic initial tour.
- **A19** — Station-set sweeps use nested first-N synthetic stations, not the sampled subsets of the paper.
- **A20** — SciPy/HiGHS substitutes for IBM CPLEX; report optimizer termination/certificate status.
- **A21** — Synthetic online traffic uses hourly (60-minute) slots, Normal(70%,10%) flow and a heuristic speed-congestion function; it is not validated SUMO dynamics.
- **A22** — Runtime instrumentation uses tracemalloc/psutil and can slow execution; no hardware-matched performance claim is made.
- **A23** — Paper-versus-ours quantitative differences are undefined when the route, benchmark or energy calibration differs.
- **A24** — A discretized-optimal policy may require a physically non-increasing charge target; independent continuous validation is mandatory.
- **A25** — Constant ambient temperature and constant SOH throughout a route.
- **A26** — Temperature capacity derating is bounded, asymmetric and synthetic; no cell calibration.
- **A27** — HVAC power is piecewise-linear in ambient temperature, not cabin control dynamics.
- **A28** — HVAC consumes battery energy during driving, with no separate charging HVAC drain.
- **A29** — Speed remains the paper's fixed speed, and temperature modifies auxiliary load, not traction efficiency or regeneration.
- **A30** — Charger follows equal normalized-SoC elapsed-time curve at reduced capacity; no cold-charge restriction or throttling.
- **A31** — Degradation term is a *per-charge throughput surrogate*, not an experimentally fitted electrochemical aging law.
- **A32** — Degradation weight is a time-equivalent objective coefficient, not electrical energy or physical duration.
- **A33** — Exact-SoC label search is globally optimal **only** over its discrete-target action space with no beam limit.
- **A34** — Equal SoC labels are merged with numerical tolerance; this is not a mathematically exact real-number implementation.
- **A35** — All Phase 3 coefficient values and all experimental geographic geometries are labeled synthetic; no exact Montoya reproduction is claimed.
- **A36** — Every scenario has synthetic Euclidean coordinates in km, never real OSM roads or station positions.
- **A37** — Fixed customer/service order and repeated depot; no optimization of customer assignment or depot placement.
- **A38** — Charging hardware is compatible with the vehicle by assumption. Especially the three-wheeler's DC charger is hypothetical and must not be treated as OEM-compatible.
- **A39** — Charging power is piecewise constant by segment with 80%, 95%, 100% breakpoints; charging losses and charger occupancy/queuing are absent.
- **A40** — Temperature is constant throughout a run; capacity derating and HVAC curves are synthetic and uncalibrated.
- **A41** — Battery health is fixed for each route; the degradation penalty is a mathematical surrogate in time-equivalent units, not cumulative SOH prediction.
- **A42** — Coach passenger loads, idle energy, driver rest, depot service, road gradients, regenerative braking, weather-dependent traction and time windows are not modeled.
- **A43** — Freight payload fits the truck by assumption. The paper's mass-linear energy model is used without calibrated resistance terms.
- **A44** — Adding stations is modeled as expanding the existing set with all other inputs fixed; outages remove one station deterministically.
- **A45** — In the exact-SoC solver, the finite charge-target optimum is certified only when no beam pruning occurs. Positivity is tested at original route nodes; zero arrival SoC at a station is allowed.
- **A46** — Very low but positive depot SoC is allowed; no safety reserve or probabilistic robustness is guaranteed.
- **A47** — The study has one deterministic geometry per scenario. These results do not support population statistics, confidence intervals or transport-system generalization.

## New validated original-XML assumptions (A48–A55)

- **A48:** Original Montoya XML inputs are genuine, but initial routes are deterministic independently generated cheapest-insertion prefixes, not the paper's unrecovered route plans.
- **A49:** Vehicle mass is assumed 1,000 kg and θ matches the XML nominal empty-vehicle kWh/km; unit customer loads are assumed, with no claim of author parameter parity.
- **A50:** The optional Euclidean dominance rule requires complete metric distances obeying triangle inequality; it is deliberately rejected for arbitrary directed/sparse graphs.
- **A51:** SoC dominates another SoC label only when its accumulated objective is no higher; each station target must remain strictly above actual arrival SoC.
- **A52:** The new 17-config physical-SoC validation compares the same independent route and charging grid; the old DP's invalid modeled route time is not a physically executable trip time.
- **A53:** Thermal parameters on original XML geometry are hypothetical, and capacity, charge power and degradation are not fitted to a specific vehicle cell chemistry.
- **A54:** All reported finite-target optimum certificates rely on no beam pruning and the existing numeric 11-decimal SoC key; on nonmetric input no dominance certificate is claimed.
- **A55:** User laptop cross-machine validation covers 36 earlier floored model objectives, not the new physical-SoC extension until rerun locally.
