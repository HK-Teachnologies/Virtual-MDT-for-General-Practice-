'use client';

import { useState, type FormEvent } from 'react';
import type { Visit } from '../lib/types';

export default function CaptureForm({ onAdd }: { onAdd: (v: Visit) => void }) {
  const [photo, setPhoto] = useState<string | null>(null);
  const [dictation, setDictation] = useState('');

  function handlePhoto(file: File | undefined) {
    if (!file) {
      setPhoto(null);
      return;
    }
    setPhoto(URL.createObjectURL(file));
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!dictation.trim() && !photo) return;
    onAdd({
      id: `v-${Date.now()}`,
      date: new Date().toISOString().slice(0, 10),
      summary: dictation.trim() || '(photo notes attached — transcription pending)',
      source: photo ? 'photo' : 'dictation',
    });
    setDictation('');
    setPhoto(null);
  }

  return (
    <form className="capture" onSubmit={handleSubmit}>
      <div className="field">
        <label htmlFor="photo">Photograph today&apos;s notes</label>
        <input
          id="photo"
          type="file"
          accept="image/*"
          onChange={(e) => handlePhoto(e.target.files?.[0])}
        />
        {photo && (
          // Plain img is enough for a local preview; no remote optimisation needed.
          <img className="photo-preview" src={photo} alt="Preview of photographed notes" />
        )}
      </div>
      <div className="field">
        <label htmlFor="dictation">Dictate the consultation</label>
        <textarea
          id="dictation"
          rows={4}
          placeholder="e.g. 52-year-old woman, known HIV on ART, hypertension, diabetes. Cough now two weeks, night sweats…"
          value={dictation}
          onChange={(e) => setDictation(e.target.value)}
        />
      </div>
      <button className="btn" type="submit">
        Add to record
      </button>
    </form>
  );
}
