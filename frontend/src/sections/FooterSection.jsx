import { docsUrl, liveAppUrl } from "../services/config";

export function FooterSection() {
  return (
    <footer className="border-t border-line px-4 py-3 text-xs text-muted flex flex-wrap gap-4 items-center justify-between">
      <span>Educational demo — not investment advice.</span>
      <div className="flex flex-wrap gap-x-4 gap-y-2">
        <a
          className="text-accent hover:underline"
          href={liveAppUrl}
          target="_blank"
          rel="noreferrer"
        >
          Live app (Vercel)
        </a>
        <a className="text-accent hover:underline" href={docsUrl} target="_blank" rel="noreferrer">
          Swagger UI (API)
        </a>
      </div>
    </footer>
  );
}
