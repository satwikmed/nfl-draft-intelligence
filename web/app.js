/* ============================================================
   NFL Draft Intelligence — Application Logic
   ============================================================ */

let BOARD_DATA = [];
let FEATURES = {};
let NFL_PERF = {};
let COMPS_DATA = {};
let STATS = [];
let VISIBLE_COUNT = 30;

// ── Bootstrap ──

document.addEventListener('DOMContentLoaded', async () => {
    initBackground();
    initNav();

    // Load data
    const [boardRes, featRes, nflRes, statsRes, compsRes] = await Promise.all([
        fetch('data/board.json').then(r => r.json()),
        fetch('data/features.json').then(r => r.json()),
        fetch('data/nfl_performance.json').then(r => r.json()),
        fetch('data/stats.json').then(r => r.json()),
        fetch('data/comps.json').then(r => r.json()),
    ]);

    BOARD_DATA = boardRes;
    FEATURES = featRes;
    NFL_PERF = nflRes;
    STATS = statsRes;
    COMPS_DATA = compsRes;

    // Hero stats
    document.getElementById('statProspects').textContent = BOARD_DATA.length.toLocaleString();
    if (BOARD_DATA.length > 0) {
        document.getElementById('heroScore').textContent = BOARD_DATA[0].pro_readiness_score?.toFixed(1) || '—';
    }

    renderBoard();
    renderDistChart();
    renderAnalytics();
    initFilters();
    initProfileSearch();
    initScrollReveal();
});

// ── Background Particles ──

