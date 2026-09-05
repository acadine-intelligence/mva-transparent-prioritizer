import de.charite.compbio.jannovar.annotation.VariantEffect;
import de.charite.compbio.jannovar.mendel.ModeOfInheritance;
import org.monarchinitiative.exomiser.core.analysis.AnalysisResults;
import org.monarchinitiative.exomiser.core.analysis.InheritanceModeOptions;
import org.monarchinitiative.exomiser.core.analysis.sample.Sample;
import org.monarchinitiative.exomiser.core.analysis.score.InheritanceModeAnalyser;
import org.monarchinitiative.exomiser.core.analysis.score.InheritanceModeAnnotator;
import org.monarchinitiative.exomiser.core.filters.FilterResult;
import org.monarchinitiative.exomiser.core.filters.FilterType;
import org.monarchinitiative.exomiser.core.filters.PathogenicityFilter;
import org.monarchinitiative.exomiser.core.genome.GenomeAssembly;
import org.monarchinitiative.exomiser.core.model.Gene;
import org.monarchinitiative.exomiser.core.model.GeneIdentifier;
import org.monarchinitiative.exomiser.core.model.GeneScore;
import org.monarchinitiative.exomiser.core.model.SampleGenotype;
import org.monarchinitiative.exomiser.core.model.SampleGenotypes;
import org.monarchinitiative.exomiser.core.model.VariantEvaluation;
import org.monarchinitiative.exomiser.core.model.frequency.Frequency;
import org.monarchinitiative.exomiser.core.model.frequency.FrequencyData;
import org.monarchinitiative.exomiser.core.model.frequency.FrequencySource;
import org.monarchinitiative.exomiser.core.model.pathogenicity.PathogenicityData;
import org.monarchinitiative.exomiser.core.model.pathogenicity.RemmScore;
import org.monarchinitiative.exomiser.core.model.pathogenicity.RevelScore;
import org.monarchinitiative.exomiser.core.pedigree.Pedigree;
import org.monarchinitiative.exomiser.core.writers.JsonResultsWriter;
import org.monarchinitiative.exomiser.core.writers.TsvVariantResultsWriter;
import org.monarchinitiative.exomiser.core.writers.OutputFormat;
import org.monarchinitiative.exomiser.core.writers.OutputSettings;
import org.monarchinitiative.svart.CoordinateSystem;
import org.monarchinitiative.svart.Strand;

import java.nio.file.Path;
import java.util.EnumSet;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

/**
 * Serialize synthetic genes through the real JsonResultsWriter after the real baseline
 * PathogenicityFilter and InheritanceModeAnalyser, so the two-stage recomputation can be
 * validated against the writer's actual field names. Also emit the direct engine answer at
 * the strict cutoff for the same genes, for comparison.
 */
public final class RoundTrip {

    private static final String SAMPLE = "SYNTHETIC_PROBAND";
    private static final PathogenicityFilter BASELINE = new PathogenicityFilter(false, PathogenicityFilter.Target.NON_CODING);

    static VariantEvaluation.Builder base(int chr, int pos, String ref, String alt, String gene, VariantEffect effect) {
        return VariantEvaluation.builder()
                .variant(GenomeAssembly.HG38.getContigById(chr), Strand.POSITIVE, CoordinateSystem.ONE_BASED, pos, ref, alt)
                .genomeAssembly(GenomeAssembly.HG38)
                .geneSymbol(gene).geneId("SYNTH:" + gene)
                .variantEffect(effect)
                .sampleGenotypes(SampleGenotypes.of(SAMPLE, SampleGenotype.het()));
    }

    static VariantEvaluation nc(int pos, String gene, float remm, float freqPercent) {
        return base(1, pos, "A", "T", gene, VariantEffect.CODING_TRANSCRIPT_INTRON_VARIANT)
                .pathogenicityData(PathogenicityData.of(RemmScore.of(remm)))
                .frequencyData(FrequencyData.of(Frequency.of(FrequencySource.GNOMAD_G_NFE, freqPercent)))
                .build();
    }

    static Gene gene(String symbol, VariantEvaluation... variants) {
        Gene g = new Gene(GeneIdentifier.builder().geneSymbol(symbol).geneId("SYNTH:" + symbol).build());
        for (VariantEvaluation v : variants) g.addVariant(v);
        return g;
    }

    /** Run the baseline pathogenicity filter then the real inheritance analyser, as the genome preset orders them. */
    static void runBaseline(List<Gene> genes, InheritanceModeAnalyser analyser) {
        for (Gene g : genes) {
            for (VariantEvaluation v : g.variantEvaluations()) v.addFilterResult(BASELINE.runFilter(v));
            analyser.analyseInheritanceModes(g);
        }
    }

