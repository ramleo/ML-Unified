# TC-P2-B — Test Cases (Parts 26–33)

> Coverage: EDA Explorer (POST /eda, Plotly charts, smart insights, ML Readiness, MI matrix, PCA 3D, SPLOM, HTML export, PDF) · EDA bug fixes · Live Metrics EDA mode · Portfolio AIRaML website · Contact form · News feed · Theme/mode bugs

---

### TC-P2-076
**Category:** Feature  
**Test Name:** POST /eda — overview fields returned for valid CSV  
**Steps:**
1. Upload a CSV with at least 5 rows and 4 columns
2. `POST https://ml-unified.onrender.com/eda` with multipart CSV upload
**Expected Result:** HTTP 200; response contains `overview.rows`, `overview.cols`, `overview.duplicates`, `overview.missing_total`, `overview.missing_pct`  
**Source:** Part26

---

### TC-P2-077
**Category:** Feature  
**Test Name:** POST /eda — columns array contains dtype and missing info  
**Steps:**
1. Upload a CSV that has at least one column with missing values
2. `POST https://ml-unified.onrender.com/eda`
**Expected Result:** `columns` array present; each entry has `name`, `dtype`, `is_numeric`, `missing`, `missing_pct`, `nunique`; the missing-value column shows `missing > 0`  
**Source:** Part26

---

### TC-P2-078
**Category:** Feature  
**Test Name:** POST /eda — numeric stats include mean, median, std, min, max, q25, q75, outliers  
**Steps:**
1. Upload a numeric CSV (e.g. Iris dataset)
2. `POST https://ml-unified.onrender.com/eda`
**Expected Result:** `stats` object present; each numeric column entry contains `mean`, `median`, `std`, `min`, `max`, `q25`, `q75`, `outliers`  
**Source:** Part26

---

### TC-P2-079
**Category:** Feature  
**Test Name:** POST /eda — distributions histogram bins for numeric cols  
**Steps:**
1. Upload CSV with numeric columns
2. `POST https://ml-unified.onrender.com/eda`
**Expected Result:** `distributions` object present; numeric column entries have `type: "histogram"` and `raw_vals` (list of raw values)  
**Source:** Part26, Part27

---

### TC-P2-080
**Category:** Feature  
**Test Name:** POST /eda — distributions bar chart for categorical cols  
**Steps:**
1. Upload CSV with at least one categorical column
2. `POST https://ml-unified.onrender.com/eda`
**Expected Result:** Categorical column in `distributions` has `type: "bar"`, `labels` (top-10 values), `counts`  
**Source:** Part26

---

### TC-P2-081
**Category:** Feature  
**Test Name:** POST /eda — correlations matrix is Pearson and NaN-safe  
**Steps:**
1. Upload a CSV that has at least one column with NaN values and at least 2 numeric columns
2. `POST https://ml-unified.onrender.com/eda`
**Expected Result:** `correlations.matrix` present; dimensions are N×N for N numeric cols; diagonal values = 1.0; no NaN or Infinity in result  
**Source:** Part26

---

### TC-P2-082
**Category:** Feature  
**Test Name:** POST /eda — skew and kurtosis in stats for numeric cols  
**Steps:**
1. Upload a numeric CSV with at least one skewed column
2. `POST https://ml-unified.onrender.com/eda`
**Expected Result:** Each numeric column in `stats` contains `skew` and `kurtosis` float values  
**Source:** Part27

---

### TC-P2-083
**Category:** Feature  
**Test Name:** POST /eda — sample preview returns first 5 rows  
**Steps:**
1. Upload a CSV with 20+ rows
2. `POST https://ml-unified.onrender.com/eda`
**Expected Result:** Response includes a `sample` field with `columns` and `rows`; `rows` array has exactly 5 entries  
**Source:** Part27

---

### TC-P2-084
**Category:** Feature  
**Test Name:** POST /eda — smart insights detects high missing percentage  
**Steps:**
1. Upload a CSV where one column has >20% missing values
2. `POST https://ml-unified.onrender.com/eda`
**Expected Result:** `insights` array contains an entry with `type: "danger"` referencing the high-missing column  
**Source:** Part27

---

### TC-P2-085
**Category:** Feature  
**Test Name:** POST /eda — smart insights detects high correlation pair  
**Steps:**
1. Upload a CSV with two nearly identical numeric columns (Pearson ≥ 0.9)
2. `POST https://ml-unified.onrender.com/eda`
**Expected Result:** `insights` array contains a `type: "danger"` entry mentioning multicollinearity  
**Source:** Part27

---

