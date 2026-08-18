# Eastern Panhandle flag architecture

Know the Gulf treats beach flags as safety-critical public data. A displayed flag must come from an authoritative flag publication, never from an inferred relationship between weather, waves, or rip-current risk and a flag color.

## Source priority

1. Direct official current-condition publication from the local authority.
2. National Weather Service Tallahassee SRFTAE flag line when the product explicitly states that the flags are based on communication with area beach officials.
3. Unavailable. The system must not manufacture or retain a stale flag merely to keep a colored status visible.

## Initial jurisdictions

- South Walton / 30A: official authority is Walton County beach officials / South Walton Fire District. Visit South Walton directs users to its beach-safety alert service. Operational current flag is normalized from the SRFTAE Walton line unless a direct machine-readable official source is subsequently added.
- Cape San Blas / Indian Pass: Visit Gulf states that the local flag system is managed by community volunteers and South Gulf Fire Rescue. Operational current flag uses the SRFTAE West Facing Gulf Beaches line.
- Gulf County State Park Beaches: operational current flag uses the separate SRFTAE State Park Gulf Beaches line.
- St. Joe Beach: Visit Gulf explicitly notes that St. Joe Beach is not managed by South Gulf Fire Rescue. It therefore remains a separate jurisdiction and uses the SRFTAE South Facing Gulf Beaches line rather than inheriting the Cape San Blas flag.
- Franklin County / St. George Island: Franklin County Parks & Recreation publishes a direct official current-condition widget. This is the primary source; SRFTAE Franklin is retained as corroboration.

## Normalized current_flag.json contract

Each jurisdiction publishes `data/<slug>/current_flag.json` with the displayed flag, severity, verification timestamp, source and authority URLs, provenance tier, freshness window, NWS reported flag where applicable, and an explicit safety note. Franklin County also records the official page's displayed update text when parsable.

The public UI should treat records beyond `stale_after_hours` as unavailable. A later UI integration should show the provenance tier and verification time in a compact source disclosure.

## Safety invariant

NWS rip-current risk, surf height, wind, tropical-weather information, and other environmental observations may be displayed as independent context. They must never be converted into a flag color. Flag evidence and forecast evidence remain separate fields and separate provenance chains.
