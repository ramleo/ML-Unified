Chapter 11Exploratory Data Analysis


> Upload a CSV and see what you actually have before deciding what to do with it. Overview and duplicate count, a per-column profile with missing values and cardinality, distributions and a correlation matrix, principal components and mutual information, and a pass, warn or fail verdict on whether each column is fit to model on. A statistic that is not defined for your data reads as a dash, never as zero. Nothing is stored, and the file is analysed in memory.

## At a glance

| | |
|---|---|
| **Also called** | Profile Before You Model |
| **Model or method** | pandas · scikit-learn (no profiling library) |
| **What you give it** | Any CSV up to 10 MB |
| **Checks** | 12 |
| **Where it runs** | On the server |
| **Find it at** | `/tools/exploratory-data-analysis` |

### What this tool does
Upload a CSV and it profiles the whole file in one pass: shape, missing
values, duplicates, per-column statistics, distributions, relationships
between columns, and a verdict on whether each column is fit to train on.
Nothing is trained here — this is the step before that, the one that decides
whether training is worth attempting at all.

### Purpose
Most model failures are decided before any model exists. A column that is 90%
missing, a target that leaks into a feature, a "numeric" column that is
secretly text, two features that are the same measurement twice — each of
these produces a model that scores well and behaves badly. This page is built
to surface those in the first minute rather than the third week.

### How to use it
1. Click **Upload CSV** and choose a file. The first row is treated as the
   header.
2. Wait for the profile. Everything below appears at once; nothing is
   computed lazily as you scroll.
3. Use the **section tabs** at the top to jump between panels. Tabs appear
   only for panels your data actually produced — a file with one numeric
   column has no scatter matrix, and no tab for one.
4. Read **Overview** and **Readiness** first. They tell you whether the rest
   is worth reading.
5. Download a **PDF or HTML report** from the Report panel when you want to
   send the profile to someone.

### Reading each panel

**Overview** — rows, columns, duplicate count, overall missing percentage,
and a quality score out of 100. The score is a rough summary, not a grade:
treat it as "how much cleaning is ahead", not "how good this data is".

**Summary** — a written paragraph describing the dataset in plain language.
Generated from the numbers, not from an opinion about your domain.

**Insights** — specific things worth knowing, each tagged with its kind.
These are the sentences most likely to change what you do next.

**Readiness** — one card per column with a verdict of **Ready**, **Review**
or **Fix**, and the reason in full text rather than hidden in a tooltip. Fix
means the column will actively hurt a model; Review means it depends on what
you are predicting.

**AI suggestions** — feature-engineering ideas from a language model, with
the provider that answered named on each. Suggestions, not instructions: the
model can see your column names and statistics, not your problem.

**First rows** — the first five rows exactly as parsed. Worth a glance: this
is where you catch a delimiter that split a column in the wrong place.

**Duplicates** — appears only when exact duplicate rows exist. Duplicates
inflate confidence in whatever they duplicate.

**Columns** — one labelled bar per column showing its missing percentage,
with type, missing count and number of distinct values beneath. Sorted so
the worst columns are impossible to miss.

**Statistics** — three views of the numeric columns: outlier counts ranked by
the IQR rule, skewness as bars either side of a centre line, and a detail
table with mean, standard deviation, quartiles and range. A skew far from
zero means the mean is not where most of the data is.

**Distributions** — a histogram per numeric column. Cards for columns with
almost no variation carry a low-variance badge; a column that barely changes
cannot help a model separate anything.

**Spread** — a box plot per column, each on its own axis. Separate axes are
deliberate: on one shared axis a column measured in millions flattens every
other column into a line.

**Mutual info** — how much knowing one column tells you about another,
including non-linear relationships that correlation misses entirely.

**Scatter matrix** — every numeric column plotted against every other. This
is where clusters, curves and hard boundaries become visible. Colour the
points by a categorical column to see whether the groups separate.

**3D projection** — the data compressed to three dimensions by PCA. If your
classes form separate clouds here, a simple model will probably work; if they
sit on top of each other, it probably will not.

**Correlations** — a Pearson heatmap. Cells that cannot be computed are
marked n/a rather than shown as zero, which would read as "unrelated".
Correlation near 1 or -1 between two features means one of them is close to
redundant.

**Clean** — apply fixes (drop columns, handle missing values) and download
the cleaned CSV.

**Report** — download the whole profile as PDF or HTML. You choose light or
dark at the moment of download, independently of the theme you are viewing in.

### Notes & limits
- Correlation and PCA describe **linear** structure. Two columns can be
  perfectly related and score near zero correlation; the scatter matrix and
  mutual information exist to catch that.
- Every verdict is about the data in isolation. The tool does not know your
  target column or your problem, so "Ready" means "nothing structurally wrong
  here", never "useful for your prediction".
- Outliers are flagged by the IQR rule, which is a convention, not a
  judgement. A flagged value can be the most important row in the file.
- Quality score and readiness are heuristics with fixed thresholds. Read the
  reason on the card, not the label.
- Large files are profiled in full, but the sample table and some charts show
  a subset for legibility. Counts always come from the whole file.
