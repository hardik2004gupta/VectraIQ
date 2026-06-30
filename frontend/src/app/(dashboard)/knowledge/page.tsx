"use client";

import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, FileText, Trash2, Search, BookOpen, Construction } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/shared/EmptyState";
import { Button } from "@/components/shared/Button";

type FileStatus = "queued" | "error";

interface UploadedFile {
  id: string;
  name: string;
  size: number;
  type: string;
  status: FileStatus;
  addedAt: Date;
  error?: string;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function KnowledgePage() {
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [search, setSearch] = useState("");

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const newFiles: UploadedFile[] = acceptedFiles.map((f) => ({
      id: crypto.randomUUID(),
      name: f.name,
      size: f.size,
      type: f.type,
      status: "queued" as FileStatus,
      addedAt: new Date(),
    }));

    setFiles((prev) => [...prev, ...newFiles]);
    toast.info("Files queued — backend upload is coming in v1.1", {
      description: "Use `make seed` to ingest documents via the CLI today.",
    });
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "text/plain": [".txt"],
      "text/html": [".html", ".htm"],
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
      "text/markdown": [".md"],
    },
    maxSize: 50 * 1024 * 1024,
  });

  const removeFile = (id: string) => {
    setFiles((prev) => prev.filter((f) => f.id !== id));
  };

  const filtered = files.filter((f) =>
    f.name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div>
      <PageHeader
        title="Knowledge Base"
        description="Upload documents to expand the retrieval corpus."
        actions={
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5"
              style={{ color: "var(--color-text-tertiary)" }} />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search files…"
              aria-label="Search uploaded files"
              className="h-8 pl-8 pr-3 text-xs rounded-lg outline-none w-48"
              style={{
                background: "var(--color-bg-surface)",
                border: "1px solid var(--color-border-default)",
                color: "var(--color-text-primary)",
              }}
            />
          </div>
        }
      />

      {/* Coming soon notice */}
      <div
        className="flex items-start gap-3 rounded-xl px-4 py-3 mb-5 text-sm"
        role="status"
        aria-live="polite"
        style={{
          background: "var(--color-warning-subtle)",
          border: "1px solid rgba(245,158,11,0.25)",
          color: "var(--color-warning)",
        }}>
        <Construction className="w-4 h-4 mt-0.5 shrink-0" aria-hidden="true" />
        <div>
          <span className="font-medium">Upload API coming in v1.1.</span>
          {" "}Files dropped here are queued locally only — they are not ingested into the knowledge base.
          To add documents today, place files in <code className="text-xs px-1 py-0.5 rounded" style={{ background: "rgba(0,0,0,0.2)" }}>seed/docs/true_data/</code> and run <code className="text-xs px-1 py-0.5 rounded" style={{ background: "rgba(0,0,0,0.2)" }}>make seed</code>.
        </div>
      </div>

      {/* Drop zone */}
      <div
        {...getRootProps()}
        role="button"
        tabIndex={0}
        aria-label="Drop zone for document upload"
        className="rounded-2xl border-2 border-dashed p-10 text-center cursor-pointer transition-all mb-6"
        style={{
          borderColor: isDragActive ? "var(--color-accent-DEFAULT)" : "var(--color-border-default)",
          background: isDragActive ? "var(--color-accent-glow)" : "var(--color-bg-surface)",
        }}>
        <input {...getInputProps()} aria-hidden="true" />
        <Upload className="w-8 h-8 mx-auto mb-3"
          aria-hidden="true"
          style={{ color: isDragActive ? "var(--color-accent-DEFAULT)" : "var(--color-text-tertiary)" }} />
        <p className="text-sm font-medium mb-1" style={{ color: "var(--color-text-primary)" }}>
          {isDragActive ? "Drop files here" : "Drag & drop files here"}
        </p>
        <p className="text-xs" style={{ color: "var(--color-text-tertiary)" }}>
          PDF, DOCX, TXT, HTML, Markdown · Max 50 MB each
        </p>
        <Button variant="outline" size="sm" className="mt-4" aria-label="Browse files to upload">
          Browse files
        </Button>
      </div>

      {/* File list */}
      {files.length === 0 ? (
        <EmptyState
          icon={BookOpen}
          title="No documents queued"
          description="Drag and drop files above to see them here. Use make seed to ingest documents into the knowledge base via the CLI."
        />
      ) : (
        <div className="rounded-xl border overflow-hidden"
          style={{ background: "var(--color-bg-surface)", borderColor: "var(--color-border-subtle)" }}>
          <div className="px-4 py-3 border-b flex items-center justify-between"
            style={{ borderColor: "var(--color-border-subtle)" }}>
            <h3 className="text-xs font-medium" style={{ color: "var(--color-text-secondary)" }}>
              {files.length} {files.length === 1 ? "file" : "files"} queued locally
            </h3>
          </div>
          <div className="divide-y" style={{ borderColor: "var(--color-border-subtle)" }}>
            <AnimatePresence>
              {filtered.map((file) => (
                <motion.div
                  key={file.id}
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                  className="flex items-center gap-3 px-4 py-3 group">
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
                    style={{ background: "var(--color-bg-elevated)" }}>
                    <FileText className="w-4 h-4" aria-hidden="true" style={{ color: "var(--color-text-tertiary)" }} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate" style={{ color: "var(--color-text-primary)" }}>
                      {file.name}
                    </p>
                    <p className="text-xs" style={{ color: "var(--color-text-tertiary)" }}>
                      {formatFileSize(file.size)} · {file.addedAt.toLocaleDateString()}
                    </p>
                  </div>
                  <span className="text-xs shrink-0" style={{ color: "var(--color-text-disabled)" }}>
                    Queued
                  </span>
                  <button
                    onClick={() => removeFile(file.id)}
                    aria-label={`Remove ${file.name}`}
                    className="shrink-0 p-1 rounded-lg transition-colors opacity-0 group-hover:opacity-100 focus-visible:opacity-100"
                    style={{ color: "var(--color-text-tertiary)" }}>
                    <Trash2 className="w-3.5 h-3.5" aria-hidden="true" />
                  </button>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        </div>
      )}
    </div>
  );
}
