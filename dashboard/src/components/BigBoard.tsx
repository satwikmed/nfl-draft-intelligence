"use client"
import React, { useState } from "react"
import { Prospect } from "@/lib/types"
import { motion, AnimatePresence } from "framer-motion"
import { Search, ChevronRight, MapPin } from "lucide-react"
import { SCHOOL_TO_STATE, ALL_STATES } from "@/lib/stateMapping"

interface Props {
  prospects: Prospect[];
  onSelect: (p: Prospect) => void;
}

export default function BigBoard({ prospects, onSelect }: Props) {
  const [search, setSearch] = useState("")
  const [posFilter, setPosFilter] = useState("All")
  const [stateFilter, setStateFilter] = useState("All States")
  const [limit, setLimit] = useState(30)

  const filtered = prospects
    .filter(p => 
      p.name.toLowerCase().includes(search.toLowerCase()) || 
      p.school.toLowerCase().includes(search.toLowerCase())
    )
    .filter(p => posFilter === "All" || p.position_group === posFilter)
    .filter(p => stateFilter === "All States" || SCHOOL_TO_STATE[p.school] === stateFilter)
    .slice(0, limit)

  return (
    <div className="w-full space-y-6">
      <div className="flex flex-col gap-4">
        <div className="flex flex-col md:flex-row gap-4 items-center">
          <div className="relative w-full md:max-w-md flex-grow">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-white/50" />
            <input
              type="text"
              placeholder="Search by name or school (e.g., 'Texas')..."
              className="w-full bg-white/5 border border-white/10 rounded-full py-2.5 pl-10 pr-4 text-white hover:bg-white/10 transition-all focus:outline-none focus:ring-2 focus:ring-cyan-500/50 backdrop-blur-md"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          
          <div className="relative w-full md:w-auto">
            <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-white/50" />
            <select
              value={stateFilter}
              onChange={(e) => setStateFilter(e.target.value)}
              className="w-full md:w-auto bg-white/5 border border-white/10 rounded-full py-2.5 pl-10 pr-8 text-white hover:bg-white/10 transition-all focus:outline-none focus:ring-2 focus:ring-cyan-500/50 backdrop-blur-md appearance-none cursor-pointer text-sm"
            >
              <option value="All States" className="bg-neutral-900">All States</option>
              {ALL_STATES.map(s => (
                <option key={s} value={s} className="bg-neutral-900">{s}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="flex gap-2 overflow-x-auto pb-2 no-scrollbar w-full">
          {["All", "QB", "RB", "WR", "TE", "OL", "DL", "LB", "DB"].map(pos => (
            <button
              key={pos}
              onClick={() => setPosFilter(pos)}
              className={`px-4 py-1.5 rounded-full text-xs font-medium transition-all ${
                posFilter === pos 
                  ? "bg-cyan-500 text-white shadow-lg shadow-cyan-500/30" 
                  : "bg-white/5 text-white/70 hover:bg-white/10 border border-white/5"
              }`}
            >
              {pos}
            </button>
          ))}
        </div>
      </div>

      <div className="overflow-hidden rounded-2xl border border-white/10 bg-black/20 backdrop-blur-xl">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-bottom border-white/10 bg-white/5">
              <th className="px-6 py-4 text-xs font-bold text-white/40 uppercase tracking-widest" title="Overall algorithm rank">Rank</th>
              <th className="px-6 py-4 text-xs font-bold text-white/40 uppercase tracking-widest">Player</th>
              <th className="px-6 py-4 text-xs font-bold text-white/40 uppercase tracking-widest" title="Position Group Profile">Pos</th>
              <th className="px-6 py-4 text-xs font-bold text-white/40 uppercase tracking-widest" title="Pro Readiness Score: The probability (0-100) this prospect develops into an NFL starter within 3 years.">Score</th>
              <th className="px-6 py-4 text-xs font-bold text-white/40 uppercase tracking-widest text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            <AnimatePresence mode="popLayout">
              {filtered.map((p, i) => (
                <motion.tr
                  key={p.player_id}
                  layout
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  transition={{ delay: i * 0.03 }}
                  className="group hover:bg-white/5 transition-colors"
                >
                  <td className="px-6 py-4">
                    <span className="text-white/30 font-mono text-sm">#{(i + 1).toString().padStart(3, '0')}</span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex flex-col">
                      <span className="text-white font-semibold group-hover:text-cyan-400 transition-colors">
                        {p.name}
                      </span>
                      <span className="text-white/40 text-xs">{p.school}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${getPosStyle(p.position_group)}`}>
                      {p.position_group}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <span className={`font-mono font-bold ${getScoreColor(p.pro_readiness_score)}`}>
                      {p.pro_readiness_score.toFixed(1)}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <button 
                      onClick={() => onSelect(p)}
                      className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full bg-white/5 text-xs text-white/60 hover:bg-white/10 hover:text-white transition-all"
                    >
                      View Intelligence <ChevronRight size={12} />
                    </button>
                  </td>
                </motion.tr>
              ))}
            </AnimatePresence>
          </tbody>
        </table>
      </div>
      
      {filtered.length < prospects.length && search === "" && posFilter === "All" && (
        <div className="flex justify-center pt-4">
          <button 
            onClick={() => setLimit(prev => prev + 50)}
            className="px-8 py-3 rounded-full bg-white/5 border border-white/10 text-white/50 text-sm hover:bg-white/10 hover:text-white transition-all backdrop-blur-md"
          >
            Load More Prospects
          </button>
        </div>
      )}
    </div>
  )
}

function getPosStyle(pos: string) {
  const styles: Record<string, string> = {
    QB: "border-cyan-500/30 text-cyan-400 bg-cyan-400/5",
    RB: "border-orange-500/30 text-orange-400 bg-orange-400/5",
    WR: "border-purple-500/30 text-purple-400 bg-purple-400/5",
    TE: "border-emerald-500/30 text-emerald-400 bg-emerald-400/5",
    OL: "border-blue-500/30 text-blue-400 bg-blue-400/5",
    DL: "border-red-500/30 text-red-400 bg-red-400/5",
    LB: "border-amber-500/30 text-amber-400 bg-amber-400/5",
    DB: "border-pink-500/30 text-pink-400 bg-pink-400/5",
  }
  return styles[pos] || "border-white/10 text-white/40"
}

function getScoreColor(score: number) {
  if (score >= 80) return "text-emerald-400";
  if (score >= 60) return "text-cyan-400";
  if (score >= 40) return "text-amber-400";
  return "text-red-400";
}