    public static void main(String[] args) throws Exception {
        Path outDir = Path.of(args[0]);
        InheritanceModeAnnotator annotator = new InheritanceModeAnnotator(Pedigree.justProband(SAMPLE), InheritanceModeOptions.defaults());
        InheritanceModeAnalyser analyser = new InheritanceModeAnalyser(annotator);

        // Four synthetic genes covering the cases the design must handle.
        List<Gene> genes = List.of(
            // G1: both partners above strict cutoff. Survives everything.
            gene("SYNG1", nc(100000, "SYNG1", 0.98f, 0.01f), nc(110000, "SYNG1", 0.97f, 0.01f)),
            // G2: partner below strict cutoff; survivor rare, so AD remains after rerun.
            gene("SYNG2", nc(200000, "SYNG2", 0.97f, 0.01f), nc(210000, "SYNG2", 0.95f, 0.01f)),
            // G3: partner below strict cutoff; survivor at 1% so no mode remains after rerun.
            gene("SYNG3", nc(300000, "SYNG3", 0.97f, 1.0f), nc(310000, "SYNG3", 0.95f, 0.01f)),
            // G4: single variant below baseline cutoff; fails at baseline, never written as passed.
            gene("SYNG4", nc(400000, "SYNG4", 0.90f, 0.01f)),
            // G6: same as G2 but the survivor carries a non-default noncoding effect (REGULATORY_REGION_VARIANT).
            gene("SYNG6", base(1, 600000, "A", "T", "SYNG6", VariantEffect.REGULATORY_REGION_VARIANT)
                    .pathogenicityData(PathogenicityData.of(RemmScore.of(0.97f)))
                    .frequencyData(FrequencyData.of(Frequency.of(FrequencySource.GNOMAD_G_NFE, 0.01f))).build(),
                 nc(610000, "SYNG6", 0.95f, 0.01f)),
            // G5: coding missense with weak REVEL; passes under NON_CODING target at both cutoffs.
            gene("SYNG5", base(1, 500000, "G", "C", "SYNG5", VariantEffect.MISSENSE_VARIANT)
                    .pathogenicityData(PathogenicityData.of(RevelScore.of(0.1f)))
                    .frequencyData(FrequencyData.of(Frequency.of(FrequencySource.GNOMAD_G_NFE, 0.01f))).build())
        );
        runBaseline(genes, analyser);
        // PASS_ONLY semantics, exactly as PassOnlyAnalysisRunner.getGenesWithVariants applies them: failed
        // variants are removed from each gene, then genes with no variants or that failed are dropped before
        // scoring and writing. The frozen lane ran in PASS_ONLY mode, so the synthetic outputs follow the same rule.
        List<Gene> passOnly = new java.util.ArrayList<>();
        for (Gene g : genes) {
            g.variantEvaluations().removeIf(v -> !v.passedFilters());
            if (g.hasVariants() && g.passedFilters()) passOnly.add(g);
        }
        // The TSV writer walks GeneScoreRanker.rankedVariants(), which needs one GeneScore per compatible
        // mode with a non-zero combined score. RawScoreGeneScorer normally builds these; here a synthetic
        // score is enough because only membership and mode, not rank, are under test.
        double synthetic = 0.9;
        for (Gene g : passOnly) {
            for (ModeOfInheritance moi : g.compatibleInheritanceModes()) {
                g.addGeneScore(GeneScore.builder().geneIdentifier(g.geneIdentifier()).modeOfInheritance(moi)
                        .combinedScore(synthetic).phenotypeScore(synthetic).variantScore(synthetic)
                        .contributingVariants(g.variantEvaluations().stream().filter(v -> v.isCompatibleWith(moi)).toList()).build());
                synthetic -= 0.01;
            }
        }

        Sample sample = Sample.builder().vcfPath(Path.of("synthetic.vcf")).probandSampleName(SAMPLE).pedigree(Pedigree.justProband(SAMPLE)).build();
        AnalysisResults results = AnalysisResults.builder().sample(sample).sampleNames(List.of(SAMPLE)).genes(passOnly).build();
        OutputSettings settings = OutputSettings.builder()
                .outputDirectory(outDir).outputFileName("roundtrip")
                .outputFormats(EnumSet.of(OutputFormat.JSON))
                .outputContributingVariantsOnly(false)
                .build();
        new JsonResultsWriter().writeFile(results, settings);
        new TsvVariantResultsWriter().writeFile(results, settings);

        // Direct engine answer at the strict cutoff, for the same genes rebuilt fresh.
        StringBuilder sb = new StringBuilder("{");
        boolean first = true;
        for (Gene g : genes) {
            java.util.List<VariantEvaluation> strict = new java.util.ArrayList<>();
            for (VariantEvaluation v : g.variantEvaluations()) {
                boolean pass = v.isWhiteListed() || !v.isNonCodingVariant()
                        || (v.pathogenicityData().pathogenicityScore(org.monarchinitiative.exomiser.core.model.pathogenicity.PathogenicitySource.REMM) != null
                            && v.pathogenicityData().pathogenicityScore(org.monarchinitiative.exomiser.core.model.pathogenicity.PathogenicitySource.REMM).score() > RemmScore.PATHOGENIC_THRESHOLD);
                if (pass) strict.add(v);
            }
            Map<ModeOfInheritance, List<VariantEvaluation>> modes = annotator.computeCompatibleInheritanceModes(strict);
            Map<String, Integer> counts = new TreeMap<>();
            for (Map.Entry<ModeOfInheritance, List<VariantEvaluation>> e : modes.entrySet()) counts.put(e.getKey().name(), e.getValue().size());
            if (!first) sb.append(',');
            first = false;
            sb.append('"').append(g.geneSymbol()).append("\":{\"strict_survivors\":").append(strict.size()).append(",\"modes\":{");
            boolean f2 = true;
            for (Map.Entry<String, Integer> e : counts.entrySet()) { if (!f2) sb.append(','); f2 = false; sb.append('"').append(e.getKey()).append("\":").append(e.getValue()); }
            sb.append("}}");
        }
        sb.append('}');
        java.nio.file.Files.writeString(outDir.resolve("engine-strict-direct.json"), sb + "\n");
        System.out.println("ok");
    }
}
