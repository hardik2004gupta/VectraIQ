import Link from "next/link";
import { ArrowRight, Zap, Shield, Database, Layers, GitBranch, Search, ChevronRight } from "lucide-react";

const FEATURES = [
  {
    icon: Layers,
    title: "Hybrid RAG",
    description: "Dense + sparse retrieval with Reciprocal Rank Fusion. HyDE for hypothetical document embeddings.",
    color: "#6366f1",
  },
  {
    icon: Database,
    title: "Text2SQL",
    description: "Natural language to SQL with human-in-the-loop approval before any query executes.",
    color: "#8b5cf6",
  },
  {
    icon: GitBranch,
    title: "Intent Routing",
    description: "GPT-4o classifies each question and routes to the optimal pipeline automatically.",
    color: "#a78bfa",
  },
  {
    icon: Shield,
    title: "9-Layer Security",
    description: "JWT auth, rate limiting, llm-guard injection scan, PII redaction, spotlighting, and hardened system prompt.",
    color: "#c4b5fd",
  },
  {
    icon: Search,
    title: "CRAG + Self-RAG",
    description: "Corrective RAG grades retrieval relevance. Self-RAG reflects on answer quality and regenerates if needed.",
    color: "#818cf8",
  },
  {
    icon: Zap,
    title: "5-Tier Cache",
    description: "Redis + in-memory LRU caching across embeddings, answers, SQL, and intent — 80% cache hit rate.",
    color: "#60a5fa",
  },
];

const TECH = [
  { name: "FastAPI", category: "Backend" },
  { name: "LangGraph", category: "Orchestration" },
  { name: "Qdrant", category: "Vector DB" },
  { name: "PostgreSQL", category: "Database" },
  { name: "GPT-4o", category: "LLM" },
  { name: "OpenAI Embeddings", category: "Embeddings" },
  { name: "Redis", category: "Cache" },
  { name: "Tavily", category: "Web Search" },
  { name: "CrossEncoder", category: "Reranking" },
  { name: "llm-guard", category: "Security" },
  { name: "Next.js 15", category: "Frontend" },
  { name: "TanStack Query", category: "State" },
];

