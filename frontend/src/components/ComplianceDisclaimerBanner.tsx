/**
 * Shown whenever the findings view is filtered to ISO27001 — the user
 * explicitly decided this catalog is seeded with publicly-known control
 * IDs/titles only (never the licensed standard's text), so this caveat
 * has to be visible wherever ISO27001 findings are shown, not just noted
 * once in a doc. Belt-and-suspenders with each finding's own summary text
 * and the API's `source_note`/`disclaimer` fields.
 */
export default function ComplianceDisclaimerBanner() {
  return (
    <div className="mb-3 rounded-xl border border-amber-300/60 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/40 dark:text-amber-200">
      Control IDs and titles reflect the publicly-known structure of ISO/IEC 27001:2022 Annex A
      as discussed in public secondary sources. This is not sourced from the licensed standard,
      has not been verified against the official text, and must not be treated as a substitute
      for a licensed copy of ISO/IEC 27001:2022.
    </div>
  );
}