### TC-P2-086
**Category:** Feature  
**Test Name:** POST /eda — quality score between 0 and 100  
**Steps:**
1. Upload any valid CSV
2. `POST https://ml-unified.onrender.com/eda`
**Expected Result:** Response contains `quality_score` (int or float); value is in range [0, 100]  
**Source:** Part27

---

### TC-P2-087
**Category:** Feature  
**Test Name:** POST /eda — box plot raw_vals present for numeric cols  
**Steps:**
1. Upload a numeric CSV
2. `POST https://ml-unified.onrender.com/eda`
**Expected Result:** Each numeric column's `stats` entry contains `raw_vals` array; length ≤ 300 (uniformly sampled)  
**Source:** Part27

---

### TC-P2-088
**Category:** Feature  
**Test Name:** POST /eda — ML Readiness flags ID-like column as fail  
**Steps:**
1. Upload a CSV with a column named `id` or `ID` where each row is unique (`nunique == nrows`)
2. `POST https://ml-unified.onrender.com/eda`
**Expected Result:** `ml_readiness` array contains an entry for the ID column with `status: "fail"` and recommendation to drop  
**Source:** Part28 (requirements), Part30 (tests)

---

### TC-P2-089
**Category:** Feature  
**Test Name:** POST /eda — ML Readiness flags near-constant column  
**Steps:**
1. Upload a CSV with a column where all values are the same (or std < 0.01)
2. `POST https://ml-unified.onrender.com/eda`
**Expected Result:** `ml_readiness` entry for that column has `status: "fail"` with "near-constant" or "useless" verdict  
**Source:** Part28, Part30

---

### TC-P2-090
**Category:** Feature  
**Test Name:** POST /eda — ML Readiness flags high-missing column (>20%)  
**Steps:**
1. Upload a CSV with a column missing >20% of its values
2. `POST https://ml-unified.onrender.com/eda`
**Expected Result:** `ml_readiness` entry for that column has `status: "fail"` with "drop" recommendation  
**Source:** Part28, Part30

---

### TC-P2-091
**Category:** Feature  
**Test Name:** POST /eda — ML Readiness flags moderate-missing column (5–20%)  
**Steps:**
1. Upload a CSV with a column missing 10% of its values
2. `POST https://ml-unified.onrender.com/eda`
**Expected Result:** `ml_readiness` entry for that column has `status: "warn"` with "impute" recommendation  
**Source:** Part28, Part30

---

### TC-P2-092
**Category:** Feature  
**Test Name:** POST /eda — mutual information matrix symmetric and values in [0,1]  
**Steps:**
1. Upload a numeric CSV with at least 3 columns
2. `POST https://ml-unified.onrender.com/eda`
**Expected Result:** `mutual_info.matrix` present; matrix is symmetric (MI[i][j] == MI[j][i]); all values in [0.0, 1.0]  
**Source:** Part28, Part30

---

### TC-P2-093
**Category:** Feature  
**Test Name:** POST /eda — mutual information matrix diagonal is 1.0 for non-constant cols  
**Steps:**
1. Upload a numeric CSV with non-constant columns
2. `POST https://ml-unified.onrender.com/eda`
**Expected Result:** Diagonal values of `mutual_info.matrix` are 1.0 for columns with variation (constant columns may have 0.0 on diagonal by convention)  
**Source:** Part30 (test: skip diagonal check for constant-col entries)

---

### TC-P2-094
**Category:** Feature  
**Test Name:** POST /eda — PCA returns 3D coordinates and explained variance  
**Steps:**
1. Upload a CSV with at least 3 numeric columns
2. `POST https://ml-unified.onrender.com/eda`
**Expected Result:** `pca.coords` array present; each entry is `[x, y, z]`; `pca.explained_variance` array has 3 floats summing to ≤ 100  
**Source:** Part28, Part29

---

### TC-P2-095
**Category:** Feature  
**Test Name:** POST /eda — PCA color_col values are strings (not raw categories)  
**Steps:**
1. Upload a CSV that has a categorical column (e.g. manufacturer names)
2. `POST https://ml-unified.onrender.com/eda`
**Expected Result:** `pca.cat_color_map[<cat_col>]` contains original string labels; the mapping from string → integer is done client-side via `indexOf`  
**Source:** Part29 (BUG: passing string arrays to Plotly sequential colorscale silently failed)

---

### TC-P2-096
**Category:** Feature  
**Test Name:** POST /eda — SPLOM returns aligned rows and color_map  
**Steps:**
1. Upload a CSV with at least 3 numeric columns and 1 categorical column
2. `POST https://ml-unified.onrender.com/eda`
**Expected Result:** `splom.color_map` present; `splom.color_map` entries have same length as `splom` coordinates (≤ 400 sampled rows); SPLOM data ≤ 8 columns  
**Source:** Part29

