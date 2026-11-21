// Citation parsing for draft text (pure, no imports, so node can test it).

/**
 * `[TKT-01842]` and prefixed IDs such as `[TKT-V5-00042]` (scripts/prepare_data.py).
 * Anchored to our ID shape: TKT, optional upper-case/digit prefix segments, then 5 digits.
 * Chase's verifier is looser (`[A-Z][A-Z0-9]*-[A-Za-z0-9-]+`); everything it accepts as a citation
 * must be one of our precedent IDs, so the narrower pattern is enough.
 */
const CITATION_RE = /\[(TKT(?:-[A-Z0-9]+)*-\d{5})\]/g;

export interface CitationMatch {
  id: string;
  /** Start of the whole `[…]` match in the text. */
  index: number;
  /** Length of the whole `[…]` match. */
  length: number;
}

export function findCitations(text: string): CitationMatch[] {
  return [...text.matchAll(CITATION_RE)].map((m) => ({ id: m[1], index: m.index ?? 0, length: m[0].length }));
}
