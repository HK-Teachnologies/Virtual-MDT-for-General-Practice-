import type { ApiBriefRun, ApiFollowUp, ApiPatient, ApiPatientQuestion, ApiReferralLetter, ApiReview, ApiSection, ApiTranscription, ApiVisit } from './types';

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

export async function addVisitAttachments(
  token: string,
  visitId: string,
  files: File[],
): Promise<ApiVisit> {
  const form = new FormData();
  for (const file of files) form.append('files', file);
  const res = await fetch(`${API_BASE}/api/patients/visits/${visitId}/attachments`, {
    method: 'POST',
    headers: authHeaders(token),
    body: form,
  });
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as ApiVisit;
}

export async function transcribeAudioNote(token: string, audio: Blob): Promise<string> {
  const form = new FormData();
  form.append('file', audio, 'dictation.webm');
  const res = await fetch(`${API_BASE}/api/mdt/transcribe`, {
    method: 'POST',
    headers: authHeaders(token),
    body: form,
  });
  if (!res.ok) throw new Error(await readError(res));
  const body = (await res.json()) as { text?: unknown };
  return typeof body.text === 'string' ? body.text : '';
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

export async function askFollowUp(
  token: string,
  patientId: string,
  question: string,
): Promise<ApiFollowUp> {
  const res = await fetch(`${API_BASE}/api/followups`, {
    method: 'POST',
    headers: authHeaders(token, { 'Content-Type': 'application/json' }),
    body: JSON.stringify({ patient_id: patientId, question }),
  });
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as ApiFollowUp;
}

export async function fetchFollowUpThread(
  token: string,
  patientId: string,
): Promise<ApiFollowUp[]> {
  const res = await fetch(`${API_BASE}/api/followups/for-patient/${patientId}`, {
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as ApiFollowUp[];
}

export async function fetchPatientQuestionsForPatient(
  token: string,
  patientId: string,
): Promise<ApiPatientQuestion[]> {
  const res = await fetch(
    `${API_BASE}/api/followups/patient-questions/for-patient/${patientId}`,
    { headers: authHeaders(token) },
  );
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as ApiPatientQuestion[];
}

export async function answerPatientQuestion(
  token: string,
  questionId: string,
  answerText: string,
): Promise<ApiPatientQuestion> {
  const res = await fetch(
    `${API_BASE}/api/followups/patient-questions/${questionId}/answer`,
    {
      method: 'POST',
      headers: authHeaders(token, { 'Content-Type': 'application/json' }),
      body: JSON.stringify({ answer_text: answerText }),
    },
  );
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as ApiPatientQuestion;
}

export async function updatePatient(
  token: string,
  patientId: string,
  data: Record<string, string | number | null>,
): Promise<ApiPatient> {
  const res = await fetch(`${API_BASE}/api/patients/${patientId}`, {
    method: 'PATCH',
    headers: authHeaders(token, { 'Content-Type': 'application/json' }),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as ApiPatient;
}

export async function deletePatient(token: string, patientId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/patients/${patientId}`, {
    method: 'DELETE',
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error(await readError(res));
}

export async function deleteVisit(token: string, visitId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/patients/visits/${visitId}`, {
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

export async function updateVisitSummary(
  token: string,
  visitId: string,
  data: { en: string; sw: string; lg: string },
): Promise<ApiVisit> {
  const res = await fetch(`${API_BASE}/api/patients/visits/${visitId}/summary`, {
    method: 'PATCH',
    headers: authHeaders(token, { 'Content-Type': 'application/json' }),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as ApiVisit;
}

export async function releaseVisitSummary(
  token: string,
  visitId: string,
): Promise<ApiVisit> {
  const res = await fetch(`${API_BASE}/api/patients/visits/${visitId}/release`, {
    method: 'POST',
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as ApiVisit;
}

export async function prepareBriefSummary(
  token: string,
  runId: string,
): Promise<{ queued: boolean; run: ApiBriefRun }> {
  const res = await fetch(`${API_BASE}/api/mdt/runs/${runId}/patient-summary`, {
    method: 'POST',
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as { queued: boolean; run: ApiBriefRun };
}

export async function updateBriefSummary(
  token: string,
  runId: string,
  data: { en: string; sw: string; lg: string },
): Promise<ApiBriefRun> {
  const res = await fetch(`${API_BASE}/api/mdt/runs/${runId}/patient-summary`, {
    method: 'PATCH',
    headers: authHeaders(token, { 'Content-Type': 'application/json' }),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as ApiBriefRun;
}

export async function releaseBriefSummary(
  token: string,
  runId: string,
): Promise<ApiBriefRun> {
  const res = await fetch(`${API_BASE}/api/mdt/runs/${runId}/patient-summary/release`, {
    method: 'POST',
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as ApiBriefRun;
}

export async function listReferralLetters(
  token: string,
  runId: string,
): Promise<ApiReferralLetter[]> {
  const res = await fetch(`${API_BASE}/api/mdt/runs/${runId}/referral-letters`, {
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as ApiReferralLetter[];
}

export async function createReferralLetter(
  token: string,
  runId: string,
  data: { destination_facility: string; reason: string; additional_note?: string },
): Promise<ApiReferralLetter> {
  const res = await fetch(`${API_BASE}/api/mdt/runs/${runId}/referral-letters`, {
    method: 'POST',
    headers: authHeaders(token, { 'Content-Type': 'application/json' }),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as ApiReferralLetter;
}

export async function releaseReferralLetter(
  token: string,
  letterId: string,
): Promise<ApiReferralLetter> {
  const res = await fetch(`${API_BASE}/api/mdt/referral-letters/${letterId}/release`, {
    method: 'POST',
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as ApiReferralLetter;
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
