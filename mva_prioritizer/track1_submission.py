"""Track 1 submission validator and local scorer mirror.

The official evaluator (pinned unchanged at ``tools/official-track1/evaluation.py``,
Space revision 1c761cc2, retrieved 2026-09-05) is permissive: it trims chromosome
text, uppercases alleles, accepts blank alleles, and matches on the exact
``(chrom, pos, ref, alt)`` tuple against a ``chr``-prefixed GRCh38 answer. A row that
parses but does not match scores zero silently, and each upload spends one of six
submissions. This module has two parsers with different jobs. ``parse_as_official`` reproduces
the gate's loader exactly (including its quirks) and is the oracle for "what would
the gate compute". ``parse_submission`` is deliberately narrower: it accepts one
canonical form (exact template header, ``chr``-prefixed names, integer positions,
upper-case ``ACGT`` alleles, distinct sorted EPCRs, notes without line breaks) and
refuses anything else, including forms the gate would normalize for us. A file that
passes the canonical check is one whose gate parse is unambiguous by inspection;
that is the point of the narrowing, and the CLI cross-checks both parsers agree.

``score_submission`` mirrors ``evaluation.py`` line for line where behaviour matters:
descending EPCR sort with stable ties, four rank tiers, half credit for a partial
compound-heterozygous match, F-max swept over the submitted EPCR thresholds with
variants (not rows) as the classifiable unit. ``tests/test_track1_submission.py``
runs the pinned official file against the mirror on every case.

No private value belongs here. The lane's frozen outputs use contigs without a
``chr`` prefix and ``MT`` for the mitochondrion; ``validate_against_lane_representation``
proves a candidate file maps onto lane keys before it is considered for upload.
"""
from __future__ import annotations

import csv
import io
import math
import re
from dataclasses import dataclass
from typing import Dict, FrozenSet, Iterable, List, Optional, Set, Tuple

HEADER = (
    "proband_id",
    "chrom_1",
    "pos_1",
    "ref_1",
    "alt_1",
    "chrom_2",
    "pos_2",
    "ref_2",
    "alt_2",
    "epcr",
    "finding_type",
    "notes",
)
MAX_ROWS = 10
EXPECTED_PROBAND = "PROBAND01"
RANK_POINT_TIERS = ((1, 100), (3, 50), (5, 25), (10, 10))
FINDING_TYPES = ("primary", "secondary")
MITOCHONDRIAL_NAMES = ("chrM", "chrMT")  # answer-key spelling is unverified in public sources
DEFAULT_MITOCHONDRIAL = "chrM"
NUCLEAR_CHROMOSOMES = frozenset([f"chr{i}" for i in range(1, 23)] + ["chrX", "chrY"])
NUCLEAR_LANE_TO_SUBMISSION = {**{str(i): f"chr{i}" for i in range(1, 23)}, "X": "chrX", "Y": "chrY"}


def accepted_chromosomes(mitochondrial_name: str = DEFAULT_MITOCHONDRIAL) -> FrozenSet[str]:
    if mitochondrial_name not in MITOCHONDRIAL_NAMES:
        raise SubmissionError(f"mitochondrial name must be one of {MITOCHONDRIAL_NAMES}")
    return NUCLEAR_CHROMOSOMES | {mitochondrial_name}


def lane_to_submission(mitochondrial_name: str = DEFAULT_MITOCHONDRIAL) -> Dict[str, str]:
    accepted_chromosomes(mitochondrial_name)
    return {**NUCLEAR_LANE_TO_SUBMISSION, "MT": mitochondrial_name}
ALLELE = re.compile(r"^[ACGT]+$")
POSITION = re.compile(r"^[1-9][0-9]*$")

Variant = Tuple[str, int, str, str]


class SubmissionError(ValueError):
    """Raised by both parsers, for different reasons.

    From ``parse_as_official``: the gate itself would raise on this file.
    From ``parse_submission``: the file is outside the canonical form. That
    includes files the gate would accept and even score fully; the message says
    which rule was broken. Neither parser uploads anything.
    """


@dataclass(frozen=True)
class SubmissionRow:
    variants: FrozenSet[Variant]
    epcr: float
    rank: int
    finding_type: str
    notes: str
    file_order: int


