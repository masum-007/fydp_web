import Link from "next/link";
import Footer from "@/components/Footer";
import {
  ArrowDownRight,
  ArrowRight,
  BrainCircuit,
  CheckCircle2,
  Cpu,
  Database,
  FileCheck2,
  Fingerprint,
  Layers3,
  Microscope,
  ScanFace,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import type { ReactNode } from "react";

const capabilities: { title: string; description: string; icon: ReactNode }[] = [
  {
    title: "Four-model deepfake screening",
    description:
      "Four complementary CNNs assess an image, and a stacking classifier combines their outputs for the final Real/Fake result.",
    icon: <BrainCircuit size={27} aria-hidden="true" />,
  },
  {
    title: "Understand the result",
    description:
      "Grad-CAM, LIME, and SHAP help readers inspect which image regions influenced the models' assessments.",
    icon: <ScanFace size={27} aria-hidden="true" />,
  },
  {
    title: "Investigation-ready PDF reports",
    description:
      "Professional reports bring together the classification, visual explanations, evidence details, and practical reading notes.",
    icon: <FileCheck2 size={27} aria-hidden="true" />,
  },
  {
    title: "Evidence-focused workflow",
    description:
      "Organize saved analyses in investigation cases, review previous results, and download individual or grouped reports.",
    icon: <Database size={27} aria-hidden="true" />,
  },
  {
    title: "Facial-region interpretation",
    description:
      "Approximate face landmarks help describe where highlighted regions appear—for example, near the cheek or hairline.",
    icon: <Fingerprint size={27} aria-hidden="true" />,
  },
  {
    title: "Designed for careful review",
    description:
      "Clear explanations distinguish model signals from proven editing, helping investigators make informed follow-up decisions.",
    icon: <ShieldCheck size={27} aria-hidden="true" />,
  },
];

const cnnModels = ["MobileNetV2", "ResNet50V2", "Xception", "EfficientNetB0"];
const explanationMethods = [
  { name: "Grad-CAM", note: "Highlights regions the individual image models responded to." },
  { name: "LIME", note: "Shows image segments that supported or opposed a result locally." },
  { name: "SHAP", note: "Compares image-region contributions with a softened reference." },
];
const platformTools = [
  "TensorFlow / Keras",
  "scikit-learn",
  "MTCNN",
  "MediaPipe Face Landmarker",
  "FastAPI",
  "Next.js",
];

function CapabilityCard({ title, description, icon }: { title: string; description: string; icon: ReactNode }) {
  return (
    <article className="group rounded-3xl border border-white/10 bg-white/[0.045] p-7 text-left transition duration-300 hover:-translate-y-1 hover:border-cyan-400/35 hover:bg-white/[0.07] sm:p-8">
      <div className="mb-6 flex h-12 w-12 items-center justify-center rounded-2xl border border-cyan-400/20 bg-cyan-400/10 text-cyan-300">
        {icon}
      </div>
      <h3 className="text-xl font-bold text-white">{title}</h3>
      <p className="mt-3 text-sm leading-7 text-slate-400">{description}</p>
    </article>
  );
}

export default function Home() {
  return (
    <main className="relative isolate min-h-screen overflow-hidden bg-[#050816] text-white">
      <div className="pointer-events-none absolute left-1/2 top-20 -z-10 h-[480px] w-[min(650px,95vw)] -translate-x-1/2 rounded-full bg-cyan-500/10 blur-[110px]" />
      <div className="pointer-events-none absolute right-0 top-[900px] -z-10 h-[360px] w-[360px] rounded-full bg-blue-500/10 blur-[120px]" />

      {/* Public landing page: no investigator login needed. */}
      <section aria-labelledby="hero-heading" className="px-6 pb-12 pt-44 sm:pt-52">
        <div className="mx-auto max-w-5xl text-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-cyan-400/20 bg-cyan-400/10 px-4 py-2 text-xs font-semibold tracking-wide text-cyan-200 sm:px-5 sm:text-sm">
            <Sparkles size={17} aria-hidden="true" /> AI Forensic Intelligence Platform
          </div>
          <h1 id="hero-heading" className="mx-auto mt-9 max-w-5xl text-5xl font-extrabold leading-[1.1] tracking-tight sm:text-6xl lg:text-7xl">
            Understand the image.
            <span className="mt-2 block bg-gradient-to-r from-cyan-300 via-cyan-400 to-blue-500 bg-clip-text text-transparent">
              Investigate the evidence.
            </span>
          </h1>
          <p className="mx-auto mt-8 max-w-3xl text-base leading-8 text-slate-300 sm:text-lg">
            NeuralEdge AI combines four deep-learning image models with explainable AI to screen for
            potential deepfakes, show image-region findings, and support a more informed investigation.
          </p>
          <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
            <Link
              href="/detect"
              className="inline-flex min-h-14 items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 px-7 py-3.5 text-base font-bold text-white shadow-lg shadow-cyan-950/30 transition hover:-translate-y-0.5 hover:from-cyan-400 hover:to-blue-500 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-cyan-300"
            >
              Try Detection <ArrowRight size={18} aria-hidden="true" />
            </Link>
            <a
              href="#technology"
              className="inline-flex min-h-14 items-center justify-center gap-2 rounded-xl border border-white/20 bg-white/5 px-7 py-3.5 text-base font-semibold text-slate-100 transition hover:border-cyan-400/45 hover:bg-white/10 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-cyan-300"
            >
              Explore Technology <ArrowDownRight size={18} aria-hidden="true" />
            </a>
          </div>
          <div className="mx-auto mt-8 flex max-w-2xl flex-wrap justify-center gap-x-6 gap-y-2 text-xs text-slate-400 sm:text-sm">
            <span className="inline-flex items-center gap-1.5"><CheckCircle2 size={16} className="text-cyan-400" aria-hidden="true" /> Free guest screening</span>
            <span className="inline-flex items-center gap-1.5"><CheckCircle2 size={16} className="text-cyan-400" aria-hidden="true" /> Three XAI methods</span>
            <span className="inline-flex items-center gap-1.5"><CheckCircle2 size={16} className="text-cyan-400" aria-hidden="true" /> Investigator case workflow</span>
          </div>
          <p className="mt-4 text-xs leading-6 text-slate-500">
            Guest mode offers quick screening; full explanations, saved cases, and forensic reports require an investigator account.
          </p>
        </div>
      </section>

      <section aria-labelledby="capabilities-heading" className="px-6 pb-12 pt-20 sm:pt-24">
        <div className="mx-auto max-w-7xl">
          <div className="text-center">
            <p className="text-sm font-bold uppercase tracking-[0.18em] text-cyan-300">What NeuralEdge AI offers</p>
            <h2 id="capabilities-heading" className="mt-4 text-3xl font-bold tracking-tight sm:text-4xl">Built for evidence-focused review</h2>
            <p className="mx-auto mt-4 max-w-2xl text-base leading-7 text-slate-400">From initial image screening to saved explanations and professional investigative reports.</p>
          </div>
          <div className="mt-12 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
            {capabilities.map((capability) => (
              <CapabilityCard key={capability.title} {...capability} />
            ))}
          </div>
        </div>
      </section>

      {/* Explore Technology intentionally targets this section, not a protected route. */}
      <section id="technology" aria-labelledby="technology-heading" className="scroll-mt-32 px-6 py-20 sm:py-24">
        <div className="mx-auto max-w-6xl">
          <div className="text-center">
            <p className="text-sm font-bold uppercase tracking-[0.18em] text-cyan-300">Inside the system</p>
            <h2 id="technology-heading" className="mt-4 text-3xl font-bold tracking-tight sm:text-4xl">Technology behind NeuralEdge AI</h2>
            <p className="mx-auto mt-4 max-w-3xl text-base leading-7 text-slate-400">
              Our final v3 system combines four CNNs with a stacking classifier. Explainability tools help readers
              understand which parts of an image influenced the screening result.
            </p>
          </div>

          <div className="mt-12 grid gap-5 lg:grid-cols-[1.2fr_0.8fr]">
            <div className="rounded-3xl border border-cyan-400/20 bg-gradient-to-br from-[#122538] to-[#0b1326] p-7 sm:p-9">
              <div className="flex items-center gap-3"><Layers3 size={24} className="text-cyan-300" aria-hidden="true" /><h3 className="text-xl font-bold">Four CNN backbones</h3></div>
              <p className="mt-3 text-sm leading-7 text-slate-300">Each model contributes its own Fake-category score. Original and horizontally flipped image views are averaged before combining model outputs.</p>
              <div className="mt-6 grid gap-3 sm:grid-cols-2">
                {cnnModels.map((name, index) => (
                  <div key={name} className="flex items-center gap-3 rounded-xl border border-white/10 bg-black/20 px-4 py-3">
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-cyan-400/10 text-xs font-bold text-cyan-300">0{index + 1}</span>
                    <span className="text-sm font-semibold text-white">{name}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="rounded-3xl border border-white/10 bg-white/[0.045] p-7 sm:p-9">
              <div className="flex items-center gap-3"><Cpu size={24} className="text-cyan-300" aria-hidden="true" /><h3 className="text-xl font-bold">Stacking ensemble</h3></div>
              <p className="mt-4 text-sm leading-7 text-slate-300">A trained logistic-regression meta-learner combines the four model scores into the final Real/Fake screening result.</p>
              <div className="mt-7 rounded-2xl border border-cyan-400/20 bg-cyan-400/[0.07] p-5">
                <p className="text-xs font-bold uppercase tracking-wider text-cyan-200">Decision process</p>
                <p className="mt-3 text-base font-semibold text-white">4 CNN scores → Stacking → Real / Fake</p>
                <p className="mt-2 text-xs leading-5 text-slate-400">The deployed decision threshold is 0.50. The model score is not proof of manipulation.</p>
              </div>
            </div>
          </div>

          <div className="mt-6 rounded-3xl border border-white/10 bg-white/[0.045] p-7 sm:p-9">
            <div className="flex items-center gap-3"><Microscope size={24} className="text-cyan-300" aria-hidden="true" /><h3 className="text-xl font-bold">Explainability methods</h3></div>
            <div className="mt-6 grid gap-5 md:grid-cols-3">
              {explanationMethods.map((method) => (
                <div key={method.name} className="rounded-2xl border border-white/10 bg-[#0a1325] p-5">
                  <p className="text-lg font-bold text-cyan-200">{method.name}</p>
                  <p className="mt-3 text-sm leading-6 text-slate-400">{method.note}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-9 text-center">
            <h3 className="text-sm font-semibold uppercase tracking-[0.16em] text-slate-300">Built with</h3>
            <div className="mt-5 flex flex-wrap justify-center gap-2.5">
              {platformTools.map((tool) => (
                <span key={tool} className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-300">{tool}</span>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section aria-labelledby="research-heading" className="px-6 pb-5 pt-5">
        <div className="mx-auto max-w-5xl rounded-3xl border border-cyan-400/20 bg-gradient-to-r from-[#102333] via-[#0f1b31] to-[#12192e] px-6 py-10 text-center sm:px-12 sm:py-12">
          <div className="mx-auto mb-5 flex h-11 w-11 items-center justify-center rounded-xl border border-cyan-400/25 bg-cyan-400/10 text-cyan-300">
            <Sparkles size={22} aria-hidden="true" />
          </div>
          <p id="research-heading" className="text-sm font-bold uppercase tracking-[0.16em] text-cyan-300">Researched &amp; Developed by</p>
          <p className="mt-4 text-2xl font-extrabold tracking-tight text-white sm:text-3xl">Masum Al Mahamud &amp; Shinthiya Islam Ayshi</p>
          <p className="mx-auto mt-3 max-w-2xl text-sm leading-6 text-slate-400">NeuralEdge AI · Final Year Design Project</p>
        </div>
      </section>

      <div className="mx-auto max-w-5xl px-6 text-center">
        <p className="mt-8 text-xs leading-6 text-slate-500">NeuralEdge AI is an automated screening and investigation-support tool. Its predictions and explanation maps do not independently authenticate an image or prove that a specific region was edited.</p>
      </div>
      <Footer />
    </main>
  );
}
