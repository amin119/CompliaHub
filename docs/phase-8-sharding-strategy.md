# Phase 8 — Graph Sharding/Partitioning Strategy (documented, not built)

Status: **documented, deliberately not implemented.** Confirmed disproportionate
to build now — see the sizing math below. Written concretely enough to be
directly actionable if this project ever does hit real scale, not a vague
placeholder.

## Why this isn't built now

Building real Neo4j sharding today would be speculative infrastructure with
zero real load to validate it against — directly against this project's own
repeated precedent (Phase 4's worker split explicitly rejected Spark/Hadoop
as overkill for this data scale).

The real ISO 27001/42001/GDPR corpus (the actual 3 standards this project's
graph is built from) produces on the order of ~90 entities and 200-320
relations, with at most 61 communities (one outlier at 52 entities, most
≤5) — see `docs/phase-3-extraction.md`, `docs/phase-4-graph-retrieval.md`.
(Separately, Phase 8's own verification found the *shared dev database*
holds 311 `Document` rows due to accumulated pytest fixtures — a real,
disclosed operational concern for the *document* deletion/rebuild feature,
but not a graph-sharding concern: entity/relation counts scale with distinct
real content, not with how many times a test fixture got re-uploaded and
deduplicated by hash.)

## Trigger conditions to revisit this

Don't build sharding speculatively — build it when one of these becomes
true, measured, not guessed:

1. **Query latency**: `graph_store.fetch_all_entities`/`fetch_all_relations`
   (used by entity resolution and community detection — both O(corpus size)
   full-graph reads) show a measured p95 latency exceeding ~2 seconds against
   the real corpus. At today's ~90 entities this is sub-100ms; degradation
   here is the first real signal, not a guessed one.
2. **Corpus size**: the real (non-test-fixture) standard count grows past
   ~20-30 standards. Reasoning: Neo4j Community edition (this project's own
   deployment — confirmed via `graph_store.py`'s own docstring) has no hard
   entity-count ceiling, but a single-instance in-memory page cache sized
   for a few hundred thousand nodes/relationships is the practical
   comfort zone for commodity hardware; extrapolating from the current
   ~90 entities/~260 relations per standard, 20-30 standards would put the
   graph in the low tens of thousands of nodes — still comfortably within
   a single instance, but the point where per-standard growth is no longer
   negligible and this document should be revisited with real numbers.

## Real constraint to name honestly

**Neo4j Fabric** (the real multi-database sharding/federation feature) is
an **Enterprise** feature. This project runs `neo4j:5-community`
(confirmed in `graph_store.py`'s own docstring) — Community edition supports
exactly one user database, no Fabric. If sharding is ever actually needed,
this project has exactly two real options:

1. **Buy an Enterprise license and use Neo4j Fabric** — the "correct" way,
   least custom code, but a real recurring cost for a project with a single
   operator today.
2. **An application-level shard router**: separate Neo4j Community
   instances (one per standard or per standard-group), with `graph_store.py`
   gaining a routing layer that picks which driver/instance to query based
   on which standard(s) a request touches, and a merge step for any query
   that must span shards (see "bridge edges" below).

**This project would choose option 2 if the trigger conditions above are
ever met** — no ongoing license cost, and the routing logic is a bounded,
one-time build rather than an ongoing subscription; the added complexity
(a routing layer, cross-shard query merging) is judged worth it over a
recurring Enterprise cost for a project of this scale and budget profile.

## Partitioning key

**Per-standard**, reusing the same provenance concept already established
elsewhere in this phase rather than inventing a second bookkeeping
mechanism: each `Document` belongs to exactly one standard (already true —
`Document.filename`/upload grouping), and each entity/relation is reachable
from the `chunk_id`/`document_id` already stamped on every relation
(`create_relation`, confirmed in `app/services/graph_store.py`). A shard
key for an entity is derived from which document(s) its supporting
relations point at — no new column needed on the entity nodes themselves,
since (per this phase's approved "full rebuild" deletion strategy) entity
nodes deliberately carry no persistent per-document provenance; a shard
assignment pass would compute this by walking relations at
migration/reshard time, not maintain it continuously.

## Bridge edges — the cross-shard case

The existing `MAPS_TO` relation type (`app/services/ontology.py`'s
`RelationType` enum) is **already** exactly the "this entity in standard A
maps to that entity in standard B" cross-standard relationship a shard
boundary must never cut. No new relation type needed. A real sharded
deployment's routing layer would treat any `MAPS_TO` edge as a
known-cross-shard case requiring a federated query (fetch both sides from
their respective shard, join in the application layer) rather than
attempting a single-instance Cypher traversal across a boundary that no
longer physically exists in one database.

## Sizing math (extrapolated from real measured figures)

| Standards ingested | Entities (~90/standard) | Relations (~260/standard) | Single-instance concern? |
|---|---|---|---|
| 3 (today, real) | ~90 | ~260 | No — negligible |
| 10 | ~900 | ~2,600 | No — still small |
| 30 (trigger threshold) | ~2,700 | ~7,800 | Revisit — measure real p95 latency |
| 100 | ~9,000 | ~26,000 | Likely needs sharding or a bigger single instance, not guessed — measure first |

These are linear extrapolations from real per-standard figures, not a new
measurement — real entity/relation counts don't grow perfectly linearly in
practice (cross-standard `MAPS_TO` merging means some entities are shared,
not purely additive), so the real trigger should always be a measured p95
query latency, not this table alone.
