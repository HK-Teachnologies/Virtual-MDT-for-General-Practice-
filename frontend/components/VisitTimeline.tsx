import type { Visit } from '../lib/types';

const SOURCE_LABEL: Record<Visit['source'], string> = {
  photo: 'photo notes',
  dictation: 'dictation',
  record: 'clinic record',
};

export default function VisitTimeline({ visits }: { visits: Visit[] }) {
  if (visits.length === 0) return <p className="muted">No visits recorded yet.</p>;
  const ordered = [...visits].sort((a, b) => b.date.localeCompare(a.date));
  return (
    <ol className="timeline">
      {ordered.map((v) => (
        <li key={v.id} className="timeline-item">
          <div className="timeline-date">
            {v.date} <span className="badge">{SOURCE_LABEL[v.source]}</span>
          </div>
          <div>{v.summary}</div>
        </li>
      ))}
    </ol>
  );
}
