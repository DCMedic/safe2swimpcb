# Data sources and limitations

- **Current PCB flag:** Visit Panama City Beach, “Current Beach Conditions,” which states conditions are provided by Beach & Surf Patrol. The collector records polling time; it may not equal official issuance time.
- **Flag definitions:** City of Panama City Beach beach-flag page.
- **Historical flag archive:** User-supplied ALERTBAY/PCBFLAGS text-message export, parsed into structured records.
- **Weather:** Open-Meteo ERA5 for finalized model training. Live/current UI may use Open-Meteo forecast/current fields. Reanalysis is not the same as an on-beach instrument.
- **Marine:** Open-Meteo ERA5-Ocean for finalized historical wave/swell features. It is relatively coarse and represents regional conditions, not exact breaker height at a specific swimmer location.
- **Tides:** NOAA CO-OPS subordinate station 8729136, New Entrance Channel, St. Andrew Bay. Tide predictions are referenced to MLLW.
- **Research model:** Time-aware logistic regression for red-or-worse association/prediction research. It is not an official rip-current forecast and is never a swimming clearance.
