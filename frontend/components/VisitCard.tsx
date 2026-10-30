'use client';

import { useEffect, useRef, useState, type FormEvent } from 'react';
import {
  addSection,
  addVisitAttachments,
  deleteSection,
  downloadAttachment,
  updateSection,
  updateTranscription,
  updateVisit,
} from '../lib/api';
import type { ApiAttachment, ApiSection, ApiTranscription, ApiVisit } from '../lib/types';
import VisitSummaryGate from './VisitSummaryGate';

const AUDIO_EXTENSIONS = ['.wav', '.mp3', '.m4a', '.ogg', '.flac', '.aac', '.opus', '.wma', '.webm'];

function isAudioFile(a: ApiAttachment): boolean {
  if (a.transcription?.kind === 'audio') return true;
  if ((a.content_type ?? '').startsWith('audio/')) return true;
  const name = a.filename.toLowerCase();
  return AUDIO_EXTENSIONS.some((ext) => name.endsWith(ext));
}

const TRANSCRIPT_LABEL: Record<string, string> = {
  image: 'Photo read',
  audio: 'Dictation transcript',
  document: 'Document text',
};

const SECTION_ORDER = [
  'lab',
  'imaging',
  'vitals',
  'diagnosis',
  'prescription',
  'notes',
  'referral',
  'other',
];

const SECTION_LABELS: Record<string, string> = {
  lab: 'Lab',
  imaging: 'Imaging',
  vitals: 'Vitals',
  notes: 'Notes',
  diagnosis: 'Diagnosis',
  prescription: 'Prescription',
  referral: 'Referral',
  other: 'Other',
};

const SOURCE_LABEL: Record<string, string> = {
  photo: 'photo notes',
  dictation: 'dictation',
  record: 'clinic record',
  typed: 'typed notes',
};

