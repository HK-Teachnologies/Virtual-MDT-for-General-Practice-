export type Certainty = 'high' | 'moderate' | 'low';
export type ItemStatus = 'suggested' | 'approved' | 'rejected' | 'edited' | 'removed';

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

export interface CitedLabel {
  label: string;
  doc_id: string;
  page: number | null;
}

export interface ApiFollowUp {
  id: string;
  patient_id: string;
  asked_by: string;
  asker_name: string;
  question: string;
  question_i18n?: { en: string; sw: string; lg: string };
  answer_text: string;
  has_audio: boolean;
  status: string;
  created_at: string;
  answered_at: string | null;
}

export interface MySummaryVisit {
  visit_id: string;
  date: string;
  en: string;
  sw: string;
  lg: string;
  ready: boolean;
  released_by_name: string | null;
  released_at: string | null;
}

export interface MyReferralLetter {
  id: string;
  destination_facility: string;
  reason: string;
  letter_text: string;
  released_by_name: string | null;
  released_at: string | null;
}

export interface MySummary {
  run_id: string | null;
  completed_at: string | null;
  summary: {
    en: string;
    sw: string;
    lg: string;
  };
  summary_released_by_name: string | null;
  summary_released_at: string | null;
  visits: MySummaryVisit[];
  referral_letters: MyReferralLetter[];
}

export interface ApiReferralLetter {
  id: string;
  run_id: string;
  patient_id: string;
  destination_facility: string;
  reason: string;
  letter_text: string;
  summary_status: string;
  released_by_name: string | null;
  released_at: string | null;
  created_at: string;
}

export interface BriefItem {
  id: string;
  specialty: string;
  concern: string;
  citation: string;
  certainty: Certainty;
  status: ItemStatus;
  source_type: string;
  question: string;
  urgent: boolean;
  selfcheck_reason: string;
  cited_labels: CitedLabel[];
}

export interface RemovedPoint {
  kind: string;
  text: string;
  sub: string;
  reason: string;
}

export interface BriefInteraction {
  drugs: string[];
  concern: string;
  citation: string;
  source_type: string;
  cited_labels: CitedLabel[];
}

export interface BriefOverdueCheck {
  check: string;
  last_done: string;
  citation: string;
  source_type: string;
  cited_labels: CitedLabel[];
}

export interface MdtBrief {
  patientId: string;
  specialties: string[];
  items: BriefItem[];
  interactions: BriefInteraction[];
  overdueChecks: BriefOverdueCheck[];
  removed: RemovedPoint[];
  model: string;
  prompt_version: string;
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
  source_type?: string;
  question?: string;
  urgent?: boolean;
  selfcheck_reason?: string;
  cited_labels?: ApiCitedLabel[];
}

export interface ApiCitedLabel {
  label?: string;
  doc_id?: string;
  page?: number | null;
}

export interface ApiBriefInteraction {
  drugs?: string[];
  concern?: string;
  citation?: string;
  source_type?: string;
  cited_labels?: ApiCitedLabel[];
}

export interface ApiBriefOverdueCheck {
  check?: string;
  last_done?: string;
  citation?: string;
  source_type?: string;
  cited_labels?: ApiCitedLabel[];
}

export interface ApiBriefRun {
  id: string;
  patient_id: string;
  status: string;
  current_step: string;
  model: string;
  prompt_version: string;
  specialties: string[];
  error: string;
  patient_summary?: { en: string; sw: string; lg: string };
  summary_status?: string;
  released_by_name?: string | null;
  released_at?: string | null;
  items: ApiBriefItem[];
  interactions?: Array<ApiBriefInteraction | string>;
  overdue_checks?: Array<ApiBriefOverdueCheck | string>;
  removed_points?: Array<{ kind?: string; point?: unknown; reason?: string }>;
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
  patient_summary?: { en: string; sw: string; lg: string };
  summary_status?: string;
  released_by_name?: string | null;
  released_at?: string | null;
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
  weight_kg: number | null;
  height_cm: number | null;
  created_at: string;
  visits: ApiVisit[];
  visit_count: number;
}
