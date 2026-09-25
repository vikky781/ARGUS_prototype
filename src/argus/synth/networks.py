"""A small fixed pool of synthetic "/16" networks, each with a stable (asn, country)
pair. Every src_ip/dst_ip this package generates is produced together with the
Network it came from, so geo_country/asn are always read off that same Network
object rather than reverse-looked-up from the IP string — they can never disagree.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

_COUNTRIES = ["US", "DE", "SG", "NL", "GB", "JP", "BR", "IN", "RU", "FR"]
_POOL_SIZE = 64


@dataclass(frozen=True)
class Network:
    octet1: int
    octet2: int
    asn: int
    country: str


def _build_pool(n: int) -> list[Network]:
    pool = []
    for i in range(n):
        octet1 = 20 + (i * 7) % 200
        octet2 = (i * 37) % 256
        asn = 64512 + i  # RFC 6996 private-use ASN range — synthetic only, never a real ASN
        country = _COUNTRIES[i % len(_COUNTRIES)]
        pool.append(Network(octet1, octet2, asn, country))
    return pool


NETWORK_POOL: list[Network] = _build_pool(_POOL_SIZE)


def random_ip_and_geo(
    net: Network, third_octet: int | None, rng: random.Random
) -> tuple[str, int, str]:
    octet3 = third_octet if third_octet is not None else rng.randint(0, 255)
    octet4 = rng.randint(1, 254)
    ip = f"{net.octet1}.{net.octet2}.{octet3}.{octet4}"
    return ip, net.asn, net.country
