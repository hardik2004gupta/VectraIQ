"use client";

import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, FileText, Trash2, Search, BookOpen, CheckCircle2, Loader2 } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/shared/EmptyState";
import { Button } from "@/components/shared/Button";
import { StatusBadge } from "@/components/shared/StatusBadge";

// Note: The /documents/upload endpoint is not yet implemented in the backend.
// This UI demonstrates the intended UX. Files are accepted and shown in a
// "processing" state. When the backend endpoint is implemented, wire it here.

type FileStatus = "queued" | "uploading" | "processing" | "done" | "error";

interface UploadedFile {
  id: string;
  name: string;
  size: number;
  type: string;
  status: FileStatus;
  progress?: number;
  addedAt: Date;
  error?: string;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const STATUS_MAP: Record<FileStatus, { label: string; icon: React.ReactNode }> = {
  queued:     { label: "Queued",     icon: <div className="w-3 h-3 rounded-full" style={{ background: "var(--color-border-strong)" }} /> },
  uploading:  { label: "Uploading",  icon: <Loader2 className="w-3 h-3 spin text-blue-400" /> },
  processing: { label: "Processing", icon: <Loader2 className="w-3 h-3 spin text-yellow-400" /> },
  done:       { label: "Indexed",    icon: <CheckCircle2 className="w-3 h-3 text-green-400" /> },
  error:      { label: "Error",      icon: <div className="w-3 h-3 rounded-full bg-red-500" /> },
};

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

    // Simulate processing states (backend endpoint pending)
    newFiles.forEach((file) => {
      setTimeout(() => {
        setFiles((prev) => prev.map((f) => f.id === file.id ? { ...f, status: "uploading" } : f));
        setTimeout(() => {
          setFiles((prev) => prev.map((f) => f.id === file.id ? { ...f, status: "processing" } : f));
          setTimeout(() => {
            setFiles((prev) => prev.map((f) => f.id === file.id ? { ...f, status: "done" } : f));
            toast.success(`${file.name} indexed successfully`);
          }, 2000);
        }, 1000);
      }, 300 + Math.random() * 700);
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
    maxSize: 50 * 1024 * 1024, // 50 MB
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

      {/* Drop zone */}
      <div
        {...getRootProps()}
        className="rounded-2xl border-2 border-dashed p-10 text-center cursor-pointer transition-all mb-6"
        style={{
          borderColor: isDragActive ? "var(--color-accent-DEFAULT)" : "var(--color-border-default)",
          background: isDragActive ? "var(--color-accent-glow)" : "var(--color-bg-surface)",
        }}>
        <input {...getInputProps()} />
        <Upload className="w-8 h-8 mx-auto mb-3"
          style={{ color: isDragActive ? "var(--color-accent-DEFAULT)" : "var(--color-text-tertiary)" }} />
        <p className="text-sm font-medium mb-1" style={{ color: "var(--color-text-primary)" }}>
          {isDragActive ? "Drop files here" : "Drag & drop files here"}
        </p>
        <p className="text-xs" style={{ color: "var(--color-text-tertiary)" }}>
          PDF, DOCX, TXT, HTML, Markdown · Max 50 MB each
        </p>
        <Button variant="outline" size="sm" className="mt-4">
          Browse files
        </Button>
      </div>

      {/* File list */}
      {files.length === 0 ? (
        <EmptyState
          icon={BookOpen}
          title="No documents yet"
          description="Upload your Kubernetes runbooks, architecture docs, and incident playbooks to enable AI-powered search."
        />
      ) : (
        <div className="rounded-xl border overflow-hidden"
          style={{ background: "var(--color-bg-surface)", borderColor: "var(--color-border-subtle)" }}>
          <div className="px-4 py-3 border-b flex items-center justify-between"
            style={{ borderColor: "var(--color-border-subtle)" }}>
            <h3 className="text-xs font-medium" style={{ color: "var(--color-text-secondary)" }}>
              {files.length} {files.length === 1 ? "document" : "documents"}
            </h3>
            <StatusBadge
              status="ok"
              label={`${files.filter((f) => f.status === "done").length} indexed`}
            />
          </div>
          <div className="divide-y" style={{ borderColor: "var(--color-border-subtle)" }}>
            <AnimatePresence>
              {filtered.map((file) => (
                <motion.div
                  key={file.id}
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                  className="flex items-center gap-3 px-4 py-3">
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
                    style={{ background: "var(--color-bg-elevated)" }}>
                    <FileText className="w-4 h-4" style={{ color: "var(--color-text-tertiary)" }} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate" style={{ color: "var(--color-text-primary)" }}>
                      {file.name}
                    </p>
                    <p className="text-xs" style={{ color: "var(--color-text-tertiary)" }}>
                      {formatFileSize(file.size)} · {file.addedAt.toLocaleDateString()}
                    </p>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    {STATUS_MAP[file.status].icon}
                    <span className="text-xs" style={{ color: "var(--color-text-tertiary)" }}>
                      {STATUS_MAP[file.status].label}
                    </span>
                  </div>
                  <button
                    onClick={() => removeFile(file.id)}
                    className="shrink-0 p-1 rounded-lg transition-colors opacity-0 hover:opacity-100 group-hover:opacity-100"
                    style={{ color: "var(--color-text-tertiary)" }}>
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        </div>
      )}

      {/* Note about backend */}
      <p className="text-xs mt-4 text-center"
        style={{ color: "var(--color-text-disabled)" }}>
        Note: Document upload backend endpoint is pending implementation.
        Files shown above are queued locally.
      </p>
    </div>
  );
}
