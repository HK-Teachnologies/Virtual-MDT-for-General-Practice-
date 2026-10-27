'use client';

import { useState, type FormEvent } from 'react';
import {
  addSection,
  deleteSection,
  downloadAttachment,
  updateSection,
  updateVisit,
} from '../lib/api';
import type { ApiAttachment, ApiSection, ApiVisit } from '../lib/types';

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
  const [editingSection, setEditingSection] = useState<string | null>(null);
  const [sectionDraft, setSectionDraft] = useState('');
  const [editingNotes, setEditingNotes] = useState(false);
  const [notesDraft, setNotesDraft] = useState(visit.notes);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function apply(updated: ApiVisit) {
    setVisit(updated);
    onChange?.(updated);
  }

  async function submitSection(e: FormEvent) {
    e.preventDefault();
    if (!token || !newContent.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const created = await addSection(token, patientId, visit.id, {
        section: newType,
        content: newContent.trim(),
      });
      apply({ ...visit, sections: [...visit.sections, created] });
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
              {!readOnly && token ? (
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
                placeholder="e.g. GeneXpert: MTB detected, rifampicin susceptible."
                value={newContent}
                onChange={(e) => setNewContent(e.target.value)}
              />
            </div>
            <div className="row">
              <button className="btn btn-primary" type="submit" disabled={busy}>
                {busy ? 'Saving…' : 'Add'}
              </button>
              <button className="btn" type="button" onClick={() => setAdding(false)}>
                Cancel
              </button>
            </div>
          </form>
        ) : (
          <button className="btn" type="button" onClick={() => setAdding(true)}>
            + Add lab / imaging / note
          </button>
        ))}

      {error && <p className="error">{error}</p>}
    </article>
  );
}
