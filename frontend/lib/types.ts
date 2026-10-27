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
