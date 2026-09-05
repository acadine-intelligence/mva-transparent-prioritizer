import de.charite.compbio.jannovar.annotation.VariantEffect;
import de.charite.compbio.jannovar.mendel.ModeOfInheritance;
import org.monarchinitiative.exomiser.core.analysis.InheritanceModeOptions;
import org.monarchinitiative.exomiser.core.analysis.score.InheritanceModeAnnotator;
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
import org.monarchinitiative.exomiser.core.model.pathogenicity.SpliceAiScore;
import org.monarchinitiative.exomiser.core.pedigree.Pedigree;
import org.monarchinitiative.svart.CoordinateSystem;
import org.monarchinitiative.svart.Strand;

import java.io.BufferedReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;

/**
 * Two-stage recomputation of a noncoding lane at a stricter ReMM cutoff, driven only by an
 * Exomiser 15.1.0 variants TSV. Stage 1 applies the validated filter mirror per unique variant.
 * Stage 2 rebuilds the survivors and asks the real InheritanceModeAnnotator which modes remain.
 *
 * Input: path to a TSV written by TsvVariantResultsWriter, the proband sample name, an output path.
 * Output: JSON keyed by gene symbol with strict_survivors and modes, in the same shape as
 * engine-strict-direct.json, so the two can be compared byte for byte after normalisation.
 *
 * Reads the input once, read-only. Writes only the output path. No reference database.
 */
public final class Recompute {

    static final double CUTOFF = RemmScore.PATHOGENIC_THRESHOLD; // 0.963, compiled constant

    static final Map<String, VariantEffect> SO_TO_EFFECT = new HashMap<>();
    static {
        for (VariantEffect e : VariantEffect.values()) SO_TO_EFFECT.put(e.getSequenceOntologyTerm(), e);
    }

