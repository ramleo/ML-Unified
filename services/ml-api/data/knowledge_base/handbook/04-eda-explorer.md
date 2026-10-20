Chapter 2EDA Explorer


> Upload any CSV dataset and instantly explore it — shape, dtypes, missing value heatmap, per-column distributions (histograms for numeric, bar charts for categorical), descriptive statistics, outlier counts, and a full Pearson correlation heatmap. No code required.

## At a glance

| | |
|---|---|
| **Model or method** | Pandas · NumPy |
| **What it does** | Exploratory Analysis |
| **Works on** | Any CSV |
| **Datasets** | ∞ |
| **Find it at** | `/eda` |

### What EDA Explorer is
EDA Explorer is an exploratory-data-analysis platform inside AIRaML: **upload any
CSV and instantly profile it** — no code. It computes the shape, dtypes, missing
values, per-column distributions, descriptive statistics, correlations, mutual
information, a 3D PCA projection and a scatter-plot matrix, surfaces plain-language
insights, and lets you export the whole thing as a PDF or HTML report.

The charts are interactive (Plotly): hover for values, rotate the 3D PCA, and
recolour plots by any column.

### What you get, section by section
- **Overview & columns** — rows × columns, dtypes, memory, and a per-column
  table of missing counts, unique counts and sample values.
- **Distributions** — histograms for numeric columns, bar charts for
  categoricals, descriptive statistics, and box plots that flag outliers.
- **Correlations & MI** — a full Pearson correlation heatmap plus a
  mutual-information heatmap (linear *and* non-linear relationships).
- **3D PCA & SPLOM** — an interactive 3D PCA scatter you can rotate and colour by
  any column, and a scatter-plot matrix across numeric features.
- **Auto insights** — plain-language findings: skew, high-missing columns, strong
  correlations, likely outliers.
- **Report** — export the whole profile as a PDF or a self-contained HTML file.

### Using EDA Explorer (step by step)
1. Click **Open the explorer** to launch the EDA mode of the app.
2. **Upload a CSV** — drag it in or pick a file. A sample dataset is available if
   you just want to look around.
3. The profile builds automatically. **Scroll the sections** — overview,
   distributions, correlations, PCA, insights.
4. **Interact with the charts** — hover for exact values, rotate the 3D PCA,
   use the colour-by picker to recolour by a column.
5. **Export** — download a PDF or HTML report to share or keep.

### What makes it interesting
- **No code, full profile.** One upload produces the analysis you would otherwise
  write dozens of pandas/matplotlib cells for.
- **Interactive, not static.** Real Plotly charts — hover, zoom, rotate — not
  fixed images.
- **Linear and non-linear.** Both a Pearson heatmap and a mutual-information
  heatmap, so you don't miss relationships correlation alone would hide.
- **One microservice.** The same FastAPI service also powers the ML Unified and
  Vision platforms; they are three modes of one deployment.

### Honest limits
- It profiles **tabular CSV data** — not images, audio or free text (use the
  Vision platform for images).
- Very wide or very large files are sampled for the heavier charts (PCA, SPLOM,
  box plots) to stay responsive; the summary stats use the full data.
- It **describes** your data; it doesn't clean, transform or model it — that's
  what the ML Unified platform and the site's other tools are for.
- Your uploaded file is processed to build the profile and isn't kept as a
  permanent dataset.

### FAQ
- **Do I need to know statistics?** No — the auto-insights explain the notable
  findings in plain language, and every chart is labelled.
- **What file types?** CSV. Convert other formats to CSV first.
- **Where does it run?** On a FastAPI backend (the EDA mode of the shared
  ML-Unified Space) — the analysis runs server-side.
- **Can I keep the results?** Yes — export a PDF or HTML report.
- **Is it free?** Yes.

### Why it matters
The first thing you do with any dataset is understand it. EDA Explorer collapses
that first hour — shape, missingness, distributions, correlations, structure —
into one upload, with interactive charts and a shareable report, so you can get to
the real questions faster.
