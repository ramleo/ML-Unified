Chapter 26Crime Scene Reconstruction


> Upload 2-6 photos of the same static scene from different angles and get an interactive 3D point cloud built from them. This is real Structure-from-Motion — SIFT feature matching, essential-matrix pose estimation, then incremental camera registration and triangulation — the same technique behind COLMAP-style photogrammetry. What it will not do is measure: there is no bundle adjustment, no camera calibration and no dense mesh, so treat the result as a demonstration rather than a forensic-grade tool.

## At a glance

| | |
|---|---|
| **Also called** | Sparse SfM |
| **Model or method** | OpenCV SIFT + incremental SfM |
| **What you give it** | Images |
| **API Calls** | 0 |
| **Where it runs** | On the server |
| **Find it at** | `/tools/crime-scene-reconstruction` |

## Using the tool

### What this tool does
Upload 2-6 photos of the same static scene, taken from slightly different
positions while walking around it, and this tool runs a real
**Structure-from-Motion (SfM)** pipeline — the same class of technique
behind photogrammetry and 3D-scanning tools like COLMAP — to reconstruct a
sparse 3D point cloud plus the estimated position of each camera.

### Purpose
Photogrammetry-style scene reconstruction from ordinary photos is a real,
widely-used technique (crime scene documentation, archaeology, real estate,
game asset creation). This demonstrates the actual underlying math —
feature matching, epipolar geometry, triangulation, incremental camera
registration — rather than faking a 3D effect. It is deliberately scoped
down from a production pipeline (see Notes & limits) and framed as an
educational demonstration, not a forensic tool.

### How to use it
1. Take 2-6 photos of a textured, static scene (a desk, a room corner, an
   object on a table) from slightly different positions, keeping enough
   overlap between consecutive shots that the same details are visible in
   each. Upload them in that order.
2. *(Optional)* Click **Pick two points on photo 1**, click two points
   whose real-world distance you know, and enter that distance in cm — this
   converts the output to approximate real-world units instead of
   arbitrary relative ones.
3. Click **Reconstruct scene**.
4. Drag the 3D viewer to rotate, scroll to zoom. Colored cones mark each
   recovered camera position.

### A worked example
Photograph a cluttered desk from 3 positions a step apart, keeping the same
objects visible in each. The tool detects matching features (SIFT keypoints)
between consecutive photos, estimates the essential matrix and relative
camera pose between photos 1 and 2, triangulates a sparse colored point
cloud, then registers photo 3's camera pose against that existing cloud via
PnP and extends it further. If two photos don't share enough visual detail
(e.g. one is a blank wall), the tool stops there with a clear warning
instead of guessing — try it with two texture-less photos to see this
failure path directly.

### Reading the result
- **Point cloud** — matched keypoints, each triangulated into 3D and
  colored from the source photo. This is sparse (from feature matches
  only), not a dense scan or mesh.
- **Camera positions (cones)** — the recovered position of each photo's
  camera, relative to the first photo (fixed at the origin).
- **Warnings** — shown whenever the reconstruction had to stop early
  (not enough matches between two consecutive photos) rather than silently
  producing garbage.
- **Scale note** — "arbitrary relative units" unless you completed the
  optional calibration step, in which case it's labeled "approximate
  real-world scale applied."

### Notes & limits
- **No bundle adjustment or loop closure.** A production SfM pipeline
  jointly refines every camera pose and 3D point together; this tool
  estimates poses sequentially, so error accumulates with each additional
  photo — the same class of limitation as visual SLAM without loop closure.
- **No camera calibration.** Focal length is estimated from the image
  dimensions alone (a standard heuristic), not measured — so shape and
  scale are approximate even with the optional distance calibration.
- **Sparse, not dense.** Output is a point cloud from matched keypoints,
  not a solid 3D model or mesh.
- **Needs real texture and overlap.** Flat, texture-less, or poorly-lit
  surfaces produce few or no matchable features — this is a real limitation
  of feature-based SfM, not a bug.
- **Not a forensic-grade tool.** This is an educational demonstration of
  the real technique, not something that should inform any actual
  investigation, measurement, or legal determination.

## What problem it solves

Two photographs of the same scene from different positions contain, between
them, the third dimension. Not because either records depth — neither does — but
because the *difference* between them does. A point that shifts a lot between
the two shots is near; one that barely moves is far. Given enough matched points
you can solve for where both cameras were and where every point is in space.

That is **Structure-from-Motion**, and it is the technique behind photogrammetry,
Google Earth's 3D buildings, and forensic scene reconstruction. This tool
implements it — genuinely, not as a wrapper around a service. Upload two to six
photographs of one static scene from different angles and get back an
interactive 3D point cloud built from your images.

It is also unusually clear about what it will not do, and the honesty is part of
the design rather than a disclaimer bolted on. There is no bundle adjustment, no
camera calibration and no dense mesh, so the output is approximately shaped and
up to scale. It demonstrates the real technique; it is not a forensic
instrument.

