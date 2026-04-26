"use client"
import React, { useState, useMemo } from "react"
import { Prospect, ModelMetrics, WidgetConfig } from "@/lib/types"
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  BarController,
  Title,
  Tooltip,
  Legend,
  ArcElement
} from "chart.js"
import { Line, Doughnut, Scatter, Bar } from "react-chartjs-2"
import { BarChart3, Users, Plus, X, Trash2 } from "lucide-react"
import { motion, AnimatePresence } from "framer-motion"

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  BarController,
  Title,
  Tooltip,
  Legend,
  ArcElement
)

interface Props {
  board: Prospect[];
  metrics: ModelMetrics;
}

const METRIC_MAP: Record<string, keyof Prospect> = {
  "Pro Readiness Score": "pro_readiness_score",
  "Predicted Career Length": "predicted_career_length",
  "40-Yard Dash": "forty_yard",
  "Vertical Jump (in)": "vertical_jump",
  "Broad Jump (in)": "broad_jump",
  "Bench Press (reps)": "bench_press",
  "3-Cone Drill": "three_cone",
  "20-Yd Shuttle": "shuttle",
  "Height (in)": "height_inches",
  "Weight (lbs)": "weight_lbs"
}

const posOptions = ["All", "QB", "RB", "WR", "TE", "OL", "DL", "LB", "DB"]

