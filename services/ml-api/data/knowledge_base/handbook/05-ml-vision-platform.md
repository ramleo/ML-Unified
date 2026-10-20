Chapter 3ML Vision Platform


> Three vision tasks in one app: classify images across 1000 ImageNet categories (MobileNetV2 · ResNet50 · SqueezeNet · GoogLeNet), detect objects with TinyYOLOv3 (COCO 80 classes), and segment scenes pixel-by-pixel with SegFormer-B0 (ADE20K 150 classes). All models run as ONNX on a FastAPI microservice.

## At a glance

| | |
|---|---|
| **Model or method** | SegFormer-B0 · YOLOv3 · MobileNetV2 |
| **What it does** | Vision |
| **Works on** | ImageNet · COCO · ADE20K |
| **Seg Classes** | 150 |
| **Find it at** | `/vision` |

### What the ML Vision Platform is
ML Vision is an image-understanding platform inside AIRaML: **three vision tasks in
one app**, all running as ONNX models on a FastAPI backend. Upload an image and
**classify** it (what is this?), **detect** objects in it (what's where?), or
**segment** it pixel by pixel (which pixels are what?).

Everything runs server-side on real trained models — free to use.

### The three tasks
- **Classification** *(1000 ImageNet classes)* — four backbones you can compare:
  **MobileNetV2, ResNet50, SqueezeNet, GoogLeNet**. Returns the top labels with
  confidence.
- **Detection** *(80 COCO classes)* — **TinyYOLOv3** draws a box around every
  detected object with its label and confidence.
- **Segmentation** *(150 ADE20K classes)* — **SegFormer-B0** labels every pixel
  (sky, road, building, person, …) as a coloured overlay.

### Using the platform (step by step)
1. Click **Open the platform** to launch the Vision mode of the app.
2. **Pick a task** — Classification, Detection or Segmentation.
3. **Upload an image** (or use a sample). Common formats work; large images are
   resized to each model's input size automatically.
4. For **Classification**, optionally **choose the backbone** (or run several) to
   compare how different models label the same image.
5. **Read the result** — ranked labels with confidence (classify), boxes over the
   image (detect), or a coloured pixel overlay with a class legend (segment).

### What makes it interesting
- **Three tasks, one app.** Classification, detection and segmentation share a
  single ONNX-on-FastAPI microservice — the same deployment that serves ML Unified
  and EDA Explorer.
- **Compare backbones.** Four classifiers side by side show the real accuracy /
  speed trade-off (a tiny SqueezeNet vs a heavier ResNet50) on your own image.
- **Runs as ONNX.** Portable, framework-agnostic model files served efficiently
  on CPU.

### Honest limits
- **Fixed label sets.** Classification is limited to the 1000 ImageNet classes,
  detection to 80 COCO classes, segmentation to 150 ADE20K classes — it can only
  name things in those vocabularies.
- **Compact models.** TinyYOLOv3 and SegFormer-B0 favour speed on CPU over
  maximum accuracy; expect misses on small, crowded or unusual scenes.
- **General-purpose, not specialised.** It is not a medical, security or
  industrial-inspection system.
- Your uploaded image is processed to produce the result and isn't kept.

### FAQ
- **Which task should I use?** Classification for "what is this?", detection for
  "what objects are in it and where?", segmentation for "which pixels belong to
  what?".
- **Why compare four classifiers?** To see the accuracy-vs-size trade-off on a
  real image — the point ImageNet backbones are chosen on.
- **Where does it run?** On a FastAPI backend (the Vision mode of the shared
  ML-Unified Space); models run server-side as ONNX, nothing in your browser.
- **Is it free?** Yes.

### Why it matters
Classification, detection and segmentation are the three workhorse computer-vision
tasks. Having all three in one app, on real ONNX models, with four classifiers you
can compare on your own image, shows the whole shape of practical vision — cleanly,
and with its limits stated.
