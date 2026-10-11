import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import Skeleton from '@platform-ui/components/Skeleton';
import type { ApiError } from '@platform-ui/api/types';
import { btnStyle, pageStyle, primaryBtnStyle } from '../styles';
import type { Dataset } from '../types';

// ── Images View ───────────────────────────────────────────────────────────────
//
// Two ways to add an image, both funnelling through the same import core:
//   1. Scan the server-side staging folder (POST /images/scan).
//   2. Add from the browser — paste (Ctrl/Cmd-V), drop onto the drop zone, or
//      pick a file — POST /images/upload per file, then re-list.

export interface ImageRow {
  slug: string;
  source_filename: string;
  content_type: string;
  byte_size: number;
  width: number | null;
  height: number | null;
  created_at: string;
  url: string;
}

export interface ScanReport {
  imported: {
    slug: string;
    source_filename: string;
    url: string;
    width: number | null;
    height: number | null;
    byte_size: number;
  }[];
  unchanged: number;
  skipped: { filename: string; reason: string }[];
}

export const GENERIC_PASTE_NAME_RE = /^image\.(png|jpe?g|gif|webp)$/i;

export function ImagesView() {
  const navigate = useNavigate();
  const [images, setImages] = useState<ImageRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [scanning, setScanning] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [report, setReport] = useState<ScanReport | null>(null);
  const [copiedSlug, setCopiedSlug] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadImages = useCallback(async () => {
    setLoading(true);
    const res = await apiFetch<Dataset<ImageRow>>('/essaycards/images');
    setLoading(false);
    if (isApiError(res)) {
      setError(res);
      return;
    }
    setError(null);
    setImages(res.rows);
  }, []);

  useEffect(() => { loadImages(); }, [loadImages]);

  const handleScan = async () => {
    setScanning(true);
    setError(null);
    setReport(null);
    const res = await apiFetch<ScanReport>('/essaycards/images/scan', { method: 'POST' });
    setScanning(false);
    if (isApiError(res)) {
      setError(res);
      return;
    }
    setReport(res);
    loadImages();
  };

  // POST each image to /images/upload sequentially (volume is tiny; sequential
  // keeps error reporting simple), then re-list and show the same
  // imported / unchanged / skipped block the scan button uses. apiFetch forces
  // a JSON Content-Type, so multipart goes through a raw fetch.
  const uploadFiles = useCallback(async (files: File[]) => {
    const imageFiles = files.filter(f => f.type.startsWith('image/'));
    if (imageFiles.length === 0) return;

    setUploading(true);
    setError(null);
    setReport(null);
    const agg: ScanReport = { imported: [], unchanged: 0, skipped: [] };

    for (const file of imageFiles) {
      const meaningful = !!file.name && !GENERIC_PASTE_NAME_RE.test(file.name);
      const name = meaningful ? file.name : 'pasted-image';
      const fd = new FormData();
      fd.append('file', file, name);
      fd.append('filename', name);
      try {
        const res = await fetch('/api/essaycards/images/upload', { method: 'POST', body: fd });
        const data = await res.json();
        if (!res.ok) {
          const reason = data?.error?.detail?.reason || data?.error?.code || `HTTP ${res.status}`;
          agg.skipped.push({ filename: name, reason });
        } else if (data.unchanged) {
          agg.unchanged += 1;
        } else {
          agg.imported.push({
            slug: data.slug,
            source_filename: data.source_filename,
            url: data.url,
            width: data.width,
            height: data.height,
            byte_size: data.byte_size,
          });
        }
      } catch (e) {
        agg.skipped.push({ filename: name, reason: String(e) });
      }
    }

    setUploading(false);
    setReport(agg);
    loadImages();
  }, [loadImages]);

  // Catch Ctrl/Cmd-V anywhere on the Images view (a plain div is not a reliable
  // paste target on its own).
  useEffect(() => {
    const onPaste = (e: ClipboardEvent) => {
      const files = e.clipboardData ? Array.from(e.clipboardData.files) : [];
      const imgs = files.filter(f => f.type.startsWith('image/'));
      if (imgs.length > 0) {
        e.preventDefault();
        uploadFiles(imgs);
      }
    };
    window.addEventListener('paste', onPaste);
    return () => window.removeEventListener('paste', onPaste);
  }, [uploadFiles]);

  const handleContainerPaste = (e: React.ClipboardEvent) => {
    const imgs = Array.from(e.clipboardData.files).filter(f => f.type.startsWith('image/'));
    if (imgs.length > 0) {
      e.preventDefault();
      uploadFiles(imgs);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
    uploadFiles(Array.from(e.dataTransfer.files));
  };

  const handleCopy = async (slug: string) => {
    try {
      await navigator.clipboard.writeText(`![](/api/essaycards/images/${slug})`);
      setCopiedSlug(slug);
      setTimeout(() => setCopiedSlug(null), 1500);
    } catch {
      setCopiedSlug(null);
    }
  };

  const busy = scanning || uploading;

  return (
    <div style={pageStyle} onPaste={handleContainerPaste}>
      <button style={{ ...btnStyle, marginBottom: 12 }} onClick={() => navigate('/essaycards')}>
        ← All essays
      </button>
      <h2 style={{ marginTop: 0 }}>Images</h2>
      <div style={{ color: 'var(--md-sys-color-on-surface-variant)', fontSize: 13, marginBottom: 12 }}>
        Add an image by pasting (Ctrl/Cmd-V), dropping a file below, or picking one —
        or drop files into the server staging folder
        (<code>{'${DATA_ROOT}'}/essaycards/staging</code>) and scan. Reference an
        imported image in essay or card text as ordinary Markdown:{' '}
        <code>![](/api/essaycards/images/&lt;slug&gt;)</code>. Keep your originals —
        the processed images folder (and the <code>originals/</code> upload archive)
        is never backed up automatically.
      </div>

      <div
        onDragOver={e => { e.preventDefault(); setDragActive(true); }}
        onDragLeave={e => { e.preventDefault(); setDragActive(false); }}
        onDrop={handleDrop}
        style={{
          border: `2px dashed ${dragActive ? '#4a90d9' : '#c0c0c0'}`,
          background: dragActive ? '#eef5fc' : '#fafafa',
          borderRadius: 8,
          padding: 20,
          textAlign: 'center',
          color: 'var(--md-sys-color-on-surface-variant)',
          fontSize: 13,
          marginBottom: 12,
        }}
      >
        {uploading ? 'Uploading…' : 'Paste or drop an image here'}
        <div style={{ marginTop: 8 }}>
          <button style={btnStyle} disabled={busy} onClick={() => fileInputRef.current?.click()}>
            Choose file…
          </button>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          multiple
          style={{ display: 'none' }}
          onChange={e => {
            if (e.target.files) uploadFiles(Array.from(e.target.files));
            e.target.value = '';
          }}
        />
      </div>

      <button style={primaryBtnStyle} disabled={busy} onClick={handleScan}>
        {scanning ? 'Scanning…' : 'Scan staging folder'}
      </button>

      {error && <div style={{ marginTop: 16 }}><ErrorCard error={error} /></div>}

      {report && (
        <div style={{
          marginTop: 16,
          padding: 12,
          borderRadius: 8,
          border: '1px solid var(--md-sys-color-outline-variant)',
          fontSize: 13,
        }}>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>Import complete</div>
          <div>Imported: {report.imported.length}</div>
          {report.imported.map(i => (
            <div key={i.slug} style={{ color: 'var(--md-sys-color-on-surface-variant)' }}>+ {i.source_filename} → {i.slug}</div>
          ))}
          <div style={{ marginTop: 4 }}>Unchanged: {report.unchanged}</div>
          {report.skipped.length > 0 && (
            <>
              <div style={{ marginTop: 4 }}>Skipped: {report.skipped.length}</div>
              {report.skipped.map((s, idx) => (
                <div key={idx} style={{ color: '#a00' }}>– {s.filename} ({s.reason})</div>
              ))}
            </>
          )}
        </div>
      )}

      <h3 style={{ marginTop: 24 }}>Imported images</h3>
      {loading && <Skeleton />}
      {!loading && images.length === 0 && (
        <div style={{ color: 'var(--md-sys-color-on-surface-variant)', fontSize: 14 }}>No images imported yet.</div>
      )}
      {!loading && images.map(img => (
        <div
          key={img.slug}
          style={{
            display: 'flex',
            gap: 12,
            padding: 12,
            border: '1px solid var(--md-sys-color-outline-variant)',
            borderRadius: 8,
            marginBottom: 8,
            alignItems: 'center',
          }}
        >
          <img
            src={img.url}
            alt={img.source_filename}
            style={{ width: 96, height: 96, objectFit: 'contain', flexShrink: 0, background: '#f5f5f5' }}
          />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontWeight: 600, wordBreak: 'break-all' }}>{img.source_filename}</div>
            <div style={{ fontSize: 12, color: 'var(--md-sys-color-on-surface-variant)' }}>
              {img.width ?? '?'}×{img.height ?? '?'} · {(img.byte_size / 1024).toFixed(0)} KB · {img.slug}
            </div>
          </div>
          <button style={btnStyle} onClick={() => handleCopy(img.slug)}>
            {copiedSlug === img.slug ? 'Copied' : 'Copy Markdown'}
          </button>
        </div>
      ))}
    </div>
  );
}
