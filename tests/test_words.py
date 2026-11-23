from __future__ import annotations

import random

from conquistas.words_ptbr import generate_queries


def test_generates_requested_amount_without_duplicates():
    queries = generate_queries(30, random.Random(42))
    assert len(queries) == 30
    assert len({q.lower() for q in queries}) == 30
    assert all(q.strip() == q and q for q in queries)


def test_zero_and_negative_return_empty():
    assert generate_queries(0) == []
    assert generate_queries(-5) == []


def test_deterministic_with_seed():
    assert generate_queries(10, random.Random(7)) == generate_queries(10, random.Random(7))


def test_large_request_still_unique():
    queries = generate_queries(60, random.Random(1))
    assert len(queries) == 60
    assert len(set(queries)) == 60