@dataclass(frozen=True)
class Submission:
    proband_id: str
    rows: Tuple[SubmissionRow, ...]


@dataclass(frozen=True)
class ScoreResult:
    proband_id: str
    full_match_rank: Optional[int]
    partial_match_rank: Optional[int]
    rank_points: float
    f_max: float
    f_max_threshold: Optional[float]
    n_predictions_at_f_max: int


def _variant(
    fields: Dict[str, str], suffix: str, line: int, required: bool, chromosomes: FrozenSet[str]
) -> Optional[Variant]:
    names = [f"chrom_{suffix}", f"pos_{suffix}", f"ref_{suffix}", f"alt_{suffix}"]
    values = [fields[name] for name in names]
    if not required and all(value == "" for value in values):
        return None
    if not required and any(value == "" for value in values):
        raise SubmissionError(f"line {line}: second variant must be complete or entirely blank")
    chrom, pos, ref, alt = values
    if chrom not in chromosomes:
        raise SubmissionError(
            f"line {line}: chrom_{suffix} must be one of chr1..chr22, chrX, chrY or the configured "
            f"mitochondrial name exactly (got {chrom!r})"
        )
    if not POSITION.match(pos):
        raise SubmissionError(f"line {line}: pos_{suffix} must be a positive integer (got {pos!r})")
    if not ALLELE.match(ref):
        raise SubmissionError(f"line {line}: ref_{suffix} must be non-empty and ACGT only (got {ref!r})")
    if not ALLELE.match(alt):
        raise SubmissionError(f"line {line}: alt_{suffix} must be non-empty and ACGT only (got {alt!r})")
    if ref == alt:
        raise SubmissionError(f"line {line}: ref_{suffix} and alt_{suffix} are identical")
    return (chrom, int(pos), ref, alt)


def parse_submission(
    text: str,
    *,
    expected_proband: str = EXPECTED_PROBAND,
    allow_repeated_pairings: bool = False,
    allow_ties: bool = False,
    allow_unsorted: bool = False,
    mitochondrial_name: str = DEFAULT_MITOCHONDRIAL,
) -> Submission:
    """Parse a Track 1 CSV in canonical form. Raises SubmissionError on anything outside it.

    A UTF-8 BOM is refused rather than stripped: the official loader opens the file
    with the default codec, so a BOM becomes part of the first header name and the
    gate raises ``KeyError('proband_id')``.
    """
    if text.startswith("\ufeff"):
        raise SubmissionError("file starts with a UTF-8 BOM; the gate would fail to find the proband_id column")
    chromosomes = accepted_chromosomes(mitochondrial_name)
    reader = csv.reader(io.StringIO(text, newline=""))
    try:
        header = next(reader)
    except StopIteration as error:
        raise SubmissionError("empty file: no header") from error
    if tuple(header) != HEADER:
        raise SubmissionError(f"header must be exactly {','.join(HEADER)}")

    raw_rows: List[SubmissionRow] = []
    seen_variants: Dict[Variant, int] = {}
    seen_rowsets: Set[FrozenSet[Variant]] = set()
    for index, record in enumerate(reader):
        line = index + 2
        if record == []:
            continue
        if len(record) != len(HEADER):
            raise SubmissionError(f"line {line}: expected {len(HEADER)} columns, got {len(record)}")
        fields = dict(zip(HEADER, record))
        if fields["proband_id"] != expected_proband:
            raise SubmissionError(f"line {line}: proband_id must be exactly {expected_proband!r}")
        first = _variant(fields, "1", line, required=True, chromosomes=chromosomes)
        second = _variant(fields, "2", line, required=False, chromosomes=chromosomes)
        variants = frozenset([first, second]) if second is not None else frozenset([first])
        if second is not None and len(variants) == 1:
            raise SubmissionError(f"line {line}: pair lists the same variant twice")
        epcr_text = fields["epcr"]
        try:
            epcr = float(epcr_text)
        except ValueError as error:
            raise SubmissionError(f"line {line}: epcr must be a number in (0, 1] (got {epcr_text!r})") from error
        if math.isnan(epcr) or not (0 < epcr <= 1):
            raise SubmissionError(f"line {line}: epcr must be in (0, 1] (got {epcr_text!r})")
        finding = fields["finding_type"]
        if finding not in FINDING_TYPES:
            raise SubmissionError(f"line {line}: finding_type must be 'primary' or 'secondary' (got {finding!r})")
        notes = fields["notes"]
        if "\n" in notes or "\r" in notes:
            raise SubmissionError(f"line {line}: notes must not contain line breaks")
        if variants in seen_rowsets:
            raise SubmissionError(f"line {line}: repeats an earlier row's variant set")
        for variant in variants:
            if variant in seen_variants and not allow_repeated_pairings:
                raise SubmissionError(
                    f"line {line}: repeats a variant from line {seen_variants[variant]}; "
                    "repeats add no F-max recall (pass allow_repeated_pairings to permit alternative pairings)"
                )
            seen_variants.setdefault(variant, line)
        seen_rowsets.add(variants)
        raw_rows.append(SubmissionRow(variants, epcr, 0, finding, notes, index))

    if not raw_rows:
        raise SubmissionError("no rows")
    if len(raw_rows) > MAX_ROWS:
        raise SubmissionError(f"{len(raw_rows)} rows; the gate accepts at most {MAX_ROWS}")

    epcrs = [r.epcr for r in raw_rows]
    if len(set(epcrs)) != len(epcrs) and not allow_ties:
        raise SubmissionError("epcr tie: the gate breaks ties by file order; pick distinct values or pass allow_ties")
    if epcrs != sorted(epcrs, reverse=True) and not allow_unsorted:
        raise SubmissionError("rows are not sorted by epcr descending (pass allow_unsorted to let the gate sort)")

    ordered = sorted(raw_rows, key=lambda r: (-r.epcr, r.file_order))
    ranked = tuple(
        SubmissionRow(r.variants, r.epcr, position + 1, r.finding_type, r.notes, r.file_order)
        for position, r in enumerate(ordered)
    )
    return Submission(expected_proband, ranked)


