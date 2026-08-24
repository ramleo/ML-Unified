# TC-HIST — Historical Regression & Feature Tests (Parts 107–112)

Source: Conversation_Part107–112.md  
Total: 44 test cases

---

## Bug Regression Tests

### TC-HIST-001
**Category:** Bug-Regression  
**Test Name:** AI Suggest — JSON truncation no longer occurs with maxTokens 2048  
**Steps:**
1. Navigate to the Feature Selection tool
2. Upload a CSV dataset (e.g. Titanic)
3. Enable at least two selection methods (e.g. Variance + Correlation)
4. Click "AI Suggest Methods"
5. Check browser console for errors

**Expected Result:** AI Suggest completes without a JSON parse error. All suggested methods applied to controls. No truncated/malformed JSON.  
**Source:** Part109, Part110

---

### TC-HIST-002
**Category:** Bug-Regression  
**Test Name:** AI Suggest — correct field names applied (selectKBestK, rfeTargetK)  
**Steps:**
1. Navigate to Feature Selection tool
2. Upload a CSV dataset
3. Enable Select K Best and RFE methods
4. Click "AI Suggest Methods"
5. Inspect which controls update after the response

**Expected Result:** K Best K control and RFE Target K control update with AI-suggested values. No controls silently fail to update due to wrong field names.  
**Source:** Part109, Part110

---

### TC-HIST-003
**Category:** Bug-Regression  
**Test Name:** FS badge count — disabled tabs show no badge  
**Steps:**
1. Navigate to Feature Selection tool
2. Upload a CSV dataset
3. Enable only Variance and Correlation methods; leave all others disabled
4. Click "Run Feature Selection"
5. Inspect all tab buttons (enabled and disabled)

**Expected Result:** Badge with feature count appears only on enabled tabs (Variance, Correlation). All disabled tabs show no badge.  
**Source:** Part109, Part110

---

### TC-HIST-004
**Category:** Bug-Regression  
**Test Name:** PCA scree chart — cumulative variance line no longer clips above chart boundary  
**Steps:**
1. Navigate to Feature Selection tool
2. Upload a multi-feature CSV (5+ numeric columns)
3. Enable PCA reduction method
4. Click "Run Feature Selection"
5. View the PCA Scree Chart

**Expected Result:** The blue cumulative variance line is fully visible for all principal components. No portion of the line is cut off at the top of the chart.  
**Source:** Part108, Part109

---

### TC-HIST-005
**Category:** Bug-Regression  
**Test Name:** Correlation heatmap — annotation threshold is |r| > 0.4 with correct caption  
**Steps:**
1. Navigate to Feature Selection tool
2. Upload Titanic CSV (or dataset with correlated features)
3. Enable Correlation method
4. Click "Run Feature Selection"
5. View the Correlation Heatmap

**Expected Result:** Cell values annotated when |r| > 0.4 (not 0.5 or 0.7). Caption reads "Values shown when |r| > 0.4 · |r| > 0.7 = multicollinearity risk".  
**Source:** Part108

---

### TC-HIST-006
**Category:** Bug-Regression  
**Test Name:** Constellation background — dots spring back to origin after cursor moves away  
**Steps:**
1. Navigate to any tool page (e.g. Feature Selection, Feature Engineering)
2. Move cursor across the ConstellationBackground area
3. Observe dots repel from cursor
4. Move cursor away from dots

**Expected Result:** Dots repel from cursor while nearby, then smoothly return to their original positions when cursor moves away (spring-back physics).  
**Source:** Part108, Part109

---

### TC-HIST-007
**Category:** Bug-Regression  
**Test Name:** UMAP 3D — pan hint shows "Ctrl-drag to pan" (not "Right-drag")  
**Steps:**
1. Navigate to Feature Selection tool
2. Upload a CSV with a categorical target column
3. Enable UMAP reduction method
4. Click "Run Feature Selection"
5. View the UMAP 3D scatter

**Expected Result:** The pan hint label reads "Ctrl-drag to pan" (not "Right-drag to pan").  
**Source:** Part108, Part109

---

### TC-HIST-008
**Category:** Bug-Regression  
**Test Name:** Chatbot bubble — elements behind transparent wrapper remain clickable  
**Steps:**
1. Navigate to any tool page that has both a dropdown/select and the AI chat bubble
2. Without opening the chat panel, click a dropdown or button located behind the chatbot wrapper area
3. Observe whether the click is captured by the dropdown

