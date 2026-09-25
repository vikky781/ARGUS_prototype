"""Offline, fully-deterministic GeoIP/ASN enrichment.

This repo's dataset is entirely synthetic: src_ip values are made-up addresses
that were never assigned by any real registry, so a real MaxMind/GeoLite2 lookup
would return meaningless results for them — and would need a licensed database
file this repo can neither ship nor download at runtime (see CLAUDE.md's offline
rule). configs/default.yaml's geoip_mmdb_path is left as an unused placeholder
for that real database; this module does not read it.

Instead, this module re-derives geo_country/asn the same way argus.synth.networks
originally assigned them: by looking up the IP's first two octets against that
same fixed pool of synthetic "/16" networks. This is a genuine re-lookup keyed on
src_ip, not a copy of whatever synth wrote into the raw export — it agrees with
synth's placeholder in this closed synthetic universe for the same reason a real
GeoIP database would agree with itself on a stable, real dataset.
"""
from __future__ import annotations

from argus.synth.networks import NETWORK_POOL

_LOOKUP: dict[tuple[int, int], tuple[int, str]] = {
    (net.octet1, net.octet2): (net.asn, net.country) for net in NETWORK_POOL
}


def enrich(src_ip: str) -> tuple[int, str]:
    """Returns (asn, geo_country) for src_ip, looked up against the synthetic pool."""
    octet1, octet2, _, _ = src_ip.split(".")
    key = (int(octet1), int(octet2))
    if key not in _LOOKUP:
        raise ValueError(f"no synthetic GeoIP entry for {src_ip}")
    return _LOOKUP[key]
