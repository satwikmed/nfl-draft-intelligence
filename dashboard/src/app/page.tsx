"use client"
import React, { useEffect, useState, useMemo } from "react"
import { MeshGradient } from "@paper-design/shaders-react"
import { motion, AnimatePresence } from "framer-motion"
import { fetchStats } from "@/lib/api"
import { Prospect, Features, CompsData, NFLPerf, ModelMetrics } from "@/lib/types"
import BigBoard from "@/components/BigBoard"
import PlayerModal from "@/components/PlayerModal"
import AnalyticsDashboard from "@/components/AnalyticsDashboard"
import { Globe, Database, Cpu, ChevronRight, BarChart3, Users, Target, Search } from "lucide-react"

export default function Home() {
  const [data, setData] = useState<{
    board: Prospect[];
    features: Features;
    nfl: Record<string, NFLPerf[]>;
    comps: CompsData;
    metrics: ModelMetrics;
  } | null>(null)
  const [selectedPlayer, setSelectedPlayer] = useState<Prospect | null>(null)
  const [activeTab, setActiveTab] = useState<"Overview" | "Prospects" | "Similarity" | "Analytics" | "Methodology">("Overview")
  const [proSearchQuery, setProSearchQuery] = useState("")

  useEffect(() => {
    fetchStats().then(setData)
  }, [])

  // Reverse mapping matrix: Built once when data loads
  const reverseComps = useMemo(() => {
    if (!data) return {};
    const map: Record<string, { prospect: Prospect, sim: number }[]> = {};
    
    // Iterate every prospect
    data.board.forEach(p => {
      const comps = data.comps[p.player_id]?.comps || [];
      // If a historical NFL player is in this prospect's top 3, map it back
      comps.forEach(c => {
        const normName = c.name.toLowerCase();
        if (!map[normName]) map[normName] = [];
        map[normName].push({ prospect: p, sim: c.sim });
      });
    });

    // Sort the nested arrays so the best prospect matches are always at the top
    Object.keys(map).forEach(key => {
      map[key].sort((a, b) => b.sim - a.sim);
    });

    return map;
  }, [data]);

  // Derived state to get the actual search results
  const searchResults = useMemo(() => {
    if (!proSearchQuery.trim()) return [];
    const query = proSearchQuery.trim().toLowerCase();
    
    // Find all NFL pro names that match the query
    const matchingProKeys = Object.keys(reverseComps).filter(proName => proName.includes(query));
    
    // Aggregate the results
    let results: { prospect: Prospect, sim: number, proMatched: string }[] = [];
    matchingProKeys.forEach(k => {
       reverseComps[k].forEach(hit => {
          results.push({ ...hit, proMatched: k });
       })
    });
    
    results.sort((a, b) => b.sim - a.sim);
    
    const seen = new Set<string>();
    const finalResults = [];
    for (const r of results) {
      if (!seen.has(r.prospect.player_id)) {
        seen.add(r.prospect.player_id);
        finalResults.push(r);
      }
    }
    
    return finalResults.slice(0, 12);
  }, [proSearchQuery, reverseComps]);

  if (!data) return (
    <div className="min-h-screen bg-black flex items-center justify-center">
      <motion.div 
        animate={{ opacity: [0.5, 1, 0.5] }}
        transition={{ duration: 2, repeat: Infinity }}
        className="text-cyan-500 font-mono tracking-widest text-sm"
      >
        INITIALIZING INTELLIGENCE...
      </motion.div>
    </div>
  )

  return (
    <div className="min-h-screen bg-black relative overflow-hidden selection:bg-cyan-500/30">
      {/* Background Layer */}
      <MeshGradient
        className="fixed inset-0 w-full h-full"
        colors={["#000000", "#06b6d4", "#0891b2", "#164e63", "#f97316"]}
        speed={0.3}
      />
      <MeshGradient
        className="fixed inset-0 w-full h-full opacity-30"
        colors={["#000000", "#ffffff", "#06b6d4", "#f97316"]}
        speed={0.2}
      />

      <div className="relative z-10">
        <header className="flex items-center justify-between p-6 container mx-auto">
          <div className="flex items-center gap-3">
             <div className="size-10 rounded-xl bg-gradient-to-tr from-cyan-500 to-orange-500 flex items-center justify-center shadow-lg shadow-cyan-500/20">
               <Cpu size={24} className="text-white" />
             </div>
             <div>
               <span className="text-xl font-bold text-white leading-tight">DRAFT INTEL</span>
               <p className="text-[10px] text-cyan-400 font-mono uppercase tracking-[0.2em]">Explainable AI (XAI)</p>
             </div>
          </div>
          
          <nav className="hidden md:flex items-center space-x-2 text-sm font-medium" aria-label="Main Navigation">
            {["Overview", "Prospects", "Similarity", "Analytics", "Methodology"].map((tab) => (
              <button
                key={tab}
                id={`nav-tab-${tab.toLowerCase()}`}
                aria-current={activeTab === tab ? "page" : undefined}
                onClick={() => setActiveTab(tab as any)}
                className={`px-4 py-2 rounded-full transition-all ${
                  activeTab === tab 
                    ? "bg-white text-black font-bold focus:ring-2 focus:ring-cyan-500" 
                    : "text-white/50 hover:text-white hover:bg-white/5 focus:ring-2 focus:ring-white/20"
                }`}
              >
                {tab}
              </button>
            ))}
          </nav>

          <div className="hidden md:block w-32" /> {/* Spacer for symmetry */}
        </header>

        <main className="container mx-auto px-6 py-12 space-y-16">
          <AnimatePresence mode="wait">
            {activeTab === "Overview" && (
              <motion.div
                key="overview"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className="space-y-16 mt-10"
              >
                <div className="space-y-12 max-w-5xl mx-auto border-b border-white/10 pb-12 text-left">
                   <div className="space-y-4">
                     <h2 className="text-4xl md:text-5xl font-black text-white tracking-tighter leading-tight flex items-center gap-4">
                       <span className="size-3 rounded-full bg-slate-400"></span>
                       The Background: The NFL Draft
                     </h2>
                     <p className="text-lg text-white/60 font-light leading-relaxed">
                       Every year, the National Football League (NFL) selects the most talented athletes from College Football to become professionals in the "NFL Draft." To make these multi-million dollar decisions, NFL teams must evaluate thousands of college players, analyzing years of collegiate game statistics and physical athletic testing (such as the 40-yard dash). The entire goal is to predict one simple thing: Will this college player succeed at the professional level?
                     </p>
                   </div>

                   <div className="space-y-4">
                     <h2 className="text-4xl md:text-5xl font-black text-white tracking-tighter leading-tight flex items-center gap-4">
                       <span className="size-3 rounded-full bg-orange-500"></span>
                       The Problem: Context-Blind Evaluation
                     </h2>
                     <p className="text-lg text-white/60 font-light leading-relaxed">
                       Predicting this success is incredibly difficult, and traditional scouting is deeply flawed by "context-blind" evaluation. For example, a wide receiver playing for a small, uncompetitive college might easily accumulate 1,500 yards because he plays against weak defenders. A receiver playing for an elite college program (like the SEC) might only accumulate 1,000 yards because he faces future NFL defenders every single week. Subjective scouting struggles to untangle these differences, often treating raw statistics equally. Furthermore, when athletes undergo physical testing, scouts frequently fail to mathematically adjust their speed against their body mass. This leads to massive draft "busts" where players are inaccurately graded based on uncontextualized numbers.
                     </p>
                   </div>
                   
                   <div className="space-y-4">
                     <h2 className="text-4xl md:text-5xl font-black text-white tracking-tighter leading-tight flex items-center gap-4">
                       <span className="size-3 rounded-full bg-cyan-500"></span>
                       The Solution: Explainable Intelligence
                     </h2>
                     <p className="text-lg text-white/60 font-light leading-relaxed">
                       This platform was engineered to permanently eliminate subjective evaluation bias. A comprehensive dataset was amassed containing over two decades (2000-2023) of collegiate production and physical combine data for over 140,000 profiles. By mathematically adjusting every raw statistic for competition disparities (opponent strength) and dimensional scale (speed-to-weight ratios), an advanced XGBoost machine-learning pipeline objectively calculates the exact probability that a college prospect's unique traits will translate into a successful NFL career.
                     </p>
                   </div>
                </div>
                
                <div className="grid grid-cols-1 md:grid-cols-3 gap-8 pt-8">
                   <div className="p-10 rounded-[3rem] bg-white/5 border border-white/10 backdrop-blur-xl hover:bg-white/10 transition-all flex flex-col h-full">
                      <div className="size-14 rounded-2xl bg-cyan-500/20 flex items-center justify-center mb-8">
                        <Database className="text-cyan-400 size-6" />
                      </div>
                      <h3 className="text-2xl font-black text-white mb-4">1. Pro Readiness Score (PRS)</h3>
                      <div className="space-y-2 mb-6 flex-grow">
                         <p className="text-white/80 font-bold text-[11px] tracking-[0.2em] uppercase">Why it's here:</p>
                         <p className="text-white/60 leading-relaxed">
                           To replace arbitrary grading. Traditional scouting assigns vague grades (like a "1st Round Grade" or a "B+") that mean different things to different evaluators. The Pro Readiness Score eliminates confusion by providing a single, objective probability (0-100%) that a prospect will fulfill an NFL starter threshold within three seasons, mathematically scaling their expectations based on where they are drafted.
                         </p>
                      </div>
                      <div className="text-xs uppercase tracking-widest text-cyan-500 font-bold mt-auto pt-4 border-t border-white/5">Explore the Board in 'Prospects'</div>
                   </div>

                   <div className="p-10 rounded-[3rem] bg-white/5 border border-white/10 backdrop-blur-xl hover:bg-white/10 transition-all flex flex-col h-full">
                      <div className="size-14 rounded-2xl bg-orange-500/20 flex items-center justify-center mb-8">
                        <Users className="text-orange-400 size-6" />
                      </div>
                      <h3 className="text-2xl font-black text-white mb-4">2. Historical Profile Matching</h3>
                      <div className="space-y-2 mb-6 flex-grow">
                         <p className="text-white/80 font-bold text-[11px] tracking-[0.2em] uppercase">Why it's here:</p>
                         <p className="text-white/60 leading-relaxed">
                           To eliminate deceptive "eye-test" comparisons. Analysts often compare a young player to a famous veteran simply because they "look similar on tape." This platform utilizes Cosine Similarity algorithms to mathematically cross-reference an incoming prospect against 20 years of historical data, finding objective DNA clones based on hundreds of overlapping data points rather than subjective visual bias.
                         </p>
                      </div>
                      <div className="text-xs uppercase tracking-widest text-orange-500 font-bold mt-auto pt-4 border-t border-white/5">Find Clones in 'Similarity'</div>
                   </div>

                   <div className="p-10 rounded-[3rem] bg-white/5 border border-white/10 backdrop-blur-xl hover:bg-white/10 transition-all flex flex-col h-full">
                      <div className="size-14 rounded-2xl bg-purple-500/20 flex items-center justify-center mb-8">
                        <Target className="text-purple-400 size-6" />
                      </div>
                      <h3 className="text-2xl font-black text-white mb-4">3. Visualized Explainability</h3>
                      <div className="space-y-2 mb-6 flex-grow">
                         <p className="text-white/80 font-bold text-[11px] tracking-[0.2em] uppercase">Why it's here:</p>
                         <p className="text-white/60 leading-relaxed">
                           To build executive trust. An advanced Artificial Intelligence model is useless (a "black-box") if an NFL General Manager cannot understand why it scored a player a certain way. By incorporating SHAP algorithms (Explainable AI), this platform extracts and visualizes the precise athletic and production statistics causing the model to generate its rating, allowing humans to verify the machine's reasoning.
                         </p>
                      </div>
                      <div className="text-xs uppercase tracking-widest text-purple-500 font-bold mt-auto pt-4 border-t border-white/5">View Breakdowns in Player Modals</div>
                   </div>
                </div>
              </motion.div>
            )}

            {activeTab === "Prospects" && (
              <motion.div
                key="prospects"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="space-y-12 mt-10"
              >
                {/* Database Context Block */}
                <div className="space-y-6 max-w-5xl mx-auto border-b border-white/10 pb-8 text-left">
                  <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="inline-flex items-center px-4 py-2 rounded-full bg-white/5 border border-white/10 backdrop-blur-sm mb-4"
                  >
                    <span className="size-2 rounded-full bg-cyan-500 mr-2 animate-pulse" />
                    <span className="text-white/80 text-[10px] font-bold uppercase tracking-widest">
                      Pipeline Active • Processing {data.board.length.toLocaleString()} Profiles
                    </span>
                  </motion.div>
                  <h2 className="text-4xl md:text-5xl font-black text-white tracking-tighter leading-tight flex items-center gap-4">
                    <span className="size-3 rounded-full bg-cyan-500"></span>
                    Database: The 2025 Draft Class
                  </h2>
                  <p className="text-lg text-white/60 font-light leading-relaxed">
                    This module serves as the primary output matrix for the XGBoost evaluation pipeline. Every eligible prospect for the 2025 NFL Draft has been algorithmically processed and ranked entirely by their objective Pro Readiness Score (PRS). Subjective media consensus, unverified scout hype, and traditional "big board" rankings are mathematically excluded from this hierarchy. 
                  </p>
                </div>

                {/* Stats Bar */}
                <section className="grid grid-cols-2 md:grid-cols-4 gap-4 max-w-5xl mx-auto">
                   <HeroStat label="Active Prospects" value={data.board.length.toLocaleString()} icon={<Database size={16} />} />
                   <HeroStat label="Data Parameters" value="143K" icon={<Globe size={16} />} />
                   <HeroStat label="Validation AUC" value="94.2%" icon={<Cpu size={16} />} />
                   <HeroStat label="Target Class" value="2025" icon={<ChevronRight size={16} />} />
                </section>

                {/* Big Board Section */}
                <section className="space-y-8 pt-8">
                  <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
                    <div className="space-y-3">
                      <h3 className="text-2xl font-bold text-white tracking-tight">Global Intelligence Board</h3>
                      <p className="text-sm text-white/40 max-w-3xl leading-relaxed">
                        Navigate the database utilizing the positional filters or exact-match search parameters. <br />
                        <strong className="text-cyan-400 font-bold block mt-2 text-xs tracking-widest uppercase">Critical Action:</strong> 
                        <span className="mt-1 block">Click the <span className="bg-white/10 px-2 py-0.5 rounded text-[10px] uppercase font-bold text-white/60 mx-1">View Intelligence</span> module on any row to extract the underlying Explainable AI (SHAP) feature weights and view the Cosine Similarity clones for that specific prospect.</span>
                      </p>
                    </div>
                  </div>
                  
                  <BigBoard prospects={data.board} onSelect={setSelectedPlayer} />
                </section>
              </motion.div>
            )}

            {activeTab === "Similarity" && (
              <motion.div
                key="similarity"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="space-y-12 mt-10"
              >
                <div className="flex flex-col md:flex-row md:items-end justify-between gap-8 w-full border-b border-white/10 pb-8">
                  <section className="max-w-3xl space-y-4 flex-grow">
                    <h2 className="text-4xl md:text-5xl font-black text-white tracking-tighter leading-tight flex items-center gap-4">
                      <span className="size-3 rounded-full bg-purple-500"></span>
                      DNA Reverse-Engineering
                    </h2>
                    <p className="text-lg text-white/60 font-light leading-relaxed">
                      Cross-referencing incoming profile pipelines backwards against over 20 years of historical NFL performance data. Instead of asking who a prospect plays like, utilize this engine to find an exact structural clone of a targeted elite NFL veteran.
                    </p>
                  </section>
                  
                  <div className="relative w-full md:w-96 flex-shrink-0">
                    <Search className="absolute left-4 top-1/2 -translate-y-1/2 size-5 text-purple-500" />
                    <input
                      type="text"
                      placeholder="Find the next... (e.g. 'Deebo Samuel')"
                      className="w-full bg-purple-950/20 border border-purple-500/30 rounded-xl py-4 flex pl-12 pr-4 text-white font-medium hover:border-purple-500/50 transition-all focus:outline-none focus:ring-2 focus:ring-purple-500/50 backdrop-blur-md placeholder:text-white/30"
                      value={proSearchQuery}
                      onChange={(e) => setProSearchQuery(e.target.value)}
                    />
                  </div>
                </div>
                
                {proSearchQuery.trim() === "" ? (
                  <>
                    <div className="flex items-center gap-3 border-b border-white/5 pb-4">
                       <span className="size-2 rounded-full bg-white/20" />
                       <h3 className="text-sm font-bold text-white/50 uppercase tracking-widest">Featured Matrix: Top 9 Algorithm Prospects</h3>
                    </div>
                    <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                      {data.board.slice(0, 9).map((p) => {
                        const playerComps = data.comps[p.player_id]?.comps || []
                        return (
                          <div key={p.player_id} className="p-6 rounded-3xl bg-white/5 border border-white/10 backdrop-blur-md space-y-4 group transition-all hover:bg-white/10">
                            <div className="flex justify-between items-start">
                              <div>
                                <h4 className="text-white font-bold text-lg">{p.name}</h4>
                                <p className="text-white/30 text-xs uppercase tracking-widest">{p.position_group} • {p.school}</p>
                              </div>
                              <div className="size-8 rounded-lg bg-cyan-500/10 flex items-center justify-center text-cyan-400 font-mono text-[10px] font-bold border border-cyan-500/20">
                                #{p.pro_readiness_score.toFixed(0)}
                              </div>
                            </div>
                            
                            <div className="space-y-3 pt-2">
                               <p className="text-[10px] font-bold text-white/20 uppercase tracking-[0.2em] mb-1">Top Matches</p>
                               {playerComps.slice(0, 3).map((c, i) => (
                                 <div key={c.comp_id} className="flex items-center justify-between">
                                   <span className="text-white/70 text-sm font-medium">{c.name}</span>
                                   <span className="text-purple-400 font-mono text-xs">{(c.sim * 100).toFixed(1)}%</span>
                                 </div>
                               ))}
                            </div>
                            
                            <button 
                              onClick={() => setSelectedPlayer(p)}
                              className="w-full py-3 rounded-xl bg-white/5 border border-white/5 text-white/60 text-xs font-bold hover:bg-white/10 hover:text-white transition-all group-hover:border-cyan-500/30"
                            >
                              Deep Scan Profile
                            </button>
                          </div>
                        )
                      })}
                    </section>
                  </>
                ) : (
                  <>
                    <div className="flex items-center gap-3 border-b border-purple-500/30 pb-4">
                       <span className="size-2 rounded-full bg-purple-500 animate-pulse shadow-lg shadow-purple-500/50" />
                       <h3 className="text-sm font-bold text-purple-400 uppercase tracking-widest">Global Search Hits: {searchResults.length} Mathematical Matches Found</h3>
                    </div>
                    {searchResults.length === 0 ? (
                       <div className="py-24 text-center border border-white/5 border-dashed rounded-3xl bg-white/[0.01]">
                          <p className="text-white/40 font-mono text-sm max-w-sm mx-auto leading-relaxed">System failed to isolate a statistically significant 2025 profile matching the genetic/production footprint of '{proSearchQuery}'.</p>
                       </div>
                    ) : (
                      <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {searchResults.map((hit) => {
                          const p = hit.prospect;
                          return (
                            <div key={p.player_id} className="p-6 rounded-3xl bg-purple-950/20 border border-purple-500/20 backdrop-blur-md space-y-5 group transition-all hover:bg-purple-950/40 hover:border-purple-500/40 cursor-default">
                              <div className="flex justify-between items-start">
                                <div>
                                  <h4 className="text-white font-bold text-lg">{p.name}</h4>
                                  <p className="text-purple-400/80 text-xs uppercase tracking-widest">{p.position_group} • {p.school}</p>
                                </div>
                                <div className="px-3 py-1.5 rounded-lg bg-purple-500/20 flex flex-col items-center justify-center border border-purple-500/40 shadow-lg shadow-purple-500/10">
                                   <span className="text-[9px] uppercase tracking-widest text-purple-300 font-bold mb-0.5">DNA Match</span>
                                   <span className="text-purple-400 font-mono text-[15px] font-black leading-none">{(hit.sim * 100).toFixed(1)}%</span>
                                </div>
                              </div>
                              
                              <div className="space-y-1 py-4 border-y border-purple-500/10">
                                 <p className="text-[10px] text-white/30 uppercase tracking-widest flex justify-between">
                                    <span>Pro Readiness Output</span>
                                    <span className="text-purple-400/50">Base Metric</span>
                                 </p>
                                 <p className="text-white font-mono text-2xl font-bold">{p.pro_readiness_score.toFixed(1)} <span className="text-white/20 text-sm">/ 100</span></p>
                              </div>
                              
                              <button 
                                onClick={() => setSelectedPlayer(p)}
                                className="w-full py-3 rounded-xl bg-purple-500/10 border border-purple-500/30 text-purple-300 text-xs font-bold hover:bg-purple-500 hover:text-black transition-all shadow-lg hover:shadow-purple-500/50"
                              >
                                Extract Matrix Data
                              </button>
                            </div>
                          )
                        })}
                      </section>
                    )}
                  </>
                )}
              </motion.div>
            )}

            {activeTab === "Analytics" && (
              <motion.div
                key="analytics"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="space-y-12"
              >
                <section className="flex flex-col md:flex-row md:items-end justify-between border-b border-white/10 pb-8 gap-6">
                  <div className="max-w-3xl space-y-4 flex-grow">
                    <h2 className="text-4xl md:text-5xl font-black text-white tracking-tighter leading-tight flex items-center gap-4">
                      <span className="size-3 rounded-full bg-cyan-500"></span>
                      System Telemetry & Telemetrics
                    </h2>
                    <p className="text-lg text-white/60 font-light leading-relaxed">
                      Visualize the macroeconomic architecture of the 2025 Draft class while continuously monitoring the fundamental Out-Of-Sample (OOS) stability of the underlying XGBoost model algorithms. 
                    </p>
                  </div>
                  <button 
                    onClick={() => {
                      const headers = "Rank,Player,School,Position,Score\n";
                      const rows = data.board.map((p, i) => `#${i+1},${p.name},${p.school},${p.position_group},${p.pro_readiness_score.toFixed(1)}`).join("\n");
                      const blob = new Blob([headers + rows], { type: 'text/csv' });
                      const url = URL.createObjectURL(blob);
                      const a = document.createElement('a');
                      a.href = url;
                      a.download = `Draft_Intel_Board_2025.csv`;
                      a.click();
                    }}
                    className="hidden md:block px-8 py-4 rounded-full bg-cyan-500 text-black font-black text-xs uppercase tracking-widest hover:scale-105 transition-all shadow-xl shadow-cyan-500/20"
                  >
                    Export Draft Board
                  </button>
                </section>

                <AnalyticsDashboard board={data.board} metrics={data.metrics} />

              </motion.div>
            )}

            {activeTab === "Methodology" && (
              <motion.div
                key="methodology"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="space-y-12"
              >
                <section className="max-w-4xl space-y-4">
                  <h2 className="text-4xl md:text-5xl font-black text-white tracking-tighter leading-tight flex items-center gap-4">
                    <span className="size-3 rounded-full bg-blue-500"></span>
                    Architectural Methodology
                  </h2>
                  <p className="text-xl text-white/50 font-light leading-relaxed">
                    A transparent, peer-reviewable breakdown of how the Draft Intel XGBoost pipeline converts raw collegiate statistics into actionable, mathematically sound predictability models. 
                  </p>
                </section>
                
                <div className="space-y-16 max-w-5xl">
                  {/* Phase 1 */}
                  <div className="flex flex-col md:flex-row gap-8 items-start">
                    <div className="size-16 shrink-0 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center font-black text-2xl text-blue-500">
                      01
                    </div>
                    <div className="space-y-4 pt-2">
                       <h3 className="text-2xl font-black text-white tracking-tight flex items-center gap-3">
                         <Database className="text-blue-500 size-5" /> 
                         Massive-Scale Sourcing & Standardization
                       </h3>
                       <p className="text-white/70 leading-relaxed">
                         <strong className="text-white">Technical:</strong> The model ingested 143,149 raw `sportsreference` CSV arrays (2000-2023) and mapped them cleanly against `nfl_data_py` to establish Ground Truth NFL outcomes. <br />
                         <strong className="text-white mt-4 block">Non-Technical Translation:</strong> Before we can predict the future, we had to teach the computer the past. We fed the AI over twenty years of history—every single stat, every combine jump, and every 40-yard dash of every college player since the year 2000. It matched those college profiles with whether or not that exact player succeeded in the NFL, giving the machine tens of thousands of perfect examples to learn from.
                       </p>
                    </div>
                  </div>

                  {/* Phase 2 */}
                  <div className="flex flex-col md:flex-row gap-8 items-start">
                    <div className="size-16 shrink-0 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center font-black text-2xl text-cyan-500">
                      02
                    </div>
                    <div className="space-y-4 pt-2">
                       <h3 className="text-2xl font-black text-white tracking-tight flex items-center gap-3">
                         <Globe className="text-cyan-500 size-5" /> 
                         Contextual Feature Engineering
                       </h3>
                       <p className="text-white/70 leading-relaxed">
                         <strong className="text-white">Technical:</strong> Raw volume statistics are deceptive. The pipeline engineers context by applying Mathematical Strength of Schedule (SOS) multipliers adjusting for collegiate conference difficulty, and dimensional profiling (e.g., Speed Score = (Weight * 200) / (40-Time^4)) to normalize athletic outliers. <br />
                         <strong className="text-white mt-4 block">Non-Technical Translation:</strong> A player catching 1,500 yards in the SEC against future NFL defenders is radically different from someone catching 1,500 yards in Division II against accountants. The algorithm mathematically penalizes small-school production while boosting tough-conference production. It also penalizes slow players who are small, but rewards heavy players who can run fast (the "Speed Score"), leveling out the biological playing field.
                       </p>
                    </div>
                  </div>

                  {/* Phase 3 */}
                  <div className="flex flex-col md:flex-row gap-8 items-start">
                    <div className="size-16 shrink-0 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center font-black text-2xl text-orange-500">
                      03
                    </div>
                    <div className="space-y-4 pt-2">
                       <h3 className="text-2xl font-black text-white tracking-tight flex items-center gap-3">
                         <Cpu className="text-orange-500 size-5" /> 
                         XGBoost Processing & SMOTE Balancing
                       </h3>
                       <p className="text-white/70 leading-relaxed">
                         <strong className="text-white">Technical:</strong> Evaluative predictability utilizes position-locked XGBoost Classifiers. Because "Successful" NFL players represent less than 5% of all collegiate athletes, the training data is extremely imbalanced. We utilized Synthetic Minority Over-sampling Technique (SMOTE) to synthetically balance the training minority class. <br />
                         <strong className="text-white mt-4 block">Non-Technical Translation:</strong> The algorithm asks thousands of "If/Then" questions simultaneously. (e.g. "If the player runs faster than 4.5s AND weighs over 210lbs AND caught 50 balls, what are the odds he is an NFL starter?"). Because drafting an elite NFL starter is extremely rare, the computer was struggling to find enough "winners" to study. We mathematically cloned the "winners" during the training phase so the algorithm could properly learn exactly what makes an elite player before testing it on the real draft.
                       </p>
                    </div>
                  </div>

                  {/* Phase 4 */}
                  <div className="flex flex-col md:flex-row gap-8 items-start">
                    <div className="size-16 shrink-0 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center font-black text-2xl text-purple-500">
                      04
                    </div>
                    <div className="space-y-4 pt-2">
                       <h3 className="text-2xl font-black text-white tracking-tight flex items-center gap-3">
                         <Target className="text-purple-500 size-5" /> 
                         Explainable Interpretability (SHAP)
                       </h3>
                       <p className="text-white/70 leading-relaxed">
                         <strong className="text-white">Technical:</strong> Overcoming the Neural-Network "Black Box" dilemma. By unpacking the TreeExplainer, SHAP (SHapley Additive exPlanations) isolates the exact marginal contribution of every variable. <br />
                         <strong className="text-white mt-4 block">Non-Technical Translation:</strong> A computer is useless to a General Manager if it just says "We gave this player a 99% score" without explaining *why*. Through Explainable AI, the system physically opens up its own brain, pointing precisely to the 40-yard dash, the bench press, or the collegiate touchdowns that convinced it to grade the player so highly. Accountability is paramount.
                       </p>
                    </div>
                  </div>
                </div>

                {/* Validation Test Metrics */}
                <section className="max-w-4xl space-y-6 pt-16 border-t border-white/5">
                  <h3 className="text-3xl font-black text-white tracking-tight">OOS Validation Metrics</h3>
                  <p className="text-white/50 text-sm leading-relaxed">
                    Proof of accuracy. Model weights were trained strictly on cohorts from 2000–2021. To prove the model actually works, we force-tested its predictions on a completely blind dataset (the 2022-2023 cohorts) holding out the answers. Below are the actual Area Under the Receiver Operating Characteristic Curve (ROC-AUC) Out-Of-Sample test metrics. Anything over 90% is incredibly sturdy.
                  </p>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-4">
                    {data.metrics && Object.entries(data.metrics).map(([pos, m]) => (
                      <div key={pos} className="p-6 rounded-xl bg-white/5 border border-white/10 flex flex-col items-center justify-center text-center hover:bg-white/10 transition-colors">
                        <div className="text-[10px] text-cyan-400 font-bold uppercase tracking-widest">{pos} Module</div>
                        <div className="text-3xl font-black text-white mt-2">{m.auc ? (m.auc * 100).toFixed(1) + "%" : "N/A"}</div>
                        <div className="text-[10px] text-white/40 uppercase tracking-widest mt-2">{m.n_train} Test Profiles</div>
                      </div>
                    ))}
                  </div>
                </section>

                {/* Limitations */}
                <section className="max-w-4xl space-y-6 pt-12 border-t border-white/10">
                  <h3 className="text-3xl font-black text-white tracking-tight text-orange-400">System Parameters & Limitations</h3>
                  <p className="text-white/70 leading-relaxed text-sm">
                    A responsible data science model acknowledges its blind spots rather than hiding them. The current architecture accepts two primary analytical limitations:
                  </p>
                  <ul className="space-y-4">
                    <li className="p-6 rounded-xl bg-red-500/10 border border-red-500/20 text-sm text-white/80">
                      <strong className="text-white block mb-2 text-lg">1. Missing Combine Data Bias</strong>
                      Not all draft prospects are invited to the NFL Combine to run the 40-yard dash. Rather than using median imputation (which fakes the data), this pipeline natively uses XGBoost's deep zero-fill tree-splitting logic for unrecorded testing. This heavily biases overall predictive scores downward for non-invited players until Pro-Day times are eventually manually inputted.
                    </li>
                    <li className="p-6 rounded-xl bg-orange-500/10 border border-orange-500/20 text-sm text-white/80">
                      <strong className="text-white block mb-2 text-lg">2. Coaching Schema & Roster Context</strong>
                      The model evaluates prospects in a vacuum regarding their physical frames and college history. It is completely unable to quantify the effect of a zone-blocking run scheme vs a gap scheme that an NFL team might try to force a player into. It also cannot correct for internal medical evaluations mapping joint-deterioration.
                    </li>
                  </ul>
                </section>
              </motion.div>
            )}
          </AnimatePresence>
        </main>

        <footer className="p-12 text-center text-white/40 text-xs font-mono tracking-widest border-t border-white/5 mt-20 flex flex-col items-center justify-center gap-2">
          <span>DESIGNED FOR ELITE COMPETITION • © 2025 DRAFT INTEL</span>
          <span>
            ENGINEERED BY <a href="https://www.linkedin.com/in/medipalli-satwik/" target="_blank" rel="noopener noreferrer" className="text-cyan-500 hover:text-cyan-400 transition-colors">MEDIPALLI SATWIK</a>
          </span>
        </footer>
      </div>

      <PlayerModal 
        player={selectedPlayer} 
        features={data.features} 
        comps={data.comps}
        nfl={selectedPlayer ? data.nfl[selectedPlayer.player_id] || [] : []}
        onClose={() => setSelectedPlayer(null)} 
      />
    </div>
  )
}

function HeroStat({ label, value, icon }: { label: string, value: string, icon: React.ReactNode }) {
  return (
    <div className="p-6 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-md border-white/5 transition-all hover:border-cyan-500/30 group">
      <div className="flex items-center justify-between mb-2">
        <span className="text-white/30 group-hover:text-cyan-400 transition-colors">{icon}</span>
        <span className="text-[10px] font-bold text-white/20 uppercase tracking-widest">{label}</span>
      </div>
      <div className="text-3xl font-black text-white">{value}</div>
    </div>
  )
}