**Expected Result:** The dropdown or button responds to the click. The chatbot's transparent fixed wrapper does not block pointer events for elements behind it.  
**Source:** Part111

---

### TC-HIST-009
**Category:** Bug-Regression  
**Test Name:** LDA panel header — entire header row is clickable to expand/collapse  
**Steps:**
1. Navigate to Feature Engineering tool
2. Upload a CSV with a text/categorical column
3. Scroll to the LDA panel
4. Click anywhere on the LDA panel header row (not just the toggle arrow)

**Expected Result:** The LDA panel expands or collapses when clicking any part of the header row.  
**Source:** Part111

---

### TC-HIST-010
**Category:** Bug-Regression  
**Test Name:** Scatter dots and axis labels — correct rendered size after SVG viewBox scaling  
**Steps:**
1. Navigate to Feature Selection tool
2. Upload a CSV with a multi-class target column (3+ classes)
3. Enable PCA or FA reduction
4. Click "Run Feature Selection"
5. View the projected scatter in the result card

**Expected Result:** Scatter dots appear small and readable (radius ~1.5px equivalent). Axis labels readable and not oversized. Legend markers are circles, not squares.  
**Source:** Part111

---

### TC-HIST-011
**Category:** Bug-Regression  
**Test Name:** LDA scatter axis labels — show "LD1"/"LD2" not "LD-1"/"LD-2" and not "UMAP-1"/"UMAP-2"  
**Steps:**
1. Navigate to Feature Selection tool
2. Upload a CSV with a 3-class categorical target
3. Enable LDA reduction
4. Click "Run Feature Selection"
5. View the LDA 2D scatter chart axes

**Expected Result:** X-axis label reads "LD1" and Y-axis reads "LD2" (no hyphen, no "UMAP" prefix).  
**Source:** Part111, Part112

---

### TC-HIST-012
**Category:** Bug-Regression  
**Test Name:** LDA slider — capped at nClasses − 1 with note shown  
**Steps:**
1. Navigate to Feature Selection tool
2. Upload a CSV with exactly 3 class values in target column
3. Enable LDA reduction
4. Observe the LDA components slider maximum value and any informational note

**Expected Result:** Slider maximum is 2 (nClasses − 1 = 3 − 1). A note reads "3 classes detected → max 2 discriminants".  
**Source:** Part112

---

### TC-HIST-013
**Category:** Bug-Regression  
**Test Name:** LDA result — amber "Capped at N" badge when selected > actual components  
**Steps:**
1. Navigate to Feature Selection tool
2. Upload a CSV with 3 classes in target column
3. Enable LDA; attempt to set components slider higher than nClasses − 1
4. Click "Run Feature Selection"
5. View the LDA result card

**Expected Result:** An amber badge reading "Capped at N" is visible in the result card, where N is the actual number of components computed.  
**Source:** Part112

---

## Feature Tests

### TC-HIST-014
**Category:** Feature  
**Test Name:** Factor Analysis (FA) — new reduction tab runs and shows loadings table  
**Steps:**
1. Navigate to Feature Selection tool
2. Upload a CSV with 5+ numeric features
3. Enable FA tab in Reduction section; set factors to 3
4. Click "Run Feature Selection"
5. View the FA result card

**Expected Result:** FA tab appears in Reduction group. Loadings table displays with one row per feature. Cells with |loading| > 0.5 are bold/orange. Variance % bar shows per factor. Download CSV button present.  
**Source:** Part109, Part110

---

### TC-HIST-015
**Category:** Feature  
**Test Name:** LDA — new reduction tab, binary target shows 1D histogram  
**Steps:**
1. Navigate to Feature Selection tool
2. Upload Titanic CSV (binary Survived target)
3. Enable LDA tab in Reduction section
4. Click "Run Feature Selection"
5. View the LDA result card

**Expected Result:** LDA tab appears in Reduction group. A 1D histogram with dots on horizontal LD1 axis is shown. Dots colored by class (0/1). Deterministic jitter positions dots vertically.  
**Source:** Part109, Part110

---

### TC-HIST-016
**Category:** Feature  
**Test Name:** LDA — warning chip shown when target is numeric or empty  
**Steps:**
1. Navigate to Feature Selection tool
2. Upload a CSV; leave target column unset or select a numeric column as target
3. Enable LDA reduction
4. Click "Run Feature Selection"

**Expected Result:** LDA result area shows warning chip: "⚠ LDA requires a categorical target column". No scatter or histogram rendered.  
**Source:** Part109, Part110

---

