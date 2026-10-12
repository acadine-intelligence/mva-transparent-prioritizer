# Leak-suite fixtures

All values are invented test literals, with no case or biological evidence.
The deliberately long ZZLEAKSYNTH gene and alias are fictional labels, not
real gene symbols. Coordinates and HPO, HGVS, rsID and ClinVar-shaped strings
are invented and assert no real annotation or association.

The tests expand these seeds into temporary CSV, VCF, JSON, TSV and Git trees.
No committed VCF or real input tree is needed. Eight numbered suffixes on the
fictional gene form the hash attack's entire public hypothesis set. The attacker
knows the exact JSON template but learns which suffix was used from the emitted
summary digest. The singleton-count attack assumes a publicly known sole
candidate, and compares worlds where that candidate is absent or present.

All temporary repositories remain without commits. The staged-blob attack uses
only a temporary index. Instruction payloads are inert text; no model, network,
terminal emulator or shell executes them.
