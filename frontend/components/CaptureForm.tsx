'use client';

import { useEffect, useState, type FormEvent } from 'react';
import { API_BASE, addVisit } from '../lib/api';
import type { ApiClinic, ApiVisit } from '../lib/types';

export default function CaptureForm({
  patientId,
  token,
  onAdded,
}: {
  patientId: string;
  token: string;
  onAdded: (v: ApiVisit) => void;
}) {
  const today = () => new Date().toISOString().slice(0, 10);
  const [files, setFiles] = useState<File[]>([]);
  const [preview, setPreview] = useState<string | null>(null);
  const [notes, setNotes] = useState('');
  const [source, setSource] = useState('typed');
  const [visitDate, setVisitDate] = useState(today());
  const [clinics, setClinics] = useState<ApiClinic[]>([]);
  const [clinicId, setClinicId] = useState('');

  useEffect(() => {
    fetch(`${API_BASE}/api/clinics`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => (res.ok ? res.json() : []))
      .then((list) => setClinics(list as ApiClinic[]))
      .catch(() => {});
  }, [token]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleFiles(list: FileList | null) {
    const picked = list ? Array.from(list) : [];
    setFiles(picked);
    const firstImage = picked.find((f) => f.type.startsWith('image/'));
    setPreview(firstImage ? URL.createObjectURL(firstImage) : null);
    if (picked.some((f) => f.type.startsWith('audio/'))) setSource('dictation');
    else if (picked.length > 0) setSource('photo');
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!notes.trim() && files.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      const form = new FormData();
      form.append('notes', notes.trim());
      form.append('source', source);
      form.append('visit_date', visitDate);
      if (clinicId) form.append('clinic_id', clinicId);
      for (const file of files) form.append('files', file);
      const visit = await addVisit(token, patientId, form);
      onAdded(visit);
      setNotes('');
      setFiles([]);
      setPreview(null);
      setSource('typed');
      setVisitDate(today());
      setClinicId('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save the visit.');
    }
    setBusy(false);
  }

  return (
    <form className="capture" onSubmit={handleSubmit}>
      <div className="field">
        <label htmlFor="visitDate">Visit date — change it when adding a past record</label>
        <input
          id="visitDate"
          type="date"
          value={visitDate}
          onChange={(e) => setVisitDate(e.target.value)}
        />
      </div>
      <div className="field">
        <label htmlFor="clinic">Clinic (classifies this record)</label>
        <select id="clinic" value={clinicId} onChange={(e) => setClinicId(e.target.value)}>
          <option value="">Select…</option>
          {clinics.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor="photo">Photos, dictation audio, or documents</label>
        <input
          id="photo"
          type="file"
          multiple
          accept="image/*,audio/*,.pdf,.txt,.md"
          onChange={(e) => handleFiles(e.target.files)}
        />
        {preview && (
          // Plain img is enough for a local preview; no remote optimisation needed.
          <img className="photo-preview" src={preview} alt="Preview of photographed notes" />
        )}
        {files
          .filter((f) => !f.type.startsWith('image/'))
          .map((f) => (
            <p className="muted" key={f.name}>
              Attached: {f.name}
            </p>
          ))}
        <p className="muted">
          Photos and audio are read by the AI; PDFs and text files are read
          directly. Every machine read is shown for verification.
        </p>
      </div>
      <div className="field">
        <label htmlFor="notes">Notes (type or dictate)</label>
        <textarea
          id="notes"
          rows={4}
          placeholder="e.g. 52-year-old woman, known HIV on ART, hypertension, diabetes. Cough now two weeks, night sweats…"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
      </div>
      <div className="field">
        <label htmlFor="source">Entry type</label>
        <select id="source" value={source} onChange={(e) => setSource(e.target.value)}>
          <option value="typed">Typed notes</option>
          <option value="dictation">Dictation</option>
          <option value="photo">Photo of handwritten notes</option>
          <option value="record">Clinic record</option>
        </select>
      </div>
      {error && <p className="error">{error}</p>}
      <button className="btn" type="submit" disabled={busy}>
        {busy ? 'Saving…' : 'Add to record'}
      </button>
    </form>
  );
}
