"""O8: keyed, deterministic, duplicate-insensitive patient pseudonyms."""
from __future__ import annotations

import hashlib
import hmac

from core.interfaces import ClusterAssignment
from core.record_ids import stable_content_fingerprint

_FINGERPRINT_PREFIX = b"patient-v1|"
_CROCKFORD_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # excludes I, L, O, U


def stable_cluster_fingerprint(record_ids: list[str]) -> bytes:
    """Return an order- and exact-duplicate-insensitive cluster fingerprint."""
    return stable_content_fingerprint(record_ids)


def _crockford_prefix(digest: bytes, length: int) -> str:
    """Encode the low ``length * 5`` bits with the Crockford alphabet."""
    if length < 1 or length * 5 > len(digest) * 8:
        raise ValueError("invalid_crockford_length")
    value = int.from_bytes(digest, "big")
    characters = []
    for _ in range(length):
        characters.append(_CROCKFORD_ALPHABET[value & 31])
        value >>= 5
    return "".join(reversed(characters))


def _cluster_digest(pseudonym_key: bytes, record_ids: list[str]) -> bytes:
    fingerprint = stable_cluster_fingerprint(record_ids)
    return hmac.new(
        pseudonym_key,
        _FINGERPRINT_PREFIX + fingerprint,
        hashlib.sha256,
    ).digest()


def pseudonym_for_cluster(
    pseudonym_key: bytes, record_ids: list[str], length: int = 16
) -> str:
    return f"PSN-{_crockford_prefix(_cluster_digest(pseudonym_key, record_ids), length)}"


def build_pseudonym_map(
    pseudonym_key: bytes, assignments: list[ClusterAssignment]
) -> dict[str, str | None]:
    """Return record -> pseudonym, extending colliding prefixes deterministically.

    Sixteen Crockford characters provide 80 bits. A collision is extraordinarily unlikely,
    but O8 requires explicit detection. If two clusters share a 16-character prefix, every
    cluster in that collision group moves to 20 characters; the process repeats in four-
    character increments until unique (up to all 255 whole digest bits).
    """
    members_by_cluster: dict[str, list[str]] = {}
    for assignment in assignments:
        if assignment.cluster_key is not None:
            members_by_cluster.setdefault(assignment.cluster_key, []).append(assignment.record_id)

    digests = {
        cluster_key: _cluster_digest(pseudonym_key, members)
        for cluster_key, members in members_by_cluster.items()
    }
    lengths = {cluster_key: 16 for cluster_key in members_by_cluster}

    while True:
        by_code: dict[str, list[str]] = {}
        for cluster_key in sorted(members_by_cluster):
            code = _crockford_prefix(digests[cluster_key], lengths[cluster_key])
            by_code.setdefault(code, []).append(cluster_key)
        collisions = [keys for keys in by_code.values() if len(keys) > 1]
        if not collisions:
            break
        for cluster_keys in collisions:
            for cluster_key in cluster_keys:
                next_length = min(lengths[cluster_key] + 4, 51)
                if next_length == lengths[cluster_key]:
                    raise RuntimeError("pseudonym_digest_collision")
                lengths[cluster_key] = next_length

    pseudonym_by_cluster = {
        cluster_key: f"PSN-{_crockford_prefix(digests[cluster_key], lengths[cluster_key])}"
        for cluster_key in members_by_cluster
    }
    return {
        assignment.record_id: (
            pseudonym_by_cluster.get(assignment.cluster_key)
            if assignment.cluster_key is not None
            else None
        )
        for assignment in assignments
    }