export default function VisitCard({
  patientId,
  visit: initial,
  token,
  readOnly = false,
  onChange,
}: {
  patientId: string;
  visit: ApiVisit;
  token: string | null;
  readOnly?: boolean;
  onChange?: (v: ApiVisit) => void;
}) {
  const [visit, setVisit] = useState(initial);
  const [adding, setAdding] = useState(false);
  const [newType, setNewType] = useState('lab');
  const [newContent, setNewContent] = useState('');
  const [resultFiles, setResultFiles] = useState<File[]>([]);
  const [resultPreviews, setResultPreviews] = useState<{ name: string; url: string }[]>([]);
  const [recording, setRecording] = useState(false);
  const [recSeconds, setRecSeconds] = useState(0);
  const [dictating, setDictating] = useState(false);
  const photoInput = useRef<HTMLInputElement | null>(null);
  const fileInput = useRef<HTMLInputElement | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const recognitionRef = useRef<{ stop: () => void } | null>(null);

  useEffect(
    () => () => {
      if (timerRef.current) clearInterval(timerRef.current);
      streamRef.current?.getTracks().forEach((t) => t.stop());
      recognitionRef.current?.stop();
      resultPreviews.forEach((p) => URL.revokeObjectURL(p.url));
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  function addResultFiles(picked: File[]) {
    if (picked.length === 0) return;
    setResultFiles((prev) => [...prev, ...picked]);
    const images = picked.filter((f) => f.type.startsWith('image/'));
    if (images.length > 0) {
      setResultPreviews((prev) => [
        ...prev,
        ...images.map((f) => ({ name: f.name, url: URL.createObjectURL(f) })),
      ]);
    }
  }

  function removeResultFile(name: string) {
    setResultFiles((prev) => prev.filter((f) => f.name !== name));
    setResultPreviews((prev) => {
      prev.filter((p) => p.name === name).forEach((p) => URL.revokeObjectURL(p.url));
      return prev.filter((p) => p.name !== name);
    });
  }

  function stopClock() {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }

  function stopDictation() {
    recognitionRef.current?.stop();
    recognitionRef.current = null;
    setDictating(false);
  }

  function toggleDictation() {
    if (dictating) {
      stopDictation();
      return;
    }
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const Ctor = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!Ctor) {
      setError('Live dictation is not supported in this browser — record an audio note instead, or type.');
      return;
    }
    try {
      const rec = new Ctor();
      rec.continuous = true;
      rec.interimResults = true;
      rec.lang = 'en-US';
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      rec.onresult = (e: any) => {
        let spoken = '';
        for (let i = e.resultIndex; i < e.results.length; i++) {
          if (e.results[i].isFinal) spoken += e.results[i][0].transcript;
        }
        if (spoken.trim()) {
          setNewContent((prev) => (prev ? `${prev} ${spoken.trim()}` : spoken.trim()));
        }
      };
      rec.onend = () => setDictating(false);
      recognitionRef.current = rec;
      rec.start();
      setDictating(true);
      setError(null);
    } catch {
      setError('Could not start dictation — record an audio note instead, or type.');
    }
  }

  async function toggleResultRecording() {
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
      addResultFiles([new File([blob], `dictation.${ext}`, { type: blob.type })]);
    };
    recorderRef.current = rec;
    rec.start();
    setRecSeconds(0);
    setRecording(true);
    timerRef.current = setInterval(() => setRecSeconds((s) => s + 1), 1000);
  }

  function cancelResult() {
    if (recording) recorderRef.current?.stop();
    stopDictation();
    resultPreviews.forEach((p) => URL.revokeObjectURL(p.url));
    setResultPreviews([]);
    setResultFiles([]);
    setNewContent('');
    setAdding(false);
  }
  const [editingSection, setEditingSection] = useState<string | null>(null);
  const [sectionDraft, setSectionDraft] = useState('');
  const [editingNotes, setEditingNotes] = useState(false);
  const [notesDraft, setNotesDraft] = useState(visit.notes);
  const [editingTranscript, setEditingTranscript] = useState<string | null>(null);
  const [transcriptDraft, setTranscriptDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function applyTranscript(updated: ApiTranscription) {
    apply({
      ...visit,
      attachments: visit.attachments.map((a) =>
        a.id === updated.attachment_id ? { ...a, transcription: updated } : a,
      ),
    });
  }

  async function saveTranscript(attachment: ApiAttachment) {
    if (!token || !transcriptDraft.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await updateTranscription(token, attachment.id, {
        text: transcriptDraft.trim(),
      });
      applyTranscript(updated);
      setEditingTranscript(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save.');
    }
    setBusy(false);
  }

  async function verifyTranscript(attachment: ApiAttachment) {
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await updateTranscription(token, attachment.id, { verified: true });
      applyTranscript(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save.');
    }
    setBusy(false);
  }

  function apply(updated: ApiVisit) {
    setVisit(updated);
    onChange?.(updated);
  }

  async function submitSection(e: FormEvent) {
    e.preventDefault();
    if (!token || recording) return;
    if (dictating) stopDictation();
    const text = newContent.trim();
    if (!text && resultFiles.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      // Text becomes a typed section; photos, dictations, and documents
      // ride along as visit attachments with the same AI read as capture.
      const created = text
        ? await addSection(token, patientId, visit.id, {
            section: newType,
            content: text,
          })
        : null;
      if (resultFiles.length > 0) {
        const updated = await addVisitAttachments(token, visit.id, resultFiles);
        apply({ ...visit, sections: updated.sections, attachments: updated.attachments });
      } else if (created) {
        apply({ ...visit, sections: [...visit.sections, created] });
      }
      resultPreviews.forEach((p) => URL.revokeObjectURL(p.url));
      setResultPreviews([]);
      setResultFiles([]);
      setNewContent('');
      setAdding(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save.');
    }
    setBusy(false);
  }

  async function saveSection(id: string) {
    if (!token || !sectionDraft.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await updateSection(token, id, { content: sectionDraft.trim() });
      apply({ ...visit, sections: visit.sections.map((s) => (s.id === id ? updated : s)) });
      setEditingSection(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save.');
    }
    setBusy(false);
  }

  async function removeSection(id: string) {
    if (!token || !window.confirm('Delete this entry?')) return;
    setError(null);
    try {
      await deleteSection(token, id);
      apply({ ...visit, sections: visit.sections.filter((s) => s.id !== id) });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not delete.');
    }
  }

  async function saveNotes() {
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await updateVisit(token, visit.id, { notes: notesDraft });
      apply(updated);
      setEditingNotes(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save.');
    }
    setBusy(false);
  }

  async function download(attachmentId: string, filename: string) {
    if (!token) return;
    try {
      await downloadAttachment(token, visit.id, attachmentId, filename);
    } catch {
      setError('Could not download the file.');
    }
  }

  const grouped = SECTION_ORDER.map((type) => ({
    type,
    items: visit.sections.filter((s) => s.section === type),
  })).filter((g) => g.items.length > 0);

  return (
    <article className="visit-card">
      <div className="timeline-title">{visit.clinic?.name ?? 'Visit'}</div>
      <div className="timeline-date">
        {visit.visit_date}{' '}
        <span className="badge">{SOURCE_LABEL[visit.source] ?? visit.source}</span>
      </div>

      {editingNotes ? (
        <div className="field">
          <textarea rows={3} value={notesDraft} onChange={(e) => setNotesDraft(e.target.value)} />
          <div className="row">
            <button className="btn btn-primary" type="button" onClick={saveNotes} disabled={busy}>
              Save
            </button>
            <button
              className="btn"
              type="button"
              onClick={() => {
                setEditingNotes(false);
                setNotesDraft(visit.notes);
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <>
          <p>{visit.notes || <span className="muted">(no notes)</span>}</p>
          {!readOnly && (
            <button className="link-btn" type="button" onClick={() => setEditingNotes(true)}>
              Edit notes
            </button>
          )}
        </>
      )}

      {visit.attachments.length > 0 && (
        <ul className="attach-list">
          {visit.attachments.map((a) => (
            <li key={a.id}>
              {a.filename}{' '}
              {isAudioFile(a) ? (
                <span className="muted">(voice note kept as text only)</span>
              ) : !readOnly && token ? (
                <button
                  className="link-btn"
                  type="button"
                  onClick={() => download(a.id, a.filename)}
                >
                  Download
                </button>
              ) : (
                <span className="muted">(sign in as staff to download)</span>
              )}
              {a.transcription ? (
                <div className="transcript">
                  <p className="muted">
                    {TRANSCRIPT_LABEL[a.transcription.kind] ?? 'Machine read'}
                    {a.transcription.verified ? (
                      <span className="badge"> verified</span>
                    ) : (
                      <span className="badge"> AI read — verify</span>
                    )}
                  </p>
                  {editingTranscript === a.id && !readOnly ? (
                    <div className="field">
                      <textarea
                        rows={3}
                        value={transcriptDraft}
                        onChange={(e) => setTranscriptDraft(e.target.value)}
                      />
                      <div className="row">
                        <button
                          className="btn btn-primary"
                          type="button"
                          onClick={() => saveTranscript(a)}
                          disabled={busy}
                        >
                          Save
                        </button>
                        <button
                          className="btn"
                          type="button"
                          onClick={() => setEditingTranscript(null)}
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <p>{a.transcription.text}</p>
                      {!readOnly && token && (
                        <div className="row">
                          {!a.transcription.verified && (
                            <button
                              className="link-btn"
                              type="button"
                              onClick={() => verifyTranscript(a)}
                              disabled={busy}
                            >
                              Mark verified
                            </button>
                          )}
                          <button
                            className="link-btn"
                            type="button"
                            onClick={() => {
                              setEditingTranscript(a.id);
                              setTranscriptDraft(a.transcription?.text ?? '');
                            }}
                          >
                            Correct text
                          </button>
                        </div>
                      )}
                    </>
                  )}
                </div>
              ) : (
                !readOnly && <p className="muted">Reading file…</p>
              )}
            </li>
          ))}
        </ul>
      )}

      {grouped.map((g) => (
        <section key={g.type}>
          <h4>{SECTION_LABELS[g.type] ?? g.type}</h4>
          {g.items.map((s) =>
            editingSection === s.id ? (
              <div className="field" key={s.id}>
                <textarea
                  rows={3}
                  value={sectionDraft}
                  onChange={(e) => setSectionDraft(e.target.value)}
                />
                <div className="row">
                  <button
                    className="btn btn-primary"
                    type="button"
                    onClick={() => saveSection(s.id)}
                    disabled={busy}
                  >
                    Save
                  </button>
                  <button className="btn" type="button" onClick={() => setEditingSection(null)}>
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div className="section-item" key={s.id}>
                <p>{s.content}</p>
                {!readOnly && (
                  <div className="row">
                    <button
                      className="link-btn"
                      type="button"
                      onClick={() => {
                        setEditingSection(s.id);
                        setSectionDraft(s.content);
                      }}
                    >
                      Edit
                    </button>
                    <button className="link-btn" type="button" onClick={() => removeSection(s.id)}>
                      Delete
                    </button>
                  </div>
                )}
              </div>
            ),
          )}
        </section>
      ))}

      {!readOnly &&
        (adding ? (
          <form onSubmit={submitSection}>
            <div className="field">
              <label htmlFor={`section-${visit.id}`}>Add result</label>
              <select
                id={`section-${visit.id}`}
                value={newType}
                onChange={(e) => setNewType(e.target.value)}
              >
                {SECTION_ORDER.map((t) => (
                  <option key={t} value={t}>
                    {SECTION_LABELS[t]}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <textarea
                rows={3}
                placeholder="e.g. GeneXpert: MTB detected, rifampicin susceptible — or dictate instead of typing."
                value={newContent}
                onChange={(e) => setNewContent(e.target.value)}
              />
            </div>
            <div className="field">
              <span className="field-label">Attach a photo of the slip, upload a file, or dictate</span>
              <div className="row capture-actions">
                <button
                  className="btn"
                  type="button"
                  onClick={() => photoInput.current?.click()}
                  disabled={busy || recording}
                >
                  Take a photo
                </button>
                <button
                  className="btn"
                  type="button"
                  onClick={() => fileInput.current?.click()}
                  disabled={busy || recording}
                >
                  Attach files
                </button>
                <button
                  className={dictating ? 'btn btn-danger' : 'btn'}
                  type="button"
                  onClick={toggleDictation}
                  disabled={busy || recording}
                >
                  {dictating ? 'Stop dictation' : 'Dictate'}
                </button>
                <button
                  className={recording ? 'btn btn-danger' : 'btn'}
                  type="button"
                  onClick={toggleResultRecording}
                  disabled={busy || dictating}
                >
                  {recording
                    ? `Stop recording (${Math.floor(recSeconds / 60)}:${String(recSeconds % 60).padStart(2, '0')})`
                    : 'Record audio'}
                </button>
              </div>
              <input
                ref={photoInput}
                type="file"
                accept="image/*"
                capture="environment"
                hidden
                onChange={(e) => {
                  addResultFiles(e.target.files ? Array.from(e.target.files) : []);
                  e.target.value = '';
                }}
              />
              <input
                ref={fileInput}
                type="file"
                multiple
                accept="image/*,audio/*,.pdf,.txt,.md"
                hidden
                onChange={(e) => {
                  addResultFiles(e.target.files ? Array.from(e.target.files) : []);
                  e.target.value = '';
                }}
              />
              {dictating && (
                <p className="muted">Listening… speak and the words appear in the notes above.</p>
              )}
              {recording && (
                <p className="muted">
                  Recording… press Stop when done. The audio is attached and transcribed for
                  verification after you save.
                </p>
              )}
              {resultPreviews.length > 0 && (
                <div className="row">
                  {resultPreviews.map((p) => (
                    <img key={p.name} className="photo-preview" src={p.url} alt={`Preview of ${p.name}`} />
                  ))}
                </div>
              )}
              {resultFiles.map((f) => (
                <p className="muted" key={f.name}>
                  {f.type.startsWith('image/') ? 'Photo' : 'Attached'}: {f.name}{' '}
                  <button className="link-btn" type="button" onClick={() => removeResultFile(f.name)}>
                    Remove
                  </button>
                </p>
              ))}
              <p className="muted">
                Photos open the camera on a phone. Recorded dictations are transcribed by the AI;
                every machine read is shown for verification.
              </p>
            </div>
            <div className="row">
              <button className="btn btn-primary" type="submit" disabled={busy || recording}>
                {busy ? 'Saving…' : 'Add'}
              </button>
              <button className="btn" type="button" onClick={cancelResult}>
                Cancel
              </button>
            </div>
          </form>
        ) : (
          <button className="btn" type="button" onClick={() => setAdding(true)}>
            + Add lab / imaging / note
          </button>
        ))}

      {token && !readOnly && (
        <VisitSummaryGate visit={visit} token={token} onApply={apply} />
      )}

      {error && <p className="error">{error}</p>}
    </article>
  );
}