function initBackground() {
    const canvas = document.getElementById('bgCanvas');
    const ctx = canvas.getContext('2d');
    let w, h, particles = [];

    function resize() {
        w = canvas.width = window.innerWidth;
        h = canvas.height = window.innerHeight;
    }
    resize();
    window.addEventListener('resize', resize);

    class Particle {
        constructor() { this.reset(); }
        reset() {
            this.x = Math.random() * w;
            this.y = Math.random() * h;
            this.vx = (Math.random() - 0.5) * 0.3;
            this.vy = (Math.random() - 0.5) * 0.3;
            this.r = Math.random() * 1.5 + 0.4;
            this.alpha = Math.random() * 0.5 + 0.1;
        }
        update() {
            this.x += this.vx;
            this.y += this.vy;
            if (this.x < 0 || this.x > w) this.vx *= -1;
            if (this.y < 0 || this.y > h) this.vy *= -1;
        }
        draw() {
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.r, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(99, 140, 255, ${this.alpha})`;
            ctx.fill();
        }
    }

    for (let i = 0; i < 60; i++) particles.push(new Particle());

    function loop() {
        ctx.clearRect(0, 0, w, h);
        particles.forEach(p => { p.update(); p.draw(); });

        // Connection lines
        for (let i = 0; i < particles.length; i++) {
            for (let j = i + 1; j < particles.length; j++) {
                const dx = particles[i].x - particles[j].x;
                const dy = particles[i].y - particles[j].y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < 150) {
                    ctx.beginPath();
                    ctx.moveTo(particles[i].x, particles[i].y);
                    ctx.lineTo(particles[j].x, particles[j].y);
                    ctx.strokeStyle = `rgba(99, 140, 255, ${0.06 * (1 - dist / 150)})`;
                    ctx.lineWidth = 0.5;
                    ctx.stroke();
                }
            }
        }
        requestAnimationFrame(loop);
    }
    loop();
}

// ── Navigation ──

function initNav() {
    document.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', e => {
            e.preventDefault();
            const page = link.dataset.page;

            document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
            link.classList.add('active');

            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            document.getElementById(`page-${page}`).classList.add('active');

            // Show/hide hero
            document.getElementById('hero').style.display = page === 'board' ? '' : 'none';
        });
    });
}

// ── Filters ──

function initFilters() {
    document.getElementById('filterPos').addEventListener('change', renderBoard);
    document.getElementById('filterYear').addEventListener('change', renderBoard);
    document.getElementById('filterSearch').addEventListener('input', renderBoard);
    document.getElementById('loadMoreBtn').addEventListener('click', () => {
        VISIBLE_COUNT += 30;
        renderBoard();
    });
}

// ── Board Rendering ──

function getFilteredData() {
    const pos = document.getElementById('filterPos').value;
    const year = document.getElementById('filterYear').value;
    const search = document.getElementById('filterSearch').value.toLowerCase();

    return BOARD_DATA.filter(p => {
        if (pos !== 'ALL' && p.position_group !== pos) return false;
        if (year !== 'ALL' && p.draft_year != year) return false;
        if (search && !p.name.toLowerCase().includes(search)) return false;
        return true;
    });
}

function renderBoard() {
    const data = getFilteredData();
    const tbody = document.getElementById('boardBody');
    tbody.innerHTML = '';

    const visible = data.slice(0, VISIBLE_COUNT);
    visible.forEach((p, i) => {
        const tr = document.createElement('tr');
        tr.style.animationDelay = `${i * 0.02}s`;
        tr.addEventListener('click', () => openProfile(p.player_id));

        const score = p.pro_readiness_score;
        const scoreClass = score >= 70 ? 'score-high' : score >= 40 ? 'score-mid' : 'score-low';
        const career = p.predicted_career_length ? p.predicted_career_length.toFixed(1) : '—';

        tr.innerHTML = `
            <td class="col-rank">${i + 1}</td>
            <td>
                <div class="player-name">${p.name}</div>
                <div class="player-meta">${p.height_inches ? formatHeight(p.height_inches) : ''} ${p.weight_lbs ? p.weight_lbs + ' lbs' : ''}</div>
            </td>
            <td><span class="pos-badge pos-${p.position_group}">${p.position_group}</span></td>
            <td class="col-school">${p.school || ''}</td>
            <td>
                <div class="draft-info">
                    ${p.draft_round ? `<span class="draft-round">${p.draft_round}</span>` : ''}
                    <div>
                        <div class="draft-details">Pick ${p.draft_pick || '—'}</div>
                        <div class="draft-details">${p.team || ''}</div>
                    </div>
                </div>
            </td>
            <td class="col-score"><span class="score-pill ${scoreClass}">${score?.toFixed(1) || '—'}</span></td>
            <td class="col-career">${career}</td>
            <td class="col-action">
                <button class="view-btn" title="View Profile">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
                </button>
            </td>
        `;
        tbody.appendChild(tr);
    });

    document.getElementById('loadMoreBtn').style.display = data.length > VISIBLE_COUNT ? '' : 'none';
}

function formatHeight(inches) {
    if (!inches) return '';
    const ft = Math.floor(inches / 12);
    const inn = Math.round(inches % 12);
    return `${ft}'${inn}"`;
}

// ── Distribution Chart ──

function renderDistChart() {
    const scores = BOARD_DATA.map(p => p.pro_readiness_score).filter(Boolean);
    const bins = Array(20).fill(0);
    scores.forEach(s => {
        const idx = Math.min(Math.floor(s / 5), 19);
        bins[idx]++;
    });

    const ctx = document.getElementById('distChart').getContext('2d');
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: bins.map((_, i) => `${i * 5}-${(i + 1) * 5}`),
            datasets: [{
                data: bins,
                backgroundColor: bins.map((_, i) => {
                    const t = i / 19;
                    return `rgba(${Math.round(239 - t * 180)}, ${Math.round(68 + t * 146)}, ${Math.round(68 + t * 92)}, 0.7)`;
                }),
                borderColor: bins.map((_, i) => {
                    const t = i / 19;
                    return `rgba(${Math.round(239 - t * 180)}, ${Math.round(68 + t * 146)}, ${Math.round(68 + t * 92)}, 1)`;
                }),
                borderWidth: 1,
                borderRadius: 4,
            }]
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: {
                x: {
                    grid: { color: 'rgba(255,255,255,0.04)' },
                    ticks: { color: '#64748b', font: { size: 10 }, maxRotation: 45 },
                },
                y: {
                    grid: { color: 'rgba(255,255,255,0.04)' },
                    ticks: { color: '#64748b' },
                }
            }
        }
    });
}

