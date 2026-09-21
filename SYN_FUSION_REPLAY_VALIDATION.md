# Fusion evidence-set identity: validation

Base: 519-green, commit 9e3f5ce402af954506fe44862bef45a5ddb853fd.

## Reproduced defect
Reversing a list of existing observations or duplicating its entries changed
fusion_id, despite unchanged independent support. Two new integration cases
failed on the original code (2 failed, 4 passed in the initial targeted run).

## Change
Validate every input record first, deduplicate by normalized_glyph_id, then
sort those IDs before calculating contributions, parents and the fusion hash.
Forged duplicates remain rejected in either order. Distinct observation IDs
remain distinct evidence, even when their source and value match.
The fix does not infer independence or change support-weight policy.

## Verification
Eight new offline integration cases use the actual secure-stack builder,
Perception Bus, AEGIS, fusion, AURA, context selector, provisional beliefs and
research agenda. They cover curated AgentDyn version/repository lineage,
reordered and duplicated inputs, unprofiled/self-declared sources, conflicting
claims, forged duplicates in both orders, and distinct observations.

Full suite executed locally: 527 passed, 2 warnings in 3.99s.
Warnings concern Starlette/httpx and an anyio deprecated alias.
Python 3.12; isolated environment restore519-venv. This is not a CI result.

## Scope and limitations
URLs and the 60-task claim are offline fixtures based on previously consulted
AgentDyn pages. There is no live web retrieval or automatic lineage discovery
in these tests. 0.8 reliability is configured test data, not a source rating.
Synthetic negative cases are explicitly identified in the test module.

Idempotence applies to identical observation IDs under unchanged configuration
and reliability state. It does not merge distinct captures of the same page.
Existing stored fusion IDs are not migrated: a first replay after upgrading
can therefore produce a new canonical ID. Original audit records are retained.

MANIFEST_SHA256.json describes current tracked files (excluding itself).
Other snapshot handoffs, PYTEST_RESULT.txt, TEST_ENVIRONMENT.json and older
checksum records remain historical records of the 519 baseline.
