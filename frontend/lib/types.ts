export type Certainty = 'high' | 'moderate' | 'low';
export type ItemStatus = 'suggested' | 'approved' | 'rejected' | 'edited';

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  role: string;
}

export interface Visit {
  id: string;
  date: string;
  summary: string;
  source: 'photo' | 'dictation' | 'record';
}

export interface Patient {
  id: string;
  name: string;
  age: number;
  sex: string;
  conditions: string[];
  medications: string[];
  visits: Visit[];
}

export interface BriefItem {
  id: string;
  specialty: string;
  concern: string;
  citation: string;
  certainty: Certainty;
  status: ItemStatus;
}

export interface MdtBrief {
  patientId: string;
  specialties: string[];
  items: BriefItem[];
  interactions: string[];
  overdueChecks: string[];
  generatedAt: string;
}

export interface ApiBriefItem {
  id: string;
  specialty: string;
  concern: string;
  citation: string;
  certainty: string;
  status: string;
  edited_text: string | null;
}

export interface ApiBriefRun {
  id: string;
  patient_id: string;
  status: string;
  current_step: string;
  specialties: string[];
  error: string;
  items: ApiBriefItem[];
}

// Shapes returned by the FastAPI backend.
export interface ApiAttachment {
  id: string;
  filename: string;
  content_type: string | null;
  transcription: ApiTranscription | null;
}

export interface ApiTranscription {
  id: string;
  attachment_id: string;
  kind: string;
  text: string;
  verified: boolean;
  model: string;
}

export interface ApiClinic {
  id: string;
  name: string;
  description: string | null;
  active: boolean;
}

export interface ApiGuideline {
  id: string;
  title: string;
  version: string;
  active: boolean;
  chunks: number;
  index_status: string;
  index_error: string;
}

export interface ApiSpecialtyMember {
  id: string;
  email: string;
  full_name: string | null;
  role: string;
}

export interface ApiSpecialty {
  id: string;
  name: string;
  description: string | null;
  active: boolean;
  member_count: number;
  members: ApiSpecialtyMember[];
}

export interface ApiReviewRecipient {
  id: string;
  user_id: string;
  email: string;
  full_name: string | null;
  specialty_id: string | null;
  specialty_name: string | null;
  emailed: boolean;
}

export interface ApiReviewResponse {
  id: string;
  author_id: string;
  author_email: string;
  author_name: string | null;
  text: string;
  has_audio: boolean;
  has_image: boolean;
  created_at: string;
}

export interface ApiReview {
  id: string;
  patient_id: string;
  patient_name: string;
  requested_by: string;
  requester_email: string;
  message: string;
  brief_snapshot: {
    specialties?: string[];
    items?: BriefItem[];
    interactions?: string[];
    overdue_checks?: string[];
  };
  status: string;
  created_at: string;
  closed_at: string | null;
  recipients: ApiReviewRecipient[];
  responses: ApiReviewResponse[];
  response_count: number;
}

export interface ApiSection {
  id: string;
  section: string;
  content: string;
  created_at: string;
}

export interface ApiVisit {
  id: string;
  visit_date: string;
  notes: string;
  source: string;
  clinic: { id: string; name: string } | null;
  attachments: ApiAttachment[];
  sections: ApiSection[];
}

export interface ApiPatient {
  id: string;
  full_name: string;
  date_of_birth: string | null;
  sex: string | null;
  phone: string | null;
  email: string | null;
  district: string | null;
  address: string | null;
  created_at: string;
  visits: ApiVisit[];
  visit_count: number;
}
