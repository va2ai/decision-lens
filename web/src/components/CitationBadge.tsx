import type { AuthorityType } from "../types/api";

const STYLES: Record<AuthorityType, string> = {
  binding_regulation: "bg-blue-100 text-blue-800 border-blue-300",
  agency_policy: "bg-amber-100 text-amber-800 border-amber-300",
  precedential_case: "bg-purple-100 text-purple-800 border-purple-300",
  non_precedential_case: "bg-slate-100 text-slate-700 border-slate-300",
  treatise: "bg-emerald-100 text-emerald-800 border-emerald-300",
  other: "bg-zinc-100 text-zinc-700 border-zinc-300",
};

const LABELS: Record<AuthorityType, string> = {
  binding_regulation: "Regulation",
  agency_policy: "Policy",
  precedential_case: "Precedent",
  non_precedential_case: "Case",
  treatise: "Treatise",
  other: "Other",
};

export function CitationBadge({
  sourceId,
  authorityType,
}: {
  sourceId: string;
  authorityType: AuthorityType;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium ${STYLES[authorityType]}`}
    >
      <span className="font-mono">{sourceId}</span>
      <span className="opacity-70">·</span>
      <span>{LABELS[authorityType]}</span>
    </span>
  );
}
