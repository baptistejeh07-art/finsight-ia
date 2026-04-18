import Link from "next/link";
import { CitationBlock } from "./citation-block";

export function Sidebar() {
  return (
    <aside className="hidden md:flex fixed left-0 top-0 h-screen w-56 flex-col bg-white text-ink-900 border-r border-ink-200 z-40">
      {/* Logo — style Streamlit (sb-logo) : texte gauche, fine ligne en dessous */}
      <Link
        href="/"
        className="block px-5 pt-6 pb-4 border-b border-ink-100"
        style={{
          fontSize: "13px",
          fontWeight: 700,
          letterSpacing: "3px",
          textTransform: "uppercase",
          color: "#111",
        }}
      >
        FinSight
      </Link>

      {/* Sections — style Streamlit (sb-label) */}
      <nav className="flex-1 px-4 py-3 overflow-y-auto">
        {/* Livrables */}
        <div className="border-b border-ink-100 pb-3.5 mb-3.5">
          <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500 mb-2.5">
            Livrables
          </div>
          <div className="text-xs text-ink-400">Disponibles après analyse</div>
        </div>

        {/* Historique d'analyses */}
        <div className="border-b border-ink-100 pb-3.5 mb-3.5">
          <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500 mb-2.5">
            Historique d&apos;analyses
          </div>
          <div className="text-xs text-ink-400">Disponibles après analyse</div>
        </div>

        {/* Citation */}
        <div className="pt-2 pb-4">
          <div className="text-[10px] font-semibold uppercase tracking-[1.5px] text-ink-500 mb-3">
            Citation
          </div>
          <CitationBlock />
        </div>
      </nav>
    </aside>
  );
}
