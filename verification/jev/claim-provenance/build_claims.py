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
 ("Step 4 stage 2", "floor+pays_gt has mean rank points 43.438", "verification/scorer-hedging/policy-probe-result.txt", "floor+pays_gt"),
 ("Step 4 stage 2", "transitive+pays_gt has 579 comparisons below the plain sort", "verification/scorer-hedging/policy-probe-result.txt", "transitive+pays_gt"),
 ("Step 4 stage 2", "Direct promotion never scores below the plain sort", "verification/scorer-hedging/policy-probe-result.txt", "direct+pays_gt"),
 ("Step 4 stage 3", "The module keeps a losing pair only where points(r) > 0.5 * points(q)", "mva_prioritizer/candidate_selection.py", "_rank_points(j + 1) > 0.5 * _rank_points(winner_rank)"),
 ("Step 4 stage 3", "The probe's docstring states every policy is implemented inside the file and the module is measured as its own row", "verification/scorer-hedging/policy_probe.py", "Every policy here is implemented inside this file"),
 ("Step 4 stage 3", "The probe builds a policy for each of three promotion modes crossed with each STAGE3 entry, plus plain and module", "verification/scorer-hedging/policy_probe.py", 'STAGE3 = {'),
 ("Step 4 stage 3", "27,594 truth comparisons over 4,000 random pools", "verification/scorer-hedging/policy-probe-result.txt", "27,594 truth comparisons"),
 ("Step 4 stage 3", "direct+demote has 75 comparisons below the plain sort and mean rank points 46.574", "verification/scorer-hedging/policy-probe-result.txt", "direct+demote"),
 ("Step 4 stage 3", "direct+pays_ge has 0 comparisons below the plain sort and mean rank points 46.557", "verification/scorer-hedging/policy-probe-result.txt", "direct+pays_ge"),
 ("Step 4 stage 3", "Demoting at equality (pays_gt) dominates with mean 46.833 and is the best eligible policy", "verification/scorer-hedging/policy-probe-result.txt", "Best policy that never scores below"),
 ("Step 4 stage 3", "The module coincides with direct+pays_gt on all 4,000 pools", "verification/scorer-hedging/policy-probe-result.txt", "Module coincides with"),
 ("Step 4 stage 3", "verify_module.py reports zero pools with a permutation-dependent result", "verification/scorer-hedging/verify-module-result.txt", "D1  determinism"),
 ("Step 4 stage 3", "verify_module.py reports zero rank-point comparisons lower than the plain sort over 20,245", "verification/scorer-hedging/verify-module-result.txt", "D4  rank points LOWER"),
 ("Step 4 stage 3", "verify_module.py reports zero kept sharing pairs at a rank that does not strictly pay", "verification/scorer-hedging/verify-module-result.txt", "D2  kept sharing pair"),
 ("Verification", "brute_force_hedging.py returns 1 when strict violations are found, so it exits non-zero by design", "verification/scorer-hedging/brute_force_hedging.py", "return 1 if strict_violations else 0"),
 ("Verification", "hedging_modes.py main() returns 0, so it exits zero", "verification/scorer-hedging/hedging_modes.py", "    return 0\n\n\nif __name__"),
 ("Verification", "verify_determinism.py imports only the standard library and does not import the evaluator", "verification/scorer-hedging/verify_determinism.py", "import"),
 ("Verification", "The evaluator bytes are pinned by SHA-256 in tests/test_track1_submission.py", "tests/test_track1_submission.py", "sha256"),
 ("Verification", "Rank points is metric 1 in the official evaluator", "tools/official-track1/evaluation.py", "Rank points (metric 1)"),
 ("Verification", "case-token-scan running scripts/verify_no_case_tokens.py is a required Build OS command in product.json", "product.json", "case-token-scan"),
 ("Verification", "The gate's default denylist path is runtime/privacy/denied-tokens.txt under the repository root", "scripts/verify_no_case_tokens.py", "DEFAULT_DENYLIST = ROOT"),
 ("Review history", "The review of 1783250 returned FAIL with blocking findings B1, B2, B3", "verification/reviews/1783250.json", '"verdict"'),
 ("Review history", "B1: the probe's demote_all wrapped the module's pays test so always-demote was never run", "verification/reviews/1783250.json", "demote_all"),
 ("Review history", "B2: promotion can lift a weaker pair above the evidence winner", "verification/reviews/1783250.json", "evidence winner displaced"),
 ("Review history", "B3: tracked Jev request files carried case-derived gene symbols from a private aggregate report", "verification/reviews/1783250.json", "aggregate-report.md"),
 ("Review history", "The second Jev pass on 1783250 covered 71 claims in 4 calls", "verification/jev/claim-provenance/report-1783250.md", "71"),
 ("Provenance", "The frozen interval map at runtime/nine-gene-audit-20260909/gene-interval-map.json is host-local and not in the public tree", "runtime/nine-gene-audit-20260909/gene-interval-map.json", ""),
 ("Provenance", "The literature-overlay artifacts in runtime/internal-review-20260907/ are host-local", "runtime/internal-review-20260907/research-review.md", ""),
 ("Row rules", "The parser rejects repeated variant ids across rows unless --allow-repeated-pairings is passed", "mva_prioritizer/track1_submission.py", "if variant in seen_variants and not allow_repeated_pairings:"),
 ("Step 4 stage 1", "Tier is the first key of the evidence sort, before lane count and native rank", "mva_prioritizer/candidate_selection.py", "TIERS.index(tier),"),
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
