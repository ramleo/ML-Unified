Chapter 1ML Unified Platform


> One app, four models. Select Iris classifier, Titanic survival predictor, Diabetes risk model, or Insurance premium estimator from a sidebar — all served from a single schema-driven FastAPI backend with dynamic forms.

## At a glance

| | |
|---|---|
| **Model or method** | Multi-Model |
| **What it does** | Platform |
| **Works on** | 4 Datasets · 26 Features |
| **Models** | 4 |
| **Find it at** | `/ml` |

### What the ML Unified Platform is
ML Unified is a tabular-prediction platform inside AIRaML: **four trained
machine-learning models in one app**, each served from a single schema-driven
FastAPI backend. Pick a model from the sidebar, fill a form that is generated
automatically from that model's feature schema, and get a live prediction back —
with the class probabilities (for classifiers) or the predicted value (for the
regressor).

Everything runs on a real backend against real trained models — not a canned
demo — and it is free to use.

### The four models
- **Iris Species** *(classification · Logistic Regression · 96.7% accuracy)* —
  three species from four petal/sepal measurements.
- **Titanic Survival** *(classification · Gradient Boosting · 82.5% accuracy)* —
  survived or not, from class, sex, age, fare and family aboard.
- **Diabetes Risk** *(classification · Random Forest · 77.5% accuracy)* — risk
  from eight clinical measurements (glucose, BMI, blood pressure, …).
- **Insurance Premium** *(regression · Random Forest · ±668 ₹ MAE)* — an annual
  premium from age, BMI, smoking status, region and more.

### Using the platform (step by step)
1. Click **Open the platform** to launch the ML mode of the app.
2. **Pick a model** in the sidebar. The form on the right rebuilds itself from
   that model's schema — the right fields, labels, and value ranges appear
   automatically.
3. **Fill the form.** Every numeric field shows its valid range (min–max) and
   step; categorical fields become dropdowns. Sensible defaults are pre-filled so
   you can predict immediately.
4. Click **Predict**. The request goes to the FastAPI backend, the trained model
   runs, and the result comes back.
5. **Read the result.** Classifiers show the predicted class and the probability
   for each class; the regressor shows the predicted number (e.g. the premium).

### What makes it interesting
- **Schema-driven, not hard-coded.** One backend serves all four models; each
  model ships a JSON schema (fields, types, ranges), and the UI builds its form
  from that schema. Adding a fifth model is a schema + a trained model, not a new
  page.
- **Honest metrics.** Each model states its real held-out metric (accuracy or
  MAE) up front — no inflated claims.
- **One microservice.** The same FastAPI service also powers EDA Explorer and the
  Vision Platform; they are three modes of one deployment.

### Honest limits
- These are **compact models on small public datasets** (Iris, Titanic, Pima
  diabetes, an insurance set). They illustrate an end-to-end ML app; they are not
  medical, financial or actuarial advice.
- A prediction is only as good as the inputs and the training data — treat the
  probabilities as the model's estimate, not ground truth.
- Inputs must fall within each field's stated range; out-of-range values are
  rejected rather than silently extrapolated.

### FAQ
- **Do I need to know ML?** No — pick a model, fill the form, read the
  prediction. The metric next to each model tells you roughly how much to trust it.
- **Where does it run?** On a FastAPI backend (the ML mode of the shared
  ML-Unified Space) — the model runs server-side, nothing is computed in your
  browser.
- **Can I see the data behind it?** Use **EDA Explorer** (a sister platform) to
  upload a CSV and profile it, or the Vision Platform for image tasks — all three
  are modes of the same app.
- **Is it free?** Yes.

### Why it matters
Most ML demos hard-code one model into one page. This shows the pattern real
products use: a single service, driven by per-model schemas, rendering the right
form and running the right model on demand — the boring, correct architecture,
done cleanly and stated honestly.
