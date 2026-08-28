export default function Eyebrow({ children }: { children: React.ReactNode }) {
  return (
    <span className="text-[11px] font-medium tracking-[0.22em] text-landing-accent uppercase">
      {children}
    </span>
  );
}
