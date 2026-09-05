import de.charite.compbio.jannovar.annotation.VariantEffect;
import de.charite.compbio.jannovar.mendel.ModeOfInheritance;
import org.monarchinitiative.exomiser.core.analysis.InheritanceModeOptions;
import org.monarchinitiative.exomiser.core.analysis.score.InheritanceModeAnnotator;
import org.monarchinitiative.exomiser.core.filters.PathogenicityFilter;
import org.monarchinitiative.exomiser.core.genome.GenomeAssembly;
import org.monarchinitiative.exomiser.core.model.SampleGenotype;
import org.monarchinitiative.exomiser.core.model.SampleGenotypes;
import org.monarchinitiative.exomiser.core.model.VariantEvaluation;
import org.monarchinitiative.exomiser.core.model.frequency.Frequency;
import org.monarchinitiative.exomiser.core.model.frequency.FrequencyData;
import org.monarchinitiative.exomiser.core.model.frequency.FrequencySource;
import org.monarchinitiative.exomiser.core.model.pathogenicity.PathogenicityData;
import org.monarchinitiative.exomiser.core.model.pathogenicity.PathogenicityScore;
import org.monarchinitiative.exomiser.core.model.pathogenicity.PathogenicitySource;
import org.monarchinitiative.exomiser.core.model.pathogenicity.RemmScore;
import org.monarchinitiative.exomiser.core.model.pathogenicity.RevelScore;
import org.monarchinitiative.exomiser.core.model.pathogenicity.SpliceAiScore;
import org.monarchinitiative.exomiser.core.pedigree.Pedigree;
import org.monarchinitiative.svart.CoordinateSystem;
import org.monarchinitiative.svart.Strand;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

/**
 * Synthetic class-level probe of the pinned Exomiser 15.1.0 pathogenicity filter and inheritance annotator.
 * Public, synthetic coordinates only. The engine source and executable are not modified.
 */
public final class Probe {

    private static final String SAMPLE = "SYNTHETIC_PROBAND";
    private static final PathogenicityFilter BASELINE = new PathogenicityFilter(false, PathogenicityFilter.Target.NON_CODING);

    /** Same three-branch logic as PathogenicityFilter.filterNonCoding, with the REMM cutoff as a parameter. */
    static boolean nonCodingPass(PathogenicityData data, double remmCutoff) {
        PathogenicityScore cadd = data.pathogenicityScore(PathogenicitySource.CADD);
        if (cadd != null && cadd.rawScore() >= 15.0) return true;
        PathogenicityScore splice = data.pathogenicityScore(PathogenicitySource.SPLICE_AI);
        if (splice != null && splice.score() > SpliceAiScore.NON_SPLICEOGENIC_SCORE) return true;
        PathogenicityScore remm = data.pathogenicityScore(PathogenicitySource.REMM);
        return remm != null && remm.score() > remmCutoff;
    }

    static boolean mirrorPass(VariantEvaluation v, double remmCutoff) {
        if (v.isWhiteListed()) return true;
        if (v.isNonCodingVariant()) return nonCodingPass(v.pathogenicityData(), remmCutoff);
        return true; // Target.NON_CODING preserves coding variants, same as the pinned filter.
    }

    static boolean strictPass(VariantEvaluation v) {
        return mirrorPass(v, RemmScore.PATHOGENIC_THRESHOLD);
    }

    static int mirrorMismatches = 0;
    static int mirrorComparisons = 0;

    /** Engine verdict, and a check that the mirror at the baseline constant agrees with the engine. */
    static boolean enginePass(VariantEvaluation v) {
        boolean engine = BASELINE.runFilter(v).passed();
        mirrorComparisons++;
        if (engine != mirrorPass(v, RemmScore.LIKELY_PATHOGENIC_THRESHOLD)) mirrorMismatches++;
        return engine;
    }

    static VariantEvaluation variant(int pos, String ref, String alt, VariantEffect effect, PathogenicityData data) {
        return VariantEvaluation.builder()
                .variant(GenomeAssembly.HG38.getContigById(1), Strand.POSITIVE, CoordinateSystem.ONE_BASED, pos, ref, alt)
                .genomeAssembly(GenomeAssembly.HG38)
                .geneSymbol("SYNTHGENE").geneId("SYNTH:1")
                .variantEffect(effect)
                .pathogenicityData(data)
                .sampleGenotypes(SampleGenotypes.of(SAMPLE, SampleGenotype.het()))
                .build();
    }

