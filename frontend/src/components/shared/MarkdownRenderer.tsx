"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { Copy, Check } from "lucide-react";
import { copyToClipboard } from "@/lib/utils";

interface CodeBlockProps {
  language: string;
  value: string;
}

function CodeBlock({ language, value }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await copyToClipboard(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative group rounded-lg overflow-hidden my-3"
      style={{ border: "1px solid var(--color-border-default)" }}>
      <div className="flex items-center justify-between px-4 py-2"
        style={{ background: "var(--color-bg-overlay)", borderBottom: "1px solid var(--color-border-subtle)" }}>
        <span className="text-xs font-mono" style={{ color: "var(--color-text-tertiary)" }}>
          {language || "text"}
        </span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 text-xs px-2 py-1 rounded transition-colors opacity-0 group-hover:opacity-100"
          style={{ color: "var(--color-text-secondary)" }}
        >
          {copied ? <Check className="w-3 h-3 text-green-400" /> : <Copy className="w-3 h-3" />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <SyntaxHighlighter
        language={language || "text"}
        style={oneDark}
        customStyle={{
          margin: 0,
          padding: "1rem",
          background: "#0f0f0f",
          fontSize: "0.8125rem",
          lineHeight: "1.6",
        }}
        showLineNumbers={value.split("\n").length > 5}
        lineNumberStyle={{ color: "#444", fontSize: "0.75rem" }}
      >
        {value}
      </SyntaxHighlighter>
    </div>
  );
}

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

export function MarkdownRenderer({ content, className }: MarkdownRendererProps) {
  return (
    <div className={`prose ${className ?? ""}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          code({ node, className, children, ...props }: any) {
            const match = /language-(\w+)/.exec(className || "");
            const isBlock = !props.inline;
            if (isBlock && match) {
              return (
                <CodeBlock
                  language={match[1]}
                  value={String(children).replace(/\n$/, "")}
                />
              );
            }
            return (
              <code className={className} {...props}>
                {children}
              </code>
            );
          },
          // Open links in new tab
          a: ({ children, href, ...props }) => (
            <a href={href} target="_blank" rel="noopener noreferrer" {...props}>
              {children}
            </a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
