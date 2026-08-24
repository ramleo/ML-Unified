# Conversation – 2026-06-02 (Part 9): Per-Project Fixes + Fill Sample Button

---

## Plan Sequence (agreed this session)

1. ✅ Categorical dropdowns — all datasets
2. ✅ Domain-informed bounds — Iris, Titanic, Diabetes
3. ✅ Human-readable class labels — Titanic, Diabetes
4. ✅ Fill Sample button — all 4 projects
5. ⬜ Portfolio website (Next.js + Vercel) — **next**
6. ⬜ MLflow experiment tracking
7. ⬜ Data drift / model drift detection
8. ⬜ Monitoring — Grafana + Prometheus
9. ⬜ Test-gate CI
10. ⬜ E2E browser testing (Playwright)
11. ⬜ Full pipeline validation (commit → live)
12. ⬜ CNN / deep learning project
13. ⬜ Data injection (DB, cloud, real-time)

**Tech decisions:**
- Frontend: **Next.js**
- Hosting: **Vercel**

---

## Fixes Done This Session

### 1. Titanic — Categorical Dropdowns
- `Pclass` → `<select>` (1 – First Class / 2 – Second Class / 3 – Third Class)
- `Sex` → `<select>` (Male / Female)
- `Embarked` → `<select>` (C – Cherbourg / Q – Queenstown / S – Southampton)
- Added `select.inp` CSS + `[data-theme="light"] select.inp` overrides
- Iris: all numeric — no dropdowns needed
- Diabetes: all numeric — no dropdowns needed
- ML-Pipeline-Auto: already auto-generates `<select>` from categorical columns ✓

### 2. Domain-Informed Feature Ranges
Created `models/feature_ranges.json` for each project from real-world sources:

**Iris** (Anderson/Fisher 1936 study):
| Feature | Min | Max | Step |
|---|---|---|---|
| SepalLengthCm | 4.3 | 7.9 | 0.1 |
| SepalWidthCm | 2.0 | 4.4 | 0.1 |
| PetalLengthCm | 1.0 | 6.9 | 0.1 |
| PetalWidthCm | 0.1 | 2.5 | 0.1 |

**Titanic** (actual passenger manifest):
| Feature | Min | Max | Step |
|---|---|---|---|
| Age | 0 | 80 | 1 |
| SibSp | 0 | 8 | 1 |
| Parch | 0 | 5 | 1 |
| Fare | 0 | 512.33 | 0.01 |

Note: Age changed from min=0.42/step=0.1 → min=0/step=1 to fix browser step-validation error ("nearest valid values are 21.92 and 22.02").

**Diabetes** (Pima Indians dataset, UCI):
| Feature | Min | Max | Step |
|---|---|---|---|
| Pregnancies | 0 | 17 | 1 |
| Glucose | 44 | 199 | 1 |
| BloodPressure | 24 | 122 | 1 |
| SkinThickness | 0 | 99 | 1 |
| Insulin | 0 | 846 | 1 |
| BMI | 18.2 | 67.1 | 0.1 |
| DiabetesPedigreeFunction | 0.078 | 2.42 | 0.001 |
| Age | 21 | 81 | 1 |

Note: Glucose/BP/BMI minimums set to lowest non-zero value (0 in raw data = missing).

### 3. Human-Readable Class Labels
- **Titanic**: `CLASSES = ["Not Survived", "Survived"]` + `CLASS_LABELS = {"0": "Not Survived", "1": "Survived"}`
- **Diabetes**: `CLASSES = ["Non-Diabetic", "Diabetic"]` + `CLASS_LABELS = {"0": "Non-Diabetic", "1": "Diabetic"}`
- **Iris**: already shows species names ("Iris-setosa" etc.) — no change needed
- Updated `resVal.textContent` and history table to use `CLASS_LABELS[String(data.prediction)]`

### 4. Fill Sample Button
Added `⚡ Fill Sample` button to all 4 projects with real dataset rows:

