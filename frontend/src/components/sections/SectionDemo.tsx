import BrowserFrame from "@/components/landing/BrowserFrame";
import DemoCitation from "@/components/landing/DemoCitation";
import AnimatedConversation from "@/components/landing/AnimatedConversation";

/**
 * The reference design has a large rounded placeholder here with a video
 * play icon — a "demo video" slot meant to be filled in later. This
 * platform has no such recording, and a fake play button that does
 * nothing when clicked would be worse than no placeholder at all — so
 * this slot is filled with something real instead: an actual live-styled
 * preview of the chat interface, built from its own real classes. The
 * messages stagger in on scroll (AnimatedConversation) so it reads as a
 * real exchange happening in front of you rather than a static screenshot.
 */
export default function SectionDemo() {
  return (
    <section className="mx-auto w-full max-w-4xl px-4 pb-24 sm:px-8">
      <BrowserFrame path="/chat">
        <AnimatedConversation className="flex flex-col gap-3 py-2">
          <div className="ml-auto max-w-[75%] rounded-3xl rounded-br-md bg-cta px-4 py-2.5 text-sm text-white">
            What controls satisfy GDPR Article 32?
          </div>
          <div className="mr-auto flex items-center gap-2 rounded-3xl rounded-bl-md bg-surface px-4 py-2 text-xs text-muted">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
            Retrieving evidence…
          </div>
          <div className="mr-auto max-w-[85%] rounded-3xl rounded-bl-md bg-surface px-4 py-2.5 text-sm text-foreground">
            Article 32 requires &ldquo;appropriate technical and organisational measures&rdquo;
            proportionate to risk — encryption, resilience, and regular testing among them.
            <div className="mt-2.5 flex flex-wrap gap-1.5 border-t border-surface-border pt-2.5">
              <DemoCitation
                label="Article 32 · GDPR"
                title="GDPR (EU) 2016/679"
                excerpt="Taking into account the state of the art... the controller and processor shall implement appropriate technical and organisational measures to ensure a level of security appropriate to the risk."
              />
            </div>
          </div>
        </AnimatedConversation>
      </BrowserFrame>
    </section>
  );
}
