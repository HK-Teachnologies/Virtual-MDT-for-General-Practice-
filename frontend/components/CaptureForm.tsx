'use client';

import { useEffect, useRef, useState, type FormEvent } from 'react';
import { API_BASE, addVisit } from '../lib/api';
import type { ApiClinic, ApiVisit } from '../lib/types';

function formatDuration(totalSeconds: number): string {
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}

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
  const [previews, setPreviews] = useState<{ name: string; url: string }[]>([]);
  const [notes, setNotes] = useState('');
  const [visitDate, setVisitDate] = useState(today());
  const [clinics, setClinics] = useState<ApiClinic[]>([]);
  const [clinicId, setClinicId] = useState('');
  const [recording, setRecording] = useState(false);
  const [recSeconds, setRecSeconds] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const photoInput = useRef<HTMLInputElement | null>(null);
  const uploadInput = useRef<HTMLInputElement | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/clinics`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => (res.ok ? res.json() : []))
      .then((list) => setClinics(list as ApiClinic[]))
      .catch(() => {});
  }, [token]);

  useEffect(
    () => () => {
      // Stop any in-progress recording and clock if the form unmounts.
      if (timerRef.current) clearInterval(timerRef.current);
      streamRef.current?.getTracks().forEach((t) => t.stop());
      previews.forEach((p) => URL.revokeObjectURL(p.url));
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  function addFiles(picked: File[]) {
    if (picked.length === 0) return;
    setFiles((prev) => [...prev, ...picked]);
    const images = picked.filter((f) => f.type.startsWith('image/'));
    if (images.length > 0) {
      setPreviews((prev) => [
        ...prev,
        ...images.map((f) => ({ name: f.name, url: URL.createObjectURL(f) })),
      ]);
    }
  }

  function removeFile(name: string) {
    setFiles((prev) => prev.filter((f) => f.name !== name));
    setPreviews((prev) => {
      const dropped = prev.filter((p) => p.name === name);
      dropped.forEach((p) => URL.revokeObjectURL(p.url));
      return prev.filter((p) => p.name !== name);
    });
  }

  function stopClock() {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }

  async function toggleRecording() {
    if (recording) {
      recorderRef.current?.stop();
      return;
    }
    setError(null);
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setError('Microphone unavailable — check the browser permission, or type the notes instead.');
      return;
    }
    streamRef.current = stream;
    const mime = ['audio/webm', 'audio/mp4'].find((m) =>
      typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported(m),
    );
    const rec = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
    chunksRef.current = [];
    rec.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data);
    };
    rec.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
      stopClock();
      setRecording(false);
      const blob = new Blob(chunksRef.current, { type: rec.mimeType || 'audio/webm' });
      if (blob.size === 0) {
        setError('Nothing was recorded — try again.');
        return;
      }
      const ext = (rec.mimeType || '').includes('mp4') ? 'm4a' : 'webm';
      addFiles([new File([blob], `dictation.${ext}`, { type: blob.type })]);
    };
    recorderRef.current = rec;
    rec.start();
    setRecSeconds(0);
    setRecording(true);
    timerRef.current = setInterval(() => setRecSeconds((s) => s + 1), 1000);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (recording) return;
    if (!notes.trim() && files.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      // The entry type follows what was captured: no separate choice needed.
      const source = files.some((f) => f.type.startsWith('audio/'))
        ? 'dictation'
        : files.some((f) => f.type.startsWith('image/'))
          ? 'photo'
          : 'typed';
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
      previews.forEach((p) => URL.revokeObjectURL(p.url));
      setPreviews([]);
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
        <span className="field-label">Capture the case — pick any combination</span>
        <div className="row capture-actions">
          <button
            className={recording ? 'btn btn-danger' : 'btn btn-primary'}
            type="button"
            onClick={toggleRecording}
            disabled={busy}
          >
            {recording ? `Stop recording (${formatDuration(recSeconds)})` : 'Record dictation'}
          </button>
          <button className="btn" type="button" onClick={() => photoInput.current?.click()} disabled={busy || recording}>
            Take a photo
          </button>
          <button className="btn" type="button" onClick={() => uploadInput.current?.click()} disabled={busy || recording}>
            Upload files
          </button>
        </div>
        <input
          ref={photoInput}
          type="file"
          accept="image/*"
          capture="environment"
          hidden
          onChange={(e) => {
            addFiles(e.target.files ? Array.from(e.target.files) : []);
            e.target.value = '';
          }}
        />
        <input
          ref={uploadInput}
          type="file"
          multiple
          accept="image/*,audio/*,.pdf,.txt,.md"
          hidden
          onChange={(e) => {
            addFiles(e.target.files ? Array.from(e.target.files) : []);
            e.target.value = '';
          }}
        />
        {recording && (
          <p className="muted">
            Recording… speak the consultation, then press Stop. The AI transcribes
            it for verification after you save.
          </p>
        )}
        {previews.length > 0 && (
          <div className="row">
            {previews.map((p) => (
              <img key={p.name} className="photo-preview" src={p.url} alt={`Preview of ${p.name}`} />
            ))}
          </div>
        )}
        {files.filter((f) => !f.type.startsWith('image/')).map((f) => (
          <p className="muted" key={f.name}>
            Attached: {f.name}{' '}
            <button className="link-btn" type="button" onClick={() => removeFile(f.name)}>
              Remove
            </button>
          </p>
        ))}
        {files.filter((f) => f.type.startsWith('image/')).map((f) => (
          <p className="muted" key={f.name}>
            Photo: {f.name}{' '}
            <button className="link-btn" type="button" onClick={() => removeFile(f.name)}>
              Remove
            </button>
          </p>
        ))}
        <p className="muted">
          Photos open the camera on a phone. Dictations are transcribed by the AI;
          PDFs and text files are read directly. Every machine read is shown for
          verification.
        </p>
      </div>

      <div className="field">
        <label htmlFor="notes">Notes (type here — or record above instead)</label>
        <textarea
          id="notes"
          rows={4}
          placeholder="e.g. 52-year-old woman, known HIV on ART, hypertension, diabetes. Cough now two weeks, night sweats…"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
      </div>
      {error && <p className="error">{error}</p>}
      <button className="btn btn-primary" type="submit" disabled={busy || recording}>
        {busy ? 'Saving…' : 'Add to record'}
      </button>
    </form>
  );
}