    static VariantEvaluation variant(int pos, String ref, String alt, VariantEffect effect, PathogenicityData data, float freqPercent) {
        return VariantEvaluation.builder()
                .variant(GenomeAssembly.HG38.getContigById(1), Strand.POSITIVE, CoordinateSystem.ONE_BASED, pos, ref, alt)
                .genomeAssembly(GenomeAssembly.HG38)
                .geneSymbol("SYNTHGENE").geneId("SYNTH:1")
                .variantEffect(effect)
                .pathogenicityData(data)
                .frequencyData(FrequencyData.of(Frequency.of(FrequencySource.GNOMAD_G_NFE, freqPercent)))
                .sampleGenotypes(SampleGenotypes.of(SAMPLE, SampleGenotype.het()))
                .build();
    }

    static String q(String s) { return "\"" + s.replace("\"", "\\\"") + "\""; }

    public static void main(String[] args) {
        StringBuilder out = new StringBuilder();
        out.append("{\"engine\":\"exomiser-core-15.1.0.jar from hash-verified public distribution\",");
        out.append("\"likely_pathogenic_threshold\":").append(RemmScore.LIKELY_PATHOGENIC_THRESHOLD).append(',');
        out.append("\"pathogenic_threshold\":").append(RemmScore.PATHOGENIC_THRESHOLD).append(',');
        out.append("\"baseline_filter\":").append(q(BASELINE.toString())).append(',');

        // Threshold cases: noncoding intron variants carrying only a REMM score.
        float[] scores = {0.913f, 0.914f, 0.9140001f, 0.915f, 0.95f, 0.962f, 0.963f, 0.9630001f, 0.964f, 1.0f};
        out.append("\"threshold_cases\":[");
        for (int i = 0; i < scores.length; i++) {
            RemmScore remm = RemmScore.of(scores[i]);
            VariantEvaluation v = variant(100000 + i, "A", "T", VariantEffect.CODING_TRANSCRIPT_INTRON_VARIANT, PathogenicityData.of(remm));
            boolean base = enginePass(v);
            if (i > 0) out.append(',');
            out.append('{')
               .append("\"remm_float\":").append(Float.toString(remm.score())).append(',')
               .append("\"remm_widened_double\":").append(Double.toString((double) remm.score())).append(',')
               .append("\"non_coding\":").append(v.isNonCodingVariant()).append(',')
               .append("\"baseline_pass\":").append(base).append(',')
               .append("\"strict_pass\":").append(strictPass(v))
               .append('}');
        }
        out.append("],");

        // Coding control: missense with a low REVEL score passes under Target.NON_CODING in both baseline and strict.
        VariantEvaluation coding = variant(200000, "G", "C", VariantEffect.MISSENSE_VARIANT, PathogenicityData.of(RevelScore.of(0.1f)));
        out.append("\"coding_control\":{\"effect\":").append(q(coding.variantEffect().toString()))
           .append(",\"non_coding\":").append(coding.isNonCodingVariant())
           .append(",\"baseline_pass\":").append(enginePass(coding))
           .append(",\"strict_pass\":").append(strictPass(coding)).append("},");

        // No-score noncoding control: fails both.
        VariantEvaluation noScore = variant(300000, "C", "G", VariantEffect.CODING_TRANSCRIPT_INTRON_VARIANT, PathogenicityData.empty());
        out.append("\"no_score_noncoding_control\":{\"baseline_pass\":").append(enginePass(noScore))
           .append(",\"strict_pass\":").append(strictPass(noScore)).append("},");

        // Whitelist bypass control.
        VariantEvaluation white = VariantEvaluation.builder()
                .variant(GenomeAssembly.HG38.getContigById(1), Strand.POSITIVE, CoordinateSystem.ONE_BASED, 400000, "T", "A")
                .genomeAssembly(GenomeAssembly.HG38).geneSymbol("SYNTHGENE").geneId("SYNTH:1")
                .variantEffect(VariantEffect.CODING_TRANSCRIPT_INTRON_VARIANT)
                .pathogenicityData(PathogenicityData.empty()).whiteListed(true)
                .sampleGenotypes(SampleGenotypes.of(SAMPLE, SampleGenotype.het())).build();
        out.append("\"whitelist_control\":{\"baseline_pass\":").append(enginePass(white))
           .append(",\"strict_pass\":").append(strictPass(white)).append("},");

        // Inheritance recomputation: an unphased heterozygous pair in one gene of a single affected proband.
        // Partner A survives both cutoffs (0.97). Partner B survives baseline only (0.95).
        VariantEvaluation a = variant(500000, "A", "G", VariantEffect.CODING_TRANSCRIPT_INTRON_VARIANT, PathogenicityData.of(RemmScore.of(0.97f)));
        VariantEvaluation b = variant(600000, "T", "C", VariantEffect.CODING_TRANSCRIPT_INTRON_VARIANT, PathogenicityData.of(RemmScore.of(0.95f)));
        InheritanceModeAnnotator annotator = new InheritanceModeAnnotator(Pedigree.justProband(SAMPLE), InheritanceModeOptions.defaults());

        List<VariantEvaluation> baselineSurvivors = new ArrayList<>();
        for (VariantEvaluation v : List.of(a, b)) if (enginePass(v)) baselineSurvivors.add(v);
        List<VariantEvaluation> strictSurvivors = new ArrayList<>();
        for (VariantEvaluation v : List.of(a, b)) if (strictPass(v)) strictSurvivors.add(v);

        out.append("\"pair\":{\"a_remm\":0.97,\"b_remm\":0.95,")
           .append("\"baseline_survivors\":").append(baselineSurvivors.size()).append(',')
           .append("\"strict_survivors\":").append(strictSurvivors.size()).append(',')
           .append("\"modes_after_baseline\":").append(modes(annotator, baselineSurvivors)).append(',')
           .append("\"modes_after_strict_rerun\":").append(modes(annotator, strictSurvivors)).append(',')
           .append("\"posthoc_note\":").append(q("Filtering the baseline records to REMM > 0.963 keeps A with its baseline-computed modes. A rerun recomputes modes from the surviving set."))
           .append("},");

        // Frequency-gated pair. Survivor at 1% population frequency: above the 0.1% AD cutoff, below the 2% AR comp-het cutoff.
        // With its partner it is recessive-compatible only. Alone, no defined mode accepts it.
        VariantEvaluation fa = variant(700000, "G", "A", VariantEffect.CODING_TRANSCRIPT_INTRON_VARIANT, PathogenicityData.of(RemmScore.of(0.97f)), 1.0f);
        VariantEvaluation fb = variant(800000, "C", "T", VariantEffect.CODING_TRANSCRIPT_INTRON_VARIANT, PathogenicityData.of(RemmScore.of(0.95f)), 0.01f);
        List<VariantEvaluation> fBase = new ArrayList<>();
        for (VariantEvaluation v : List.of(fa, fb)) if (enginePass(v)) fBase.add(v);
        List<VariantEvaluation> fStrict = new ArrayList<>();
        for (VariantEvaluation v : List.of(fa, fb)) if (strictPass(v)) fStrict.add(v);
        out.append("\"frequency_gated_pair\":{\"inheritance_options\":\"InheritanceModeOptions.defaults()\",")
           .append("\"ad_max_freq_percent\":").append(annotator.getInheritanceModeOptions().getMaxFreqForMode(ModeOfInheritance.AUTOSOMAL_DOMINANT)).append(',')
           .append("\"ar_max_freq_percent\":").append(annotator.getInheritanceModeOptions().getMaxFreqForMode(ModeOfInheritance.AUTOSOMAL_RECESSIVE)).append(',')
           .append("\"survivor_frequency_percent\":1.0,\"partner_frequency_percent\":0.01,\"survivor_remm\":0.97,\"partner_remm\":0.95,")
           .append("\"baseline_survivors\":").append(fBase.size()).append(',')
           .append("\"strict_survivors\":").append(fStrict.size()).append(',')
           .append("\"modes_after_baseline\":").append(modes(annotator, fBase)).append(',')
           .append("\"modes_after_strict_rerun\":").append(modes(annotator, fStrict))
           .append("},");
        out.append("\"mirror_engine_comparisons\":").append(mirrorComparisons).append(',');
        out.append("\"mirror_mismatches_at_baseline_cutoff\":").append(mirrorMismatches).append('}');
        System.out.println(out);
        if (mirrorMismatches != 0) System.exit(1);
    }

    static String modes(InheritanceModeAnnotator annotator, List<VariantEvaluation> variants) {
        Map<ModeOfInheritance, List<VariantEvaluation>> result = annotator.computeCompatibleInheritanceModes(variants);
        Map<String, Integer> counts = new TreeMap<>();
        for (Map.Entry<ModeOfInheritance, List<VariantEvaluation>> e : result.entrySet()) counts.put(e.getKey().name(), e.getValue().size());
        StringBuilder sb = new StringBuilder("{");
        boolean first = true;
        for (Map.Entry<String, Integer> e : counts.entrySet()) {
            if (!first) sb.append(',');
            first = false;
            sb.append(q(e.getKey())).append(':').append(e.getValue());
        }
        return sb.append('}').toString();
    }
}
