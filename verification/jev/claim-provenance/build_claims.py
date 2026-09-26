"""Claim-provenance pass over docs/22 (post-review-3 text), Jev backend.

Builds the claim set from the current document, pairs each claim with an
excerpt from a TRACKED artifact only, and asks Jev whether the excerpt
supports the claim. Excerpts from anything under runtime/ are refused by
construction: those files are host-local and their contents carry case
symbols, so the claim is recorded with the path only and the excerpt
"HOST-LOCAL ARTIFACT, NOT EXCERPTED" (which Jev scores as unsupported; the
report separates that bucket from real gaps).
"""
from __future__ import annotations
import json, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
DOC = ROOT / "docs/22-candidate-selection-rule.md"
OUT = ROOT / "verification/jev/claim-provenance"
DECIDE = pathlib.Path.home() / "projects/rlcd/bin/decide"
TAG = sys.argv[1] if len(sys.argv) > 1 else "post-review-3"

def tracked(path: str) -> bool:
    if path.startswith("runtime/"):
        return False
    return subprocess.run(["git", "ls-files", "--error-unmatch", path], cwd=ROOT,
                          capture_output=True).returncode == 0

def grab(path: str, needle: str, width: int = 420) -> str:
    if not tracked(path):
        return "HOST-LOCAL ARTIFACT, NOT EXCERPTED"
    p = ROOT / path
    if not p.exists():
        return "NO SOURCE FOUND"
    text = p.read_text(errors="replace")
    i = text.find(needle)
    if i < 0:
        return "NO SOURCE FOUND"
    lo = max(0, i - width // 3); hi = min(len(text), i + len(needle) + width)
    return text[lo:hi]

# (where, claim, source_path, needle)
CLAIMS = [
 ("Step 4 stage 2", "Insert-and-shift promotion lowered 5,220 scores in 327,600 comparisons at four rows", "verification/reviews/741aaad.json", "5,220"),
 ("Step 4 stage 2", "batch/floor+pays_gt has mean rank points 34.895 and 10 comparisons below the plain sort", "verification/scorer-hedging/policy-probe-result.txt", "batch/floor+pays_gt"),
 ("Step 4 stage 2", "batch/transitive+pays_gt has 589 comparisons below the plain sort", "verification/scorer-hedging/policy-probe-result.txt", "batch/transitive+pays_gt"),
 ("Step 4 stage 2", "batch/direct+keep has 44 and batch/direct+demote has 34 comparisons below the plain sort", "verification/scorer-hedging/policy-probe-result.txt", "batch/direct+keep"),
 ("Step 4 stage 3", "The module keeps a losing pair only where points(r) > 0.5 * points(q)", "mva_prioritizer/candidate_selection.py", "_rank_points(j + 1) > 0.5 * _rank_points(winner_rank)"),
 ("Step 4 stage 3", "The module removes a losing pair when a single for its unshared allele already sits above it", "mva_prioritizer/candidate_selection.py", "if any(not out[k].is_pair and out[k].variants == frozenset({u}) for k in range(j)):"),
 ("Step 4 stage 3", "resolve_rows promotes to a fixpoint, then demotes to a fixpoint, and repeats until a round changes nothing", "mva_prioritizer/candidate_selection.py", "changed = False\n        while True:\n            out, what = _demote_once(out)"),
 ("Step 4 stage 3", "The probe's docstring states every policy is implemented inside the file and the module is measured as its own row", "verification/scorer-hedging/policy_probe.py", "Every policy here is implemented inside this file"),
 ("Step 4 stage 3", "The probe defines two schedules, step and batch, and builds a policy for each schedule, promotion mode and STAGE3 entry", "verification/scorer-hedging/policy_probe.py", 'for schedule in ("step", "batch"):'),
 ("Step 4 stage 3", "36,033 truth comparisons over 3,000 random pools from 10 alleles in 4 genes, 4/3/2/1 per gene, tiers A/B/C", "verification/scorer-hedging/policy-probe-result.txt", "36,033 truth comparisons"),
 ("Step 4 stage 3", "batch/direct+pays_gt has 0 below and mean 36.357; step/direct+pays_gt has 0 below and mean 36.353", "verification/scorer-hedging/policy-probe-result.txt", "step/direct+pays_gt"),
 ("Step 4 stage 3", "batch/direct+pays_ge has 0 below and mean 36.155", "verification/scorer-hedging/policy-probe-result.txt", "batch/direct+pays_ge"),
 ("Step 4 stage 3", "batch/direct+demote has mean 36.296 and 34 below; batch/direct+keep has mean 35.899 and 44 below", "verification/scorer-hedging/policy-probe-result.txt", "batch/direct+demote"),
 ("Step 4 stage 3", "The best eligible policy is batch/direct+pays_gt and the module coincides with it on every pool under two seeds", "verification/scorer-hedging/policy-probe-result.txt", "Eligible policies (never below the plain sort)"),
 ("Step 4 stage 3", "verify_module.py reports zero pools with a permutation-dependent result", "verification/scorer-hedging/verify-module-result.txt", "D1  determinism"),
 ("Step 4 stage 3", "verify_module.py reports zero rank-point comparisons lower than the plain sort over 20,245", "verification/scorer-hedging/verify-module-result.txt", "D4  rank points LOWER"),
 ("Step 4 stage 3", "verify_module.py reports zero kept sharing pairs at a rank that does not strictly pay", "verification/scorer-hedging/verify-module-result.txt", "D2  kept sharing pair"),
 ("Verification", "brute_force_hedging.py returns 1 when strict violations are found, so it exits non-zero by design", "verification/scorer-hedging/brute_force_hedging.py", "return 1 if strict_violations else 0"),
 ("Verification", "hedging_modes.py main() returns 0, so it exits zero", "verification/scorer-hedging/hedging_modes.py", "    return 0\n\n\nif __name__"),
 ("Verification", "verify_determinism.py imports only the standard library and does not import the evaluator", "verification/scorer-hedging/verify_determinism.py", "import"),
 ("Verification", "The evaluator bytes are pinned by SHA-256 in tests/test_track1_submission.py", "tests/test_track1_submission.py", "sha256"),
 ("Verification", "Rank points is metric 1 in the official evaluator", "tools/official-track1/evaluation.py", "Rank points (metric 1)"),
 ("Verification", "case-token-scan running scripts/verify_no_case_tokens.py is a required Build OS command in product.json", "product.json", "case-token-scan"),
 ("Verification", "The gate exits 2 with denylist_missing when the denylist file is absent", "scripts/verify_no_case_tokens.py", "denylist_missing"),
 ("Verification", "The gate has a --history flag that scans every blob reachable from any ref", "scripts/verify_no_case_tokens.py", '"--history"'),
 ("Verification", "build_case_token_denylist.py reads the interval map, the HGNC responses and the aggregate report, and writes runtime/privacy/denied-tokens.txt", "scripts/build_case_token_denylist.py", "INTERVAL_MAP = ROOT"),
 ("Verification", "build_case_token_denylist.py takes alias_symbol and prev_symbol from the HGNC responses", "scripts/build_case_token_denylist.py", '"alias_symbol", "prev_symbol"'),
 ("Verification", "build_case_token_denylist.py also takes Entrez, Ensembl gene, RefSeq, OMIM, CCDS, UniProt and MANE ids from the HGNC responses", "scripts/build_case_token_denylist.py", "HGNC_ID_FIELDS = ("),
 ("Verification", "verify-module-result.txt reports 8,305 comparisons with rank points higher than the plain sort and 0 lower", "verification/scorer-hedging/verify-module-result.txt", "D4  rank points higher"),
 ("Step 4 stage 3", "The schedule test asserts the batch file and asserts the step file is not produced, on the pool from the review of 28761f8", "tests/test_candidate_selection.py", "self.assertNotEqual(variants, step)"),
 ("Review history", "The review of 25d0b47 found the tracked verify_module receipt was produced by an intermediate module and the schedule test did not separate the schedules", "verification/reviews/25d0b47.json", "7,982"),
 ("Step 4 stage 3", "The two schedules diverge on 22 of the 3,000 tracked pools", "docs/22-candidate-selection-rule.md", "22 of the 3,000"),
 ("Review history", "The review of 1783250 returned FAIL", "verification/reviews/1783250.json", '"verdict": "FAIL"'),
 ("Review history", "The review of 28761f8 returned FAIL with blocking findings B1 and B2", "verification/reviews/28761f8.json", '"verdict"'),
 ("Review history", "B1 of 28761f8: the probe demoted to a fixpoint before re-promoting while the module re-promoted after every demotion, hidden by a universe with at most three alleles per gene", "verification/reviews/28761f8.json", "three alleles per gene"),
 ("Review history", "B2 of 28761f8: the sentence giving always-demote the highest raw mean at 46.574 was false against the tracked result, where direct+pays_gt scored 46.833", "verification/reviews/28761f8.json", "46.574"),
 ("Review history", "The second Jev pass on 1783250 covered 71 claims in 4 calls", "verification/jev/claim-provenance/report-1783250.md", "71"),
 ("Provenance", "The frozen interval map at runtime/nine-gene-audit-20260909/gene-interval-map.json is host-local and not in the public tree", "runtime/nine-gene-audit-20260909/gene-interval-map.json", ""),
 ("Provenance", "The literature-overlay artifacts in runtime/internal-review-20260907/ are host-local", "runtime/internal-review-20260907/research-review.md", ""),
 ("Row rules", "The parser rejects repeated variant ids across rows unless allow_repeated_pairings is set", "mva_prioritizer/track1_submission.py", "if variant in seen_variants and not allow_repeated_pairings:"),
 ("Step 4 stage 1", "Tier is the first key of the evidence sort, before lane count and native rank", "mva_prioritizer/candidate_selection.py", "TIERS.index(tier),"),
 ("Publication", "docs/20 says the history scan found three historical blobs, that the fixture gene was pre-registered from literature and is also a case-flagged recurrent gene, and that both facts are checkable only from runtime/", "docs/20-track1-submission-gate.md", "checkable only from the host-local artifacts"),
]

claims = []
for n, (where, claim, path, needle) in enumerate(CLAIMS, 1):
    claims.append({"claim_id": f"c{n:02d}", "where": where, "claim": claim, "source_path": path,
                   "excerpt": grab(path, needle) if needle else ("HOST-LOCAL ARTIFACT, NOT EXCERPTED" if not tracked(path) else "NO SOURCE FOUND")})

# sanity: no excerpt may come from runtime/ and no excerpt may carry a denied token
deny_path = ROOT / "runtime/privacy/denied-tokens.txt"
denied = [t.strip() for t in deny_path.read_text().splitlines() if t.strip()] if deny_path.exists() else []
for c in claims:
    assert not (c["source_path"].startswith("runtime/") and c["excerpt"] not in ("HOST-LOCAL ARTIFACT, NOT EXCERPTED",)), c["claim_id"]
    for t in denied:
        assert not re.search(rf"\b{re.escape(t)}\b", c["excerpt"]), f"{c['claim_id']} carries a denied token"

state = {"document": "docs/22-candidate-selection-rule.md", "claims": claims}
questions = {c["claim_id"]: {"type": "noul", "instructions":
    f"Consider the entry in `claims` whose `claim_id` is {c['claim_id']}. Does its `excerpt` fully support its `claim`, "
    "including every number, date, path and quoted line, with no contradiction? Answer no if any number differs, if the excerpt "
    "is about something else, if the excerpt says NO SOURCE FOUND or HOST-LOCAL ARTIFACT, or if the claim goes beyond what the excerpt says."}
    for c in claims}
req = {"state": state, "questions": questions}
(OUT / f"request-{TAG}.json").write_text(json.dumps(req, indent=1) + "\n")
(OUT / f"claims-{TAG}.json").write_text(json.dumps(claims, indent=1) + "\n")
print(f"{len(claims)} claims -> {OUT / f'request-{TAG}.json'}")