### TC-HIST-017
**Category:** Feature  
**Test Name:** LDA — 3-class dataset shows 2D scatter  
**Steps:**
1. Navigate to Feature Selection tool
2. Upload Iris CSV (3-class Species target)
3. Enable LDA reduction
4. Click "Run Feature Selection"

**Expected Result:** LDA result shows a 2D SVG scatter with axis labels LD1/LD2, dots colored by class, and a legend.  
**Source:** Part109, Part110

---

### TC-HIST-018
**Category:** Feature  
**Test Name:** LDA — 4+ class dataset shows 3D scatter with OrbitControls  
**Steps:**
1. Navigate to Feature Selection tool
2. Upload a CSV with 4+ distinct class values in target column
3. Enable LDA reduction
4. Click "Run Feature Selection"
5. Drag to rotate the 3D scatter

**Expected Result:** LDA result shows a 3D Three.js scatter. Rotation responds to drag. "Reset view" button resets camera.  
**Source:** Part109, Part110

---

### TC-HIST-019
**Category:** Feature  
**Test Name:** Latent Dirichlet Allocation — FE tool generates topic columns from text column  
**Steps:**
1. Navigate to Feature Engineering tool
2. Upload a CSV with at least one string/text column
3. Scroll to the LDA panel; select the text column; set nTopics=5, nIter=50
4. Click "Run LDA"
5. Observe output columns

**Expected Result:** Columns `lda_topic_0` through `lda_topic_4` appended to the dataset. Each topic shows top-word chips in per-topic colors in the panel.  
**Source:** Part110

---

### TC-HIST-020
**Category:** Feature  
**Test Name:** FE LDA — only string/categorical columns appear in column selector  
**Steps:**
1. Navigate to Feature Engineering tool
2. Upload a mixed CSV (numeric and text columns)
3. Open LDA panel; inspect column selector

**Expected Result:** Only string/categorical columns listed in the LDA column selector. Numeric columns are not shown.  
**Source:** Part110

---

### TC-HIST-021
**Category:** Feature  
**Test Name:** FE LDA — custom stopwords merged with built-in list  
**Steps:**
1. Navigate to Feature Engineering tool
2. Upload a CSV with a text column containing known repeated words (e.g., "ship", "ocean")
3. Open LDA panel; enter "ship, ocean" in the custom stopwords field
4. Run LDA; inspect top words per topic

**Expected Result:** "ship" and "ocean" do not appear as top words in any topic output. Other high-frequency words still appear normally.  
**Source:** Part112

---

### TC-HIST-022
**Category:** Feature  
**Test Name:** FE LDA — stemming toggle reduces word variants to stems  
**Steps:**
1. Navigate to Feature Engineering tool
2. Upload a CSV with text column containing words like "running", "runner", "runs"
3. Enable the Stemming toggle in LDA panel
4. Run LDA; inspect top words per topic

**Expected Result:** Words with common suffixes (ing, er, s, ed, etc.) appear in stemmed form. Words ≤ 4 chars are unchanged.  
**Source:** Part112

---

### TC-HIST-023
**Category:** Feature  
**Test Name:** FE LDA — min document frequency slider filters rare words  
**Steps:**
1. Navigate to Feature Engineering tool
2. Upload a CSV with text column; set min doc frequency slider to 5
3. Run LDA

**Expected Result:** Words appearing in fewer than 5 documents do not appear in any topic's top words.  
**Source:** Part112

---

### TC-HIST-024
**Category:** Data  
**Test Name:** FE LDA — row cap at 1000 rows (silently processed)  
**Steps:**
1. Navigate to Feature Engineering tool
2. Upload a CSV with more than 1000 text rows
3. Run LDA

**Expected Result:** LDA runs without error. Only the first 1000 rows are processed (no crash or freeze). Topic columns are appended.  
**Source:** Part110, Part112

---

### TC-HIST-025
**Category:** Feature  
**Test Name:** PCA — "Auto (Kaiser)" toggle keeps only components with eigenvalue > 1  
**Steps:**
1. Navigate to Feature Selection tool
2. Upload a CSV with 6+ numeric features
3. Enable PCA reduction tab
4. Toggle "Auto (Kaiser)" ON
5. Click "Run Feature Selection"

**Expected Result:** Slider dims and shows "auto". PCA retains only components with eigenvalue > 1 (minimum 1 component). Component count differs from slider value.  
**Source:** Part112

---

