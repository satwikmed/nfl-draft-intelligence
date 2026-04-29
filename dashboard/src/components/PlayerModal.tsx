"use client"
import React, { useMemo } from "react"
import { Prospect, Features, CompsData, NFLPerf } from "@/lib/types"
import { motion, AnimatePresence } from "framer-motion"
import { X, Target, BarChart3, TrendingUp, Users, Zap } from "lucide-react"
import {
  Chart as ChartJS,
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
  BarElement,
  CategoryScale,
  LinearScale,
} from 'chart.js'
import { Radar, Bar } from 'react-chartjs-2'

ChartJS.register(
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
  BarElement,
  CategoryScale,
  LinearScale
)

interface Props {
  player: Prospect | null;
  features: Features;
  comps: CompsData;
  nfl: NFLPerf[];
  onClose: () => void;
}

export default function PlayerModal({ player, features, comps, nfl, onClose }: Props) {
  if (!player) return null;

  const playerFeats = features[player.player_id] || {}
  const playerComps = comps[player.player_id]?.comps || []

  const scoutingReport = useMemo(() => {
    const score = player.pro_readiness_score
    let report = ""
    if (score >= 80) report = `${player.name} is an elite ${player.position_group} prospect with generational traits.`
    else if (score >= 60) report = `${player.name} projects as a reliable NFL starter with a high technical floor.`
    else report = `${player.name} possesses specific athletic advantages but requires significant development.`

    if (playerFeats.speed_score > 100) report += " His explosive lateral speed is a key differentiator."
    return report
  }, [player, playerFeats])

  const radarData = {
    labels: ['Athleticism', 'Production', 'Frame', 'Readiness', 'Agility', 'Strength'],
    datasets: [{
      label: player.name,
      data: [
        playerFeats.athletic_composite * 100 || 50,
        playerFeats.production_score * 100 || 50,
        (player.weight_lbs || 200) / 3,
        player.pro_readiness_score,
        playerFeats.agility_score || 50,
        playerFeats.strength_score || 50
      ],
      backgroundColor: 'rgba(255, 255, 255, 0.2)',
      borderColor: 'rgba(255, 255, 255, 0.8)',
      pointBackgroundColor: 'rgba(6, 182, 212, 1)',
      borderWidth: 2,
    }]
  }

  const xaiFeatureData = {
    labels: ['Production Factor', 'Speed Matrix', 'Dimensional Composite'],
    datasets: [{
      data: [
        (playerFeats.production_score * 100) || 60,
        (playerFeats.speed_score) || 50,
        (playerFeats.athletic_composite * 100) || 55
      ],
      backgroundColor: [
        'rgba(6, 182, 212, 0.8)',
        'rgba(249, 115, 22, 0.8)',
        'rgba(168, 85, 247, 0.8)'
      ],
      borderRadius: 6,
    }]
  }

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 md:p-8">
        <motion.div 
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
          className="absolute inset-0 bg-white/10 backdrop-blur-md"
        />
        
        <motion.div
          initial={{ opacity: 0, scale: 0.9, y: 40 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.9, y: 40 }}
          className="relative w-full max-w-5xl max-h-[90vh] overflow-y-auto rounded-[3rem] bg-white/10 border border-white/20 shadow-[0_8px_32px_0_rgba(255,255,255,0.1)] p-8 md:p-14 no-scrollbar backdrop-blur-2xl"
          style={{ filter: "url(#glass-effect)" }}
        >
          {/* Subtle top highlights */}
          <div className="absolute top-0 left-10 right-10 h-px bg-gradient-to-r from-transparent via-white/30 to-transparent" />

          {/* Close Button */}
          <button 
            onClick={onClose}
            className="absolute top-10 right-10 p-3 rounded-full bg-white/10 hover:bg-white/20 text-white/70 hover:text-white transition-all border border-white/10 z-10"
          >
            <X size={20} />
          </button>

          <div className="space-y-14">
            {/* Header section */}
            <div className="flex flex-col md:flex-row gap-10 items-start md:items-center">
              <div className="size-28 rounded-[2.5rem] bg-gradient-to-br from-white via-white/80 to-cyan-400 flex items-center justify-center text-5xl font-black text-black shadow-xl">
                {player.name.split(' ').map(n => n[0]).join('')}
              </div>
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <span className="px-4 py-1.5 rounded-full bg-white/20 border border-white/30 text-white text-[10px] font-black uppercase tracking-[0.2em] shadow-sm">
                    {player.position_group} Core DNA
                  </span>
                </div>
                <h2 className="text-6xl font-black text-white tracking-tighter leading-none">
                  {player.name}
                </h2>
                <div className="flex items-center gap-2 text-white/60 font-light text-xl">
                   <span>{player.school}</span>
                   <span className="size-1 rounded-full bg-white/30" />
                   <span className="text-cyan-300 font-medium">Class of {player.draft_year || '2026'}</span>
                </div>
              </div>
            </div>

            {/* Premium Stats Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
              <DeepStat label="Pro Readiness" value={player.pro_readiness_score.toFixed(1)} icon={<TrendingUp size={16} />} color="text-white" highlight="bg-cyan-500/20" def="Probability of starter-caliber performance within 3 years." />
              <DeepStat label="Draft Projection" value={player.draft_pick || "Early 1st"} icon={<BarChart3 size={16} />} color="text-white" highlight="bg-white/10" def="Estimated selection range based on 2026 big boards." />
              <DeepStat label="Career Runway" value={`${player.predicted_career_length?.toFixed(1) || '4.2'}Y`} icon={<Zap size={16} />} color="text-white" highlight="bg-orange-500/20" def="Projected active longevity factoring positional hazard rates." />
              <DeepStat label="Similarity" value={`${playerComps.length} Matches`} icon={<Users size={16} />} color="text-white" highlight="bg-white/10" def="Total historic NFL clones mapped via Cosine Similarity." />
            </div>

            {/* Main Content Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-12">
              {/* Left Column: Scouting */}
              <div className="space-y-10">
                <div className="p-10 rounded-[2.5rem] bg-white/5 border border-white/10 backdrop-blur-xl relative group">
                  <div className="absolute top-0 left-8 size-8 -translate-y-1/2 rounded-xl bg-white flex items-center justify-center shadow-lg">
                    <Target className="size-4 text-black" />
                  </div>
                  <h3 className="text-white font-black text-2xl mb-2">Explainable AI (XAI) Base Weights</h3>
                  <p className="text-white/40 mb-6 text-sm">{scoutingReport}</p>
                  <div className="h-[140px] w-full">
                    <Bar 
                      data={xaiFeatureData} 
                      options={{
                        indexAxis: 'y',
                        maintainAspectRatio: false,
                        scales: {
                          x: { display: false, max: 120 },
                          y: { 
                            grid: { display: false }, 
                            ticks: { color: 'rgba(255,255,255,0.7)', font: { family: 'Inter', weight: 'bold' } },
                            border: { display: false }
                          }
                        },
                        plugins: { legend: { display: false } }
                      }} 
                    />
                  </div>
                </div>

                <div className="p-10 rounded-[2.5rem] bg-white/5 border border-white/10 backdrop-blur-xl">
                  <h3 className="text-white font-black text-2xl mb-8">Position-Locked Historical Clones</h3>
                  <div className="space-y-6">
                    {playerComps.map((c, i) => (
                      <div key={c.comp_id} className="flex items-center justify-between group">
                        <div className="flex items-center gap-5">
                          <span className="text-white/20 font-black text-sm italic tracking-widest">#{i+1}</span>
                          <span className="text-white font-bold text-xl drop-shadow-sm">{c.name}</span>
                        </div>
                        <div className="text-right">
                           <div className="text-[10px] text-white/30 font-bold uppercase tracking-widest mb-1">Match Accuracy</div>
                           <span className="font-black text-2xl text-white drop-shadow-[0_0_8px_rgba(255,255,255,0.3)]">
                             {Math.min(c.sim, 100).toFixed(1)}%
                           </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Right Column: Visualization */}
              <div className="p-10 rounded-[2.5rem] bg-white/10 border border-white/20 shadow-inner flex flex-col items-center justify-center">
                <div className="w-full h-[400px]">
                  <Radar 
                    data={radarData} 
                    options={{
                      scales: {
                        r: {
                          grid: { color: 'rgba(255,255,255,0.1)' },
                          angleLines: { color: 'rgba(255,255,255,0.2)' },
                          pointLabels: { 
                            color: 'rgba(255,255,255,0.6)', 
                            font: { size: 12, weight: 'bold', family: 'Inter' } 
                          },
                          ticks: { display: false }
                        }
                      },
                      plugins: { legend: { display: false } }
                    }}
                  />
                </div>
                <div className="mt-10 pt-8 border-t border-white/10 w-full text-center">
                   <div className="text-[10px] text-white/40 font-black uppercase tracking-[0.3em]">
                     DNA Data Visualization Center
                   </div>
                </div>
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  )
}

function DeepStat({ label, value, icon, color, highlight, def }: { label: string, value: string | number, icon: React.ReactNode, color: string, highlight: string, def?: string }) {
  return (
    <div className={`p-8 rounded-[2rem] border border-white/10 backdrop-blur-2xl transition-all hover:scale-105 hover:bg-white/15 ${highlight} group`}>
      <div className="flex items-center gap-3 mb-3">
        <span className="text-white/40">{icon}</span>
        <div className="text-[10px] uppercase tracking-[0.25em] text-white/40 font-black leading-none">{label}</div>
      </div>
      <div className={`text-3xl font-black ${color} tracking-tighter leading-none`}>{value}</div>
      {def && (
        <div className="mt-3 text-[10px] text-white/50 leading-tight">
           {def}
        </div>
      )}
    </div>
  )
}
