// "Przykładowe sprawy" for the jury (brief: the site must allow uploading or choosing one of the
// example applications; FUNKCJE F19, F20). Choosing a case or reading a scan is not wired to the
// engine yet, so both say so.
import { motion } from 'motion/react'
import { FileUp, FolderOpen } from 'lucide-react'
import { SPRING_PRESS } from '@/lib/ease'
import { CASES } from '@/lib/mockData'
import { MockModal, SimBadge } from './MockModal'

export function CasesDialog({
  open,
  onClose,
  onMock,
}: {
  open: boolean
  onClose: () => void
  onMock: (message: string) => void
}) {
  return (
    <MockModal open={open} label="Przykładowe sprawy" onClose={onClose} className="max-w-3xl">
      <div className="pr-10">
        <SimBadge>wczytanie sprawy w przygotowaniu</SimBadge>
        <h2 className="mt-3 text-2xl leading-tight font-bold tracking-tight text-navy-900">
          Sprawdź na przykładowej sprawie
        </h2>
        <p className="mt-1 text-navy-500">
          Wybierz sprawę z zestawu ZUS albo wgraj wniosek. Kalkulator porówna wynik z decyzją ZUS.
        </p>
      </div>

      <button
        type="button"
        onClick={() => onMock('Odczyt wniosku ze skanu (AI) dodamy w kolejnym kroku.')}
        className="group mt-6 flex w-full items-center gap-4 rounded-3xl border-2 border-dashed border-navy-200 px-5 py-4 text-left transition-[border-color,background-color] duration-200 hover:border-zus-400 hover:bg-zus-50/50"
      >
        <span className="grid size-11 place-items-center rounded-2xl bg-zus-50 text-zus-700 transition-transform duration-200 group-hover:-translate-y-0.5">
          <FileUp className="size-5" />
        </span>
        <span className="flex-1">
          <span className="block font-bold text-navy-900">Wgraj wniosek (PDF albo zdjęcie)</span>
          <span className="block text-sm text-navy-500">ZAM, Z-3, Z-3a, ZAS-53 — odczyt pól z obrazu strony</span>
        </span>
        <span className="rounded-full bg-zus-600 px-2 py-0.5 text-[10px] font-black tracking-wide text-white">AI</span>
      </button>

      <div className="mt-5 grid grid-cols-2 gap-2 sm:grid-cols-3">
        {CASES.map((c) => (
          <motion.button
            key={c.id}
            type="button"
            onClick={() => onMock(`Wczytanie sprawy ${c.id} do kalkulatora — w przygotowaniu.`)}
            whileTap={{ scale: 0.97, transition: SPRING_PRESS }}
            className="flex flex-col items-start rounded-2xl border border-line px-4 py-3 text-left transition-[border-color,background-color] duration-200 hover:border-navy-200 hover:bg-navy-50/40 focus-visible:ring-2 focus-visible:ring-zus-400 focus-visible:outline-none"
          >
            <span className="flex items-center gap-1.5 text-xs font-black text-navy-400">
              <FolderOpen className="size-3.5" /> {c.id}
            </span>
            <span className="mt-1 leading-snug font-bold text-navy-900">{c.title}</span>
            <span className="mt-0.5 text-sm leading-snug text-navy-500">{c.topic}</span>
          </motion.button>
        ))}
      </div>
    </MockModal>
  )
}
