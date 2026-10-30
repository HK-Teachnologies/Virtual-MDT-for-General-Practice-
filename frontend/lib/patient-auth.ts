import { API_BASE } from './api';
import type {
  ApiFollowUp,
  ApiPatient,
  ApiPatientQuestion,
  MySummary,
} from './types';

const STORAGE_KEY = 'mdt-patient-token';

async function readError(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown };
    return typeof body.detail === 'string' ? body.detail : `Request failed (${res.status})`;
  } catch {
    return `Request failed (${res.status})`;
  }
}

export function getPatientToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(STORAGE_KEY);
}

export async function requestOtp(identifier: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/patient-auth/request`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ identifier }),
  });
  if (!res.ok) throw new Error(await readError(res));
}

export async function verifyOtp(identifier: string, code: string): Promise<string> {
  const res = await fetch(`${API_BASE}/api/patient-auth/verify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ identifier, code }),
  });
  if (!res.ok) throw new Error(await readError(res));
  const { access_token } = (await res.json()) as { access_token: string };
  localStorage.setItem(STORAGE_KEY, access_token);
  return access_token;
}

export async function fetchOwnRecord(token: string): Promise<ApiPatient | undefined> {
  const res = await fetch(`${API_BASE}/api/patient-auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) return undefined;
  return (await res.json()) as ApiPatient;
}

export function clearPatientToken() {
  localStorage.removeItem(STORAGE_KEY);
}

export async function fetchMySummary(token: string): Promise<MySummary | undefined> {
  const res = await fetch(`${API_BASE}/api/patient-auth/my-summary`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) return undefined;
  return (await res.json()) as MySummary;
}

export async function fetchMyQuestions(token: string): Promise<ApiFollowUp[] | undefined> {
  const res = await fetch(`${API_BASE}/api/followups/mine`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) return undefined;
  return (await res.json()) as ApiFollowUp[];
}

export async function answerQuestion(
  token: string,
  id: string,
  text: string,
  audio: File | null,
): Promise<ApiFollowUp> {
  const form = new FormData();
  form.append('text', text);
  if (audio) form.append('audio', audio);
  const res = await fetch(`${API_BASE}/api/followups/${id}/answer`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as ApiFollowUp;
}

export async function askDoctor(
  token: string,
  text: string,
  audio: File | null,
): Promise<ApiPatientQuestion> {
  const form = new FormData();
  form.append('text', text);
  if (audio) form.append('audio', audio);
  const res = await fetch(`${API_BASE}/api/followups/patient-questions`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as ApiPatientQuestion;
}

export async function fetchMyAskedQuestions(
  token: string,
): Promise<ApiPatientQuestion[]> {
  const res = await fetch(`${API_BASE}/api/followups/patient-questions/mine`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as ApiPatientQuestion[];
}