// ── Player Profile ──

function openProfile(playerId) {
    const p = BOARD_DATA.find(d => d.player_id === playerId);
    if (!p) return;

    const modal = document.getElementById('playerModal');
    const content = document.getElementById('modalContent');
    const feats = FEATURES[playerId] || {};
    const nfl = NFL_PERF[playerId] || [];

    // Combine stats
    const combineMetrics = [
        { key: 'forty_yard', label: '40-Yard', unit: 's', lower: true },
        { key: 'bench_press', label: 'Bench', unit: 'reps', lower: false },
        { key: 'vertical_jump', label: 'Vertical', unit: '"', lower: false },
        { key: 'broad_jump', label: 'Broad Jump', unit: '"', lower: false },
        { key: 'three_cone', label: '3-Cone', unit: 's', lower: true },
        { key: 'shuttle', label: 'Shuttle', unit: 's', lower: true },
    ];

    const combineHTML = combineMetrics.map(m => {
        const val = p[m.key];
        const pctile = feats[`${m.key}_percentile`];
        if (!val) return `<div class="combine-stat"><div class="combine-stat-val" style="color:var(--text-muted)">—</div><div class="combine-stat-label">${m.label}</div></div>`;

        const pctileColor = pctile >= 70 ? 'var(--accent-3)' : pctile >= 40 ? 'var(--accent-warn)' : 'var(--accent-danger)';
        return `
            <div class="combine-stat">
                <div class="combine-stat-val">${val}${m.unit}</div>
                <div class="combine-stat-label">${m.label}</div>
                ${pctile != null ? `<div class="combine-stat-pctile" style="color:${pctileColor}">${pctile.toFixed(0)}th pctile</div>` : ''}
            </div>`;
    }).join('');

    // Radar chart data
    const radarLabels = [];
    const radarValues = [];
    combineMetrics.forEach(m => {
        const pctile = feats[`${m.key}_percentile`];
        if (pctile != null) {
            radarLabels.push(m.label);
            radarValues.push(pctile);
        }
    });

    // Comps
    const pComps = COMPS_DATA[playerId]?.comps || [];
    const compsHTML = pComps.length > 0 ? `
        <div class="comp-list">
            ${pComps.map(c => `
                <div class="comp-card">
                    <div class="comp-sim">${c.sim.toFixed(1)}%</div>
                    <div>
                        <div class="comp-name">${c.name}</div>
                        <div class="comp-detail">Similarity Score</div>
                    </div>
                </div>
            `).join('')}
        </div>` : '<p style="color:var(--text-muted);text-align:center;padding:20px;">No matches found</p>';

    // Scouting Report
    const reportText = generateScoutingReport(p, feats);

    // NFL career chart
    let careerChartHTML = '';
    if (nfl.length > 0) {
        careerChartHTML = `
            <div class="profile-card profile-card-full">
                <h4>NFL Career Performance</h4>
                <canvas id="modalCareerChart" height="180"></canvas>
            </div>`;
    }

    const scoreVal = p.pro_readiness_score;
    const scoreColor = scoreVal >= 70 ? 'var(--accent-3)' : scoreVal >= 40 ? 'var(--accent-warn)' : 'var(--accent-danger)';
    const initials = p.name.split(' ').map(w => w[0]).join('').slice(0, 2);

    content.innerHTML = `
        <button class="modal-close" onclick="closeModal()">✕</button>

        <div class="profile-header">
            <div class="profile-avatar">${initials}</div>
            <div class="profile-info">
                <h2>${p.name}</h2>
                <div class="profile-tags">
                    <span class="pos-badge pos-${p.position_group}">${p.position_group}</span>
                    <span class="profile-tag">${p.school}</span>
                    <span class="profile-tag">${p.draft_year} Draft</span>
                    ${p.team ? `<span class="profile-tag">${p.team}</span>` : ''}
                    ${p.draft_round ? `<span class="profile-tag">Rd ${p.draft_round}, Pick ${p.draft_pick}</span>` : ''}
                </div>
            </div>
            <div class="profile-scores">
                <div class="profile-score-box">
                    <div class="profile-score-val" style="color:${scoreColor}">${scoreVal?.toFixed(1) || '—'}</div>
                    <div class="profile-score-label">Pro Readiness</div>
                </div>
                ${p.predicted_career_length ? `
                <div class="profile-score-box">
                    <div class="profile-score-val" style="color:var(--accent-1)">${p.predicted_career_length.toFixed(1)}</div>
                    <div class="profile-score-label">Career (yrs)</div>
                </div>` : ''}
            </div>
        </div>

        <div class="profile-body">
            <div class="scouting-report">
                <div class="report-title">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                    AI Scouting Report
                </div>
                <div class="report-text">${reportText}</div>
            </div>

            <div class="profile-grid">
                <div class="profile-card">
                    <h4>Athletic Profile</h4>
                    <div class="combine-grid">${combineHTML}</div>
                </div>
                <div class="profile-card">
                    <h4>Radar Chart</h4>
                    ${radarValues.length >= 3 ? '<canvas id="modalRadar" height="240"></canvas>' : '<p style="color:var(--text-muted);text-align:center;padding:40px;">Insufficient combine data</p>'}
                </div>
                <div class="profile-card">
                    <h4>Top Comparisons</h4>
                    ${compsHTML}
                </div>
                <div class="profile-card">
                    <h4>Physical Profile</h4>
                    ${renderPhysicalProfile(p)}
                </div>
                ${careerChartHTML}
                <div class="profile-card profile-card-full">
                    <h4>Technical Evaluation</h4>
                    ${renderFeatureList(feats)}
                </div>
            </div>
        </div>
    `;

    modal.classList.add('active');
    document.body.style.overflow = 'hidden';

    // Render radar chart
    if (radarValues.length >= 3) {
        setTimeout(() => {
            const radarCtx = document.getElementById('modalRadar').getContext('2d');
            new Chart(radarCtx, {
                type: 'radar',
                data: {
                    labels: radarLabels,
                    datasets: [{
                        data: radarValues,
                        backgroundColor: 'rgba(99, 140, 255, 0.15)',
                        borderColor: 'rgba(99, 140, 255, 0.8)',
                        borderWidth: 2,
                        pointBackgroundColor: 'rgba(99, 140, 255, 1)',
                        pointBorderColor: '#fff',
                        pointRadius: 4,
                    }]
                },
                options: {
                    responsive: true,
                    plugins: { legend: { display: false } },
                    scales: {
                        r: {
                            min: 0, max: 100,
                            grid: { color: 'rgba(255,255,255,0.06)' },
                            angleLines: { color: 'rgba(255,255,255,0.06)' },
                            ticks: { display: false },
                            pointLabels: { color: '#94a3b8', font: { size: 11, weight: '600' } },
                        }
                    }
                }
            });
        }, 50);
    }

    // NFL career chart
    if (nfl.length > 0) {
        setTimeout(() => {
            const carCtx = document.getElementById('modalCareerChart');
            if (!carCtx) return;

            const datasets = [];
            const seasons = nfl.map(n => n.season);

            if (p.position_group === 'QB') {
                datasets.push({
                    label: 'Pass Yards',
                    data: nfl.map(n => n.passing_yards || 0),
                    backgroundColor: 'rgba(99,140,255,0.6)',
                    borderColor: 'rgba(99,140,255,1)',
                    borderWidth: 1,
                    borderRadius: 4,
                });
            } else if (['RB'].includes(p.position_group)) {
                datasets.push({
                    label: 'Rush Yards',
                    data: nfl.map(n => n.rushing_yards || 0),
                    backgroundColor: 'rgba(99,140,255,0.6)',
                    borderColor: 'rgba(99,140,255,1)',
                    borderWidth: 1,
                    borderRadius: 4,
                });
                datasets.push({
                    label: 'Rec Yards',
                    data: nfl.map(n => n.receiving_yards || 0),
                    backgroundColor: 'rgba(168,85,247,0.5)',
                    borderColor: 'rgba(168,85,247,1)',
                    borderWidth: 1,
                    borderRadius: 4,
                });
            } else if (['WR', 'TE'].includes(p.position_group)) {
                datasets.push({
                    label: 'Rec Yards',
                    data: nfl.map(n => n.receiving_yards || 0),
                    backgroundColor: 'rgba(168,85,247,0.6)',
                    borderColor: 'rgba(168,85,247,1)',
                    borderWidth: 1,
                    borderRadius: 4,
                });
            } else {
                datasets.push({
                    label: 'Tackles',
                    data: nfl.map(n => n.tackles || 0),
                    backgroundColor: 'rgba(99,140,255,0.6)',
                    borderColor: 'rgba(99,140,255,1)',
                    borderWidth: 1,
                    borderRadius: 4,
                });
                datasets.push({
                    label: 'Sacks',
                    data: nfl.map(n => n.sacks || 0),
                    backgroundColor: 'rgba(239,68,68,0.5)',
                    borderColor: 'rgba(239,68,68,1)',
                    borderWidth: 1,
                    borderRadius: 4,
                });
            }

            new Chart(carCtx.getContext('2d'), {
                type: 'bar',
                data: { labels: seasons, datasets },
                options: {
                    responsive: true,
                    plugins: { legend: { labels: { color: '#94a3b8', font: { size: 11 } } } },
                    scales: {
                        x: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#64748b' } },
                        y: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#64748b' } },
                    }
                }
            });
        }, 100);
    }
}

