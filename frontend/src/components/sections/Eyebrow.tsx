export default function Eyebrow({ children }: { children: React.ReactNode }) {
  return (
    <span className="text-xs font-bold tracking-wide text-accent uppercase">
      {children}
    </span>
  );
}
