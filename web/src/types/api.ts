/**
 * Zod schemas mirroring api/schemas/pipeline.py.
 *
 * Keep this file in sync with the Pydantic models — these are the typed contracts
 * at the API boundary. Field names use snake_case to match the Python source of truth.
 */

import { z } from "zod";

export const AuthorityType = z.enum([
  "binding_regulation",
  "agency_policy",
  "precedential_case",
  "non_precedential_case",
  "treatise",
  "other",
]);
export type AuthorityType = z.infer<typeof AuthorityType>;

export const DocumentType = z.enum([
  "administrative_denial",
  "appeal_decision",
  "medical_examination",
  "policy_memo",
  "unknown",
]);
export type DocumentType = z.infer<typeof DocumentType>;

export const DocumentIssue = z.object({
  issue_text: z.string(),
  decision: z.enum(["granted", "denied", "deferred", "remanded", "other"]),
  stated_reason: z.string().nullable().optional(),
  source_span: z.tuple([z.number(), z.number()]),
  confidence: z.number().min(0).max(1),
});
export type DocumentIssue = z.infer<typeof DocumentIssue>;

export const EvidenceItem = z.object({
  label: z.string(),
  description: z.string(),
  source_type: z.enum(["document", "missing", "inferred", "external"]),
  favorability: z.enum(["favorable", "adverse", "neutral", "missing"]),
});
export type EvidenceItem = z.infer<typeof EvidenceItem>;

export const Citation = z.object({
  source_id: z.string(),
  source_title: z.string(),
  authority_type: AuthorityType,
  passage: z.string(),
  url: z.string().nullable().optional(),
  validated: z.boolean(),
});
export type Citation = z.infer<typeof Citation>;

export const ReportFinding = z.object({
  issue_index: z.number(),
  finding_text: z.string(),
  supporting_source_ids: z.array(z.string()),
  confidence: z.number().min(0).max(1),
});
export type ReportFinding = z.infer<typeof ReportFinding>;

export const StrategyRecommendation = z.object({
  finding_index: z.number(),
  recommendation: z.string(),
  priority: z.enum(["critical", "important", "optional"]),
});
export type StrategyRecommendation = z.infer<typeof StrategyRecommendation>;

export const CriticFlag = z.object({
  target_index: z.number(),
  flag_type: z.string(),
  explanation: z.string(),
  severity: z.enum(["block", "warn", "info"]),
});
export type CriticFlag = z.infer<typeof CriticFlag>;

export const AnalysisReport = z.object({
  doc_type: DocumentType,
  parties: z.record(z.string(), z.string()),
  issues: z.array(DocumentIssue),
  evidence: z.array(EvidenceItem),
  findings: z.array(ReportFinding),
  citations: z.array(Citation),
  strategy: z.array(StrategyRecommendation),
  critic_flags: z.array(CriticFlag),
  pipeline_warnings: z.array(z.string()),
  overall_confidence: z.number().min(0).max(1),
  faithfulness_score: z.number().min(0).max(1),
  prompt_version: z.string(),
  generated_at: z.string(),
});
export type AnalysisReport = z.infer<typeof AnalysisReport>;

export const AnalyzeRequest = z.object({
  text: z.string().min(1),
});
export type AnalyzeRequest = z.infer<typeof AnalyzeRequest>;
