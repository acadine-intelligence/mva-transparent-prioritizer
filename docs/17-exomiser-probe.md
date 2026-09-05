# Exomiser 15.1.0 threshold and inheritance probe

Date: 2026-09-05. Scope: public synthetic probe of two engine classes. No patient data, no reference databases, no private analysis.

## What ran

The Java program checked in as `tools/exomiser-probe/Probe.java` (SHA-256 `f8947dac3c5021e3cd482d41b5e091292fcba6af257823d89698f1b41b346881`), compiled against the published `exomiser-core-15.1.0.jar` and executed with the pinned Temurin 21 JDK. Both artifacts were downloaded from their public release URLs into a scratch directory on the M4 and matched the SHA-256 pins in `config/reference-bundle.json` exactly. The engine source was not modified. The encrypted M1 volume was not touched. The same directory holds the later `RoundTrip.java` and `Recompute.java`; each fixture in `tests/fixtures/` names the program and the run that produced it.

The probe constructs synthetic `VariantEvaluation` objects on GRCh38 chromosome 1 at invented positions, runs them through the engine's own `PathogenicityFilter(false, Target.NON_CODING)` (the genome preset's configuration), and feeds survivors to the engine's own `InheritanceModeAnnotator` for a single affected proband.

Artifacts: `tools/exomiser-probe/` holds the sources; the run receipt lives alongside them in the private run history. `tests/fixtures/exomiser_probe_output.json` is the verbatim output. `tests/test_exomiser_probe_fixture.py` pins the recorded behaviour.

## Findings

The ReMM cutoff is a compiled constant. `RemmScore.LIKELY_PATHOGENIC_THRESHOLD` is `0.914` and `PATHOGENIC_THRESHOLD` is `0.963`. The filter reads the first. There is no configuration path to the second in this version. A stricter run needs a source change and a rebuilt jar, or a post-filter that mirrors the engine logic.

Both cutoffs are strict greater-than. A score of exactly `0.914f` fails the baseline filter; `0.9140001f` passes. The same holds at `0.963`. The float `0.914f` widens to `0.9139999747...` as a double, below the constant, so the strict comparison is stable at the boundary rather than an accident of representation.

A parent-written mirror of `filterNonCoding` with the cutoff as a parameter agreed with the engine on all 17 comparisons at the baseline constant. The probe fails closed if a mismatch is ever recorded. This gives the mirror at `0.963` a defensible claim to represent the engine's behaviour at that cutoff, within the class-level scope.

Controls behaved as the source reads. A missense variant with REVEL 0.1 passes under `Target.NON_CODING` at both cutoffs because the filter preserves coding variants. A noncoding variant with no score fails both. A whitelisted variant with no score passes both.

The inheritance result is the part that matters for the earlier sensitivity plan. Two unphased heterozygous noncoding variants in one gene, REMM 0.97 and 0.95, both survive the baseline filter. The engine annotates the pair as compatible with autosomal dominant (2 variants) and autosomal recessive (2 variants). Under the stricter cutoff only the 0.97 variant survives. Rerunning the annotator on the survivor yields autosomal dominant only. Autosomal recessive disappears. A post-hoc filter of the baseline records would have kept the 0.97 variant with its baseline-computed recessive compatibility attached.

A second pair adds population frequency, which the annotator gates per mode. The engine's default cutoffs are 0.1% for dominant and 2% for recessive compound-heterozygous. The survivor (REMM 0.97) carries a synthetic 1% frequency; its partner (REMM 0.95) carries 0.01%. At baseline the engine reports dominant for the rare partner only and recessive for both. After the stricter cutoff removes the partner, a rerun on the 1% survivor returns no compatible mode at all. That variant would drop out of the results entirely. Post-hoc filtering of the baseline records would carry its recessive label forward as if nothing had changed. This is the sharper version of the finding: not a mode downgrade but a candidate that a rerun removes and a post-hoc filter keeps.

## What this does and does not establish

It establishes, against the real engine classes, that final-record threshold filtering is not equivalent to a rerun when a compound pair straddles the cutoff. This was previously shown only with a toy Python counterexample. It also fixes the exact boundary semantics and confirms the cutoff cannot be changed by configuration in 15.1.0.

It confirms the reading of the source that the public noncoding benchmark (`config/noncoding-benchmark-v1.json`, 2026-08-31) was built on. That benchmark models both cutoffs as strict greater-than using Decimal arithmetic, with boundary cases at 0.913999, 0.914, and 0.914001. The engine's float behaviour (0.914f fails, 0.9140001f passes) agrees. The benchmark had been checked against the source text; it is now checked against the executed engine.

It does not measure how often this happens in the private genome. It does not exercise phenotype scoring, gene ranking, the frequency filter, regulatory feature filtering, or the full CLI. Single-proband unphased data cannot distinguish cis from trans; the engine's recessive annotation reflects that ambiguity and so does this probe.

## Consequence for the sensitivity plan

The old staged post-hoc script is confirmed invalid on engine grounds, not only on toy grounds. A private ReMM 0.963 sensitivity comparison, if ever approved, must either rebuild the engine with the constant changed or apply the validated mirror before inheritance annotation and then rerun annotation. Filtering the frozen output is not a substitute.

## Verification

`python3 -m unittest tests.test_exomiser_probe_fixture` passes 7 tests. The test file was observed failing before the fixture existed. Five deliberate fixture corruptions (recessive mode retained after rerun, a recorded mirror mismatch, an inclusive boundary, a dropped coding control, a recessive label surviving the frequency-gated rerun) each caused test failure; the fixture hash was restored afterwards.
