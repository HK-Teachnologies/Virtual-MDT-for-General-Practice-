'use client';

import { useEffect, useRef, useState } from 'react';

export default function VoiceRecorder({
  onRecording,
  onClear,
}: {
  onRecording: (blob: Blob) => void;
  onClear: () => void;
}) {
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [preview, setPreview] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(
    () => () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (preview) URL.revokeObjectURL(preview);
    },
    [preview],
  );

  async function start() {
    setError(null);
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setError('Microphone unavailable - check browser permission.');
      return;
    }
    const mime = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : '';
    const rec = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
    chunksRef.current = [];
    rec.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data);
    };
    rec.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      if (timerRef.current) clearInterval(timerRef.current);
      setRecording(false);
      const blob = new Blob(chunksRef.current, { type: rec.mimeType || 'audio/webm' });
      if (blob.size === 0) {
        setError('Nothing was recorded - try again.');
        return;
      }
      if (preview) URL.revokeObjectURL(preview);
      setPreview(URL.createObjectURL(blob));
      onRecording(blob);
    };
    recorderRef.current = rec;
    setSeconds(0);
    timerRef.current = setInterval(() => setSeconds((s) => s + 1), 1000);
    rec.start();
    setRecording(true);
  }

  function stop() {
    recorderRef.current?.stop();
  }

  function clear() {
    if (preview) URL.revokeObjectURL(preview);
    setPreview(null);
    onClear();
  }

  const mm = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;

  return (
    <div>
      {!recording && !preview && (
        <button className="btn" type="button" onClick={start}>
          🎙 Record voice note
        </button>
      )}
      {recording && (
        <div className="row">
          <span className="badge badge-responded">● {mm}</span>
          <button className="btn" type="button" onClick={stop}>
            ⏹ Stop
          </button>
        </div>
      )}
      {preview && (
        <div className="row">
          <audio controls src={preview} />
          <button className="btn" type="button" onClick={clear}>
            Remove
          </button>
        </div>
      )}
      {error && <p className="error">{error}</p>}
    </div>
  );
}
