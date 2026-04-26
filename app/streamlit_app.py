"""
NFL Draft Intelligence System — Streamlit Dashboard.

Multi-page app with:
1. Big Board: ranked prospects with Pro Readiness Scores
2. Player Profile: deep-dive with SHAP explanations and comps
3. Comp Explorer: similarity search across history
4. Draft Simulator: mock-draft based on model predictions
"""

import sys
from pathlib import Path

# Ensure project root is on path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

from src.utils.db import query_df, get_table_counts
from src.features.builder import get_feature_matrix
from src.models.comp_engine import find_comps
from src.models.survival import get_survival_curve

# =============================================================================
# Page Config
# =============================================================================

st.set_page_config(
    page_title="NFL Draft Intelligence",
    page_icon="🏈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    .stApp {
        font-family: 'Inter', sans-serif;
    }

    /* Dark sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0a1628 0%, #1a2744 100%);
    }

    [data-testid="stSidebar"] * {
        color: #e2e8f0 !important;
    }

    /* Score badges */
    .score-high { color: #10b981; font-weight: 700; font-size: 1.5em; }
    .score-mid  { color: #f59e0b; font-weight: 700; font-size: 1.5em; }
    .score-low  { color: #ef4444; font-weight: 700; font-size: 1.5em; }

    /* Card styling */
    .metric-card {
        background: linear-gradient(135deg, #1e293b, #334155);
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        border: 1px solid #475569;
    }
    .metric-card h3 { color: #94a3b8; font-size: 0.85em; margin: 0; }
    .metric-card h1 { color: #f1f5f9; margin: 5px 0 0 0; }

    /* Headers */
    .big-header {
        font-size: 2.5em;
        font-weight: 800;
        background: linear-gradient(135deg, #3b82f6, #8b5cf6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5em;
    }

    div[data-testid="stMetricValue"] {
        font-size: 2em;
        font-weight: 700;
    }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# Sidebar Navigation
# =============================================================================

st.sidebar.markdown("# 🏈 Draft Intel")
st.sidebar.markdown("---")
page = st.sidebar.radio(
    "Navigate",
    ["📊 Big Board", "👤 Player Profile", "🔍 Comp Explorer", "📈 Analytics"],
    label_visibility="collapsed",
)

# Database stats in sidebar
with st.sidebar.expander("📦 Database Stats"):
    try:
        counts = get_table_counts()
        for table, count in counts.items():
            st.text(f"{table}: {count:,}")
    except:
        st.text("DB not initialized")


# =============================================================================
# Helper Functions
# =============================================================================

def score_color(score: float) -> str:
    if score >= 70: return "score-high"
    elif score >= 40: return "score-mid"
    return "score-low"

def score_badge(score: float) -> str:
    cls = score_color(score)
    return f'<span class="{cls}">{score:.1f}</span>'

def get_big_board(position: str = "ALL", year: int = None) -> pd.DataFrame:
    """Get ranked prospects with Pro Readiness Scores."""
    sql = """
        SELECT p.player_id, p.name, p.school, p.position, p.position_group,
               p.draft_year, p.height_inches, p.weight_lbs,
               d.round as draft_round, d.pick as draft_pick, d.team,
               pred.pro_readiness_score,
               pred.predicted_career_length,
               pred.comp_1_id, pred.comp_1_similarity,
               pred.comp_2_id, pred.comp_2_similarity,
               pred.comp_3_id, pred.comp_3_similarity
        FROM prospects p
        INNER JOIN draft_picks d ON p.player_id = d.player_id
        LEFT JOIN predictions pred ON p.player_id = pred.player_id
        WHERE p.position_group IS NOT NULL
    """
    params = []
    if position != "ALL":
        sql += " AND p.position_group = ?"
        params.append(position)
    if year:
        sql += " AND p.draft_year = ?"
        params.append(year)

    sql += " ORDER BY pred.pro_readiness_score DESC NULLS LAST"

    return query_df(sql, tuple(params) if params else None)


# =============================================================================
# Pages
# =============================================================================

if page == "📊 Big Board":
    st.markdown('<div class="big-header">NFL Draft Big Board</div>', unsafe_allow_html=True)
    st.markdown("*AI-powered prospect rankings using combine, college production, and historical modeling*")

    col1, col2, col3 = st.columns(3)
    with col1:
        positions = ["ALL"] + ["QB", "RB", "WR", "TE", "OL", "DL", "LB", "DB"]
        pos_filter = st.selectbox("Position Group", positions)
    with col2:
        years = list(range(2025, 1999, -1))
        year_filter = st.selectbox("Draft Year", years)
    with col3:
        top_n = st.slider("Show Top N", 10, 200, 50)

    board = get_big_board(pos_filter, year_filter)

    if board.empty:
        st.warning("No prospects found for these filters.")
    else:
        # Summary metrics
        scored = board[board["pro_readiness_score"].notna()]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Prospects", len(board))
        m2.metric("With Scores", len(scored))
        m3.metric("Avg Score", f"{scored['pro_readiness_score'].mean():.1f}" if len(scored) > 0 else "—")
        m4.metric("Med Career (yrs)", f"{scored['predicted_career_length'].median():.1f}" if scored['predicted_career_length'].notna().any() else "—")

        st.divider()

        # Display big board
        display = board.head(top_n)[[
            "name", "position_group", "school", "draft_year",
            "draft_round", "draft_pick", "team",
            "pro_readiness_score", "predicted_career_length"
        ]].copy()

        display.columns = [
            "Name", "Pos", "School", "Year",
            "Rd", "Pick", "Team",
            "Pro Score", "Career (yrs)"
        ]

        display["Rank"] = range(1, len(display) + 1)
        display = display[["Rank"] + [c for c in display.columns if c != "Rank"]]

        # Score distribution
        st.subheader("Score Distribution")
        if len(scored) > 0:
            fig = px.histogram(
                scored, x="pro_readiness_score",
                nbins=30,
                color_discrete_sequence=["#3b82f6"],
                labels={"pro_readiness_score": "Pro Readiness Score"},
            )
            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("Rankings")
        st.dataframe(
            display.style.format({
                "Pro Score": "{:.1f}",
                "Career (yrs)": "{:.1f}",
            }).background_gradient(
                cmap="RdYlGn", subset=["Pro Score"], vmin=0, vmax=100
            ),
            use_container_width=True,
            height=600,
        )


elif page == "👤 Player Profile":
    st.markdown('<div class="big-header">Player Profile</div>', unsafe_allow_html=True)

    # Player search
    search = st.text_input("🔍 Search player by name", "Patrick Mahomes")

    if search:
        results = query_df(
            "SELECT player_id, name, school, position_group, draft_year FROM prospects WHERE name LIKE ? AND position_group IS NOT NULL ORDER BY draft_year DESC LIMIT 20",
            (f"%{search}%",)
        )

        if results.empty:
            st.warning("No players found.")
        else:
            selected = st.selectbox(
                "Select player",
                results["player_id"].tolist(),
                format_func=lambda pid: f"{results[results['player_id']==pid].iloc[0]['name']} ({results[results['player_id']==pid].iloc[0]['school']}, {int(results[results['player_id']==pid].iloc[0]['draft_year'])})"
            )

            if selected:
                pdata = query_df(
                    """SELECT p.*, d.round, d.pick, d.team,
                              pred.pro_readiness_score, pred.predicted_career_length,
                              c.forty_yard, c.bench_press, c.vertical_jump,
                              c.broad_jump, c.three_cone, c.shuttle
                       FROM prospects p
                       LEFT JOIN draft_picks d ON p.player_id = d.player_id
                       LEFT JOIN predictions pred ON p.player_id = pred.player_id
                       LEFT JOIN combine_results c ON p.player_id = c.player_id
                       WHERE p.player_id = ?""",
                    (selected,)
                )

                if not pdata.empty:
                    p = pdata.iloc[0]

                    # Header
                    c1, c2, c3 = st.columns([2, 1, 1])
                    with c1:
                        st.header(p["name"])
                        st.caption(f"{p['position']} | {p['school']} | {int(p['draft_year'])}")
                        if pd.notna(p.get("round")):
                            st.caption(f"Drafted: Round {int(p['round'])}, Pick {int(p['pick'])} by {p['team']}")

                    with c2:
                        score = p.get("pro_readiness_score")
                        if pd.notna(score):
                            st.metric("Pro Readiness", f"{score:.1f}/100")
                        else:
                            st.metric("Pro Readiness", "N/A")

                    with c3:
                        career = p.get("predicted_career_length")
                        if pd.notna(career):
                            st.metric("Predicted Career", f"{career:.1f} yrs")
                        else:
                            st.metric("Predicted Career", "N/A")

                    st.divider()

                    # Combine radar chart
                    col_left, col_right = st.columns(2)

                    with col_left:
                        st.subheader("Athletic Profile")
                        combine_metrics = {
                            "40-Yard": p.get("forty_yard"),
                            "Bench": p.get("bench_press"),
                            "Vertical": p.get("vertical_jump"),
                            "Broad Jump": p.get("broad_jump"),
                            "3-Cone": p.get("three_cone"),
                            "Shuttle": p.get("shuttle"),
                        }

                        valid = {k: v for k, v in combine_metrics.items() if pd.notna(v)}
                        if valid:
                            metrics_df = pd.DataFrame([valid])
                            st.dataframe(metrics_df, use_container_width=True)

                            # Get percentiles
                            features = query_df(
                                "SELECT feature_name, feature_value FROM features WHERE player_id = ? AND feature_name LIKE '%_percentile'",
                                (selected,)
                            )
                            if not features.empty:
                                pctile_data = dict(zip(features["feature_name"], features["feature_value"]))
                                categories = list(pctile_data.keys())
                                values = list(pctile_data.values())

                                fig = go.Figure(data=go.Scatterpolar(
                                    r=values + [values[0]],
                                    theta=[c.replace("_percentile", "").replace("_", " ").title() for c in categories] + [categories[0].replace("_percentile", "").replace("_", " ").title()],
                                    fill='toself',
                                    fillcolor='rgba(59, 130, 246, 0.2)',
                                    line=dict(color='#3b82f6'),
                                ))
                                fig.update_layout(
                                    polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                                    template="plotly_dark",
                                    paper_bgcolor="rgba(0,0,0,0)",
                                    height=350,
                                    margin=dict(t=30, b=30),
                                )
                                st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.info("No combine data available.")

                    with col_right:
                        st.subheader("Historical Comps")
                        try:
                            comps = find_comps(selected, n_comps=5)
                            if comps:
                                for comp in comps:
                                    with st.container(border=True):
                                        st.markdown(f"**{comp['comp_name']}** — {comp['similarity']:.1f}% match")
                                        nfl = comp.get("nfl_summary", {})
                                        if nfl.get("seasons", 0) > 0:
                                            st.caption(f"{nfl['seasons']} NFL seasons, {nfl.get('total_games', 0)} games")
                                            for k, v in nfl.items():
                                                if k.startswith("career_"):
                                                    st.caption(f"  {k.replace('career_', '').replace('_', ' ').title()}: {v:,}")
                            else:
                                st.info("No comps available.")
                        except Exception as e:
                            st.error(f"Comp error: {e}")

                    # NFL Performance
                    nfl_perf = query_df(
                        "SELECT * FROM nfl_performance WHERE player_id = ? ORDER BY season",
                        (selected,)
                    )
                    if not nfl_perf.empty:
                        st.divider()
                        st.subheader("NFL Career Performance")

                        pos_group = p["position_group"]
                        if pos_group == "QB":
                            fig = go.Figure()
                            fig.add_trace(go.Bar(x=nfl_perf["season"], y=nfl_perf["passing_yards"], name="Pass Yards", marker_color="#3b82f6"))
                            fig.add_trace(go.Scatter(x=nfl_perf["season"], y=nfl_perf["passing_tds"]*100, name="TDs (×100)", mode='lines+markers', line=dict(color="#10b981")))
                            fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", barmode="group")
                            st.plotly_chart(fig, use_container_width=True)
                        elif pos_group in ("RB", "WR", "TE"):
                            fig = go.Figure()
                            if pos_group == "RB":
                                fig.add_trace(go.Bar(x=nfl_perf["season"], y=nfl_perf["rushing_yards"], name="Rush Yards", marker_color="#3b82f6"))
                            fig.add_trace(go.Bar(x=nfl_perf["season"], y=nfl_perf["receiving_yards"], name="Rec Yards", marker_color="#8b5cf6"))
                            fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", barmode="group")
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            fig = go.Figure()
                            fig.add_trace(go.Bar(x=nfl_perf["season"], y=nfl_perf["tackles"], name="Tackles", marker_color="#3b82f6"))
                            fig.add_trace(go.Bar(x=nfl_perf["season"], y=nfl_perf["sacks"], name="Sacks", marker_color="#ef4444"))
                            fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", barmode="group")
                            st.plotly_chart(fig, use_container_width=True)


elif page == "🔍 Comp Explorer":
    st.markdown('<div class="big-header">Comp Explorer</div>', unsafe_allow_html=True)
    st.markdown("*Find historical NFL player comparisons for any prospect*")

    search = st.text_input("🔍 Search player", "Josh Allen")
    n_comps = st.slider("Number of comps", 3, 10, 5)

    if search:
        results = query_df(
            """SELECT p.player_id, p.name, p.school, p.position_group, p.draft_year
               FROM prospects p
               INNER JOIN draft_picks d ON p.player_id = d.player_id
               WHERE p.name LIKE ? AND p.position_group IS NOT NULL
               ORDER BY p.draft_year DESC LIMIT 10""",
            (f"%{search}%",)
        )

        if not results.empty:
            selected = st.selectbox(
                "Select player",
                results["player_id"].tolist(),
                format_func=lambda pid: f"{results[results['player_id']==pid].iloc[0]['name']} ({results[results['player_id']==pid].iloc[0]['school']}, {int(results[results['player_id']==pid].iloc[0]['draft_year'])})"
            )

            if selected and st.button("Find Comps", type="primary"):
                with st.spinner("Computing similarity..."):
                    comps = find_comps(selected, n_comps=n_comps)

                if comps:
                    for i, comp in enumerate(comps, 1):
                        with st.container(border=True):
                            c1, c2 = st.columns([3, 1])
                            with c1:
                                st.markdown(f"### #{i} {comp['comp_name']}")
                                nfl = comp.get("nfl_summary", {})
                                if nfl.get("seasons", 0) > 0:
                                    stats = []
                                    for k, v in nfl.items():
                                        if k.startswith("career_"):
                                            stats.append(f"{k.replace('career_', '').replace('_', ' ').title()}: **{v:,}**")
                                    st.markdown(f"📊 {nfl['seasons']} seasons, {nfl.get('total_games', 0)} games")
                                    st.markdown(" | ".join(stats[:4]))

                            with c2:
                                st.metric("Similarity", f"{comp['similarity']:.1f}%")

                            if comp.get("matching_features"):
                                with st.expander("🔗 Matching Features"):
                                    for feat in comp["matching_features"]:
                                        st.text(f"  {feat['feature']}: {feat['target_value']} vs {feat['comp_value']}")
                else:
                    st.warning("No comps found.")
        else:
            st.warning("Player not found.")


elif page == "📈 Analytics":
    st.markdown('<div class="big-header">Draft Analytics</div>', unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["📊 Score Distribution", "📈 Position Analysis", "🔬 Survival"])

    with tab1:
        st.subheader("Pro Readiness Score Distribution by Position")
        scores = query_df("""
            SELECT p.position_group, pred.pro_readiness_score
            FROM predictions pred
            INNER JOIN prospects p ON pred.player_id = p.player_id
            WHERE pred.pro_readiness_score IS NOT NULL
              AND p.position_group IS NOT NULL
        """)

        if not scores.empty:
            fig = px.box(
                scores, x="position_group", y="pro_readiness_score",
                color="position_group",
                color_discrete_sequence=px.colors.qualitative.Set2,
                labels={"position_group": "Position", "pro_readiness_score": "Score"},
            )
            fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.subheader("Draft Efficiency by Position")
        efficiency = query_df("""
            SELECT p.position_group,
                   AVG(pred.pro_readiness_score) as avg_score,
                   COUNT(*) as n_players,
                   AVG(d.round) as avg_round
            FROM predictions pred
            INNER JOIN prospects p ON pred.player_id = p.player_id
            INNER JOIN draft_picks d ON p.player_id = d.player_id
            WHERE pred.pro_readiness_score IS NOT NULL
              AND p.position_group IS NOT NULL
            GROUP BY p.position_group
        """)

        if not efficiency.empty:
            fig = px.scatter(
                efficiency, x="avg_round", y="avg_score",
                size="n_players", color="position_group",
                labels={"avg_round": "Avg Draft Round", "avg_score": "Avg Pro Readiness Score"},
                color_discrete_sequence=px.colors.qualitative.Set2,
                text="position_group",
            )
            fig.update_traces(textposition="top center")
            fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

    with tab3:
        st.subheader("Career Survival by Position")
        survival = query_df("""
            SELECT p.position_group, pred.predicted_career_length
            FROM predictions pred
            INNER JOIN prospects p ON pred.player_id = p.player_id
            WHERE pred.predicted_career_length IS NOT NULL
              AND p.position_group IS NOT NULL
        """)

        if not survival.empty:
            fig = px.violin(
                survival, x="position_group", y="predicted_career_length",
                color="position_group",
                color_discrete_sequence=px.colors.qualitative.Set2,
                labels={"position_group": "Position", "predicted_career_length": "Predicted Career (seasons)"},
                box=True,
            )
            fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
