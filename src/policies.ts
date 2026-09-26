// Policy documents are static per session, so each one is fetched once and
// shared by the blank criteria grid and the policy viewer.

import { api } from './api/client';
import type { PolicyDocument } from './types';

const cache = new Map<string, Promise<PolicyDocument | null>>();

export function loadPolicy(policyId: string): Promise<PolicyDocument | null> {
  const cached = cache.get(policyId);

  if (cached) return cached;

  const pending = api.policy(policyId).catch(() => {
    cache.delete(policyId);

    return null;
  });

  cache.set(policyId, pending);

  return pending;
}