---

### TC-P2-097
**Category:** Feature  
**Test Name:** POST /eda — narrative paragraph present and mentions row count  
**Steps:**
1. Upload a CSV with known row count (e.g. 100 rows)
2. `POST https://ml-unified.onrender.com/eda`
**Expected Result:** `narrative` field is a non-empty string; string contains the row count number  
**Source:** Part28, Part30

---

### TC-P2-098
**Category:** Bug-Regression  
**Test Name:** EDA histogram — autobinx=true prevents giant bars  
**Steps:**
1. Upload a CSV with a column where most values cluster in a narrow range (e.g. 70 out of 77 rows between 0.1 and 0.2)
2. Run EDA analysis
3. View the distribution chart for that column in the frontend
**Expected Result:** Histogram shows a reasonable distribution with multiple visible bars; NOT one giant bar filling the chart  
**Source:** Part29, Part30 (BUG: pre-computed numpy bins caused all rows to fall in 1 bin)

---

### TC-P2-099
**Category:** Bug-Regression  
**Test Name:** EDA HTML export — distribution charts captured (off-screen rendering)  
**Steps:**
1. Upload any CSV with numeric columns
2. Click "Export Report" button
3. Open the downloaded `.html` file
**Expected Result:** All distribution charts are visible as images in the exported HTML; no blank/empty chart placeholders  
**Source:** Part29, Part30, Part31 (BUG occurred 4 times: final fix = off-screen `staticPlot:true, responsive:false`)

---

### TC-P2-100
**Category:** Bug-Regression  
**Test Name:** EDA HTML export — capture restore failure does not discard captured image  
**Steps:**
1. Upload a CSV
2. Click "Export Report"
3. Verify all charts appear in exported HTML
**Expected Result:** Even if `Plotly.relayout` restore step throws an error, the already-captured PNG is still included in the export; no charts are silently dropped  
**Source:** Part29, Part30 (BUG: single try/catch block discarded captured image when restore threw)

---

### TC-P2-101
**Category:** Bug-Regression  
**Test Name:** EDA PDF export — original tab not locked  
**Steps:**
1. Upload a CSV and run EDA
2. Click "Download PDF" (or equivalent)
3. Scroll and interact with the original EDA tab immediately
**Expected Result:** Original EDA tab remains fully interactive; no scroll or interaction lock; PDF opens in a new tab via blob URL  
**Source:** Part30, Part31 (BUG: `window.print()` in any tab froze all browser tabs)

---

### TC-P2-102
**Category:** Bug-Regression  
**Test Name:** EDA — no window.print() call exists in codebase  
**Steps:**
1. Search `services/ml-api/frontend/index.html` for `window.print(`
**Expected Result:** Zero occurrences of `window.print(` in the file; PDF button generates blob URL instead  
**Source:** Part31

---

### TC-P2-103
**Category:** Bug-Regression  
**Test Name:** EDA heatmap — bottom row not cut off for 15-label matrices  
**Steps:**
1. Upload a CSV with 12–15 numeric columns
2. Run EDA and scroll to the Pearson correlation heatmap
**Expected Result:** All rows of the heatmap visible; bottom row and its x-axis labels not cut off; dynamic cell sizing applies  
**Source:** Part31 (BUG: `Math.min(600, ...)` cap insufficient for -45° rotated labels)

---

### TC-P2-104
**Category:** Bug-Regression  
**Test Name:** EDA heatmap — cell annotations visible in HTML export  
**Steps:**
1. Upload a CSV with 3+ numeric columns
2. Export as HTML
3. Open the exported file and inspect the correlation/MI heatmap
**Expected Result:** Cell annotations (numeric values like "0.87", "-0.32") visible in the exported heatmap; white text on dark cells  
**Source:** Part31 (BUG: `text`/`texttemplate` missing from off-screen traces; inherited color invisible)

---

### TC-P2-105
**Category:** Bug-Regression  
**Test Name:** EDA — lasso and box select buttons removed from chart modebar  
**Steps:**
1. Navigate to EDA Explorer, upload a CSV
2. Hover over any Plotly chart to reveal the modebar
**Expected Result:** Lasso select and box select buttons are NOT present in the modebar; only zoom, pan, and reset controls remain  
**Source:** Part30 (BUG: non-functional in EDA context)

---

