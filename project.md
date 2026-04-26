NFL Draft Prospect Intelligence System
Project overview
A full-stack analytics system that evaluates NFL draft prospects by combining college production data, athletic testing, and historical draft outcomes to generate a composite "Pro Readiness Score," find historical player comparisons, and model career longevity — all surfaced through an interactive web app and a three-part LinkedIn content series.

Why this project stands out
This isn't a notebook with some charts. It's a deployed system that mirrors what NFL analytics departments actually build. It covers data engineering, domain-specific feature engineering, multi-model ML pipelines, survival analysis, model explainability, full-stack app development, and public-facing analytical writing. A recruiter looking at this sees someone who can do the entire job, not just one piece of it.

Architecture
Layer 1 — Data ingestion
Goal: Build a reproducible pipeline that pulls, cleans, and stores data from four free public sources into a local SQLite database.
Data sources:

NFL Combine results (2000–2025): 40-yard dash, bench press, vertical jump, broad jump, 3-cone drill, shuttle. Source: Pro Football Reference, NFL Combine historical data.
College production stats: Season-level and game-level stats for every FBS player. Source: cfbfastR (Python/R package), College Football Reference.
NFL play-by-play and player stats: Post-draft NFL performance to define "success" labels for training. Source: nflverse (nfl-data-py Python package).
Historical draft picks: Every pick from 2000–2025 with round, pick number, team, and career outcome. Source: Pro Football Reference draft history.

Schema design (SQLite):

prospects — one row per player-draft-year, keyed on a unique player ID. Contains biographical info (name, school, position, height, weight, draft year).
combine_results — athletic testing metrics linked to prospect ID.
college_stats — season-level college production linked to prospect ID. Includes games played, passing/rushing/receiving/defensive stats depending on position.
draft_picks — actual draft outcome (round, pick, team) linked to prospect ID.
nfl_performance — post-draft NFL stats by season, linked to prospect ID. Used to generate success labels and survival targets.
features — computed feature vectors per prospect (output of Layer 2).
predictions — model outputs per prospect (output of Layer 3).

Pipeline mechanics:

Python scripts using requests, pandas, and nfl_data_py for ingestion.
Idempotent: re-running the pipeline upserts rather than duplicates.
Logging for missing data (not every prospect has combine results).
Output: a single nfl_draft.db SQLite file that the rest of the system reads from.


Layer 2 — Feature engineering
Goal: Transform raw stats into the same kinds of metrics NFL analytics departments use to evaluate prospects. Every feature is position-aware — a QB's feature vector looks completely different from a CB's.
Feature categories:
Athletic profile (from Combine data):

Raw metrics: 40 time, bench reps, vertical, broad jump, 3-cone, shuttle.
Positional percentiles: where does this player rank among all players at his position historically? A 4.45 forty means something different for a WR vs. a TE.
Athletic composite score: a weighted z-score combining all measurables into a single athleticism number, position-adjusted.
Size-adjusted speed score: (weight × 200) / (40_time^4) — heavier players who still run fast get credit.

Production metrics (from college stats):

Dominator rating: what percentage of his team's total receiving yards / rushing yards / touchdowns did he account for? Higher = more dominant.
Breakout age: the earliest season where the player exceeded a production threshold (e.g., 20% dominator rating). Earlier breakouts correlate with NFL success.
Final season production: stats from the player's last college season, which captures his peak.
Career trajectory: is production trending up, flat, or declining? Computed as the slope of a simple regression over season-by-season stats.
Yards per route run / yards per carry / passer rating: efficiency metrics that normalize for opportunity volume.

Context adjustors:

Strength of schedule (SoS): adjust production based on the quality of opponents faced. 1,000 yards against SEC defenses is not the same as 1,000 yards against Sun Belt defenses. Source: team SRS ratings from cfbfastR.
Usage rate: snaps played as a percentage of team snaps, targets as a percentage of team pass attempts.
Competition quality: average draft capital of defenders faced (approximated from team-level data).

Efficiency scores (position-specific):

QBs: completion % over expected, turnover-worthy play rate, pressure-to-sack rate, depth of target, play-action efficiency.
WRs/TEs: contested catch rate, yards after catch per reception, target separation proxy.
RBs: yards after contact per carry, breakaway run rate (runs of 15+ yards as % of carries), receiving efficiency.
Defensive players: pressure rate, missed tackle rate, coverage snaps per target allowed.

Output: Each prospect gets a feature vector of 30–50 features (depending on position) stored in the features table.