function renderFeatureList(feats) {
    const display = [
        { key: 'athletic_composite', label: 'Athletic Composite', fmt: v => v.toFixed(2) },
        { key: 'speed_score', label: 'Speed Score', fmt: v => v.toFixed(1) },
        { key: 'bmi', label: 'BMI', fmt: v => v.toFixed(1) },
        { key: 'draft_capital_value', label: 'Draft Capital', fmt: v => v.toFixed(1) },
        { key: 'college_seasons', label: 'College Seasons', fmt: v => v.toFixed(0) },
    ];

    const items = display
        .filter(d => feats[d.key] != null)
        .map(d => `
            <div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.04);">
                <span style="color:var(--text-secondary);font-size:0.88em">${d.label}</span>
                <span style="font-family:'JetBrains Mono',monospace;font-weight:600;font-size:0.92em">${d.fmt(feats[d.key])}</span>
            </div>
        `).join('');

    return items || '<p style="color:var(--text-muted);text-align:center;padding:20px;">No features computed</p>';
}

function renderPhysicalProfile(p) {
    const items = [];
    if (p.height_inches) items.push(`<div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.04);"><span style="color:var(--text-secondary);font-size:0.88em">Height</span><span style="font-family:'JetBrains Mono',monospace;font-weight:600">${formatHeight(p.height_inches)}</span></div>`);
    if (p.weight_lbs) items.push(`<div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.04);"><span style="color:var(--text-secondary);font-size:0.88em">Weight</span><span style="font-family:'JetBrains Mono',monospace;font-weight:600">${p.weight_lbs} lbs</span></div>`);
    if (p.draft_year) items.push(`<div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.04);"><span style="color:var(--text-secondary);font-size:0.88em">Draft Year</span><span style="font-family:'JetBrains Mono',monospace;font-weight:600">${p.draft_year}</span></div>`);
    if (p.draft_round) items.push(`<div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.04);"><span style="color:var(--text-secondary);font-size:0.88em">Draft</span><span style="font-family:'JetBrains Mono',monospace;font-weight:600">Rd ${p.draft_round}, Pick ${p.draft_pick}</span></div>`);
    if (p.team) items.push(`<div style="display:flex;justify-content:space-between;padding:8px 0;"><span style="color:var(--text-secondary);font-size:0.88em">Team</span><span style="font-weight:600">${p.team}</span></div>`);
    return items.join('') || '<p style="color:var(--text-muted);text-align:center;padding:20px;">No data</p>';
}