def parse_as_official(text: str) -> Dict[str, Submission]:
    """Mirror of ``evaluation.load_submission``: permissive, exactly as the gate reads a file.

    Use this to learn what the gate would compute for a file, including files the
    strict validator refuses. It trims chromosome text, uppercases alleles, accepts
    blank alleles, groups by proband, sorts by EPCR descending with stable ties, and
    raises SubmissionError where the official loader raises ValueError or KeyError.
    A leading BOM is left in place, as the gate leaves it, so the first column name
    is not ``proband_id`` and the lookup fails exactly as it does there.
    """
    reader = csv.DictReader(io.StringIO(text, newline=""))
    by_proband: Dict[str, List[Tuple[FrozenSet[Variant], float, str]]] = {}
    for record in reader:
        try:
            pid = record["proband_id"].strip()
            first = _official_variant(record["chrom_1"], record["pos_1"], record["ref_1"], record["alt_1"])
        except KeyError as error:
            raise SubmissionError(f"gate would raise KeyError: {error}") from error
        second = _official_variant(
            record.get("chrom_2", ""), record.get("pos_2", ""), record.get("ref_2", ""), record.get("alt_2", "")
        )  # .get defaults exactly as the gate; a short row still yields None under a present column
        if first is None:
            raise SubmissionError(f"Row missing primary variant for proband {pid}")
        variants = frozenset([first, second]) if second else frozenset([first])
        try:
            epcr = float(record["epcr"])
        except (KeyError, TypeError, ValueError) as error:
            raise SubmissionError("gate would raise on epcr") from error
        if not (0 < epcr <= 1):
            raise SubmissionError(f"EPCR {epcr} out of range (0,1] for proband {pid}")
        finding = (record.get("finding_type") or "primary").strip().lower()
        if finding not in FINDING_TYPES:
            raise SubmissionError(f"finding_type must be 'primary' or 'secondary' for proband {pid}, got '{finding}'")
        by_proband.setdefault(pid, []).append((variants, epcr, finding))
    result: Dict[str, Submission] = {}
    for pid, rows in by_proband.items():
        if len(rows) > MAX_ROWS:
            raise SubmissionError(f"Proband {pid} has {len(rows)} rows; max is {MAX_ROWS}")
        ordered = sorted(enumerate(rows), key=lambda item: (-item[1][1], item[0]))
        result[pid] = Submission(
            pid,
            tuple(
                SubmissionRow(variants, epcr, position + 1, finding, "", original)
                for position, (original, (variants, epcr, finding)) in enumerate(ordered)
            ),
        )
    return result