### TC-P2-106
**Category:** Bug-Regression  
**Test Name:** EDA — double-click resets chart zoom  
**Steps:**
1. Navigate to EDA Explorer, upload a CSV
2. Zoom into any 2D Plotly chart (scroll or drag)
3. Double-click the chart
**Expected Result:** Chart resets to original zoom/autosize state; `doubleclick: 'reset+autosize'` behavior  
**Source:** Part30

---

### TC-P2-107
**Category:** Bug-Regression  
**Test Name:** EDA — PCA 3D scatter has scroll zoom enabled  
**Steps:**
1. Upload a CSV with 3+ numeric columns
2. View the PCA 3D scatter plot
3. Use scroll wheel over the chart
**Expected Result:** Chart zooms in/out with scroll; `scrollZoom: true` is active  
**Source:** Part29, Part30 (BUG: `scrollZoom: false` explicitly set)

---

### TC-P2-108
**Category:** Bug-Regression  
**Test Name:** EDA CSV download button removed  
**Steps:**
1. Upload a CSV and run EDA
2. Inspect result panel for any "Download CSV" or "Export CSV" button
**Expected Result:** No CSV download button present; it was removed because it only re-downloaded the original file unchanged  
**Source:** Part30

---

### TC-P2-109
**Category:** Feature  
**Test Name:** POST /eda — edge case: single-column CSV handled gracefully  
**Steps:**
1. Upload a CSV with exactly 1 column and 10 rows
2. `POST https://ml-unified.onrender.com/eda`
**Expected Result:** HTTP 200; `overview.cols: 1`; no server error or crash  
**Source:** Part30 (edge case test: `TestEdgeCases`)

---

### TC-P2-110
**Category:** Feature  
**Test Name:** POST /eda — edge case: all-missing column handled gracefully  
**Steps:**
1. Upload a CSV where one column has 100% null/NaN values
2. `POST https://ml-unified.onrender.com/eda`
**Expected Result:** HTTP 200; missing-column stats show `missing_pct: 100`; no crash or division-by-zero error  
**Source:** Part30

---

### TC-P2-111
**Category:** Feature  
**Test Name:** POST /eda — edge case: empty CSV returns error  
**Steps:**
1. Upload a 0-byte or header-only CSV (no data rows)
2. `POST https://ml-unified.onrender.com/eda`
**Expected Result:** HTTP 400 or 422; error message is plain English describing the empty file  
**Source:** Part30

---

### TC-P2-112
**Category:** Feature  
**Test Name:** POST /eda — non-CSV file returns error  
**Steps:**
1. Upload a `.txt` or `.json` file to the EDA endpoint
2. `POST https://ml-unified.onrender.com/eda`
**Expected Result:** HTTP 400 or 415; error message indicates file must be CSV  
**Source:** Part30

---

### TC-P2-113
**Category:** Bug-Regression  
**Test Name:** EDA Live Metrics — ?mode=eda shows only ML Unified stats  
**Steps:**
1. Navigate to `https://ml-unified.onrender.com/?mode=eda`
2. Click "Live Metrics"
**Expected Result:** Panel shows only one section (ML Unified / EDA Explorer); ML Vision section absent; mode=eda falls to ml branch not the `else` branch  
**Source:** Part26 (BUG: `APP_MODE === 'eda'` fell through to `else` showing both sections)

---

### TC-P2-114
**Category:** Bug-Regression  
**Test Name:** EDA Live Metrics — label shows "EDA EXPLORER" not "ML UNIFIED"  
**Steps:**
1. Navigate to `https://ml-unified.onrender.com/?mode=eda`
2. Open Live Metrics panel
**Expected Result:** Section header label reads "EDA EXPLORER"; does NOT say "ML UNIFIED"  
**Source:** Part26

---

### TC-P2-115
**Category:** Bug-Regression  
**Test Name:** EDA router import at top of app.py (ruff E402 fixed)  
**Steps:**
1. Run `.venv/bin/ruff check services/ml-api/app.py`
**Expected Result:** No E402 errors; `from routers import eda` appears near top of file (line 2), not after function definitions  
**Source:** Part26

---

### TC-P2-116
**Category:** UI  
**Test Name:** EDA Explorer — sticky section nav tabs scroll to sections  
**Steps:**
1. Navigate to `https://ml-unified.onrender.com/?mode=eda`
2. Upload a CSV and run EDA
3. Click "Correlations" in the sticky nav strip
**Expected Result:** Page scrolls to the Correlations section; active tab is highlighted in the nav  
**Source:** Part27

---

### TC-P2-117
**Category:** UI  
**Test Name:** EDA Explorer — quality score chip is colour-coded  
**Steps:**
1. Upload a CSV with many missing values (quality < 60)
2. View the overview chips
**Expected Result:** Quality chip appears in red (< 60) or amber (60–79) or green (≥ 80) based on the score  
**Source:** Part27

