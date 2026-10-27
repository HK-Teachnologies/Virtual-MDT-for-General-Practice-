import { MOCK_PATIENTS, mockBrief } from './mock';
import type { MdtBrief, Patient } from './types';

// Base URL of the FastAPI backend. Falls back to mock data when unreachable,
// so the frontend demo works standalone before the backend exists.
export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

async function tryFetch<T>(path: string, token?: string): Promise<T | null> {
  try {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 1500);
    const res = await fetch(`${API_BASE}${path}`, {
      signal: ctrl.signal,
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    });
    clearTimeout(timer);
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export async function getPatients(token?: string): Promise<Patient[]> {
  const remote = await tryFetch<Patient[]>('/api/patients', token);
  return remote ?? MOCK_PATIENTS;
}

export async function getPatient(id: string, token?: string): Promise<Patient | undefined> {
  const remote = await tryFetch<Patient>(`/api/patients/${id}`, token);
  return remote ?? MOCK_PATIENTS.find((p) => p.id === id);
}

export async function getBrief(patientId: string, token?: string): Promise<MdtBrief> {
  const remote = await tryFetch<MdtBrief>(`/api/patients/${patientId}/brief`, token);
  if (remote) return remote;
  await new Promise((r) => setTimeout(r, 800)); // simulate the agent run
  return mockBrief(patientId);
}
