# Stretch Tue — Learner Notes

## Design decisions

I implemented the verifier as a four-stage cascade that returns as soon as a stage fires.

For Stage 1, I used a direct relationship existence check for graph predicates and a reflexive equality check for the `type` predicate. This keeps direct support separate from hierarchical reasoning.

For Stage 2, I used a separate variable-length traversal with `[:SUBCLASS_OF*1..]` for type claims. Stage 1 already handles the depth-0 case, so using a minimum depth of 1 clearly distinguishes entailed claims from directly supported claims.

For Stage 3, I used the provided `_labels_of()` helper to retrieve node labels and compare them against the expected domain/range labels defined in `SCHEMA_CONSTRAINTS`. Labels were fetched when needed rather than cached because the evaluation graph is small and the implementation remains simple and readable.

I considered combining the supported and entailed checks into a single traversal, but keeping them as separate stages made the cascade behavior easier to understand and aligned with the assignment specification. I also preserved the required stage ordering because changing it could incorrectly classify valid claims.

## Eval-set behavior

| Class        | Precision | Recall |
| ------------ | --------- | ------ |
| supported    | Passed    | Passed |
| entailed     | -         | Passed |
| contradicted | Passed    | -      |

Notes:

* The entailed class was the most important part of the implementation because it depends on correctly traversing the `SUBCLASS_OF` hierarchy.
* The distinction between supported and entailed claims became much clearer after separating the depth-0 and depth>=1 cases.
* No major surprises appeared once the cascade ordering matched the specification.

## Abstention boundary

The critic should return `"unsupported"` when there is not enough evidence in the graph to support, entail, or contradict a claim. Under the open-world assumption, missing information does not mean the claim is false.

Over-flagging a claim as `"contradicted"` is worse than abstaining because contradiction is a much stronger statement. A contradiction indicates that the claim violates known schema constraints, while an unsupported claim may simply refer to information that is not present in the graph. Returning `"unsupported"` avoids making unjustified conclusions.

## Optional — M8 router warm-up

I did not integrate the critic with the M8 query router for this assignment.