---

### TC-P2-118
**Category:** UI  
**Test Name:** EDA Explorer — stats table shows skew colour coding  
**Steps:**
1. Upload a CSV with at least one highly skewed column (abs skew > 2)
2. View the Statistics section
**Expected Result:** Skew cell for that column is highlighted in red; moderate skew (abs > 1) in amber; low skew remains default  
**Source:** Part27

---

### TC-P2-119
**Category:** UI  
**Test Name:** EDA Explorer — Plotly distribution charts use native autobinx  
**Steps:**
1. Upload a CSV with a numeric column
2. View the Distributions section
**Expected Result:** Charts are Plotly `type: 'histogram'` (interactive, zoomable); NOT static SVG bar charts; bins are auto-computed  
**Source:** Part27

---

### TC-P2-120
**Category:** UI  
**Test Name:** EDA Explorer — Plotly correlation heatmap shows annotated cell values  
**Steps:**
1. Upload a numeric CSV with 3+ columns
2. View the Correlations section
**Expected Result:** Plotly heatmap visible with RdBu colour scale; each cell shows a numeric annotation (e.g. "0.87"); NOT a CSS grid table  
**Source:** Part27

---

### TC-P2-121
**Category:** UI  
**Test Name:** EDA Explorer — box plots show outlier dots  
**Steps:**
1. Upload a CSV with a column that has outliers (IQR method)
2. View the Box Plots section
**Expected Result:** All numeric columns shown side-by-side in one Plotly box plot chart; outlier points visible as dots outside whiskers  
**Source:** Part27

---

### TC-P2-122
**Category:** UI  
**Test Name:** EDA Explorer — section nav active tab updates on scroll  
**Steps:**
1. Upload a CSV and run EDA
2. Scroll down through the results sections
**Expected Result:** Active tab in the sticky nav updates to highlight the currently visible section (IntersectionObserver)  
**Source:** Part29

---

### TC-P2-123
**Category:** UI  
**Test Name:** EDA Explorer — low variance warning badge shown on distribution card  
**Steps:**
1. Upload a CSV with a nearly-constant column (std/range < 5%)
2. View the Distributions section
**Expected Result:** That column's distribution card title shows a "⚠ low variance" badge  
**Source:** Part29

---

### TC-P2-124
**Category:** UI  
**Test Name:** EDA Explorer — PCA 3D scatter color dropdown works  
**Steps:**
1. Upload a CSV with numeric columns and at least 1 categorical or low-cardinality numeric column
2. View the PCA 3D Scatter section
3. Change the color dropdown to a different column
**Expected Result:** 3D scatter recolors points based on selected column; colorbar labels show original category names  
**Source:** Part29

---

### TC-P2-125
**Category:** UI  
**Test Name:** EDA Explorer — SPLOM lower triangle only, color dropdown works  
**Steps:**
1. Upload a CSV with 3+ numeric columns
2. View the SPLOM (Scatter Plot Matrix) section
3. Change the color column in the dropdown
**Expected Result:** SPLOM shows lower triangle only (`showupperhalf: false`); color changes on dropdown selection  
**Source:** Part29

---

### TC-P2-126
**Category:** Feature  
**Test Name:** EDA Explorer — HTML export is self-contained and opens offline  
**Steps:**
1. Upload a CSV, run EDA
2. Click "Export Report"
3. Open the downloaded `.html` file while offline (no internet)
**Expected Result:** Report renders fully including charts (as embedded PNG images), sections, and styles; no external resource requests needed  
**Source:** Part27, Part29

---

### TC-P2-127
**Category:** Feature  
**Test Name:** EDA Explorer — exported HTML has embedded chart PNGs  
**Steps:**
1. Upload a CSV with numeric columns
2. Click "Export Report"
3. Open exported HTML and view source
**Expected Result:** Chart images are `<img src="data:image/png;base64,...">` tags; all chart sections (distributions, box plots, correlation heatmap, MI heatmap) have their PNG images embedded  
**Source:** Part27, Part29

---

### TC-P2-128
**Category:** Feature  
**Test Name:** Render — Python version controlled by .python-version file  
**Steps:**
1. Check that `services/ml-api/.python-version` contains `3.11.0`
2. Deploy to Render and check the build log Python version
**Expected Result:** Render uses Python 3.11.0; NOT Python 3.14.x; build completes without wheel compilation failures  
**Source:** Part31 (BUG: PYTHON_VERSION env var does not work; only `.python-version` file works)

---