function closeModal() {
    document.getElementById('playerModal').classList.remove('active');
    document.body.style.overflow = '';
}

document.querySelector('.modal-backdrop')?.addEventListener('click', closeModal);
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });

// ── Profile Search ──

function initProfileSearch() {
    const input = document.getElementById('profileSearch');
    const results = document.getElementById('profileSearchResults');
    if (!input || !results) return;

    input.addEventListener('input', () => {
        const q = input.value.toLowerCase().trim();
        results.innerHTML = '';
        if (q.length < 2) return;

        const matches = BOARD_DATA.filter(p => p.name.toLowerCase().includes(q)).slice(0, 10);
        matches.forEach(p => {
            const div = document.createElement('div');
            div.className = 'search-result';
            div.innerHTML = `
                <div class="search-result-name">${p.name}</div>
                <div class="search-result-meta">${p.position_group} · ${p.school} · ${p.draft_year}</div>
            `;
            div.addEventListener('click', () => {
                openProfile(p.player_id);
                results.innerHTML = '';
                input.value = '';
            });
            results.appendChild(div);
        });
    });
}

// ── Analytics ──

function renderAnalytics() {
    if (!STATS.length) return;

    // Position avg score chart
    const posCtx = document.getElementById('posChart').getContext('2d');
    const posColors = {
        QB: '#f87171', RB: '#60a5fa', WR: '#c084fc', TE: '#34d399',
        OL: '#fbbf24', DL: '#f472b6', LB: '#38bdf8', DB: '#a78bfa'
    };

    new Chart(posCtx, {
        type: 'bar',
        data: {
            labels: STATS.map(s => s.position_group),
            datasets: [{
                label: 'Avg Pro Readiness Score',
                data: STATS.map(s => s.avg_score),
                backgroundColor: STATS.map(s => posColors[s.position_group] || '#666').map(c => c + '99'),
                borderColor: STATS.map(s => posColors[s.position_group] || '#666'),
                borderWidth: 1,
                borderRadius: 6,
            }]
        },
        options: {
            responsive: true,
            indexAxis: 'y',
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#64748b' }, min: 0, max: 100 },
                y: { grid: { display: false }, ticks: { color: '#94a3b8', font: { weight: '600' } } },
            }
        }
    });

    // Career length chart
    const carCtx = document.getElementById('careerChart').getContext('2d');
    new Chart(carCtx, {
        type: 'bar',
        data: {
            labels: STATS.map(s => s.position_group),
            datasets: [{
                label: 'Avg Predicted Career (yrs)',
                data: STATS.map(s => s.avg_career),
                backgroundColor: STATS.map(s => posColors[s.position_group] || '#666').map(c => c + '66'),
                borderColor: STATS.map(s => posColors[s.position_group] || '#666'),
                borderWidth: 1,
                borderRadius: 6,
            }]
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { display: false }, ticks: { color: '#94a3b8', font: { weight: '600' } } },
                y: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#64748b' } },
            }
        }
    });

    // Scatter: score vs pick
    const scatterCtx = document.getElementById('scatterChart').getContext('2d');
    const scatterData = BOARD_DATA
        .filter(p => p.draft_pick && p.pro_readiness_score)
        .slice(0, 300)
        .map(p => ({
            x: p.draft_pick,
            y: p.pro_readiness_score,
            pos: p.position_group,
        }));

    const posList = ['QB', 'RB', 'WR', 'TE', 'OL', 'DL', 'LB', 'DB'];
    const scatterDatasets = posList.map(pos => ({
        label: pos,
        data: scatterData.filter(d => d.pos === pos),
        backgroundColor: (posColors[pos] || '#666') + '88',
        borderColor: posColors[pos] || '#666',
        pointRadius: 4,
        pointHoverRadius: 6,
    }));

    new Chart(scatterCtx, {
        type: 'scatter',
        data: { datasets: scatterDatasets },
        options: {
            responsive: true,
            plugins: {
                legend: { labels: { color: '#94a3b8', font: { size: 11 }, usePointStyle: true, pointStyle: 'circle' } },
            },
            scales: {
                x: {
                    title: { display: true, text: 'Draft Pick', color: '#64748b' },
                    grid: { color: 'rgba(255,255,255,0.04)' },
                    ticks: { color: '#64748b' },
                },
                y: {
                    title: { display: true, text: 'Pro Readiness Score', color: '#64748b' },
                    grid: { color: 'rgba(255,255,255,0.04)' },
                    ticks: { color: '#64748b' },
                    min: 0, max: 100,
                },
            }
        }
    });

    // Position stat cards
    const posCards = document.getElementById('posCards');
    STATS.forEach(s => {
        const color = posColors[s.position_group] || '#666';
        posCards.innerHTML += `
            <div class="pos-card" style="--accent-col:${color}">
                <div class="pos-card-title" style="color:${color}">${s.position_group}</div>
                <div class="pos-card-sub">${s.total.toLocaleString()} prospects</div>
                <div class="pos-card-stat" style="color:${color}">${s.avg_score.toFixed(1)}</div>
                <div class="pos-card-label">Avg Score</div>
            </div>
        `;
    });
}

