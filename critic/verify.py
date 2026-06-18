"""KG critic verifier — four-stage cascade.

Given a (subject_id, predicate, object_id) claim, decide whether the
recipes graph supports it, entails it, contradicts it, or has nothing
to say (unsupported / abstain).

Cascade order — MUST be applied in this sequence per the stretch
contract (§5 of the W9B Phase 3 build contract). The first stage that
fires returns; later stages do not run.

  1. **Direct EXISTS** — check whether the claim's edge / class-membership
     holds directly in the graph (no traversal of SUBCLASS_OF*).
     -> verdict="supported", confidence=1.0

  2. **Hierarchical entailment via [:SUBCLASS_OF*0..]** — for "type"
     claims, check whether `subject_id` reaches `object_id` along the
     SUBCLASS_OF chain (depth >=1; depth-0 is handled by Stage 1).
     -> verdict="entailed", confidence=0.7

  3. **Domain/range violation detection** — read SCHEMA_CONSTRAINTS
     below. If the predicate is in the dict and either the subject's or
     object's label disagrees with the expected (source_label, target_label)
     pair, the claim is structurally impossible.
     -> verdict="contradicted", confidence=0.8

  4. **Otherwise** — none of the above fired.
     -> verdict="unsupported", confidence=0.5

The whole point of the cascade (over a plain "does this edge exist"
ASK-style check) is the entailment stage — without it, recall on the
entailed-only subset collapses to 0.
"""
from __future__ import annotations

from .verdict import Verdict


# ─── Course-provided constant — do NOT modify. ───────────────────────
SCHEMA_CONSTRAINTS: dict[str, tuple[str, str]] = {
    "USES_INGREDIENT":    ("Recipe", "Ingredient"),
    "OF_CUISINE":         ("Recipe", "Cuisine"),
    "BY_AUTHOR":          ("Recipe", "Author"),
    "REQUIRES_TECHNIQUE": ("Recipe", "Technique"),
}


def _labels_of(driver, node_id: str) -> list[str]:
    """Course-provided helper. Return the non-:Entity labels of the node
    with the given id, or [] if the node does not exist. Uses
    parameterized Cypher (never f-string interpolation)."""
    with driver.session() as session:
        result = session.run(
            "MATCH (n:Entity {id: $id}) RETURN [l IN labels(n) WHERE l <> 'Entity'] AS labels",
            id=node_id,
        )
        row = result.single()
        return list(row["labels"]) if row else []


def verify_claim(driver, claim: tuple[str, str, str]) -> Verdict:
    """Adjudicate a (subject_id, predicate, object_id) claim against the
    recipes graph via the four-stage cascade documented at the top of
    this module.
    """
    subject_id, predicate, object_id = claim

    
    if predicate == "type":
        if subject_id == object_id:
            return Verdict(
                "supported",
                [(subject_id, object_id)],
                1.0,
            )

    elif predicate in SCHEMA_CONSTRAINTS:
        query = f"""
        MATCH (h:Entity {{id: $subject_id}})
              -[:{predicate}]->
              (t:Entity {{id: $object_id}})
        RETURN h.id AS h, t.id AS t
        LIMIT 1
        """

        with driver.session() as session:
            row = session.run(
                query,
                subject_id=subject_id,
                object_id=object_id,
            ).single()

        if row:
            return Verdict(
                "supported",
                [(subject_id, object_id)],
                1.0,
            )

   
    if predicate == "type":
        query = """
        MATCH path =
            (h:Entity {id: $subject_id})
            -[:SUBCLASS_OF*1..]->
            (t:Entity {id: $object_id})
        RETURN [n IN nodes(path) | n.id] AS chain
        LIMIT 1
        """

        with driver.session() as session:
            row = session.run(
                query,
                subject_id=subject_id,
                object_id=object_id,
            ).single()

        if row:
            return Verdict(
                "entailed",
                [tuple(row["chain"])],
                0.7,
            )

   
    if predicate in SCHEMA_CONSTRAINTS:
        expected_source, expected_target = SCHEMA_CONSTRAINTS[predicate]

        subject_labels = _labels_of(driver, subject_id)
        object_labels = _labels_of(driver, object_id)

        source_ok = expected_source in subject_labels
        target_ok = expected_target in object_labels

        if not source_ok or not target_ok:
            return Verdict(
                "contradicted",
                [(subject_id, object_id)],
                0.8,
            )

    return Verdict(
        "unsupported",
        [],
        0.5,
    )