    /** Mirror of PathogenicityFilter.filterNonCoding with the cutoff as a parameter. Same three branches. */
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
        return true; // Target.NON_CODING keeps coding variants.
    }

    record Row(String gene, String contig, int start, int end, String ref, String alt, String moi,
               boolean whitelisted, String genotype, String soTerm, String allFreq, String allPath) {}

    static List<Row> readRows(Path tsv) throws Exception {
        List<Row> rows = new ArrayList<>();
        try (BufferedReader r = Files.newBufferedReader(tsv, StandardCharsets.UTF_8)) {
            String header = r.readLine();
            if (header == null || !header.startsWith("#RANK\t")) throw new IllegalStateException("not an Exomiser variants TSV");
            List<String> cols = List.of(header.split("\t", -1));
            int cGene = cols.indexOf("GENE_SYMBOL"), cMoi = cols.indexOf("MOI"), cWl = cols.indexOf("WHITELIST_VARIANT");
            int cContig = cols.indexOf("CONTIG"), cStart = cols.indexOf("START"), cEnd = cols.indexOf("END");
            int cRef = cols.indexOf("REF"), cAlt = cols.indexOf("ALT"), cGt = cols.indexOf("GENOTYPE");
            int cFc = cols.indexOf("FUNCTIONAL_CLASS"), cFreq = cols.indexOf("ALL_FREQ"), cPath = cols.indexOf("ALL_PATH");
            for (int c : new int[]{cGene, cMoi, cWl, cContig, cStart, cEnd, cRef, cAlt, cGt, cFc, cFreq, cPath}) {
                if (c < 0) throw new IllegalStateException("missing TSV column");
            }
            String line;
            while ((line = r.readLine()) != null) {
                if (line.isEmpty()) continue;
                String[] f = line.split("\t", -1);
                rows.add(new Row(f[cGene], f[cContig], Integer.parseInt(f[cStart]), Integer.parseInt(f[cEnd]), f[cRef], f[cAlt],
                        f[cMoi], "1".equals(f[cWl]), f[cGt], f[cFc], f[cFreq], f[cPath]));
            }
        }
        return rows;
    }

    static FrequencyData parseFreq(String allFreq) {
        if (allFreq.isEmpty()) return FrequencyData.empty();
        List<Frequency> fs = new ArrayList<>();
        for (String kv : allFreq.split(",")) {
            String[] p = kv.split("=", 2);
            fs.add(Frequency.of(FrequencySource.valueOf(p[0]), Float.parseFloat(p[1])));
        }
        return FrequencyData.of(fs);
    }

    static PathogenicityData parsePath(String allPath) {
        if (allPath.isEmpty()) return PathogenicityData.empty();
        List<PathogenicityScore> ps = new ArrayList<>();
        for (String kv : allPath.split(",")) {
            String[] p = kv.split("=", 2);
            ps.add(PathogenicityScore.of(PathogenicitySource.valueOf(p[0]), Float.parseFloat(p[1])));
        }
        return PathogenicityData.of(ps);
    }

    static VariantEvaluation rebuild(Row row, String sample) {
        VariantEffect effect = SO_TO_EFFECT.get(row.soTerm());
        if (effect == null) throw new IllegalStateException("unknown SO term " + row.soTerm());
        VariantEvaluation v = VariantEvaluation.builder()
                .variant(GenomeAssembly.HG38.getContigByName(row.contig()), Strand.POSITIVE, CoordinateSystem.ONE_BASED,
                        row.start(), row.ref(), row.alt())
                .genomeAssembly(GenomeAssembly.HG38)
                .geneSymbol(row.gene()).geneId("TSV:" + row.gene())
                .variantEffect(effect)
                .sampleGenotypes(SampleGenotypes.of(sample, SampleGenotype.parseGenotype(row.genotype())))
                .frequencyData(parseFreq(row.allFreq()))
                .pathogenicityData(parsePath(row.allPath()))
                .build();
        if (row.whitelisted()) v.setWhiteListed(true);
        return v;
    }

    /** JSON string literal with the two escapes that matter for symbols and keys. */
    static String q(String s) {
        return "\"" + s.replace("\\", "\\\\").replace("\"", "\\\"") + "\"";
    }

    static String jsonList(Set<String> values) {
        StringBuilder b = new StringBuilder("[");
        boolean first = true;
        for (String v : new TreeSet<>(values)) { if (!first) b.append(','); first = false; b.append(q(v)); }
        return b.append(']').toString();
    }

    public static void main(String[] args) throws Exception {
        Path tsv = Path.of(args[0]);
        String sample = args[1];
        Path out = Path.of(args[2]);
        Path detailOut = args.length > 3 ? Path.of(args[3]) : null;

        // TSV MOI abbreviations back to the engine's mode names, from the engine's own enum.
        Map<String, String> abbreviationToMode = new HashMap<>();
        for (ModeOfInheritance moi : ModeOfInheritance.values()) {
            if (moi.getAbbreviation() != null) abbreviationToMode.put(moi.getAbbreviation(), moi.name());
        }
        abbreviationToMode.put("ANY", ModeOfInheritance.ANY.name());

        List<Row> rows = readRows(tsv);
        // Collapse rows to unique variants per gene; record the baseline MOI set per variant.
        Map<String, Map<String, Row>> uniqueByGene = new LinkedHashMap<>();
        Map<String, Set<String>> baselineModes = new HashMap<>();
        for (Row row : rows) {
            String key = row.contig() + "|" + row.start() + "|" + row.ref() + "|" + row.alt();
            uniqueByGene.computeIfAbsent(row.gene(), g -> new LinkedHashMap<>()).putIfAbsent(key, row);
            String mode = abbreviationToMode.get(row.moi());
            if (mode == null) throw new IllegalStateException("unknown MOI abbreviation " + row.moi());
            baselineModes.computeIfAbsent(row.gene() + "#" + key, k -> new TreeSet<>()).add(mode);
        }

        InheritanceModeAnnotator annotator = new InheritanceModeAnnotator(Pedigree.justProband(sample), InheritanceModeOptions.defaults());

        StringBuilder sb = new StringBuilder("{");
        StringBuilder detail = new StringBuilder("{\"tsv_rows\":" + rows.size() + ",\"cutoff\":" + CUTOFF + ",\"genes\":{");
        boolean first = true;
        int totalRows = rows.size(), totalUnique = 0, stage1Kept = 0, genesWithMode = 0;
        for (Map.Entry<String, Map<String, Row>> e : uniqueByGene.entrySet()) {
            String gene = e.getKey();
            List<VariantEvaluation> survivors = new ArrayList<>();
            Map<String, VariantEvaluation> keyToSurvivor = new LinkedHashMap<>();
            Set<String> geneBaselineModes = new TreeSet<>();
            for (Map.Entry<String, Row> kv : e.getValue().entrySet()) {
                totalUnique++;
                geneBaselineModes.addAll(baselineModes.get(gene + "#" + kv.getKey()));
                VariantEvaluation v = rebuild(kv.getValue(), sample);
                if (mirrorPass(v, CUTOFF)) { survivors.add(v); keyToSurvivor.put(kv.getKey(), v); }
            }
            stage1Kept += survivors.size();
            Map<ModeOfInheritance, List<VariantEvaluation>> modes = annotator.computeCompatibleInheritanceModes(survivors);
            Map<String, Integer> counts = new TreeMap<>();
            Map<String, Set<String>> strictModesByKey = new HashMap<>();
            for (Map.Entry<ModeOfInheritance, List<VariantEvaluation>> m : modes.entrySet()) {
                counts.put(m.getKey().name(), m.getValue().size());
                for (VariantEvaluation ve : m.getValue()) {
                    for (Map.Entry<String, VariantEvaluation> ks : keyToSurvivor.entrySet()) {
                        if (ks.getValue() == ve) strictModesByKey.computeIfAbsent(ks.getKey(), k -> new TreeSet<>()).add(m.getKey().name());
                    }
                }
            }
            if (!counts.isEmpty()) genesWithMode++;
            if (!first) { sb.append(','); detail.append(','); }
            first = false;
            sb.append(q(gene)).append(":{\"strict_survivors\":").append(survivors.size()).append(",\"modes\":{");
            boolean f2 = true;
            for (Map.Entry<String, Integer> c : counts.entrySet()) { if (!f2) sb.append(','); f2 = false; sb.append(q(c.getKey())).append(':').append(c.getValue()); }
            sb.append("}}");

            // Detail: per-gene baseline and strict mode sets, and per-variant outcome.
            detail.append(q(gene)).append(":{\"baseline_modes\":").append(jsonList(geneBaselineModes))
                  .append(",\"strict_modes\":").append(jsonList(counts.keySet()))
                  .append(",\"strict_survivors\":").append(survivors.size()).append(",\"variants\":{");
            boolean f3 = true;
            for (String key : e.getValue().keySet()) {
                if (!f3) detail.append(','); f3 = false;
                boolean pass = keyToSurvivor.containsKey(key);
                detail.append(q(key)).append(":{\"baseline_modes\":").append(jsonList(baselineModes.get(gene + "#" + key)))
                      .append(",\"stage1_pass\":").append(pass)
                      .append(",\"strict_modes\":").append(jsonList(strictModesByKey.getOrDefault(key, Set.of()))).append('}');
            }
            detail.append("}}");
        }
        sb.append('}');
        detail.append("}}");
        Files.writeString(out, sb + "\n");
        if (detailOut != null) Files.writeString(detailOut, detail + "\n");
        System.out.println("{\"tsv_rows\":" + totalRows + ",\"unique_variants\":" + totalUnique + ",\"stage1_kept\":" + stage1Kept
                + ",\"genes\":" + uniqueByGene.size() + ",\"genes_with_mode_after_stage2\":" + genesWithMode + ",\"cutoff\":" + CUTOFF + "}");
    }
}
