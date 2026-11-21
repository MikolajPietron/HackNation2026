import type { ReactNode } from 'react'
import type { Timeline } from '@/types'

/** What the calculator assumes, what is AI and what is not, and where the rules come from. */
export function AboutPanel({ timeline }: { timeline: Timeline | null }) {
  return (
    <div className="mx-auto max-w-2xl space-y-5 p-5 lg:p-8">
      <h1 className="text-2xl font-black text-navy-900 lg:text-3xl">Założenia i źródła</h1>

      <Card title="Co robi AI, a co kalkulator">
        <p>
          Rozmowę prowadzi asystent AI. Daty, długości urlopów i terminy wniosków liczy kalkulator
          reguł — bez AI. Każda liczba ma źródło z cytatem.
        </p>
      </Card>

      <Card title="Założenia kalkulatora">
        {timeline ? (
          <ul className="list-disc space-y-1.5 pl-5 marker:text-zus-400">
            {timeline.assumptions.map((assumption) => (
              <li key={assumption}>{assumption}</li>
            ))}
          </ul>
        ) : (
          <p>Pojawią się, gdy podasz datę porodu.</p>
        )}
      </Card>

      <Card title="Źródła">
        <ul className="list-disc space-y-1.5 pl-5 marker:text-zus-400">
          <li>Przewodnik ZUS z opisu wyzwania HackNation 2026 — najważniejsze źródło.</li>
          <li>Kodeks pracy — wymiary urlopów i terminy wniosków.</li>
          <li>Ustawa zasiłkowa — wysokość zasiłku macierzyńskiego.</li>
        </ul>
        {timeline && (
          <p className="mt-3 text-xs text-navy-500">Wersja parametrów: {timeline.params_version}</p>
        )}
      </Card>

      <p className="px-1 text-xs text-navy-500">
        Wersja demonstracyjna. Nie zastępuje decyzji ZUS ani pracodawcy.
      </p>
    </div>
  )
}

function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-3xl bg-white p-6 text-[15px] leading-relaxed text-navy-700 shadow-card">
      <h2 className="mb-2 text-xs font-black tracking-widest text-zus-700 uppercase">{title}</h2>
      {children}
    </section>
  )
}
