/// <reference types="vite/client" />

export type JobStatus =
  | "queued"
  | "downloading"
  | "extracting_audio"
  | "transcribing"
  | "analyzing"
  | "rendering"
  | "done"
  | "failed";

export interface ClipInfo {
  index: number;
  start: number;
  end: number;
  duration: number;
  title: string;
  score: number;
  transcript: string;
  url: string;
}

export interface JobStatusResponse {
  job_id: string;
  status: JobStatus;
  progress: number;
  message: string;
  error: string | null;
  clips: ClipInfo[];
  source_title: string | null;
  source_duration: number | null;
}

export interface CreateJobOptions {
  url?: string;
  file?: File;
  numClips: number;
}

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

export async function createJob(opts: CreateJobOptions): Promise<{ job_id: string }> {
  const fd = new FormData();
  if (opts.url) fd.append("url", opts.url);
  if (opts.file) fd.append("file", opts.file);
  fd.append("num_clips", String(opts.numClips));
  const resp = await fetch(`${API_BASE}/jobs`, { method: "POST", body: fd });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`Failed to create job: ${resp.status} ${text}`);
  }
  return resp.json();
}

export async function fetchJob(jobId: string): Promise<JobStatusResponse> {
  const resp = await fetch(`${API_BASE}/jobs/${jobId}`);
  if (!resp.ok) throw new Error(`Failed to fetch job: ${resp.status}`);
  return resp.json();
}

export function fileUrl(path: string): string {
  return `${API_BASE}${path}`;
}