def _official_variant(chrom: Optional[str], pos: Optional[str], ref: Optional[str], alt: Optional[str]) -> Optional[Variant]:
    """Mirror of ``evaluation._parse_variant`` including its crash on short rows.

    ``csv.DictReader`` yields ``None`` for cells a short row does not supply. The
    gate calls ``.strip()`` on ``ref``/``alt`` unconditionally once ``chrom`` and
    ``pos`` are present, so a short row raises ``AttributeError`` there. The
    ``.get(..., "")`` defaults in the loader apply only to absent second-variant
    columns, not to short rows under present columns.
    """
    if not chrom or not pos:
        return None
    try:
        position = int(pos)
    except ValueError as error:
        raise SubmissionError("gate would raise on a position") from error
    if ref is None or alt is None:
        raise SubmissionError("gate would raise AttributeError on a short row")
    return (chrom.strip(), position, ref.strip().upper(), alt.strip().upper())


def _rank_to_points(rank: int) -> int:
    for max_rank, points in RANK_POINT_TIERS:
        if rank <= max_rank:
            return points
    return 0


def score_submission(submission: Submission, true_variants: FrozenSet[Variant]) -> ScoreResult:
    """Mirror of ``evaluation.score_proband`` for one proband."""
    rows = submission.rows
    is_compound_het = len(true_variants) == 2
    full_match_rank = None
    partial_match_rank = None
    for r in rows:
        if r.variants == true_variants:
            full_match_rank = r.rank
            break
    if is_compound_het and full_match_rank is None:
        for r in rows:
            if r.variants & true_variants:
                partial_match_rank = r.rank
                break
    if full_match_rank is not None:
        rank_points = float(_rank_to_points(full_match_rank))
    elif partial_match_rank is not None:
        rank_points = 0.5 * _rank_to_points(partial_match_rank)
    else:
        rank_points = 0.0

    best_f = 0.0
    best_threshold = None
    best_n = 0
    for threshold in sorted({r.epcr for r in rows}, reverse=True):
        predicted: Set[Variant] = set()
        n_rows = 0
        for r in rows:
            if r.epcr >= threshold:
                predicted |= r.variants
                n_rows += 1
        tp = len(predicted & true_variants)
        fp = len(predicted - true_variants)
        fn = len(true_variants - predicted)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
        if f > best_f:
            best_f, best_threshold, best_n = f, threshold, n_rows
    return ScoreResult(
        submission.proband_id, full_match_rank, partial_match_rank, rank_points, best_f, best_threshold, best_n
    )


def submission_to_lane_key(variant: Variant, mitochondrial_name: str = DEFAULT_MITOCHONDRIAL) -> Tuple[str, int, str, str]:
    """Map a submission variant to the lane's contig naming (no prefix, MT for the mitochondrion)."""
    chrom = variant[0]
    for lane_name, submission_name in lane_to_submission(mitochondrial_name).items():
        if submission_name == chrom:
            return (lane_name, variant[1], variant[2], variant[3])
    raise SubmissionError(f"no lane contig for {chrom!r}")


def validate_against_lane_representation(
    submission: Submission,
    lane_keys: Iterable[Tuple[str, int, str, str]],
    mitochondrial_name: str = DEFAULT_MITOCHONDRIAL,
) -> None:
    """Every submitted variant must exist in the lane under the lane's own naming.

    ``lane_keys`` are ``(contig, pos, ref, alt)`` tuples as the lane writes them. A key
    carrying a ``chr`` prefix means the caller mixed representations; refuse rather than
    guess. This function receives keys, never rows, and reports counts only.
    """
    keys = set(lane_keys)
    prefixed = [k for k in keys if k[0].startswith("chr")]
    if prefixed:
        raise SubmissionError(f"representation error: {len(prefixed)} lane key(s) carry a chr prefix")
    missing = 0
    for r in submission.rows:
        for variant in r.variants:
            if submission_to_lane_key(variant, mitochondrial_name) not in keys:
                missing += 1
    if missing:
        raise SubmissionError(f"{missing} submitted variant(s) not present in the lane under lane naming")
