import { useEffect, useRef, useState } from "react";
import { createJob, fetchJob, fileUrl, type ClipInfo, type JobStatusResponse } from "./api";

type Mode = "url" | "file";

const STATUS_COPY: Record<string, string> = {
  queued: "Queued",
  downloading: "Downloading source",
  extracting_audio: "Extracting audio",
  transcribing: "Transcribing (this is the slowest step)",
  analyzing: "Scoring highlights",
  rendering: "Rendering vertical clips",
  done: "Done",
  failed: "Failed",
};

function fmtTime(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function App() {
  const [mode, setMode] = useState<Mode>("url");
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [numClips, setNumClips] = useState(10);
  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<JobStatusResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  useEffect(() => {
    if (!jobId) return;
    let cancelled = false;
    const tick = async () => {
      try {
        const j = await fetchJob(jobId);
        if (cancelled) return;
        setJob(j);
        if (j.status !== "done" && j.status !== "failed") {
          pollRef.current = window.setTimeout(tick, 1500);
        }
      } catch (err) {
        if (!cancelled) setError(String(err));
      }
    };
    tick();
    return () => {
      cancelled = true;
      if (pollRef.current) window.clearTimeout(pollRef.current);
    };
  }, [jobId]);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setJob(null);
    setSubmitting(true);
    try {
      const resp = await createJob({
        url: mode === "url" ? url.trim() : undefined,
        file: mode === "file" ? file ?? undefined : undefined,
        numClips,
      });
      setJobId(resp.job_id);
    } catch (err) {
      setError(String(err));
    } finally {
      setSubmitting(false);
    }
  };

  const reset = () => {
    if (pollRef.current) window.clearTimeout(pollRef.current);
    setJobId(null);
    setJob(null);
    setError(null);
    setUrl("");
    setFile(null);
  };

  return (
    <div className="container">
      <header>
        <h1>
          <span className="logo">🎬</span> Clip Genius
        </h1>
        <p className="tagline">AI highlight clipper for streams, podcasts & webinars</p>
      </header>

      {!jobId && (
        <form className="card" onSubmit={onSubmit}>
          <div className="tabs">
            <button
              type="button"
              className={mode === "url" ? "active" : ""}
              onClick={() => setMode("url")}
            >
              From URL
            </button>
            <button
              type="button"
              className={mode === "file" ? "active" : ""}
              onClick={() => setMode("file")}
            >
              Upload file
            </button>
          </div>

          {mode === "url" ? (
            <label className="field">
              <span>Stream / video URL</span>
              <input
                type="url"
                placeholder="https://www.youtube.com/watch?v=…"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                required
              />
              <small>Twitch VOD, YouTube, direct MP4 — anything yt-dlp supports.</small>
            </label>
          ) : (
            <label className="field">
              <span>Video file</span>
              <input
                type="file"
                accept="video/*"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                required
              />
            </label>
          )}

          <label className="field">
            <span>Number of clips: {numClips}</span>
            <input
              type="range"
              min={1}
              max={20}
              value={numClips}
              onChange={(e) => setNumClips(Number(e.target.value))}
            />
          </label>

          <button className="primary" type="submit" disabled={submitting}>
            {submitting ? "Starting…" : "Generate clips"}
          </button>
          {error && <p className="error">{error}</p>}
        </form>
      )}

      {jobId && job && (
        <section className="card">
          <div className="row">
            <div>
              <div className="job-id">Job {job.job_id}</div>
              {job.source_title && (
                <div className="source-title">
                  {job.source_title}
                  {job.source_duration ? ` · ${fmtTime(job.source_duration)}` : ""}
                </div>
              )}
            </div>
            <button className="ghost" onClick={reset}>
              New job
            </button>
          </div>

          <div className="status">
            <div className={`status-label status-${job.status}`}>
              {STATUS_COPY[job.status] ?? job.status}
            </div>
            <div className="progress">
              <div className="progress-bar" style={{ width: `${Math.round(job.progress * 100)}%` }} />
            </div>
            <div className="status-message">{job.message}</div>
            {job.error && <div className="error">{job.error}</div>}
          </div>

          {job.clips.length > 0 && (
            <div className="clips">
              {job.clips.map((c) => (
                <ClipCard key={c.index} clip={c} />
              ))}
            </div>
          )}
        </section>
      )}

      <footer>
        <small>Made with Clip Genius · free clips include a watermark</small>
      </footer>
    </div>
  );
}

function ClipCard({ clip }: { clip: ClipInfo }) {
  const src = fileUrl(clip.url);
  return (
    <article className="clip">
      <video controls preload="metadata" src={src} />
      <div className="clip-meta">
        <div className="clip-title">
          #{clip.index}. {clip.title}
        </div>
        <div className="clip-sub">
          {fmtTime(clip.start)} – {fmtTime(clip.end)} · {clip.duration.toFixed(1)}s · score{" "}
          {clip.score.toFixed(2)}
        </div>
        <a className="download" href={src} download={`clip_${clip.index}.mp4`}>
          ↓ Download MP4
        </a>
      </div>
    </article>
  );
}
