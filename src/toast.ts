// Toast queue shared by the whole app. Success notes clear themselves;
// errors stay until the reviewer dismisses them or a newer error replaces them.

import { reactive } from 'vue';

export type ToastKind = 'success' | 'error';

export interface Toast {
  id: number;
  kind: ToastKind;
  message: string;
}

const SUCCESS_LIFETIME_MS = 5000;

const MAX_TOASTS = 3;

const toasts = reactive<Toast[]>([]);

let nextId = 1;

export function dismissToast(id: number): void {
  const index = toasts.findIndex((toast) => toast.id === id);

  if (index !== -1) toasts.splice(index, 1);
}

export function notify(kind: ToastKind, message: string): void {
  const id = nextId;

  nextId += 1;

  if (kind === 'error') {
    for (const stale of toasts.filter((toast) => toast.kind === 'error')) dismissToast(stale.id);
  }

  toasts.push({ id, kind, message });

  while (toasts.length > MAX_TOASTS) toasts.shift();

  if (kind === 'success') setTimeout(() => dismissToast(id), SUCCESS_LIFETIME_MS);
}

export function useToasts(): Toast[] {
  return toasts;
}
