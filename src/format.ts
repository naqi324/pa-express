// Shared display formatting helpers.

import type { CriterionStatus, PlanType, PolicyRef, Urgency } from './types';

export function formatDateTime(iso: string): string {
  const date = new Date(iso);

  if (Number.isNaN(date.getTime())) return iso;

  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

const DATE_ONLY = /^(\d{4})-(\d{2})-(\d{2})$/;

// A bare yyyy-mm-dd is a calendar date, not UTC midnight; parsing it as UTC
// shows a date of birth one day early west of Greenwich.
function parseDate(iso: string): Date {
  const parts = DATE_ONLY.exec(iso);

  if (!parts) return new Date(iso);

  return new Date(Number(parts[1]), Number(parts[2]) - 1, Number(parts[3]));
}

export function formatDate(iso: string): string {
  const date = parseDate(iso);

  if (Number.isNaN(date.getTime())) return iso;

  return date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

// Compact 24-hour stamp for fixed-width lifecycle cells.
export function formatStamp(iso: string): string {
  const date = new Date(iso);

  if (Number.isNaN(date.getTime())) return iso;

  return date.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  });
}

const PLAN_LABELS: Record<PlanType, string> = {
  commercial: 'Commercial',
  medicare_advantage: 'Medicare Advantage',
  medicaid: 'Medicaid',
};

export function planTypeLabel(plan: PlanType): string {
  return PLAN_LABELS[plan];
}

const URGENCY_LABELS: Record<Urgency, string> = {
  standard: 'Standard',
  expedited: 'Expedited',
};

export function urgencyLabel(urgency: Urgency): string {
  return URGENCY_LABELS[urgency];
}

const VERDICT_LABELS: Record<CriterionStatus, string> = {
  MET: 'Met',
  NOT_MET: 'Not met',
  INSUFFICIENT: 'Insufficient',
};

export function verdictLabel(status: CriterionStatus): string {
  return VERDICT_LABELS[status];
}

// The one canonical rendering of a policy reference. Every surface (policy
// basis, criteria header, attribution, letter facts) uses this string so the
// reference never varies by screen or engine.
export function policyLabel(policy: PolicyRef | null): string {
  if (!policy) return '—';

  if (policy.source_type === 'ncd') {
    const version = policy.ncd_version ? ` · Version ${policy.ncd_version}` : '';

    return `${policy.code} — ${policy.title}${version} · CMS National Coverage Determination`;
  }

  const contractor = policy.contractor ? ` · ${policy.contractor}` : '';

  return `${policy.code} — ${policy.title}${contractor} · CMS Local Coverage Determination`;
}

// The policy id used by /api/policies and /api/coverage.
export function policyId(policy: PolicyRef): string {
  return policy.source_type === 'ncd' ? (policy.ncd_id ?? policy.code) : (policy.lcd_id ?? policy.code);
}
