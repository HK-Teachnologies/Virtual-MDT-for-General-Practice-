import type { MdtBrief, Patient } from './types';

// Synthetic demo data only. No real patient data is used anywhere in this app.
export const MOCK_PATIENTS: Patient[] = [
  {
    id: 'demo-01',
    name: 'Synthetic patient A (demo)',
    age: 52,
    sex: 'Female',
    conditions: ['HIV (on ART)', 'Hypertension', 'Type 2 diabetes'],
    medications: [
      'Tenofovir / lamivudine / dolutegravir',
      'Amlodipine 5 mg daily',
      'Metformin 500 mg twice daily',
    ],
    visits: [
      {
        id: 'v1',
        date: '2026-08-04',
        summary: 'HIV clinic: viral load suppressed. BP 150/95, HbA1c 8.1%.',
        source: 'record',
      },
      {
        id: 'v2',
        date: '2026-09-08',
        summary: 'NCD clinic: BP 146/92, fasting glucose 9.4 mmol/L. Metformin continued.',
        source: 'record',
      },
      {
        id: 'v3',
        date: '2026-10-12',
        summary: 'OPD: dry cough for 1 week, no fever. Amoxicillin given, advised to return if it persists.',
        source: 'record',
      },
    ],
  },
  {
    id: 'demo-02',
    name: 'Synthetic patient B',
    age: 64,
    sex: 'Male',
    conditions: ['Hypertension', 'Chronic kidney disease (stage 3)'],
    medications: ['Lisinopril 10 mg daily', 'Atorvastatin 20 mg nightly'],
    visits: [
      {
        id: 'v1',
        date: '2026-09-15',
        summary: 'NCD clinic: BP 158/98, eGFR 42. ACE inhibitor continued with monitoring.',
        source: 'record',
      },
    ],
  },
  {
    id: 'demo-03',
    name: 'Synthetic patient C',
    age: 38,
    sex: 'Female',
    conditions: ['HIV (on ART)', 'Depression (suspected)'],
    medications: ['Tenofovir / lamivudine / dolutegravir'],
    visits: [
      {
        id: 'v1',
        date: '2026-10-02',
        summary: 'HIV clinic: good adherence, reports low mood and poor sleep for 2 months.',
        source: 'record',
      },
    ],
  },
];

const DEMO_BRIEF: MdtBrief = {
  patientId: 'demo-01',
  specialties: ['HIV care', 'TB', 'Endocrinology', 'Pharmacy'],
  generatedAt: '2026-10-27',
  items: [
    {
      id: 'tb-1',
      specialty: 'TB',
      concern:
        'Two-week cough in a person living with HIV: screen for TB with sputum GeneXpert and chest X-ray before attributing symptoms to a bacterial chest infection.',
      citation: 'Uganda National TB Guidelines (2023), intensified case finding in PLHIV',
      certainty: 'high',
      status: 'suggested',
    },
    {
      id: 'pharm-1',
      specialty: 'Pharmacy',
      concern:
        'If TB treatment is started, check rifampicin interaction with dolutegravir (twice-daily dolutegravir dosing is recommended during co-treatment).',
      citation: 'WHO consolidated HIV guidelines (2024), TB/HIV co-treatment',
      certainty: 'high',
      status: 'suggested',
    },
    {
      id: 'endo-1',
      specialty: 'Endocrinology',
      concern:
        'HbA1c 8.1% with fasting glucose 9.4 mmol/L: glycaemic control is above target. Review adherence, diet, and whether therapy needs intensifying; an overdue kidney function test should be done before any dose change.',
      citation: 'Uganda Clinical Guidelines (2023), diabetes management',
      certainty: 'moderate',
      status: 'suggested',
    },
    {
      id: 'hiv-1',
      specialty: 'HIV care',
      concern:
        'Viral load suppressed on current ART. No ART change indicated; continue adherence support and routine monitoring.',
      citation: 'Uganda HIV treatment guidelines (2022)',
      certainty: 'high',
      status: 'suggested',
    },
  ],
  interactions: [
    'Rifampicin (if TB treatment starts) reduces dolutegravir levels — adjust dosing per guideline.',
  ],
  overdueChecks: [
    'Kidney function test (creatinine/eGFR) — overdue, needed before diabetes therapy change.',
    'Annual diabetic foot and eye screening — due.',
  ],
};

export function mockBrief(patientId: string): MdtBrief {
  if (patientId === 'demo-01') return structuredClone(DEMO_BRIEF);
  const patient = MOCK_PATIENTS.find((p) => p.id === patientId);
  return {
    patientId,
    specialties: ['General medicine', 'Pharmacy'],
    generatedAt: new Date().toISOString().slice(0, 10),
    items: [
      {
        id: 'gen-1',
        specialty: 'General medicine',
        concern: `Review control of known conditions (${patient?.conditions.join(', ') ?? '—'}) against the latest visit and confirm follow-up plan.`,
        citation: 'Uganda Clinical Guidelines (2023)',
        certainty: 'moderate',
        status: 'suggested',
      },
      {
        id: 'pharm-1',
        specialty: 'Pharmacy',
        concern: 'Reconcile current medication list and check for interactions or duplications.',
        citation: 'Uganda Clinical Guidelines (2023), rational prescribing',
        certainty: 'moderate',
        status: 'suggested',
      },
    ],
    interactions: [],
    overdueChecks: ['Routine review of chronic-disease monitoring tests — confirm nothing is overdue.'],
  };
}