## How it works, step by step

1. **Find features in every photo.** SIFT keypoints and descriptors.
2. **Match the first pair** with a brute-force matcher and Lowe's ratio test.
3. **Estimate the relative pose** of camera 2 from camera 1, using the essential
   matrix with RANSAC.
4. **Triangulate** the matched points into 3D.
5. **Filter by cheirality** — drop anything that came out behind either camera.
6. **For each additional photo:** match it against what is already reconstructed,
   solve for its position with PnP + RANSAC, then triangulate the new points it
   brings.
7. **Colour every point** by sampling the pixel it came from.
8. **Optionally scale to real units** by naming two points and the real distance
   between them.

## The model or algorithm

### SIFT — finding the same corner in two photographs

Everything depends on matching a point in one image to the same physical point
in another, taken from a different angle, distance and possibly light.

**SIFT** — the Scale-Invariant Feature Transform — does this by finding points
that are stable under exactly those changes. It searches for extrema across a
scale pyramid, so a corner is found at whatever size it appears; it assigns each
keypoint a dominant orientation and describes it *relative* to that, so rotation
does not change the descriptor; and it describes the local patch as a set of
gradient-orientation histograms, which are robust to brightness changes because
gradients are.

The result is a 128-number descriptor per keypoint that is roughly the same
whether the photo was taken from two metres or four, upright or tilted, in
sunlight or shade.

**A licensing note that matters practically:** SIFT was patented until 2020 and
lived in `opencv-contrib`. Since OpenCV 4.4 it is patent-free and in the main
`cv2` module, which is why this runs on plain `opencv-python-headless` with no
extra dependency.

### Lowe's ratio test

Matching descriptors by nearest neighbour alone produces a great many wrong
matches, because repeated texture — brickwork, foliage, carpet — looks the same
everywhere.

The ratio test asks for each keypoint's **two** nearest neighbours and keeps the
match only if:

```
best.distance 

## Limits

- **No bundle adjustment and no loop closure** — pose error accumulates.
- **No camera calibration.** Focal length is a heuristic, lens distortion is
  ignored entirely.
- **Sparse only.** Points, not surfaces; no mesh, no texture.
- **2 to 6 photos.**
- **The scene must be static.** Anything that moves between shots breaks the
  correspondence assumption outright.
- **Texture is required.** Blank walls, glass, water and repetitive patterns
  give SIFT nothing stable to match.
- **Photos need to overlap substantially** and differ enough in viewpoint —
  too similar gives a degenerate baseline, too different fails matching.
- **Not forensic-grade**, stated by the tool itself. Do not present a distance
  from it as a measurement.

## Likely interview questions

**"How do you get 3D from 2D photographs?"**
From parallax. The same physical point projects to different image positions in
two views, and how much it shifts depends on how far away it is. Match enough
points and you can solve for the relative pose of the two cameras — via the
essential matrix — and then intersect the rays to get 3D positions. The
constraint you cannot escape is scale: two images alone cannot distinguish a
large scene far away from a small one close up, so the reconstruction is always
up to scale unless something external gives you a real distance.

**"What does Lowe's ratio test do, and why does it matter here?"**
For each descriptor, find the two nearest neighbours and keep the match only if
the best is less than 0.75 times the distance of the second. It rejects
ambiguous matches — the ones that look similar to many things, which is exactly
what repetitive texture produces. It matters because everything downstream
assumes the correspondences are mostly correct; a scene of brickwork or foliage
fails here first, and no amount of RANSAC downstream recovers from bad matches
in bulk.

**"Why RANSAC?"**
Because even after the ratio test some matches are wrong, and least-squares
fitting is not robust — one bad correspondence can distort the whole estimate.
RANSAC samples a minimal set, fits a model, counts inliers, and repeats, keeping
the model most correspondences agree with. It is used twice here: for the
essential matrix on the first pair, and for PnP on every camera added after.

**"What is bundle adjustment and what does not having it cost you?"**
It is the global refinement: jointly optimise all camera poses and all 3D points
to minimise total reprojection error. Without it, each camera is placed relative
to what came before, so errors compound and the reconstruction drifts — a
straight wall bends. It is the same problem as SLAM without loop closure. It is
also why this tool caps at six photos, and I would rather state that than let
someone assume it scales.

**"Your reconstruction is 'up to scale'. Explain."**
The translation recovered from an essential matrix is a unit vector — direction
without magnitude. That is mathematics, not a bug: a room photographed from three
metres and a dolls' house photographed from thirty centimetres produce identical
images. To get real units you need something external — a known object in frame,
a calibrated stereo rig, or the two-point distance calibration this tool offers.
And even then the *shape* is only approximate, because the intrinsics were
estimated from image dimensions rather than measured, so I would not call the
result a measurement.