export default function AnalyticsDashboard({ board, metrics }: Props) {
  // Original System Telemetry State
  const lineData = {
    labels: ['1st', '2nd', '3rd', '4th', '5th', '6th', '7th', 'UDFA'],
    datasets: [
      {
        label: 'Success Expectation Threshold',
        data: [150, 150, 100, 100, 100, 50, 50, 50],
        borderColor: '#06b6d4',
        backgroundColor: 'rgba(6, 182, 212, 0.5)',
        tension: 0.4,
        borderWidth: 3,
        pointRadius: 6,
        pointBackgroundColor: '#fff'
      }
    ]
  };

  const posCounts = board.reduce((acc, p) => {
    acc[p.position_group] = (acc[p.position_group] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const doughnutData = {
    labels: Object.keys(posCounts),
    datasets: [{
      data: Object.values(posCounts),
      backgroundColor: ['#06b6d4', '#f97316', '#a855f7', '#10b981', '#ef4444', '#3b82f6', '#f59e0b', '#ec4899'],
      borderWidth: 0,
      hoverOffset: 10
    }]
  };

  // Legacy Scatter State (Now kept as Default Query Engine)
  const [queryPos, setQueryPos] = useState<string>("WR")
  const [xMetricName, setXMetricName] = useState<string>("40-Yard Dash")
  const [yMetricName, setYMetricName] = useState<string>("Pro Readiness Score")

  const customScatterData = useMemo(() => {
    const xKey = METRIC_MAP[xMetricName];
    const yKey = METRIC_MAP[yMetricName];
    let pool = board;
    if (queryPos !== "All") pool = pool.filter(p => p.position_group === queryPos);
    pool = pool.filter(p => p[xKey] != null && p[yKey] != null);

    return {
      datasets: [{
        label: `${queryPos} Prospects (${pool.length})`,
        data: pool.map(p => ({ x: Number(p[xKey]), y: Number(p[yKey]), raw: p })),
        backgroundColor: 'rgba(6, 182, 212, 0.6)',
        borderColor: 'rgba(6, 182, 212, 1)',
        borderWidth: 1,
        pointRadius: 4,
        pointHoverRadius: 6
      }]
    };
  }, [board, queryPos, xMetricName, yMetricName]);

  // BYOD Spawner Engine State
  const [spawnedWidgets, setSpawnedWidgets] = useState<WidgetConfig[]>([])
  const [showBuilder, setShowBuilder] = useState(false)
  const [bType, setBType] = useState<"SCATTER" | "BAR" | "KPI">("KPI")
  const [bPos, setBPos] = useState("All")
  const [bX, setBX] = useState("Pro Readiness Score")
  const [bY, setBY] = useState("Pro Readiness Score")

  const spawnWidget = () => {
    setSpawnedWidgets([...spawnedWidgets, {
      id: Math.random().toString(),
      type: bType,
      positionGroup: bPos,
      xMetricName: bX,
      yMetricName: bY
    }])
    setShowBuilder(false)
  }

  return (
    <div className="space-y-12 pb-12">
      {/* 2x2 System Telemetry Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Module 1: The Line Chart */}
        <div className="p-8 rounded-[2rem] bg-white/5 border border-white/10 backdrop-blur-md">
           <h4 className="text-white font-black mb-1">Success Expectation Mapping</h4>
           <div className="h-[250px] w-full mt-8">
             <Line 
               data={lineData} 
               options={{
                 maintainAspectRatio: false,
                 scales: { y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: 'rgba(255,255,255,0.5)' } }, x: { grid: { display: false }, ticks: { color: 'rgba(255,255,255,0.5)' } } },
                 plugins: { legend: { display: false } }
               }} 
             />
           </div>
        </div>

        {/* Module 2: The Custom Query Engine */}
        <div className="p-8 rounded-[2rem] bg-white/5 border border-white/10 backdrop-blur-md flex flex-col">
           <div className="flex flex-col mb-6">
             <h4 className="text-white font-black mb-1">Interactive Matrix Tool</h4>
             <div className="flex flex-wrap gap-2 text-xs mt-4">
               <select value={queryPos} onChange={e => setQueryPos(e.target.value)} className="bg-black/40 border border-white/10 rounded-lg px-2 py-1.5 text-cyan-400">
                 {posOptions.map(p => <option key={p} value={p}>{p}</option>)}
               </select>
               <select value={xMetricName} onChange={e => setXMetricName(e.target.value)} className="bg-black/40 border border-white/10 rounded-lg px-2 py-1.5 text-white max-w-[140px]">
                 {Object.keys(METRIC_MAP).map(m => <option key={m} value={m}>X: {m}</option>)}
               </select>
               <select value={yMetricName} onChange={e => setYMetricName(e.target.value)} className="bg-black/40 border border-white/10 rounded-lg px-2 py-1.5 text-white max-w-[140px]">
                 {Object.keys(METRIC_MAP).map(m => <option key={m} value={m}>Y: {m}</option>)}
               </select>
             </div>
           </div>
           <div className="h-[200px] w-full flex-grow">
             <Scatter 
               data={customScatterData} 
               options={{
                 maintainAspectRatio: false,
                 scales: {
                   y: { title: { display: true, text: yMetricName, color: 'rgba(255,255,255,0.4)', font: {size: 10} }, grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: 'rgba(255,255,255,0.5)' } },
                   x: { title: { display: true, text: xMetricName, color: 'rgba(255,255,255,0.4)', font: {size: 10} }, grid: { display: false }, ticks: { color: 'rgba(255,255,255,0.5)' } }
                 },
                 plugins: { legend: { display: false }, tooltip: { callbacks: { label: function(context: any) { const raw = context.raw.raw; return `${raw.name}: [X: ${context.parsed.x}, Y: ${context.parsed.y}]`; } } } }
               }} 
             />
           </div>
        </div>

        {/* Module 3: Active Model Status */}
        <div className="p-8 rounded-[2rem] bg-white/5 border border-white/10 backdrop-blur-md">
           <h4 className="text-white font-black mb-6">OOS Validation Metrics</h4>
           <div className="space-y-4 max-h-[250px] overflow-y-auto no-scrollbar pr-2">
             {Object.entries(metrics).map(([pos, data]) => (
               <div key={pos} className="flex items-center justify-between p-3 rounded-xl bg-white/5 border border-white/5">
                 <div className="flex items-center gap-3">
                   <div className="size-8 rounded-lg bg-cyan-500/20 flex items-center justify-center text-cyan-400 font-bold text-xs">{pos}</div>
                   <span className="text-white/60 text-sm">AUC Score</span>
                 </div>
                 <div className="text-white font-mono font-bold">{data.auc ? (data.auc * 100).toFixed(1) + "%" : "N/A"}</div>
               </div>
             ))}
           </div>
        </div>

        {/* Module 4: Doughnut Distribution */}
        <div className="p-8 rounded-[2rem] bg-white/5 border border-white/10 backdrop-blur-md flex flex-col items-center justify-center">
           <h4 className="text-white font-black mb-6 w-full text-left">Positional Weighting</h4>
           <div className="h-[200px] w-full flex justify-center">
             <Doughnut 
               data={doughnutData} 
               options={{ maintainAspectRatio: false, cutout: '75%', plugins: { legend: { position: 'right', labels: { color: 'rgba(255,255,255,0.7)', font: { size: 10 } } } } }} 
             />
           </div>
        </div>
      </div>

      {/* Scout Workbench - BYOD Engine */}
      <div className="pt-16 border-t border-white/10">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h3 className="text-3xl font-black text-white tracking-tight flex items-center gap-4">
              <span className="size-3 rounded-full bg-orange-500"></span>
              Scout Workbench
            </h3>
            <p className="text-white/50 text-sm mt-2">Deploy custom intelligence widgets directly into your localized dashboard.</p>
          </div>
          
          <button 
            onClick={() => setShowBuilder(true)}
            className="flex items-center gap-2 px-6 py-3 rounded-xl bg-orange-500 text-black font-black text-xs uppercase tracking-widest hover:scale-105 transition-all shadow-xl shadow-orange-500/20"
          >
            <Plus size={16} /> Add Module
          </button>
        </div>

        {/* Visualized Widgets */}
        {spawnedWidgets.length === 0 ? (
          <div className="py-24 border border-white/5 border-dashed rounded-[2rem] flex flex-col items-center justify-center text-center">
            <BarChart3 className="size-12 text-white/10 mb-4" />
            <p className="text-white/40 font-mono text-sm">Workbench Empty. Spawn an intelligence module to begin custom profiling.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <AnimatePresence>
              {spawnedWidgets.map(w => (
                <WidgetRenderBlock 
                  key={w.id} 
                  config={w} 
                  board={board} 
                  onRemove={() => setSpawnedWidgets(spawnedWidgets.filter(x => x.id !== w.id))} 
                />
              ))}
            </AnimatePresence>
          </div>
        )}
      </div>

      {/* Builder Modal */}
      <AnimatePresence>
        {showBuilder && (
          <motion.div 
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-6"
          >
            <div className="bg-neutral-900 border border-white/10 rounded-[2rem] w-full max-w-lg overflow-hidden shadow-2xl">
               <div className="p-6 border-b border-white/5 flex justify-between items-center bg-white/[0.02]">
                 <h4 className="text-xl font-bold text-white uppercase tracking-widest text-sm">Module Blueprint</h4>
                 <button onClick={() => setShowBuilder(false)} className="text-white/40 hover:text-white"><X size={20}/></button>
               </div>
               
               <div className="p-8 space-y-6">
                 <div>
                   <label className="block text-xs font-bold text-white/50 uppercase tracking-widest mb-2">Module Format</label>
                   <select value={bType} onChange={(e: any) => setBType(e.target.value)} className="w-full bg-black/50 border border-white/10 rounded-xl p-3 text-white">
                     <option value="KPI">KPI Target Summary (Average)</option>
                     <option value="BAR">Bar Chart (Top 10 Leaders)</option>
                     <option value="SCATTER">Scatter Matrix (Cross-Reference)</option>
                   </select>
                 </div>

                 <div>
                   <label className="block text-xs font-bold text-white/50 uppercase tracking-widest mb-2">Target Position</label>
                   <select value={bPos} onChange={(e: any) => setBPos(e.target.value)} className="w-full bg-black/50 border border-white/10 rounded-xl p-3 text-white">
                     {posOptions.map(p => <option key={p} value={p}>{p}</option>)}
                   </select>
                 </div>

                 <div>
                   <label className="block text-xs font-bold text-white/50 uppercase tracking-widest mb-2">Primary Metric (X-Axis / KPI Target)</label>
                   <select value={bX} onChange={(e) => setBX(e.target.value)} className="w-full bg-black/50 border border-white/10 rounded-xl p-3 text-white">
                     {Object.keys(METRIC_MAP).map(m => <option key={m} value={m}>{m}</option>)}
                   </select>
                 </div>

                 {bType === "SCATTER" && (
                   <div>
                     <label className="block text-xs font-bold text-white/50 uppercase tracking-widest mb-2">Secondary Metric (Y-Axis)</label>
                     <select value={bY} onChange={(e) => setBY(e.target.value)} className="w-full bg-black/50 border border-white/10 rounded-xl p-3 text-white">
                       {Object.keys(METRIC_MAP).map(m => <option key={m} value={m}>{m}</option>)}
                     </select>
                   </div>
                 )}

                 <div className="pt-4">
                    <button onClick={spawnWidget} className="w-full py-4 rounded-xl bg-orange-500 text-black font-black uppercase tracking-widest text-sm hover:bg-orange-400 transition-colors">
                      Spawn Module
                    </button>
                 </div>
               </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function WidgetRenderBlock({ config, board, onRemove }: { config: WidgetConfig, board: Prospect[], onRemove: () => void }) {
  const xKey = METRIC_MAP[config.xMetricName]
  let pool = board;
  if (config.positionGroup !== "All") pool = pool.filter(p => p.position_group === config.positionGroup);
  
  // Filter nulls
  pool = pool.filter(p => p[xKey] != null);
  
  // Render Logic
  let content = null;

  if (config.type === "KPI") {
    const avg = pool.length > 0 ? (pool.reduce((sum, p) => sum + Number(p[xKey]), 0) / pool.length).toFixed(2) : "0.00";
    content = (
      <div className="flex flex-col items-center justify-center py-6">
        <span className="text-5xl font-black text-white">{avg}</span>
        <span className="text-[10px] uppercase tracking-widest text-white/50 mt-2 text-center max-w-[200px]">Class Average</span>
      </div>
    );
  }

  else if (config.type === "BAR") {
    // Top 10 by X
    pool.sort((a, b) => Number(b[xKey]) - Number(a[xKey]));
    const top10 = pool.slice(0, 10);
    const chartData = {
      labels: top10.map(p => p.name.split(" ")[1] || p.name),
      datasets: [{
        label: config.xMetricName,
        data: top10.map(p => Number(p[xKey])),
        backgroundColor: 'rgba(249, 115, 22, 0.7)'
      }]
    };
    content = (
      <div className="h-[200px] w-full">
         <Bar data={chartData} options={{ maintainAspectRatio: false, plugins:{legend:{display:false}}, scales: {x:{grid:{display:false}, ticks:{color:'rgba(255,255,255,0.4)', font:{size:9}}}, y:{grid:{color:'rgba(255,255,255,0.05)'}, ticks:{color:'rgba(255,255,255,0.4)'}}} }} />
      </div>
    );
  }

  else if (config.type === "SCATTER") {
    const yKey = METRIC_MAP[config.yMetricName];
    pool = pool.filter(p => p[yKey] != null);
    const scatterData = {
      datasets: [{
        label: config.positionGroup,
        data: pool.map(p => ({ x: Number(p[xKey]), y: Number(p[yKey]), raw: p })),
        backgroundColor: 'rgba(249, 115, 22, 0.6)',
      }]
    };
    content = (
      <div className="h-[200px] w-full">
         <Scatter data={scatterData} options={{ maintainAspectRatio: false, plugins:{legend:{display:false}, tooltip:{callbacks:{label: function(ctx:any){return `${ctx.raw.raw.name}: [${ctx.parsed.x}, ${ctx.parsed.y}]`}}}}, scales:{ x:{grid:{display:false}, ticks:{color:'rgba(255,255,255,0.4)'}}, y:{grid:{color:'rgba(255,255,255,0.05)'}, ticks:{color:'rgba(255,255,255,0.4)'}} } }} />
      </div>
    );
  }

  return (
    <motion.div 
      initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.9 }}
      className="p-6 rounded-[2rem] bg-orange-950/20 border border-orange-500/20 backdrop-blur-md flex flex-col group relative"
    >
      <button onClick={onRemove} className="absolute top-4 right-4 text-white/20 hover:text-red-500 transition-colors opacity-0 group-hover:opacity-100">
         <Trash2 size={16} />
      </button>

      <div className="mb-6 border-b border-orange-500/20 pb-4 pr-6">
        <h5 className="font-bold text-orange-400 text-sm leading-tight">
          {config.type === "SCATTER" ? `${config.positionGroup} Matrix` : `${config.positionGroup} Target`}
        </h5>
        <p className="text-white/60 text-[10px] uppercase tracking-widest mt-1">
          {config.type === "SCATTER" ? `${config.xMetricName} vs ${config.yMetricName}` : config.xMetricName}
        </p>
      </div>
      <div className="flex-grow">
        {content}
      </div>
    </motion.div>
  )
}