Layer 3 — Model pipeline
Three models that work together. Each one does something different, and the combination is what makes this project feel like a real analytics system rather than a one-off notebook.
Model A — Pro Readiness Score (XGBoost classifier)
What it predicts: Binary classification — will this prospect become a "successful" NFL player within their first 3 seasons?
Defining "success": A prospect is labeled successful if they meet position-specific thresholds within their first 3 NFL seasons: QBs must earn a starting role for 8+ games in at least one season, skill position players must exceed a games-started or production threshold, defensive players must reach a snap-count or impact-play threshold. The exact thresholds are calibrated from historical data to produce a roughly 35-40% success rate (reflecting reality — most draft picks don't pan out).
Training data: Draft classes 2000–2021 (enough time to observe 3 seasons of NFL performance). 2022–2023 classes reserved for validation. 2024–2025 are the prediction targets.
Modeling approach:

Separate XGBoost models per position group (QB, RB, WR, TE, OL, DL, LB, DB). Each position has different features that matter.
Hyperparameter tuning via Optuna with 5-fold cross-validation.
Class imbalance handled via scale_pos_weight.
Output: a probability score from 0 to 100 representing "pro readiness."

Explainability (this is critical for LinkedIn):

SHAP values for every prediction. For each prospect, you can say: "His score is 78 because his dominator rating is elite (+12 points), his breakout age is early (+8 points), but his 3-cone time is concerning (-6 points)."
Global feature importance plots per position.
Partial dependence plots showing how each feature affects the score.

Model B — Historical comp engine (similarity search)
What it does: For any prospect, finds the 3 most similar historical players based on pre-draft profile.
Approach:

Compute cosine similarity between the prospect's feature vector and every historical prospect's feature vector (within the same position group).
Weight features by their SHAP importance from Model A — features that matter more for NFL success should matter more in the comp search.
Return top 3 matches with similarity percentage and a comparison card showing where the prospect matches and diverges from each comp.

Why this matters: "This WR profiles as an 84% match to pre-draft Ja'Marr Chase" is the single most shareable thing you can put on LinkedIn. It's concrete, provocative, and invites debate.
Model C — Career survival model (Kaplan-Meier + Cox regression)
What it predicts: How long a player's career will last, and when they'll reach milestones (first start, first Pro Bowl selection, career end).
Approach:

Kaplan-Meier survival curves by position and draft round, showing the probability of still being in the league after N seasons.
Cox proportional hazards model using pre-draft features to predict individual career duration.
Handles right-censoring (players still active have incomplete career data).

Why this matters: This is the "wow" model. Almost nobody applies survival analysis to draft evaluation. It lets you say things like: "Even though Player A has a higher Pro Readiness Score, Player B's survival model projects a career 2.3 years longer." That's the kind of insight that gets a hiring manager's attention.

Layer 4 — Interactive web app
Dual deployment: A Streamlit app for the full analytical experience and a React dashboard for the polished, shareable version.
Streamlit app (analytical depth)
View 1 — Big board:

Full prospect ranking table, sortable by Pro Readiness Score, position, school, or any feature.
Filter by position group, draft round projection, conference.
Color-coded tiers (green = elite, yellow = starter, orange = rotational, red = risky).
Click any prospect to open their profile.

View 2 — Player profile:

Radar chart showing the prospect's percentile rank across key features for their position.
SHAP waterfall chart explaining why their Pro Readiness Score is what it is.
Top 3 historical comps with comparison cards.
Survival curve showing projected career trajectory.
Raw stats table for the curious.

View 3 — Comp explorer:

Search any historical player and see their pre-draft profile.
See which current prospects match them.
Side-by-side comparison tool: pick two prospects and see how they differ across every dimension.

View 4 — Draft simulator:

Mock draft engine where the user drafts for a specific team.
Shows value-over-replacement (VOR) for each pick relative to available alternatives.
Highlights model-suggested "steals" (high Pro Readiness Score players projected to fall).

React dashboard (LinkedIn showcase)

A cleaner, more visual version of the big board and player profiles.
Deployed on GitHub Pages or Vercel for zero hosting cost.
Designed for screenshots and screen recordings that look great in LinkedIn posts.
Mobile-responsive so it looks good when people open the link on their phones from LinkedIn.


Layer 5 — LinkedIn content strategy
Post 1 — Pre-draft predictions (publish 3-5 days before the NFL Draft)
Format: Carousel or long-form text post with embedded visuals.
Content:

Your model's top 10 overall prospects and top 5 per position.
Highlight 3-4 "hot takes" where your model disagrees with consensus: "My model has [Player X] as WR1 over [Player Y]. Here's why."
Include one SHAP waterfall chart as a visual.
Link to the live app so people can explore the full board.
End with: "I'll be back after the draft to grade how my model performed."

Engagement hook: Disagreement with conventional wisdom drives comments. People will argue, and that's the point.
Post 2 — Post-draft model grade (publish 1-2 days after the draft)
Format: Long-form text post.
Content:

Score your model's accuracy: how many of your top prospects went in the range you projected?
Highlight your best calls and your worst misses.
Show the comp engine's most interesting matchups: "The Jaguars drafted [Player X], who profiles as a 79% match to [Historical Player]. Here's what that means for their offense."
Be honest about what the model missed — this is more impressive than pretending you nailed everything.

Engagement hook: Humility and analytical rigor. NFL Twitter and LinkedIn love a good "here's where I was wrong and why."
Post 3 — Technical deep dive (publish 1-2 weeks after the draft)
Format: Long-form article (LinkedIn article, not just a post).
Content:

The full methodology: data sources, feature engineering decisions, model architecture, survival analysis approach.
Interesting findings from the data: "Breakout age before 20 correlates with NFL success at a rate of X% vs. Y% for later breakouts."
SHAP analysis: which features matter most per position?
Lessons learned and what you'd do differently.
Link to the GitHub repo.

Engagement hook: This is the post that gets you DMs from analytics departments. It signals depth and technical maturity.

Tech stack

Languages: Python (primary), R (for cfbfastR data pulls if needed), JavaScript (React frontend).
Data storage: SQLite (fits your existing stack, zero cost).
ML/Stats: scikit-learn, XGBoost, lifelines (survival analysis), SHAP, Optuna (hyperparameter tuning).
Visualization: matplotlib, seaborn, plotly (interactive charts in Streamlit).
Web app: Streamlit (analytical app), React + Tailwind CSS (showcase dashboard).
Deployment: Streamlit Community Cloud (free), GitHub Pages or Vercel (free for React app).
Version control: Git + GitHub with a clean README, documented notebooks, and reproducible pipeline.


Repo structure
nfl-draft-intelligence/
├── README.md
├── requirements.txt
├── data/
│   ├── raw/                    # Raw downloaded data (gitignored)
│   ├── processed/              # Cleaned datasets
│   └── nfl_draft.db            # SQLite database
├── notebooks/
│   ├── 01_data_ingestion.ipynb
│   ├── 02_feature_engineering.ipynb
│   ├── 03_pro_readiness_model.ipynb
│   ├── 04_comp_engine.ipynb
│   ├── 05_survival_analysis.ipynb
│   └── 06_exploratory_analysis.ipynb
├── src/
│   ├── ingestion/
│   │   ├── combine.py
│   │   ├── college_stats.py
│   │   ├── nfl_performance.py
│   │   └── draft_history.py
│   ├── features/
│   │   ├── athletic.py
│   │   ├── production.py
│   │   ├── context.py
│   │   └── builder.py
│   ├── models/
│   │   ├── pro_readiness.py
│   │   ├── comp_engine.py
│   │   └── survival.py
│   └── utils/
│       ├── db.py
│       └── config.py
├── app/
│   ├── streamlit_app.py
│   ├── pages/
│   │   ├── big_board.py
│   │   ├── player_profile.py
│   │   ├── comp_explorer.py
│   │   └── draft_simulator.py
│   └── components/
│       ├── radar_chart.py
│       ├── shap_plot.py
│       └── survival_curve.py
├── dashboard/                  # React frontend
│   ├── src/
│   ├── public/
│   └── package.json
├── linkedin/
│   ├── post_1_predictions.md
│   ├── post_2_results.md
│   └── post_3_deep_dive.md
└── .gitignore

Execution timeline
Weeks 1-2 — Data foundation:
Build the ingestion pipeline, design the SQLite schema, pull and clean all historical data. Validate data quality with exploratory analysis.
Weeks 3-4 — Feature engineering:
Build all feature modules (athletic, production, context, efficiency). Compute feature vectors for every prospect in the database. Validate by spot-checking known players.
Weeks 5-7 — Model development:
Train position-specific XGBoost models, build the comp engine, implement survival analysis. Run cross-validation, tune hyperparameters, generate SHAP explanations.
Weeks 8-9 — App development:
Build the Streamlit app with all four views. Deploy to Streamlit Community Cloud. Start the React dashboard for the polished showcase version.
Week 10 — Polish and content:
Finalize the React dashboard and deploy. Write LinkedIn post drafts. Generate prediction visuals. Clean up the GitHub repo with a strong README.
Draft week — Go live:
Publish Post 1 before the draft. Publish Post 2 after. Publish Post 3 the following week.

What makes this "wow"

Survival analysis on draft prospects — almost nobody does this. It's the single most differentiating technical element.
Position-specific models with SHAP explainability — shows you understand that ML is only useful when you can explain it.
Historical comp engine — this is the feature that makes people share your posts. "He profiles like a young Tyreek Hill" with data behind it is irresistible.
Deployed, interactive app — not a notebook, not a PDF. A thing people can use.
Three-post LinkedIn arc — shows you can communicate findings, not just produce them. Prediction → accountability → methodology is a narrative that builds credibility.
Full GitHub repo with clean code — any recruiter who clicks through sees production-quality Python, not spaghetti.