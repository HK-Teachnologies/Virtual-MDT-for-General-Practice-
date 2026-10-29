'use client';

import { useState } from 'react';
import { updatePatient } from '../lib/api';
import type { ApiPatient } from '../lib/types';

function bmi(weightKg: number | null, heightCm: number | null): string | null {
  if (!weightKg || !heightCm || heightCm <= 0) return null;
  return (weightKg / (heightCm / 100) ** 2).toFixed(1);
}

export default function PatientDetails({
  patient,
  token,
  onSaved,
}: {
  patient: ApiPatient;
  token: string | null;
  onSaved: (p: ApiPatient) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    full_name: patient.full_name,
    phone: patient.phone ?? '',
    email: patient.email ?? '',
    district: patient.district ?? '',
    address: patient.address ?? '',
    date_of_birth: patient.date_of_birth ?? '',
    sex: patient.sex ?? '',
    weight_kg: patient.weight_kg != null ? String(patient.weight_kg) : '',
    height_cm: patient.height_cm != null ? String(patient.height_cm) : '',
  });

  function set(key: keyof typeof form, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function save() {
    if (!token) return;
    setSaving(true);
    setError(null);
    try {
      const num = (v: string) => (v.trim() === '' ? null : Number(v.trim()));
      const weight = num(form.weight_kg);
      const height = num(form.height_cm);
      if ((weight != null && Number.isNaN(weight)) || (height != null && Number.isNaN(height))) {
        throw new Error('Weight and height must be numbers.');
      }
      const saved = await updatePatient(token, patient.id, {
        full_name: form.full_name.trim(),
        phone: form.phone.trim() || null,
        email: form.email.trim() || null,
        district: form.district.trim() || null,
        address: form.address.trim() || null,
        date_of_birth: form.date_of_birth || null,
        sex: form.sex || null,
        weight_kg: weight,
        height_cm: height,
      });
      onSaved(saved);
      setEditing(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save changes.');
    }
    setSaving(false);
  }

  const summaryBits = [
    patient.weight_kg != null ? `${patient.weight_kg} kg` : null,
    patient.height_cm != null ? `${patient.height_cm} cm` : null,
    bmi(patient.weight_kg, patient.height_cm) ? `BMI ${bmi(patient.weight_kg, patient.height_cm)}` : null,
  ].filter(Boolean);

  return (
    <details className="panel patient-details">
      <summary>
        Details{summaryBits.length > 0 ? ` — ${summaryBits.join(' · ')}` : ' — add measurements'}
      </summary>
      {error && <p className="error">{error}</p>}
      {!editing ? (
        <div>
          <dl className="detail-list">
            <div><dt>Name</dt><dd>{patient.full_name}</dd></div>
            {patient.phone && <div><dt>Phone</dt><dd>{patient.phone}</dd></div>}
            {patient.email && <div><dt>Email</dt><dd>{patient.email}</dd></div>}
            {patient.district && <div><dt>District</dt><dd>{patient.district}</dd></div>}
            {patient.address && <div><dt>Area</dt><dd>{patient.address}</dd></div>}
            {patient.date_of_birth && <div><dt>Born</dt><dd>{patient.date_of_birth}</dd></div>}
            {patient.sex && <div><dt>Sex</dt><dd>{patient.sex}</dd></div>}
            {patient.weight_kg != null && <div><dt>Weight</dt><dd>{patient.weight_kg} kg</dd></div>}
            {patient.height_cm != null && <div><dt>Height</dt><dd>{patient.height_cm} cm</dd></div>}
            {bmi(patient.weight_kg, patient.height_cm) && (
              <div><dt>BMI</dt><dd>{bmi(patient.weight_kg, patient.height_cm)}</dd></div>
            )}
          </dl>
          <p className="muted">Visit-level vitals (BP, temperature, …) go on each visit as a Vitals section.</p>
          <button className="btn" type="button" onClick={() => setEditing(true)}>
            Edit details
          </button>
        </div>
      ) : (
        <div>
          <div className="field">
            <label htmlFor="pd-name">Full name</label>
            <input id="pd-name" value={form.full_name} onChange={(e) => set('full_name', e.target.value)} />
          </div>
          <div className="row">
            <div className="field">
              <label htmlFor="pd-phone">Phone</label>
              <input id="pd-phone" value={form.phone} onChange={(e) => set('phone', e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="pd-email">Email</label>
              <input id="pd-email" type="email" value={form.email} onChange={(e) => set('email', e.target.value)} />
            </div>
          </div>
          <div className="row">
            <div className="field">
              <label htmlFor="pd-district">District</label>
              <input id="pd-district" value={form.district} onChange={(e) => set('district', e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="pd-area">Area of residence</label>
              <input id="pd-area" value={form.address} onChange={(e) => set('address', e.target.value)} />
            </div>
          </div>
          <div className="row">
            <div className="field">
              <label htmlFor="pd-dob">Date of birth</label>
              <input id="pd-dob" type="date" value={form.date_of_birth} onChange={(e) => set('date_of_birth', e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="pd-sex">Sex</label>
              <select id="pd-sex" value={form.sex} onChange={(e) => set('sex', e.target.value)}>
                <option value="">Select…</option>
                <option value="Male">Male</option>
                <option value="Female">Female</option>
              </select>
            </div>
          </div>
          <div className="row">
            <div className="field">
              <label htmlFor="pd-weight">Weight (kg, optional)</label>
              <input id="pd-weight" type="number" min="0" step="0.1" placeholder="e.g. 68.5" value={form.weight_kg} onChange={(e) => set('weight_kg', e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="pd-height">Height (cm, optional)</label>
              <input id="pd-height" type="number" min="0" step="0.1" placeholder="e.g. 172" value={form.height_cm} onChange={(e) => set('height_cm', e.target.value)} />
            </div>
          </div>
          <div className="row">
            <button className="btn btn-primary" type="button" onClick={save} disabled={saving || !form.full_name.trim()}>
              {saving ? 'Saving…' : 'Save'}
            </button>
            <button className="btn" type="button" onClick={() => setEditing(false)} disabled={saving}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </details>
  );
}