const FAQS = [
  {
    q: "What is VectraIQ?",
    a: "VectraIQ is a production-grade AI Knowledge Platform built for Kubernetes IT-Operations and SRE teams. It combines Hybrid RAG, Text2SQL, and intelligent intent routing to answer operational questions accurately from your runbooks and cluster data.",
  },
  {
    q: "How does the hybrid search work?",
    a: "Hybrid search combines dense vector search (Qdrant cosine similarity) with sparse TF-IDF BM25 search, fused using Reciprocal Rank Fusion (RRF). This outperforms pure dense search for keyword-heavy queries like pod names and error codes.",
  },
  {
    q: "Is my data secure?",
    a: "Yes. All inputs are scanned by llm-guard for prompt injection and toxicity. PII is redacted from both inputs and outputs. SQL queries require human approval before execution. JWT authentication with rate limiting protects all endpoints.",
  },
  {
    q: "What is Text2SQL with human-in-the-loop?",
    a: "When you ask a question about your cluster data, VectraIQ generates a SQL SELECT query, shows it to you for review, and only executes it after your explicit approval. No data is ever modified — only SELECTs are allowed.",
  },
  {
    q: "Can I upload my own documentation?",
    a: "Yes. The Knowledge Base page allows you to upload PDF, DOCX, HTML, and TXT files. Documents are parsed, chunked, embedded, and indexed for immediate retrieval.",
  },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen" style={{ background: "var(--color-bg-base)" }}>
      {/* Navbar */}
      <nav className="fixed top-0 inset-x-0 z-50 glass"
        style={{ borderBottom: "1px solid var(--color-border-subtle)" }}>
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg gradient-accent flex items-center justify-center">
              <Zap className="w-4 h-4 text-white" />
            </div>
            <span className="font-semibold text-sm" style={{ color: "var(--color-text-primary)" }}>
              VectraIQ
            </span>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/login"
              className="text-sm px-3 py-1.5 rounded-lg transition-colors"
              style={{ color: "var(--color-text-secondary)" }}>
              Sign in
            </Link>
            <Link href="/register"
              className="text-sm px-3 py-1.5 rounded-lg font-medium gradient-accent text-white">
              Get started
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="pt-32 pb-20 px-6 text-center relative overflow-hidden">
        <div className="absolute inset-0 pointer-events-none"
          style={{
            background: "radial-gradient(ellipse 80% 60% at 50% -20%, rgba(99,102,241,0.15), transparent)",
          }} />
        <div className="max-w-3xl mx-auto relative">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full mb-6 text-xs font-medium"
            style={{
              background: "var(--color-accent-glow)",
              border: "1px solid rgba(99,102,241,0.3)",
              color: "var(--color-accent-light)",
            }}>
            <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse" />
            Production-ready AI Platform
          </div>
          <h1 className="text-5xl font-bold mb-5 tracking-tight leading-tight">
            <span className="gradient-text">AI-Powered</span>
            <br />
            Kubernetes Copilot
          </h1>
          <p className="text-lg mb-8 max-w-xl mx-auto leading-relaxed"
            style={{ color: "var(--color-text-secondary)" }}>
            Hybrid RAG + Text2SQL + Intelligent Routing with enterprise security.
            Ask anything about your Kubernetes cluster in natural language.
          </p>
          <div className="flex items-center justify-center gap-3">
            <Link href="/register"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl font-medium text-sm text-white gradient-accent glow-accent transition-all hover:scale-[1.02]">
              Start for free
              <ArrowRight className="w-4 h-4" />
            </Link>
            <Link href="/login"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl font-medium text-sm border transition-colors"
              style={{
                borderColor: "var(--color-border-default)",
                color: "var(--color-text-secondary)",
              }}>
              Sign in
              <ChevronRight className="w-4 h-4" />
            </Link>
          </div>
        </div>

        {/* Terminal preview */}
        <div className="max-w-2xl mx-auto mt-16">
          <div className="rounded-2xl overflow-hidden"
            style={{
              border: "1px solid var(--color-border-subtle)",
              background: "var(--color-bg-surface)",
              boxShadow: "var(--shadow-elevated)",
            }}>
            <div className="flex items-center gap-1.5 px-4 py-3"
              style={{ borderBottom: "1px solid var(--color-border-subtle)", background: "var(--color-bg-elevated)" }}>
              <div className="w-3 h-3 rounded-full bg-red-500/70" />
              <div className="w-3 h-3 rounded-full bg-yellow-500/70" />
              <div className="w-3 h-3 rounded-full bg-green-500/70" />
              <span className="ml-2 text-xs" style={{ color: "var(--color-text-tertiary)" }}>
                VectraIQ AI Chat
              </span>
            </div>
            <div className="p-5 text-left space-y-4">
              <div className="flex gap-3">
                <div className="w-7 h-7 rounded-full bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center shrink-0">
                  <span className="text-xs text-indigo-400 font-semibold">U</span>
                </div>
                <div className="flex-1">
                  <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
                    Why are my pods in CrashLoopBackOff in the prod namespace?
                  </p>
                </div>
              </div>
              <div className="flex gap-3">
                <div className="w-7 h-7 rounded-full gradient-accent flex items-center justify-center shrink-0">
                  <Zap className="w-3.5 h-3.5 text-white" />
                </div>
                <div className="flex-1">
                  <p className="text-sm leading-relaxed" style={{ color: "var(--color-text-primary)" }}>
                    Based on the retrieved runbooks, <code className="text-indigo-400 text-xs bg-indigo-400/10 px-1 py-0.5 rounded">CrashLoopBackOff</code> typically indicates one of three root causes...
                  </p>
                  <div className="mt-2 flex items-center gap-2">
                    <span className="text-xs px-2 py-0.5 rounded-full"
                      style={{ background: "var(--color-success-subtle)", color: "var(--color-success)" }}>
                      ✓ 3 sources
                    </span>
                    <span className="text-xs px-2 py-0.5 rounded-full"
                      style={{ background: "var(--color-info-subtle)", color: "var(--color-info)" }}>
                      ⚡ Cached
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="py-20 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold mb-3" style={{ color: "var(--color-text-primary)" }}>
              Enterprise AI capabilities
            </h2>
            <p className="text-base" style={{ color: "var(--color-text-secondary)" }}>
              Every technique from cutting-edge AI research, production-hardened.
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {FEATURES.map((f) => (
              <div key={f.title}
                className="p-5 rounded-xl border transition-colors hover:border-white/10"
                style={{
                  background: "var(--color-bg-surface)",
                  borderColor: "var(--color-border-subtle)",
                }}>
                <div className="w-9 h-9 rounded-xl flex items-center justify-center mb-4"
                  style={{ background: `${f.color}20`, border: `1px solid ${f.color}30` }}>
                  <f.icon className="w-4.5 h-4.5" style={{ color: f.color }} />
                </div>
                <h3 className="text-sm font-semibold mb-2" style={{ color: "var(--color-text-primary)" }}>
                  {f.title}
                </h3>
                <p className="text-sm leading-relaxed" style={{ color: "var(--color-text-tertiary)" }}>
                  {f.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Tech Stack */}
      <section className="py-20 px-6" style={{ background: "var(--color-bg-subtle)" }}>
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-10">
            <h2 className="text-2xl font-bold mb-2" style={{ color: "var(--color-text-primary)" }}>
              Built on proven infrastructure
            </h2>
            <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
              Production-tested at scale.
            </p>
          </div>
          <div className="flex flex-wrap gap-2 justify-center">
            {TECH.map((t) => (
              <div key={t.name}
                className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs"
                style={{
                  background: "var(--color-bg-surface)",
                  border: "1px solid var(--color-border-subtle)",
                }}>
                <span style={{ color: "var(--color-text-secondary)" }}>{t.name}</span>
                <span className="px-1.5 py-0.5 rounded text-xs font-medium"
                  style={{ background: "var(--color-bg-elevated)", color: "var(--color-text-tertiary)" }}>
                  {t.category}
                </span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="py-20 px-6">
        <div className="max-w-2xl mx-auto">
          <h2 className="text-2xl font-bold text-center mb-10" style={{ color: "var(--color-text-primary)" }}>
            Frequently asked questions
          </h2>
          <div className="space-y-2">
            {FAQS.map((faq) => (
              <details key={faq.q}
                className="group rounded-xl border overflow-hidden"
                style={{ background: "var(--color-bg-surface)", borderColor: "var(--color-border-subtle)" }}>
                <summary className="flex items-center justify-between px-5 py-4 cursor-pointer text-sm font-medium select-none"
                  style={{ color: "var(--color-text-primary)" }}>
                  {faq.q}
                  <ChevronRight className="w-4 h-4 shrink-0 transition-transform group-open:rotate-90"
                    style={{ color: "var(--color-text-tertiary)" }} />
                </summary>
                <div className="px-5 pb-4 text-sm leading-relaxed"
                  style={{ color: "var(--color-text-secondary)" }}>
                  {faq.a}
                </div>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 px-6">
        <div className="max-w-lg mx-auto text-center">
          <div className="p-8 rounded-2xl"
            style={{
              background: "var(--color-bg-surface)",
              border: "1px solid rgba(99,102,241,0.2)",
              boxShadow: "0 0 40px rgba(99,102,241,0.1)",
            }}>
            <h2 className="text-2xl font-bold mb-3" style={{ color: "var(--color-text-primary)" }}>
              Ready to deploy?
            </h2>
            <p className="text-sm mb-6" style={{ color: "var(--color-text-secondary)" }}>
              Set up your own VectraIQ instance with Docker Compose in minutes.
            </p>
            <Link href="/register"
              className="inline-flex items-center gap-2 px-6 py-2.5 rounded-xl font-medium text-sm text-white gradient-accent glow-accent">
              Create account
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-10 px-6 border-t"
        style={{ borderColor: "var(--color-border-subtle)" }}>
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-indigo-400" />
            <span className="text-sm font-semibold" style={{ color: "var(--color-text-primary)" }}>
              VectraIQ
            </span>
          </div>
          <p className="text-xs" style={{ color: "var(--color-text-tertiary)" }}>
            Production-grade AI Knowledge Platform
          </p>
        </div>
      </footer>
    </div>
  );
}