### TC-P2-129
**Category:** Bug-Regression  
**Test Name:** Render — startup _load() failure does not prevent port binding  
**Steps:**
1. Intentionally break a model file on Render (or deploy with a bad pkl)
2. Trigger a deploy
3. Check Render logs
**Expected Result:** uvicorn binds its port successfully; `_load()` failure appears in logs as a caught exception; service responds to `/health` (or returns an error) rather than failing to start entirely  
**Source:** Part31 (commit `39857f3`: wrapped `_load()` in try-except)

---

### TC-P2-130
**Category:** Feature  
**Test Name:** Portfolio — ML Vision Platform card links to ?mode=vision  
**Steps:**
1. Navigate to `https://ml-portfolio-rho.vercel.app/`
2. Find the "ML Vision Platform" card
3. Click "Launch App"
**Expected Result:** Browser opens `https://ml-unified.onrender.com/?mode=vision` (or similar); app loads in vision-only mode  
**Source:** Part22, Part23

---

### TC-P2-131
**Category:** Feature  
**Test Name:** Portfolio — EDA Explorer card links to ?mode=eda  
**Steps:**
1. Navigate to `https://ml-portfolio-rho.vercel.app/`
2. Find the "EDA Explorer" card
3. Click "Launch App"
**Expected Result:** Browser opens `https://ml-unified.onrender.com/?mode=eda`; EDA panel loads by default  
**Source:** Part26

---

### TC-P2-132
**Category:** Feature  
**Test Name:** Portfolio — ML Unified Platform card links to ?mode=ml  
**Steps:**
1. Navigate to `https://ml-portfolio-rho.vercel.app/`
2. Find the "ML Unified Platform" card
3. Click "Launch App"
**Expected Result:** Browser opens `https://ml-unified.onrender.com/?mode=ml`; ML Unified sidebar loads  
**Source:** Part22

---

### TC-P2-133
**Category:** Feature  
**Test Name:** Portfolio hero — "Hi, I'm" prefix removed  
**Steps:**
1. Navigate to `https://ml-portfolio-rho.vercel.app/`
2. Read the hero heading
**Expected Result:** Hero heading shows only "AIRaML" (gradient text); no "Hi, I'm" prefix  
**Source:** Part23

---

### TC-P2-134
**Category:** Feature  
**Test Name:** Portfolio hero — stats show "2 Live Platforms" not "4 Live Projects"  
**Steps:**
1. Navigate to `https://ml-portfolio-rho.vercel.app/`
2. Read the stats chips in the hero section
**Expected Result:** Stats show "2 Live Platforms", "4 Datasets", "96.7% Best Accuracy", "Auto-ML Pipeline"  
**Source:** Part23

---

### TC-P2-135
**Category:** Feature  
**Test Name:** AIRaML website — navbar shows all 7 nav links plus Resume button  
**Steps:**
1. Navigate to `https://ml-portfolio-rho.vercel.app/`
2. Inspect the navbar
**Expected Result:** Navbar contains links for: Hero/Home, About, Skills, Projects, Pipeline, News, Timeline, Contact; plus a "Resume" download button  
**Source:** Part32

---

### TC-P2-136
**Category:** Feature  
**Test Name:** AIRaML website — Skills section shows 6 categories  
**Steps:**
1. Navigate to `https://ml-portfolio-rho.vercel.app/`
2. Scroll to Skills section
**Expected Result:** 6 skill categories visible: Machine Learning, Deep Learning, Generative AI, NLP, Computer Vision, MLOps & Tools; each with its correct accent color  
**Source:** Part32

---

### TC-P2-137
**Category:** Feature  
**Test Name:** AIRaML website — ML Pipeline Showcase shows 7 interactive stages  
**Steps:**
1. Navigate to `https://ml-portfolio-rho.vercel.app/`
2. Scroll to ML Pipeline section
3. Click on each stage
**Expected Result:** 7 stages visible: Data Ingestion, EDA, Feature Engineering, Model Training, Evaluation, Deployment, Monitoring; each stage is interactive/clickable  
**Source:** Part32

---

### TC-P2-138
**Category:** Feature  
**Test Name:** AIRaML website — arXiv papers tab loads without API key  
**Steps:**
1. Navigate to `https://ml-portfolio-rho.vercel.app/`
2. Scroll to News section
3. Click "Research Papers" tab
**Expected Result:** arXiv papers load without any API key; papers are displayed with titles and links; no error message  
**Source:** Part32, Part33

---