| Project | Sample Data | Expected Prediction |
|---|---|---|
| Titanic | Female, 1st class, Age 38, Fare 71.28, Embarked C | Survived |
| Iris | 5.1 / 3.5 / 1.4 / 0.2 | Iris-setosa |
| Diabetes | Pregnancies 1, Glucose 89, BP 66, BMI 28.1, Age 21 | Non-Diabetic |
| Insurance | Age 35, Income 75k, Married, Employed, Urban | Mid-range premium |

**Root cause fixed**: `clearAllFields()` and `fillSample()` were both missing from Iris/Titanic/Diabetes (older bootstrap didn't include them). Added both functions explicitly.

**Also fixed**: Clear button invisible in light mode — added `[data-theme="light"] button[onclick="clearAllFields()"]` CSS override.

**Sample name shortened**: "Cumings, Mrs. John Bradley" → "Smith, Mr. John" to avoid input summary overflow.

---

## Bugs Fixed (hero + tooltip from previous session)

### Tooltip `?` disappeared after page load
- **Root cause**: JS did `_ch.textContent = 'Likely...'` which wiped the `<span class="tip-wrap">` tooltip HTML inside `ciHeader`
- **Fix**: Wrapped header text in `<span id="ciHeaderTxt">` — JS now updates only that span
- Applied to both `Temp-Insurance/index.html` and `ML-Pipeline-Auto/auto_pipeline.py`

### Hero light theme
- Changed overlay from dark navy `rgba(26,60,94,.35)` → white/soft blue `rgba(255,255,255,.62)` / `rgba(220,235,255,.68)`
- Added `body.light .hero-h1`, `body.light .hero p`, `body.light .hero > div > div:first-child` dark color rules
- Tooltip icon: bumped to 16px, 50% white opacity, 1.5px border

---

## Commits This Session

| Repo | Commit | Description |
|---|---|---|
| ML-Titanic | `8b39a0a` | Categorical dropdowns: Pclass, Sex, Embarked |
| ML-Titanic | `ce14afb` | Domain-informed feature_ranges.json |
| ML-Titanic | `cb8646b` | Fix Age slider step validation |
| ML-Titanic | `1125081` | Human-readable class labels |
| ML-Titanic | `dec966d` | Add Fill Sample button |
| ML-Titanic | `5eb8ffc` | Add missing clearAllFields + fillSample functions |
| ML-Titanic | `f7e95fa` | Fix Clear button invisible in light mode |
| ML-Titanic | `2aaaa1b` | Shorten sample Name |
| ML-Iris | `d415588` | Domain-informed feature_ranges.json |
| ML-Iris | `1196deb` | Add Fill Sample button |
| ML-Iris | `794086b` | Add missing clearAllFields + fillSample functions |
| ML-Iris | `8c184cf` | Fix Clear button invisible in light mode |
| ML-Diabetes | `997f96e` | Domain-informed feature_ranges.json |
| ML-Diabetes | `c91ad2b` | Human-readable class labels |
| ML-Diabetes | `b304bdf` | Add Fill Sample button |
| ML-Diabetes | `cc4f8f6` | Add missing clearAllFields + fillSample functions |
| ML-Diabetes | `4bb24f0` | Fix Clear button invisible in light mode |
| Temp-Insurance | `ab852a4` | Light theme: white/soft hero, dark text, clear btn |
| Temp-Insurance | `7cca66f` | Tooltip icon larger + higher contrast |
| Temp-Insurance | `6ba9bef` | Fix tooltip: ciHeaderTxt span so JS doesn't wipe HTML |
| Temp-Insurance | `82d5832` | Add Fill Sample button |
| ML-Pipeline-Auto | `0da341c` | Template: hero light theme fixes |
| ML-Pipeline-Auto | `2d4463f` | Template: tooltip icon size |
| ML-Pipeline-Auto | `56a6ba1` | Template: fix ciHeaderTxt tooltip bug |

---

## Standing Rules
- Always apply changes to ALL affected repos simultaneously
- Also push to `ML-Pipeline-Auto` (+ re-embed `bootstrap.py`) for template changes
- Run unit tests before pushing (Insurance: 33 tests must pass)
- Conversation logs stored in `ML-Iris/` folder
- Light theme: ALL elements must adapt — overlays, text, images, buttons, icons