### TC-HIST-026
**Category:** Feature  
**Test Name:** PCA — 2D/3D toggle available when 3+ components computed  
**Steps:**
1. Navigate to Feature Selection tool
2. Upload a CSV with 5+ numeric features
3. Enable PCA; set components to 3
4. Click "Run Feature Selection"
5. Inspect the PCA result card for a 2D/3D toggle

**Expected Result:** A 2D/3D toggle is visible. Selecting 3D shows the scatter in three dimensions. Note explains "3D available with 3+ components".  
**Source:** Part112

---

### TC-HIST-027
**Category:** Feature  
**Test Name:** FA — 2D/3D toggle available when 3+ factors computed  
**Steps:**
1. Navigate to Feature Selection tool
2. Enable FA reduction; set factors to 3
3. Click "Run Feature Selection"
4. Inspect FA result card

**Expected Result:** 2D/3D toggle visible. Selecting 3D shows 3D scatter with axis prefix "F" (F1, F2, F3). 2D shows 2D scatter.  
**Source:** Part112

---

### TC-HIST-028
**Category:** Feature  
**Test Name:** PCA + FA — projected scatter colored by target class  
**Steps:**
1. Navigate to Feature Selection tool
2. Upload a CSV with a categorical target column
3. Enable PCA (3 components); click "Run Feature Selection"
4. View the projected scatter in the PCA result card

**Expected Result:** Scatter shows one dot per data row. Dots are colored by class value. A legend lists class colors. x/y axis lines and labels are visible.  
**Source:** Part111

---

### TC-HIST-029
**Category:** Feature  
**Test Name:** FS — Drop Columns panel excludes selected columns from selection run  
**Steps:**
1. Navigate to Feature Selection tool
2. Upload a CSV with 6+ columns
3. Expand the "Exclude Columns" panel above the tab bar
4. Click to exclude 2 columns (they show strikethrough + red tint)
5. Click "Run Feature Selection"

**Expected Result:** The 2 excluded columns do not appear in ranking tables or selection results. Header badge shows count of excluded columns.  
**Source:** Part108

---

### TC-HIST-030
**Category:** Feature  
**Test Name:** FS — HowItWorks section shows method-specific label per tab  
**Steps:**
1. Navigate to Feature Selection tool
2. Enable Variance method; run selection
3. Click the Variance tab; expand the HowItWorks section

**Expected Result:** HowItWorks label reads "How Variance Filter works" (not a generic "How it works").  
**Source:** Part109

---

### TC-HIST-031
**Category:** Feature  
**Test Name:** FS — AI Suggest uses jsonMode for clean structured output  
**Steps:**
1. Navigate to Feature Selection tool
2. Upload a CSV
3. Click "AI Suggest Methods"
4. Check that no "No JSON found" error appears

**Expected Result:** AI Suggest succeeds. `jsonMode: true` ensures Gemini returns clean JSON. Methods update without parse errors.  
**Source:** Part108, Part109

---

### TC-HIST-032
**Category:** Feature  
**Test Name:** ML Capabilities cards — hover tilt + glow effect active  
**Steps:**
1. Navigate to the homepage or ML Capabilities section
2. Hover the cursor over a Capability card
3. Move cursor across the card surface

**Expected Result:** Card tilts in 3D following cursor position. Accent-colored glow and border appear. A shimmer radial gradient follows tilt angle. Card springs back to flat when cursor leaves.  
**Source:** Part111

---

### TC-HIST-033
**Category:** Feature  
**Test Name:** UMAP 3D — Reset view button returns camera to initial position  
**Steps:**
1. Navigate to Feature Selection tool
2. Upload a CSV with categorical target
3. Enable UMAP (3D); run selection
4. Drag to rotate the 3D scatter to an arbitrary angle
5. Click "Reset view"

**Expected Result:** Camera snaps back to the initial default orientation.  
**Source:** Part107

---

### TC-HIST-034
**Category:** AutoML  
**Test Name:** AutoML accent color is green (not purple) matching Step 4 badge  
**Steps:**
1. Navigate to the AutoML tool
2. Observe the accent/highlight color used in step indicators and badges

