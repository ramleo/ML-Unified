# Clustering Guide

## When to Use Clustering

Clustering is unsupervised — there is no target variable. Use it to:
- Discover natural groupings in data (customer segments, document topics)
- Compress or summarize data before supervised learning
- Anomaly detection (points that don't belong to any cluster)
- Preprocessing for semi-supervised learning

Clustering is exploratory. Results depend heavily on the algorithm, distance metric, and hyperparameters. Always validate clusters with domain knowledge, not just metrics.

---

## K-Means

**How it works**: Assign each point to the nearest centroid. Recompute centroids as cluster means. Repeat until convergence.

**Strengths**: Fast, scalable, simple to understand. Works well when clusters are roughly spherical and similar in size.

**Weaknesses**: Must specify K in advance. Sensitive to outliers (centroid is pulled toward them). Fails on non-spherical clusters (crescents, rings). Assumes clusters have similar variance.

**Hyperparameters**:
- `n_clusters` (K): Most important parameter. Choose via elbow method or silhouette score.
- `n_init`: Number of random initializations (default 10). Run multiple times, keep best inertia.
- `init`: `"k-means++"` (default) is much better than random initialization.
- `max_iter`: Convergence iterations (default 300 is usually enough).

**Choosing K — elbow method**:
Plot inertia (within-cluster sum of squares) vs K. Look for the "elbow" where adding more clusters gives diminishing returns. The elbow is often subjective — silhouette score is more reliable.

**Choosing K — silhouette score**:
Silhouette score ranges from -1 to 1. Higher = better defined clusters. Try K from 2 to 10, pick the K with the highest average silhouette.

```python
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

scores = []
for k in range(2, 11):
    km = KMeans(n_clusters=k, init="k-means++", n_init=10, random_state=42)
    labels = km.fit_predict(X_scaled)
    scores.append(silhouette_score(X_scaled, labels))
best_k = range(2, 11)[scores.index(max(scores))]
```

**Always scale features before K-Means.** Euclidean distance is not meaningful when features have different units or scales.

---

## DBSCAN

**How it works**: Groups points that are densely packed together (within `eps` distance and at least `min_samples` neighbors). Points in low-density regions are labeled as noise (-1).

**Strengths**: Does not require specifying K. Finds arbitrarily shaped clusters. Naturally handles outliers — they become noise points rather than distorting clusters.

**Weaknesses**: Sensitive to `eps` and `min_samples`. Struggles when clusters have very different densities. Poor performance in high dimensions (curse of dimensionality makes all distances similar).

**Hyperparameters**:
- `eps`: Neighborhood radius. Critical. Too small → everything is noise. Too large → everything is one cluster.
- `min_samples`: Minimum neighbors to form a dense region. Rule of thumb: `2 * n_features` for low-dimensional data.

**Choosing eps**: Plot the k-nearest-neighbor distance for each point (k = min_samples), sorted in ascending order. Look for the "knee" — that distance is a good `eps`.

```python
from sklearn.cluster import DBSCAN
from sklearn.neighbors import NearestNeighbors
import numpy as np

k = 2 * X_scaled.shape[1]
nbrs = NearestNeighbors(n_neighbors=k).fit(X_scaled)
distances, _ = nbrs.kneighbors(X_scaled)
distances = np.sort(distances[:, k-1])
# Plot distances to find the knee
```

**Noise label**: DBSCAN assigns label `-1` to noise points. These are outliers. Do not pass them to downstream models without handling.

---

## Hierarchical Clustering (Agglomerative)

**How it works**: Start with each point as its own cluster. Iteratively merge the two closest clusters. Produces a dendrogram (tree) showing all merge decisions.

**Strengths**: No need to specify K in advance (can cut the dendrogram at any level). Deterministic. Produces a full hierarchy of clusterings.

**Weaknesses**: O(n²) memory and O(n² log n) time — not suitable for >10k samples. Greedy merges cannot be undone.

**Hyperparameters**:
- `n_clusters`: Cut the dendrogram at this level.
- `linkage`: How to measure distance between clusters.
  - `ward`: Minimizes variance within clusters. Usually best for compact clusters.
  - `complete`: Maximum distance between cluster members. Creates compact clusters.
  - `average`: Average distance. Compromise between ward and complete.
  - `single`: Minimum distance. Prone to "chaining" (long thin clusters).

```python
from sklearn.cluster import AgglomerativeClustering
model = AgglomerativeClustering(n_clusters=4, linkage="ward")
labels = model.fit_predict(X_scaled)
```

---

## Gaussian Mixture Models (GMM)

**How it works**: Assumes data comes from a mixture of K Gaussian distributions. Fits means, covariances, and mixing weights via Expectation-Maximization.

**Strengths**: Soft assignments (probability of belonging to each cluster). Handles elliptical clusters (covariance can be estimated). More flexible than K-Means.

**Weaknesses**: More parameters to estimate — needs more data. Sensitive to initialization. Can overfit with full covariance matrices on small datasets.

```python
from sklearn.mixture import GaussianMixture
gmm = GaussianMixture(n_components=3, covariance_type="full", random_state=42)
labels = gmm.fit_predict(X_scaled)
probs = gmm.predict_proba(X_scaled)  # soft assignments
```

---

## Evaluation Metrics

### Silhouette Score
Measures how similar each point is to its own cluster vs the nearest other cluster. Range: -1 (wrong cluster) to 1 (perfect). Above 0.5 is considered good.

```python
from sklearn.metrics import silhouette_score
score = silhouette_score(X_scaled, labels)
```

### Davies-Bouldin Index
Ratio of within-cluster scatter to between-cluster separation. Lower is better. More intuitive than silhouette for comparing cluster compactness.

### Calinski-Harabasz Score
Ratio of between-cluster dispersion to within-cluster dispersion. Higher is better. Fast to compute.

### When ground truth is available
- **Adjusted Rand Index (ARI)**: Agreement between predicted and true labels, adjusted for chance. 1.0 = perfect.
- **Normalized Mutual Information (NMI)**: Information shared between labels. 1.0 = perfect.

---

## Algorithm Selection Guide

| Situation | Recommended |
|-----------|-------------|
| Unknown K, roughly spherical clusters | K-Means with silhouette to pick K |
| Unknown K, arbitrary shapes | DBSCAN |
| Need hierarchy/dendrogram | Agglomerative |
| Need soft cluster assignments | GMM |
| Large dataset (>100k rows) | K-Means (MiniBatchKMeans for speed) |
| High noise/outliers expected | DBSCAN |
| Very high dimensions (>50 features) | Reduce with PCA first, then cluster |

---

## Practical Tips

1. **Always scale features** — K-Means, DBSCAN, and hierarchical clustering use distance metrics that are sensitive to feature scale.

2. **Reduce dimensionality first** for high-dimensional data — PCA to 10–20 components improves both speed and cluster quality.

3. **Validate with domain knowledge** — a clustering with silhouette 0.6 that doesn't make business sense is useless. A clustering with 0.3 that produces actionable segments is valuable.

4. **Try multiple algorithms** — if K-Means and DBSCAN agree, you have more confidence in the clusters.

5. **Visualize with t-SNE or UMAP** — project to 2D after clustering to visually verify cluster separation.
