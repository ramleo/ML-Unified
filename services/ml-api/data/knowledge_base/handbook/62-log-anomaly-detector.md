Chapter 54Log Anomaly Detector


> A live security-log monitor. A real scikit-learn Isolation Forest learns what normal web traffic looks like from a baseline, then flags the requests that don't fit — brute-force login floods, scrapers walking random URLs, oversized payloads, error-heavy bursts at 3am — in a rolling feed where anomalies flash red. The traffic is simulated and labelled (a live serverless site can't stream its own logs into a public page), and the model is scored honestly against ground truth it never sees, so it can be caught missing an attack or raising a false alarm.

## At a glance

| | |
|---|---|
| **Also called** | Live Engine · Isolation Forest |
| **Model or method** | scikit-learn IsolationForest |
| **What you give it** | Simulated request-log stream |
| **Traffic Features** | 5 |
| **Where it runs** | On the server, with a live external check |
| **Find it at** | `/tools/anomaly-detection` |

### What this tool does
It watches a stream of web-server request logs and flags the ones that
don't look like normal traffic — a brute-force login flood, a scraper
walking random URLs, an oversized upload, a burst of failed requests at
3am. The detector is a real **Isolation Forest** (scikit-learn), the
classic unsupervised anomaly-detection algorithm, running on the FastAPI
backend.

### The honest part: the traffic is simulated
A live site on serverless hosting can't pipe its own real request logs
into a public page, and faking that would be dishonest. So the tool
generates a **labelled** stream instead: a large baseline of normal
traffic, plus a handful of planted attacks whose true identity it keeps
hidden from the model. The Isolation Forest is trained on the normal
baseline **only** — it never sees which requests are attacks. That's what
makes the scorecard trustworthy: the model can be caught missing an attack
or raising a false alarm, and the numbers say so.

### How to read it
1. Press **Run detection**. The model first learns "normal" from the
   baseline, then the live feed starts.
2. Each request slides into the feed. A **red row** is one the model
   flagged as anomalous; a quiet row passed.
3. The red chip names the single feature that deviated most from normal
   (e.g. *Requests/min*, *Payload size*). It's a plain-English hint for a
   human — not the model's internal reason for flagging.
4. When the run finishes, the **scorecard** compares the model's flags
   against the ground truth: attacks caught, missed, false alarms, and
   precision / recall.

### The five features
The model looks at five ordinary pieces of request metadata a real WAF
already has:
- **Requests/min** — how fast one IP is hitting the site (floods stand out).
- **Payload size** — an unusually large body can mean an exfiltration or
  upload abuse.
- **Time of day** — human traffic clusters in daytime; 3am bursts are odd.
- **Path randomness** — how token-like the URL looks (its share of digits);
  fuzzers and scanners hit random hex-ish paths, an app's own named routes
  don't.
- **Error rate** — a spike of 401/403/500 from one IP suggests probing.

### What it is and isn't
The detector is genuinely unsupervised machine learning doing real work;
the traffic is a teaching harness, not a live SIEM. A production version
would feed real logs and retrain on its own traffic over time. Isolation
Forest is a strong first line, not a complete security stack — it finds
statistical outliers, and a careful attacker who blends into normal
traffic is exactly what it can miss.
