# Design system: MVA Transparent Prioritizer

## Visual thesis

The first release uses a plain operator CLI. The design favors auditability over visual density. The output should read like a lab receipt: stable sections, fixed terms, visible uncertainty, and no decorative status language.

## Reference board

The physical reference is a laboratory run receipt. The interaction reference is the Unix command and exit-code contract. The project rejects generic dashboards, colored confidence meters, and decorative AI insight panels.

## Tokens

- Typography: inherited terminal monospace.
- Color: no color-only meaning. ANSI color is disabled when output is redirected.
- Spacing: one blank line between sections and fixed indentation for nested evidence.
- Radius, elevation, motion, iconography, charts, and illustration: absent in the first release.

## Components

The CLI renders a stage receipt, warning block, evidence-lane table, candidate reason list, and privacy projection summary. Detailed candidate components exist only in private files. Text wraps without truncating identifiers in private output. Public stdout never contains those identifiers.

## Graphic and content assets

The first release has no generated, licensed, or remote visual asset. Warnings use plain medical research language and retain qualifications.

## Quality bar

Snapshot tests cover terminal text and deterministic private-file rendering with synthetic data. Tests check narrow and wide terminal widths, redirected output, stable exit codes, plain-text screen-reader order, and absence of protected field shapes. A later visual interface requires its own responsive and accessibility evidence.
