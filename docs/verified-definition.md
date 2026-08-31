# What "verified" means (FND-005 — draft pending G0-Q6)

Atlas never stores or displays a single unexplained `verified: true`.
Any badge links to this definition and decomposes into the nine
independent dimensions of SPEC section 1.1:

`document_authority_state`, `captured_copy_provenance_state`,
`integrity_verification_state`, `anchor_resolution_state`,
`authority_sufficiency_state`, `mechanical_verification_state`,
`semantic_review_state`, `effective_distribution_decision`,
`freshness_state`.

Mechanical verification proves byte/anchor integrity of a captured copy;
it does not alone prove authenticity at issuance, semantic support,
completeness or currentness. Before G6, every published source-derived
factual assertion additionally requires `semantic_review_state:
human_approved`.
