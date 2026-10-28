import type { ApiBriefRun, ApiPatient, ApiReview, ApiSection, ApiTranscription, ApiVisit } from './types';

// Base URL of the FastAPI backend (origin only: every path below adds /api).
export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

function authHeaders(token: string, extra?: Record<string, string>) {
  return { Authorization: `Bearer ${token}`, ...extra };
}

async function readError(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown };
    return typeof body.detail === 'string' ? body.detail : `Request failed (${res.status})`;
  } catch {
    return `Request failed (${res.status})`;
  }
}

export async function getPatients(token: string): Promise<ApiPatient[]> {
  try {
    const res = await fetch(`${API_BASE}/api/patients`, {
      headers: authHeaders(token),
    });
    if (!res.ok) return [];
    return (await res.json()) as ApiPatient[];
  } catch {
    return [];
  }
}

export async function getPatient(id: string, token: string): Promise<ApiPatient | undefined> {
  try {
    const res = await fetch(`${API_BASE}/api/patients/${id}`, {
      headers: authHeaders(token),
    });
    if (!res.ok) return undefined;
    return (await res.json()) as ApiPatient;
  } catch {
    return undefined;
  }
}

export async function createPatient(
  token: string,
  data: {
    full_name: string;
    date_of_birth?: string;
    sex?: string;
    phone?: string;
    email?: string;
    district?: string;
    address?: string;
  },
): Promise<ApiPatient> {
  const res = await fetch(`${API_BASE}/api/patients`, {
    method: 'POST',
    headers: authHeaders(token, { 'Content-Type': 'application/json' }),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as ApiPatient;
}

export async function addVisit(
  token: string,
  patientId: string,
  form: FormData,
): Promise<ApiVisit> {
  const res = await fetch(`${API_BASE}/api/patients/${patientId}/visits`, {
    method: 'POST',
    headers: authHeaders(token),
    body: form,
  });
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as ApiVisit;
}

export async function requestBriefRun(token: string, patientId: string): Promise<ApiBriefRun> {
  const res = await fetch(`${API_BASE}/api/mdt/brief`, {
    method: 'POST',
    headers: authHeaders(token, { 'Content-Type': 'application/json' }),
    body: JSON.stringify({ patient_id: patientId }),
  });
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as ApiBriefRun;
}

export async function getBriefRun(token: string, runId: string): Promise<ApiBriefRun> {
  const res = await fetch(`${API_BASE}/api/mdt/runs/${runId}`, {
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as ApiBriefRun;
}

export async function listBriefRuns(token: string, patientId: string): Promise<ApiBriefRun[]> {
  const res = await fetch(`${API_BASE}/api/mdt/patients/${patientId}/runs`, {
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as ApiBriefRun[];
}

export async function signOffBriefItem(
  token: string,
  itemId: string,
  data: { status: string; edited_text?: string },
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/mdt/items/${itemId}`, {
    method: 'PATCH',
    headers: authHeaders(token, { 'Content-Type': 'application/json' }),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(await readError(res));
}

export async function addSection(
  token: string,
  patientId: string,
  visitId: string,
  data: { section: string; content: string },
): Promise<ApiSection> {
  const res = await fetch(`${API_BASE}/api/patients/${patientId}/visits/${visitId}/sections`, {
    method: 'POST',
    headers: authHeaders(token, { 'Content-Type': 'application/json' }),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as ApiSection;
}

export async function updateSection(
  token: string,
  sectionId: string,
  data: { section?: string; content?: string },
): Promise<ApiSection> {
  const res = await fetch(`${API_BASE}/api/patients/sections/${sectionId}`, {
    method: 'PATCH',
    headers: authHeaders(token, { 'Content-Type': 'application/json' }),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as ApiSection;
}

export async function getOpenReviews(token: string, patientId: string): Promise<ApiReview[]> {
  const res = await fetch(`${API_BASE}/api/reviews/for-patient/${patientId}`, {
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as ApiReview[];
}

export async function deletePatient(token: string, patientId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/patients/${patientId}`, {
    method: 'DELETE',
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error(await readError(res));
}

export async function deleteSection(token: string, sectionId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/patients/sections/${sectionId}`, {
    method: 'DELETE',
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error(await readError(res));
}

export async function updateVisit(
  token: string,
  visitId: string,
  data: { notes?: string; visit_date?: string; clinic_id?: string | null; source?: string },
): Promise<ApiVisit> {
  const res = await fetch(`${API_BASE}/api/patients/visits/${visitId}`, {
    method: 'PATCH',
    headers: authHeaders(token, { 'Content-Type': 'application/json' }),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as ApiVisit;
}

export async function updateTranscription(
  token: string,
  attachmentId: string,
  data: { text?: string; verified?: boolean },
): Promise<ApiTranscription> {
  const res = await fetch(`${API_BASE}/api/mdt/transcriptions/${attachmentId}`, {
    method: 'PATCH',
    headers: authHeaders(token, { 'Content-Type': 'application/json' }),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as ApiTranscription;
}

export async function downloadAttachment(
  token: string,
  visitId: string,
  attachmentId: string,
  filename: string,
): Promise<void> {
  const res = await fetch(
    `${API_BASE}/api/patients/visits/${visitId}/attachments/${attachmentId}`,
    { headers: authHeaders(token) },
  );
  if (!res.ok) throw new Error(await readError(res));
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
