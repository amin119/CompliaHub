"use client";

import BrowserFrame from "@/components/landing/BrowserFrame";
import DemoCitation from "@/components/landing/DemoCitation";
import SeverityBadge from "@/components/SeverityBadge";

/**
 * The hero's product shot: both halves of CompliaHub side by side, so the
 * dual nature is visible before a visitor scrolls at all. Ask on the left
 * (a streamed, cited answer), Scan on the right (findings mapped to a
 * control).
 *
 * Entirely cosmetic — `DemoCitation` never calls the API, and the findings
 * are illustrative. The severity badges are the *real* `SeverityBadge`, so
 * the preview can't drift from how findings actually look in the product.
 */

const FINDINGS = [
  { severity: "HIGH", title: "Weak hash algorithm", file: "app/auth.py:42" },
  { severity: "MEDIUM", title: "Debug mode enabled", file: "app/config.py:8" },
  { severity: "LOW", title: "Unpinned dependency", file: "requirements.txt" },
];

export default function SplitPreview() {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <BrowserFrame path="compliahub.app/chat">
        <div className="flex flex-col gap-3 text-sm">
          <p className="ml-auto max-w-[85%] rounded-3xl rounded-br-md bg-cta px-4 py-2.5 text-accent-contrast">
            What satisfies GDPR Article 32?
          </p>
          <div className="mr-auto max-w-[92%] rounded-3xl rounded-bl-md border border-surface-border bg-surface px-4 py-2.5 text-foreground">
            <p className="leading-relaxed">
              Article 32 requires encryption of personal data and the ability to restore
              availability after an incident
              <span className="animate-blink-caret ml-0.5 inline-block h-3.5 w-[2px] -translate-y-0.5 bg-current align-middle" />
            </p>
            <div className="mt-3 flex flex-wrap gap-1.5 border-t border-surface-border pt-3">
              <DemoCitation
                label="Article 32"
                title="gdpr.pdf — Article 32"
                excerpt="Taking into account the state of the art… the controller shall implement appropriate technical and organisational measures."
              />
              <DemoCitation
                label="A.8.24"
                title="iso-27001.pdf — A.8.24"
                excerpt="Rules for the effective use of cryptography, including key management, shall be defined and implemented."
              />
            </div>
          </div>
        </div>
      </BrowserFrame>

      <BrowserFrame path="compliahub.app/scanner">
        <div className="flex flex-col gap-2.5">
          {FINDINGS.map((finding) => (
            <div
              key={finding.title}
              className="flex items-center gap-3 rounded-2xl border border-surface-border bg-surface px-3.5 py-2.5"
            >
              <SeverityBadge severity={finding.severity} />
              <div className="min-w-0">
                <p className="truncate text-sm text-foreground">{finding.title}</p>
                <p className="truncate text-xs text-muted">{finding.file}</p>
              </div>
            </div>
          ))}
          <p className="mt-1 text-xs leading-relaxed text-muted">
            Mapped to <span className="text-accent">ISO 27001 A.8.24</span>, validated by AI, and
            waiting on a human reviewer.
          </p>
        </div>
      </BrowserFrame>
    </div>
  );
}