### TC-P2-139
**Category:** Feature  
**Test Name:** AIRaML website — Industry News tab shows message when NEWSAPI_KEY missing  
**Steps:**
1. Ensure `NEWSAPI_KEY` is NOT set in Vercel environment
2. Navigate to News section
3. Click "Industry News" / "AI News" tab
**Expected Result:** A message is shown indicating the API key needs to be configured; no crash or unhandled error  
**Source:** Part33

---

### TC-P2-140
**Category:** Feature  
**Test Name:** AIRaML website — Contact form submits when RESEND_API_KEY is set  
**Steps:**
1. Ensure `RESEND_API_KEY` is set in Vercel
2. Navigate to Contact section
3. Fill in Name, Email, Message and submit
**Expected Result:** Form submits successfully; user receives confirmation message; email sent via Resend to configured address  
**Source:** Part32

---

### TC-P2-141
**Category:** Feature  
**Test Name:** AIRaML website — Contact form falls back to console.log without RESEND_API_KEY  
**Steps:**
1. Ensure `RESEND_API_KEY` is NOT set in Vercel
2. Submit the contact form
**Expected Result:** Form submits without crashing; Vercel logs show `console.log` of the submission; user sees a graceful success or fallback message  
**Source:** Part32

---

### TC-P2-142
**Category:** Feature  
**Test Name:** AIRaML website — Experience Timeline shows current role as Capgemini  
**Steps:**
1. Navigate to `https://ml-portfolio-rho.vercel.app/`
2. Scroll to Experience / Timeline section
**Expected Result:** Most recent role shows "Capgemini" with title "Consultant B2" (NOT "Data Engineer")  
**Source:** Part33 (fix: title corrected from Data Engineer to Consultant B2)

---

### TC-P2-143
**Category:** Feature  
**Test Name:** AIRaML website — NewsAPI query filters to AI/ML terms  
**Steps:**
1. Navigate to Industry News tab (with NEWSAPI_KEY set)
2. Inspect the news articles displayed
**Expected Result:** Articles are relevant to: artificial intelligence, machine learning, deep learning, large language models, generative AI, neural networks, MLOps; unrelated news articles absent  
**Source:** Part33

---