**Expected Result:** Accent color is green (#22c55e), not purple (#818cf8). Step 4 badge and ACCENT-colored elements match.  
**Source:** Part107

---

### TC-HIST-035
**Category:** Feature  
**Test Name:** FS page — modularized, page.tsx renders without error after refactor  
**Steps:**
1. Navigate to Feature Selection tool
2. Upload any CSV
3. Enable multiple methods across Filter, Score, Wrapper, Reduction groups
4. Run selection; inspect all result cards

**Expected Result:** Page loads without JS errors. All result cards render. Tabs group correctly by Filter/Score/Wrapper/Reduction. No undefined component errors from modularized imports.  
**Source:** Part107, Part108

---

### TC-HIST-036
**Category:** Feature  
**Test Name:** FE page — modularized hooks, page renders without error  
**Steps:**
1. Navigate to Feature Engineering tool
2. Upload a CSV
3. Apply a transform (e.g. scale a numeric column)
4. Use AI Suggest
5. Run LDA on a text column

**Expected Result:** All three actions complete without error. Hooks (useFELDA, useFETransforms, useFEAISuggest, useFEFileLoad) operate independently with no state collision.  
**Source:** Part111

---

### TC-HIST-037
**Category:** UI  
**Test Name:** ReductionTabs — label font size is 0.82rem  
**Steps:**
1. Navigate to Feature Selection tool
2. Enable PCA, UMAP, FA, and LDA reduction tabs
3. Inspect the enable-label and value-display text in each panel via DevTools computed styles

**Expected Result:** Font size for enable labels and value displays in all reduction panels is 0.82rem.  
**Source:** Part111

---

### TC-HIST-038
**Category:** UI  
**Test Name:** HowItWorks section — visually separated from sticky Run button row  
**Steps:**
1. Navigate to Feature Selection tool
2. Upload a CSV
3. Scroll to the sticky "Run Feature Selection" button row
4. Observe the HowItWorks section below (or above) it

**Expected Result:** A visible gap (1.5rem margin-top wrapper) separates the HowItWorks section from the sticky Run button row. No visual overlap.  
**Source:** Part111

---

### TC-HIST-039
**Category:** Feature  
**Test Name:** LDA panel in FE — "How Latent Dirichlet Allocation works" collapsible section present  
**Steps:**
1. Navigate to Feature Engineering tool
2. Upload a CSV with a text column
3. Scroll to the LDA panel; look for the expandable documentation section

**Expected Result:** A collapsible "How Latent Dirichlet Allocation works" section is visible. Expanding it shows the 7-step pipeline. Stopword count reads "~320".  
**Source:** Part112

---

### TC-HIST-040
**Category:** Data  
**Test Name:** UMAP — samples max 400 rows for graph construction (no crash on large dataset)  
**Steps:**
1. Navigate to Feature Selection tool
2. Upload a CSV with more than 400 rows
3. Enable UMAP reduction
4. Click "Run Feature Selection"

**Expected Result:** UMAP completes without crashing. Scatter is rendered. Remaining rows beyond 400 projected via kNN extension without error.  
**Source:** Part112

---

### TC-HIST-041
**Category:** Data  
**Test Name:** FA — samples max 500 rows for factoring (no crash on large dataset)  
**Steps:**
1. Navigate to Feature Selection tool
2. Upload a CSV with more than 500 rows
3. Enable FA reduction
4. Click "Run Feature Selection"

**Expected Result:** FA completes without crashing. Loadings table renders for all features. Rows beyond 500 handled via kNN extension.  
**Source:** Part112

---

### TC-HIST-042
**Category:** Feature  
**Test Name:** FS — method agreement table appears only when 2+ scoring methods are active  
**Steps:**
1. Navigate to Feature Selection tool
2. Upload a CSV
3. Enable only Variance (1 method); run — inspect results (no agreement table expected)
4. Also enable Lasso and Tree; run again

**Expected Result:** With 1 scoring method: no agreement table. With Lasso + Tree active: method agreement table appears below rankings showing ✓/× grid with "N/5 agree" consensus column.  
**Source:** Part107

---

### TC-HIST-043
**Category:** Feature  
**Test Name:** FS — pipeline indicator shows active methods as colored pills above Run button  
**Steps:**
1. Navigate to Feature Selection tool
2. Enable 3 methods (e.g. Variance, Lasso, PCA)
3. Look at the area above the "Run Feature Selection" button

**Expected Result:** Three colored pills separated by arrows are shown, one per active method. Disabling a method removes its pill.  
**Source:** Part107

---

### TC-HIST-044
**Category:** Feature  
**Test Name:** FS — Reset Methods button clears results and resets opts to defaults  
**Steps:**
1. Navigate to Feature Selection tool
2. Upload a CSV; enable multiple methods; run selection
3. Click "Reset Methods"

**Expected Result:** All methods reset to default configuration. Result cards disappear. Uploaded file remains loaded (not cleared).  
**Source:** Part107