// ── Helpers ──

function generateScoutingReport(p, feats) {
    const pos = p.position_group;
    const score = p.pro_readiness_score;
    let report = "";

    if (score >= 75) {
        report = `${p.name} is an elite ${pos} prospect with a rare blend of physical traits and proven performance. Our model identifies him as a high-probability NFL starter with All-Pro ceiling. `;
    } else if (score >= 55) {
        report = `${p.name} projects as a reliable ${pos} contributor with the versatility to start early in his career. He shows strong baseline metrics in key success indicators. `;
    } else if (score >= 35) {
        report = `${p.name} possesses specific athletic advantages but may require significant technical refinement at the next level. High-upside developmental piece. `;
    } else {
        report = `${p.name} enters the draft as a deep sleeper with specialized situational value. His path to a long-term roster spot depends on immediate special teams impact. `;
    }

    if (feats.athletic_composite > 0.8) {
        report += "His athletic composite score is exceptional, placing him in the top tier of historical peers. ";
    }
    if (feats.speed_score > 105) {
        report += `Displays explosive vertical speed (Speed Score: ${feats.speed_score.toFixed(1)}), a key differentiator in today's NFL. `;
    }
    if (feats.college_seasons >= 4) {
        report += "Considerable college experience suggests a more polished technical floor than younger peers. ";
    }

    return report;
}

function initScrollReveal() {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
            }
        });
    }, { threshold: 0.1 });

    function refresh() {
        document.querySelectorAll('.reveal').forEach(el => observer.observe(el));
    }

    refresh();
    
    // Refresh when changing pages or loading board
    window.addEventListener('pageChanged', refresh);
    const originalRenderBoard = renderBoard;
    renderBoard = (...args) => {
        originalRenderBoard(...args);
        setTimeout(refresh, 50);
    };
}