### TC-P2-144
**Category:** UI  
**Test Name:** Portfolio — 3D card tilt responds to mouse movement  
**Steps:**
1. Navigate to `https://ml-portfolio-rho.vercel.app/`
2. Hover mouse over a project card and move it around
**Expected Result:** Card tilts in 3D (rotateX/rotateY up to ±12°) following cursor; accent glow intensifies with tilt magnitude; card springs back to flat on mouse leave  
**Source:** Part32, Part28 (#14)

---

### TC-P2-145
**Category:** UI  
**Test Name:** Portfolio — staggered card entrance animation on scroll  
**Steps:**
1. Navigate to `https://ml-portfolio-rho.vercel.app/`
2. Scroll down to the projects grid (cards initially off-screen)
3. Observe as cards enter viewport
**Expected Result:** Cards animate in from opacity:0/y:40 to opacity:1/y:0 with spring physics; each card staggered by 100ms (index × 0.1s)  
**Source:** Part32, Part28 (#15)

---

### TC-P2-146
**Category:** UI  
**Test Name:** Portfolio — per-accent glow on card hover  
**Steps:**
1. Navigate to `https://ml-portfolio-rho.vercel.app/`
2. Hover over a project card
**Expected Result:** `box-shadow: 0 0 40px ${accent}66` visible on the card; each card's glow matches its unique accent color from registry.json  
**Source:** Part32, Part28 (#17)

---

### TC-P2-147
**Category:** UI  
**Test Name:** Portfolio — tag filter animation (AnimatePresence)  
**Steps:**
1. Navigate to `https://ml-portfolio-rho.vercel.app/`
2. Click a tag filter (e.g. "Vision")
**Expected Result:** Non-matching cards animate out (scale:0.8, opacity:0 exit); matching cards animate in (spring from scale:0.8); remaining cards smoothly reflow  
**Source:** Part32, Part28 (#18)

---

### TC-P2-148
**Category:** UI  
**Test Name:** Portfolio — metric counter counts up when card enters viewport  
**Steps:**
1. Navigate to `https://ml-portfolio-rho.vercel.app/`
2. Scroll until a project card with a metric number (e.g. "150") enters the viewport
**Expected Result:** Metric number counts up from 0 to its final value over ~1 second using requestAnimationFrame; does NOT jump directly to the final value  
**Source:** Part32, Part28 (#19)

---

### TC-P2-149
**Category:** UI  
**Test Name:** Portfolio — colored top border on each card matches accent  
**Steps:**
1. Navigate to `https://ml-portfolio-rho.vercel.app/`
2. Inspect each project card's top border
**Expected Result:** Each card has a 3px solid top border in its unique accent color; borders span full card width  
**Source:** Part32, Part28 (#20)

---

### TC-P2-150
**Category:** UI  
**Test Name:** Portfolio — AIRaML headline is large (≥5rem on desktop)  
**Steps:**
1. Navigate to `https://ml-portfolio-rho.vercel.app/`
2. Measure or visually verify the hero headline font size on a ≥1280px viewport
**Expected Result:** "AIRaML" gradient headline appears at 5–6rem on desktop; it is the dominant visual element in the hero  
**Source:** Part32, Part28 (#25)

---

### TC-P2-151
**Category:** UI  
**Test Name:** Portfolio — equal card heights in projects grid  
**Steps:**
1. Navigate to `https://ml-portfolio-rho.vercel.app/`
2. Compare card heights in the projects grid
**Expected Result:** All cards in the same row are equal height; "Launch App" button always at the bottom of each card; description fills remaining space  
**Source:** Part32, Part28 (#24)

---

### TC-P2-152
**Category:** Feature  
**Test Name:** ml-vision — GET / root endpoint returns 200  
**Steps:**
1. `GET <VISION_API>/` (the root endpoint of ml-vision service)
**Expected Result:** HTTP 200; some valid JSON response; NOT 404  
**Source:** Part25 (ml-vision must have root endpoint to avoid 404 inflating error rate)

---

### TC-P2-153
**Category:** Feature  
**Test Name:** ml-api — GET /app-config returns vision URL  
**Steps:**
1. `GET https://ml-unified.onrender.com/app-config`
**Expected Result:** HTTP 200; JSON contains `vision_url` field with the ml-vision service URL  
**Source:** Part20 (microservices split: `/app-config` added to ml-api)

---

### TC-P2-154
**Category:** Feature  
**Test Name:** ml-vision warmup thread pre-downloads TinyYOLOv3 on startup  
**Steps:**
1. Deploy ml-vision service (fresh deploy, no cached models)
2. Wait 60 seconds for warmup to complete
3. `POST <VISION_API>/detect-objects` with a test image
**Expected Result:** First detection request after warmup completes in < 30 seconds (model already on disk); no 502 due to model download during request  
**Source:** Part21

---

### TC-P2-155
**Category:** E2E  
**Test Name:** Full vision flow — classify → detect → segment in one session  
**Steps:**
1. Navigate to `https://ml-unified.onrender.com/?mode=vision`
2. Click "Image Classifier" — upload a dog photo — classify with MobileNetV2
3. Click "Object Detection" — upload same photo — detect with threshold 0.3
4. Click "Image Segmentation" — upload same photo — segment with SegFormer-B0
**Expected Result:** All three operations succeed; results shown in each panel; no errors; no JavaScript console errors; each panel shows its respective colored annotated output  
**Source:** Part22 (full Vision suite working)

---

### TC-P2-156
**Category:** E2E  
**Test Name:** Full EDA flow — upload CSV → view all sections → export HTML  
**Steps:**
1. Navigate to `https://ml-unified.onrender.com/?mode=eda`
2. Upload a CSV file (e.g. Iris dataset)
3. Wait for analysis to complete
4. Scroll through all sections: Overview, Sample, Columns, Statistics, Distributions, Box Plots, Correlations
5. Click "Export Report"
**Expected Result:** All sections render with data; Plotly charts are interactive; HTML export downloads successfully and opens offline with embedded chart images  
**Source:** Part26, Part27, Part29

---

### TC-P2-157
**Category:** E2E  
**Test Name:** Theme sync round-trip — portfolio → ml unified → portfolio  
**Steps:**
1. Set portfolio to light theme
2. Launch ML Unified from a portfolio card → verify light theme
3. Toggle to dark theme in ML Unified
4. Click Portfolio link in ML Unified navbar → verify dark theme
5. Refresh portfolio → verify dark theme persists
**Expected Result:** Theme transfers in both directions via `?theme=` URL param; param is stripped after application; refresh always reads from localStorage; no stale URL param causing regression  
**Source:** Part23, Part24

---

### TC-P2-158
**Category:** E2E  
**Test Name:** CI/CD full pipeline — push to main triggers lint, test, and deploy  
**Steps:**
1. Make a valid small change to `services/ml-api/app.py` (e.g. add a comment)
2. Push to main branch
3. Monitor GitHub Actions run
4. After CI passes, check Render deploy log
**Expected Result:** CI runs: ruff passes → pytest passes → deploy job triggers Render hook → Render deploys within 5 minutes → `GET /health` returns 200  
**Source:** Part16

---
