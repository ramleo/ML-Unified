# Third-party model weights

Every model file committed to this repository, where it came from, and what
licence it carries. Written because "which licence is this under" was a
question nobody could answer from the filesystem, and because one of these
answers decides the licence of the project as a whole.

Python and JavaScript dependencies are not listed here — they are declared in
`requirements*.txt` and resolved by pip, and none of them is redistributed in
this repository.

## What is committed

| File | Size | Upstream | Upstream licence |
|---|---|---|---|
| `services/ml-api/routers/rag/models/yolov8s-oiv7.onnx` | 44 MB | Ultralytics YOLOv8s, Open Images V7 (601 classes), exported locally to ONNX | **AGPL-3.0** |
| `services/ml-api/routers/rag/models/signature-detector.onnx` | 36 MB | [Mels22/Signature-Detection-Verification](https://huggingface.co/Mels22/Signature-Detection-Verification) — YOLO11s fine-tune, SignverOD dataset | Apache-2.0 *(see note)* |
| `services/ml-api/routers/rag/models/yolov8n-ppe.onnx` | 12 MB | Hansung-Cho/yolov8-ppe-detection — YOLOv8n fine-tune | MIT *(see note)* |
| `services/ml-api/routers/rag/models/depth/model_quantized.onnx` | 37 MB | [onnx-community/depth-anything-v2-small-ONNX](https://huggingface.co/onnx-community/depth-anything-v2-small-ONNX) | Apache-2.0 |
| `services/ml-api/routers/rag/models/face-liveness.onnx` | 612 KB | MiniFASNetV2-SE, minivision-ai/Silent-Face-Anti-Spoofing via facenox/face-antispoof-onnx | Apache-2.0 |
| `services/ml-api/routers/rag/models/face-detection-yunet.onnx` | 228 KB | OpenCV Zoo YuNet, © Shiqi Yu | MIT |

Models under `services/ml-api/models/` are not third party — they are scikit-learn
and PyTorch artefacts trained in this repository on public datasets (Titanic,
Iris, Diabetes, MNIST, an insurance pricing set) and carry this project's own
licence.

## Note on the three YOLO models — why this project is AGPL-3.0

The first three rows are all Ultralytics-architecture models. That matters more
than the per-file licence text suggests.

Ultralytics dual-licenses YOLOv8 and YOLO11 as AGPL-3.0 or a paid Enterprise
licence, and their founder has stated in writing (ultralytics/ultralytics issue
#22458) that **weights produced by training with Ultralytics YOLO are derivative
works under AGPL-3.0, and that exporting to ONNX or serving through a different
runtime does not change that.** This repository does exactly that: it exports to
ONNX once, locally, and serves through `onnxruntime` with no Ultralytics package
at runtime. Under their reading, that is not a way out.

If that reading is right, it reaches all three files, not just the first. The
Apache-2.0 and MIT terms on rows two and three are each a fine-tuner's statement
about their own contribution; neither can grant more than the base weights allow.

Whether model weights are legally a derivative work of the training code is
genuinely unsettled — no court has ruled on it, and Ultralytics' position is
self-interested. It is also the most authoritative statement available, and
AGPL-3.0 §13 exists precisely for a network-accessible hosted service like this
one.

So rather than rely on the argument being wrong, this project takes the
compliant path and is licensed AGPL-3.0 itself. Section 13 asks one thing of a
hosted service: that people interacting with it over a network can obtain the
source. The repository is public and the running application links to it, which
is that obligation met rather than argued with.

Permissive replacements were searched for at length and none covers the class
vocabulary this project needs — RT-DETR and RF-DETR are cleanly Apache-2.0 but
COCO-80 only; D-FINE on Objects365 is missing every weapon and licence-plate
class; Grounding DINO is clean and open-vocabulary but measured around 5 seconds
per image on CPU. The finding stands: there is no drop-in swap, so the licence
moved instead of the model.

## If you fork this

AGPL-3.0 applies to the whole of this repository, including the model weights as
distributed here. If you run a modified version as a network service, §13
requires you to offer your users its complete source. The frontend that normally
drives this API lives in a separate repository under the MIT licence, and is not
covered by this one.
