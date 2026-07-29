"""Object detection for standalone image and video-frame citations —
MMRAG-07 follow-up ("where is the X").

Runs ONCE at ingest time per image/frame via ONNX Runtime + a YOLOv8s
model trained on Open Images V7 (601 classes), so a later "where is the
cyclist" question is answered by a free metadata lookup at query/chat time
(frontend keyword-matches the question against each citation's stored
detections; citations.py also labels each chunk's detections into the
LLM's own context, so the chat *text* answer can reference them too), not
a fresh vision call. Deliberately NOT the `ultralytics` package — it pulls
in torchvision, matplotlib, polars, and its own opencv-python (which
conflicts with the opencv-python-headless already used elsewhere in this
codebase for video frame sampling). onnxruntime needs only
numpy/protobuf/flatbuffers, and was already a project dependency.

Model provenance: yolov8s-oiv7.onnx has no official pre-exported ONNX
release (unlike the earlier COCO-trained yolov8n.onnx, which shipped
directly from Ultralytics' GitHub releases) — it was exported ONCE,
locally, from Ultralytics' official yolov8s-oiv7.pt weights (`model.export
(format="onnx")`, in a throwaway venv, never a runtime dependency) and
committed here as a versioned asset, same as the code around it. No
download-on-first-use step needed for this model, unlike the earlier
CLIP figure-similarity feature.

Real, measured reason for "s" over the smaller/faster "n" variant: tested
both against the same real photo (4 people + a bus). The nano model's
raw confidence for "Bus" topped out at 0.18 and "Person" at 0.17 — both
below the detection threshold, so it silently found NOTHING on an image
where the object is obviously, unambiguously present. The small variant
scored the same bus at 0.74 and the same people (as "Man") at 0.7 —
correctly detected. Open Images V7's 601-class problem is simply too hard
for the nano model's capacity; this isn't a threshold tuning issue.

Real, disclosed limitation kept from v1: still closed-vocabulary — 601
classes is a large jump from COCO's 80, but an object outside this set
still won't be found. Open Images V7 is also hierarchical (e.g. "Man" is
a subclass of "Person") — a specific subclass often scores higher
confidence than its generic parent, so a query for "person" may need to
also match "Man"/"Woman"/"Boy"/"Girl" (handled in the frontend's
label-matching, not here).
"""
from __future__ import annotations

import base64
import io
import json
import logging
import os
import threading

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

_MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "yolov8s-oiv7.onnx")
_INPUT_SIZE = 640
_CONF_THRESH = 0.35
_IOU_THRESH = 0.45
_MAX_DETECTIONS = 8  # caps noise on a busy photo/frame

# Open Images V7's 601 classes, in the exact index order the model was
# trained/exported with (ultralytics YOLO(...).names, 0-indexed).
OIV7_CLASSES = [
    'Accordion', 'Adhesive tape', 'Aircraft', 'Airplane', 'Alarm clock', 'Alpaca', 'Ambulance', 'Animal', 'Ant',
    'Antelope', 'Apple', 'Armadillo', 'Artichoke', 'Auto part', 'Axe', 'Backpack', 'Bagel', 'Baked goods',
    'Balance beam', 'Ball', 'Balloon', 'Banana', 'Band-aid', 'Banjo', 'Barge', 'Barrel', 'Baseball bat',
    'Baseball glove', 'Bat (Animal)', 'Bathroom accessory', 'Bathroom cabinet', 'Bathtub', 'Beaker', 'Bear', 'Bed',
    'Bee', 'Beehive', 'Beer', 'Beetle', 'Bell pepper', 'Belt', 'Bench', 'Bicycle', 'Bicycle helmet',
    'Bicycle wheel', 'Bidet', 'Billboard', 'Billiard table', 'Binoculars', 'Bird', 'Blender', 'Blue jay', 'Boat',
    'Bomb', 'Book', 'Bookcase', 'Boot', 'Bottle', 'Bottle opener', 'Bow and arrow', 'Bowl', 'Bowling equipment',
    'Box', 'Boy', 'Brassiere', 'Bread', 'Briefcase', 'Broccoli', 'Bronze sculpture', 'Brown bear', 'Building',
    'Bull', 'Burrito', 'Bus', 'Bust', 'Butterfly', 'Cabbage', 'Cabinetry', 'Cake', 'Cake stand', 'Calculator',
    'Camel', 'Camera', 'Can opener', 'Canary', 'Candle', 'Candy', 'Cannon', 'Canoe', 'Cantaloupe', 'Car',
    'Carnivore', 'Carrot', 'Cart', 'Cassette deck', 'Castle', 'Cat', 'Cat furniture', 'Caterpillar', 'Cattle',
    'Ceiling fan', 'Cello', 'Centipede', 'Chainsaw', 'Chair', 'Cheese', 'Cheetah', 'Chest of drawers', 'Chicken',
    'Chime', 'Chisel', 'Chopsticks', 'Christmas tree', 'Clock', 'Closet', 'Clothing', 'Coat', 'Cocktail',
    'Cocktail shaker', 'Coconut', 'Coffee', 'Coffee cup', 'Coffee table', 'Coffeemaker', 'Coin', 'Common fig',
    'Common sunflower', 'Computer keyboard', 'Computer monitor', 'Computer mouse', 'Container',
    'Convenience store', 'Cookie', 'Cooking spray', 'Corded phone', 'Cosmetics', 'Couch', 'Countertop',
    'Cowboy hat', 'Crab', 'Cream', 'Cricket ball', 'Crocodile', 'Croissant', 'Crown', 'Crutch', 'Cucumber',
    'Cupboard', 'Curtain', 'Cutting board', 'Dagger', 'Dairy Product', 'Deer', 'Desk', 'Dessert', 'Diaper', 'Dice',
    'Digital clock', 'Dinosaur', 'Dishwasher', 'Dog', 'Dog bed', 'Doll', 'Dolphin', 'Door', 'Door handle',
    'Doughnut', 'Dragonfly', 'Drawer', 'Dress', 'Drill (Tool)', 'Drink', 'Drinking straw', 'Drum', 'Duck',
    'Dumbbell', 'Eagle', 'Earrings', 'Egg (Food)', 'Elephant', 'Envelope', 'Eraser', 'Face powder',
    'Facial tissue holder', 'Falcon', 'Fashion accessory', 'Fast food', 'Fax', 'Fedora', 'Filing cabinet',
    'Fire hydrant', 'Fireplace', 'Fish', 'Flag', 'Flashlight', 'Flower', 'Flowerpot', 'Flute', 'Flying disc',
    'Food', 'Food processor', 'Football', 'Football helmet', 'Footwear', 'Fork', 'Fountain', 'Fox', 'French fries',
    'French horn', 'Frog', 'Fruit', 'Frying pan', 'Furniture', 'Garden Asparagus', 'Gas stove', 'Giraffe', 'Girl',
    'Glasses', 'Glove', 'Goat', 'Goggles', 'Goldfish', 'Golf ball', 'Golf cart', 'Gondola', 'Goose', 'Grape',
    'Grapefruit', 'Grinder', 'Guacamole', 'Guitar', 'Hair dryer', 'Hair spray', 'Hamburger', 'Hammer', 'Hamster',
    'Hand dryer', 'Handbag', 'Handgun', 'Harbor seal', 'Harmonica', 'Harp', 'Harpsichord', 'Hat', 'Headphones',
    'Heater', 'Hedgehog', 'Helicopter', 'Helmet', 'High heels', 'Hiking equipment', 'Hippopotamus',
    'Home appliance', 'Honeycomb', 'Horizontal bar', 'Horse', 'Hot dog', 'House', 'Houseplant', 'Human arm',
    'Human beard', 'Human body', 'Human ear', 'Human eye', 'Human face', 'Human foot', 'Human hair', 'Human hand',
    'Human head', 'Human leg', 'Human mouth', 'Human nose', 'Humidifier', 'Ice cream', 'Indoor rower',
    'Infant bed', 'Insect', 'Invertebrate', 'Ipod', 'Isopod', 'Jacket', 'Jacuzzi', 'Jaguar (Animal)', 'Jeans',
    'Jellyfish', 'Jet ski', 'Jug', 'Juice', 'Kangaroo', 'Kettle', 'Kitchen & dining room table',
    'Kitchen appliance', 'Kitchen knife', 'Kitchen utensil', 'Kitchenware', 'Kite', 'Knife', 'Koala', 'Ladder',
    'Ladle', 'Ladybug', 'Lamp', 'Land vehicle', 'Lantern', 'Laptop', 'Lavender (Plant)', 'Lemon', 'Leopard',
    'Light bulb', 'Light switch', 'Lighthouse', 'Lily', 'Limousine', 'Lion', 'Lipstick', 'Lizard', 'Lobster',
    'Loveseat', 'Luggage and bags', 'Lynx', 'Magpie', 'Mammal', 'Man', 'Mango', 'Maple', 'Maracas',
    'Marine invertebrates', 'Marine mammal', 'Measuring cup', 'Mechanical fan', 'Medical equipment', 'Microphone',
    'Microwave oven', 'Milk', 'Miniskirt', 'Mirror', 'Missile', 'Mixer', 'Mixing bowl', 'Mobile phone', 'Monkey',
    'Moths and butterflies', 'Motorcycle', 'Mouse', 'Muffin', 'Mug', 'Mule', 'Mushroom', 'Musical instrument',
    'Musical keyboard', 'Nail (Construction)', 'Necklace', 'Nightstand', 'Oboe', 'Office building',
    'Office supplies', 'Orange', 'Organ (Musical Instrument)', 'Ostrich', 'Otter', 'Oven', 'Owl', 'Oyster',
    'Paddle', 'Palm tree', 'Pancake', 'Panda', 'Paper cutter', 'Paper towel', 'Parachute', 'Parking meter',
    'Parrot', 'Pasta', 'Pastry', 'Peach', 'Pear', 'Pen', 'Pencil case', 'Pencil sharpener', 'Penguin', 'Perfume',
    'Person', 'Personal care', 'Personal flotation device', 'Piano', 'Picnic basket', 'Picture frame', 'Pig',
    'Pillow', 'Pineapple', 'Pitcher (Container)', 'Pizza', 'Pizza cutter', 'Plant', 'Plastic bag', 'Plate',
    'Platter', 'Plumbing fixture', 'Polar bear', 'Pomegranate', 'Popcorn', 'Porch', 'Porcupine', 'Poster',
    'Potato', 'Power plugs and sockets', 'Pressure cooker', 'Pretzel', 'Printer', 'Pumpkin', 'Punching bag',
    'Rabbit', 'Raccoon', 'Racket', 'Radish', 'Ratchet (Device)', 'Raven', 'Rays and skates', 'Red panda',
    'Refrigerator', 'Remote control', 'Reptile', 'Rhinoceros', 'Rifle', 'Ring binder', 'Rocket', 'Roller skates',
    'Rose', 'Rugby ball', 'Ruler', 'Salad', 'Salt and pepper shakers', 'Sandal', 'Sandwich', 'Saucer', 'Saxophone',
    'Scale', 'Scarf', 'Scissors', 'Scoreboard', 'Scorpion', 'Screwdriver', 'Sculpture', 'Sea lion', 'Sea turtle',
    'Seafood', 'Seahorse', 'Seat belt', 'Segway', 'Serving tray', 'Sewing machine', 'Shark', 'Sheep', 'Shelf',
    'Shellfish', 'Shirt', 'Shorts', 'Shotgun', 'Shower', 'Shrimp', 'Sink', 'Skateboard', 'Ski', 'Skirt', 'Skull',
    'Skunk', 'Skyscraper', 'Slow cooker', 'Snack', 'Snail', 'Snake', 'Snowboard', 'Snowman', 'Snowmobile',
    'Snowplow', 'Soap dispenser', 'Sock', 'Sofa bed', 'Sombrero', 'Sparrow', 'Spatula', 'Spice rack', 'Spider',
    'Spoon', 'Sports equipment', 'Sports uniform', 'Squash (Plant)', 'Squid', 'Squirrel', 'Stairs', 'Stapler',
    'Starfish', 'Stationary bicycle', 'Stethoscope', 'Stool', 'Stop sign', 'Strawberry', 'Street light',
    'Stretcher', 'Studio couch', 'Submarine', 'Submarine sandwich', 'Suit', 'Suitcase', 'Sun hat', 'Sunglasses',
    'Surfboard', 'Sushi', 'Swan', 'Swim cap', 'Swimming pool', 'Swimwear', 'Sword', 'Syringe', 'Table',
    'Table tennis racket', 'Tablet computer', 'Tableware', 'Taco', 'Tank', 'Tap', 'Tart', 'Taxi', 'Tea', 'Teapot',
    'Teddy bear', 'Telephone', 'Television', 'Tennis ball', 'Tennis racket', 'Tent', 'Tiara', 'Tick', 'Tie',
    'Tiger', 'Tin can', 'Tire', 'Toaster', 'Toilet', 'Toilet paper', 'Tomato', 'Tool', 'Toothbrush', 'Torch',
    'Tortoise', 'Towel', 'Tower', 'Toy', 'Traffic light', 'Traffic sign', 'Train', 'Training bench', 'Treadmill',
    'Tree', 'Tree house', 'Tripod', 'Trombone', 'Trousers', 'Truck', 'Trumpet', 'Turkey', 'Turtle', 'Umbrella',
    'Unicycle', 'Van', 'Vase', 'Vegetable', 'Vehicle', 'Vehicle registration plate', 'Violin', 'Volleyball (Ball)',
    'Waffle', 'Waffle iron', 'Wall clock', 'Wardrobe', 'Washing machine', 'Waste container', 'Watch', 'Watercraft',
    'Watermelon', 'Weapon', 'Whale', 'Wheel', 'Wheelchair', 'Whisk', 'Whiteboard', 'Willow', 'Window',
    'Window blind', 'Wine', 'Wine glass', 'Wine rack', 'Winter melon', 'Wok', 'Woman', 'Wood-burning stove',
    'Woodpecker', 'Worm', 'Wrench', 'Zebra', 'Zucchini',
]

_PERSON_LABELS = {"Man", "Woman", "Boy", "Girl", "Person"}
_FACE_LABELS = {"Human face"}
_FACE_CLASS_IDS = {i for i, name in enumerate(OIV7_CLASSES) if name in _FACE_LABELS}
_MAX_PERSON_CROPS = 4  # bounds extra inference passes on a busy photo
_CROP_PAD_RATIO = 0.15  # a little slack so a face near the person box's edge isn't clipped

_session = None
_session_lock = threading.Lock()


def _get_session():
    global _session
    if _session is None:
        with _session_lock:
            if _session is None:
                import onnxruntime as ort
                _session = ort.InferenceSession(_MODEL_PATH, providers=["CPUExecutionProvider"])
    return _session


def _infer_raw(img: Image.Image):
    """Letterboxes `img` to the model's fixed input size and runs the ONNX
    session. Returns the raw per-anchor predictions plus everything needed
    to map boxes back to `img`'s own pixel space — factored out so a
    person-box crop can be run through the identical pipeline as the
    full frame (see `_detect_faces_in_person_crops`)."""
    orig_w, orig_h = img.size
    scale = min(_INPUT_SIZE / orig_w, _INPUT_SIZE / orig_h)
    new_w, new_h = max(1, round(orig_w * scale)), max(1, round(orig_h * scale))
    resized = img.resize((new_w, new_h), Image.BILINEAR)
    canvas = Image.new("RGB", (_INPUT_SIZE, _INPUT_SIZE), (114, 114, 114))
    pad_x, pad_y = (_INPUT_SIZE - new_w) // 2, (_INPUT_SIZE - new_h) // 2
    canvas.paste(resized, (pad_x, pad_y))

    arr = np.asarray(canvas).astype(np.float32) / 255.0
    arr = arr.transpose(2, 0, 1)[None, ...]

    session = _get_session()
    out = session.run(None, {session.get_inputs()[0].name: arr})[0]  # (1, 4+len(OIV7_CLASSES), 8400)
    pred = out[0].T  # (8400, 4+601): 4 box coords + one score per class
    return pred, orig_w, orig_h, scale, pad_x, pad_y


def _decode_detections(pred, orig_w, orig_h, scale, pad_x, pad_y, conf_thresh, allowed_ids=None):
    """Turns raw per-anchor predictions into (class_id, confidence,
    box_xyxy) tuples in the ORIGINAL (un-padded) image's pixel space,
    thresholded and NMS'd per class. `allowed_ids`, when given, restricts
    which classes are kept (used to search a crop for faces only)."""
    boxes_cxcywh = pred[:, :4]
    class_ids = np.argmax(pred[:, 4:], axis=1)
    confidences = np.max(pred[:, 4:], axis=1)

    keep_mask = confidences >= conf_thresh
    if allowed_ids is not None:
        keep_mask &= np.isin(class_ids, list(allowed_ids))
    if not keep_mask.any():
        return []
    boxes_cxcywh, class_ids, confidences = boxes_cxcywh[keep_mask], class_ids[keep_mask], confidences[keep_mask]

    cx, cy, w, h = boxes_cxcywh[:, 0], boxes_cxcywh[:, 1], boxes_cxcywh[:, 2], boxes_cxcywh[:, 3]
    # Undo the letterbox padding/scale to get coords back in the
    # ORIGINAL image's pixel space, not the padded 640x640 input.
    x0 = (cx - w / 2 - pad_x) / scale
    x1 = (cx + w / 2 - pad_x) / scale
    y0 = (cy - h / 2 - pad_y) / scale
    y1 = (cy + h / 2 - pad_y) / scale
    boxes_xyxy = np.stack([
        np.clip(x0, 0, orig_w), np.clip(y0, 0, orig_h),
        np.clip(x1, 0, orig_w), np.clip(y1, 0, orig_h),
    ], axis=1)

    results = []
    for c in np.unique(class_ids):
        mask = class_ids == c
        b, s = boxes_xyxy[mask], confidences[mask]
        for k in _nms(b, s):
            results.append((int(c), float(s[k]), b[k]))
    return results


def _detect_faces_in_person_crops(img: Image.Image, person_boxes: list[tuple[int, float, np.ndarray]]) -> list[tuple[int, float, np.ndarray]]:
    """Real gap this closes: a face that's a small fraction of a wide shot
    (e.g. a UN General Assembly speaker filmed head-to-waist across a
    whole hall) can score under `_CONF_THRESH` at full-frame 640x640
    resolution even though the body around it detects fine — most of the
    letterboxed input is background, not face. Cropping to each detected
    person box BEFORE the same 640x640 resize gives the face far more
    effective pixels, at the cost of one extra (bounded, capped) inference
    pass per person box, only when the full-frame pass found no face at
    all. No new model, no threshold change for the general case."""
    orig_w, orig_h = img.size
    found: list[tuple[int, float, np.ndarray]] = []
    for _, _, box in sorted(person_boxes, key=lambda t: -t[1])[:_MAX_PERSON_CROPS]:
        x0, y0, x1, y1 = box
        pad_x, pad_y = (x1 - x0) * _CROP_PAD_RATIO, (y1 - y0) * _CROP_PAD_RATIO
        cx0, cy0 = max(0, int(x0 - pad_x)), max(0, int(y0 - pad_y))
        cx1, cy1 = min(orig_w, int(x1 + pad_x)), min(orig_h, int(y1 + pad_y))
        if cx1 - cx0 < 4 or cy1 - cy0 < 4:
            continue
        crop = img.crop((cx0, cy0, cx1, cy1))
        pred, cw, ch, scale, pad_x2, pad_y2 = _infer_raw(crop)
        for class_id, conf, crop_box in _decode_detections(
                pred, cw, ch, scale, pad_x2, pad_y2, _CONF_THRESH, allowed_ids=_FACE_CLASS_IDS):
            found.append((class_id, conf, crop_box + np.array([cx0, cy0, cx0, cy0])))
    return found


def _nms(boxes: np.ndarray, scores: np.ndarray, iou_thresh: float = _IOU_THRESH) -> list[int]:
    idxs = scores.argsort()[::-1]
    keep: list[int] = []
    while len(idxs) > 0:
        i = idxs[0]
        keep.append(i)
        if len(idxs) == 1:
            break
        rest = idxs[1:]
        xx0 = np.maximum(boxes[i, 0], boxes[rest, 0])
        yy0 = np.maximum(boxes[i, 1], boxes[rest, 1])
        xx1 = np.minimum(boxes[i, 2], boxes[rest, 2])
        yy1 = np.minimum(boxes[i, 3], boxes[rest, 3])
        inter = np.maximum(0, xx1 - xx0) * np.maximum(0, yy1 - yy0)
        area_i = (boxes[i, 2] - boxes[i, 0]) * (boxes[i, 3] - boxes[i, 1])
        area_r = (boxes[rest, 2] - boxes[rest, 0]) * (boxes[rest, 3] - boxes[rest, 1])
        iou = inter / (area_i + area_r - inter + 1e-9)
        idxs = rest[iou <= iou_thresh]
    return keep


def detect_objects(b64: str) -> list[dict]:
    """Runs the detector over a base64 PNG/JPEG. Returns up to
    _MAX_DETECTIONS {label, confidence, bbox: [x,y,w,h] normalized 0-1}
    sorted by confidence descending. [] on any failure (corrupt image, no
    detections) — never blocks ingestion."""
    try:
        img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
        orig_w, orig_h = img.size
        if orig_w == 0 or orig_h == 0:
            return []

        pred, ow, oh, scale, pad_x, pad_y = _infer_raw(img)
        raw = _decode_detections(pred, ow, oh, scale, pad_x, pad_y, _CONF_THRESH)

        person_boxes = [r for r in raw if OIV7_CLASSES[r[0]] in _PERSON_LABELS]
        has_face = any(OIV7_CLASSES[r[0]] in _FACE_LABELS for r in raw)
        if person_boxes and not has_face:
            raw = raw + _detect_faces_in_person_crops(img, person_boxes)

        results = [(OIV7_CLASSES[c], conf, box) for c, conf, box in raw]
        results.sort(key=lambda t: -t[1])
        results = results[:_MAX_DETECTIONS]

        return [
            {"label": label, "confidence": round(conf, 3),
             "bbox": [round(float(box[0] / orig_w), 4), round(float(box[1] / orig_h), 4),
                      round(float((box[2] - box[0]) / orig_w), 4), round(float((box[3] - box[1]) / orig_h), 4)]}
            for label, conf, box in results
        ]
    except Exception as exc:
        logger.warning("Object detection failed: %s", exc)
        return []


def _spatial_phrase(bbox: list[float]) -> str:
    """Coarse on purpose (a 3x3 grid, not coordinates) — a chat model needs a
    phrase to work with, not numbers to (mis)interpret."""
    x, y, w, h = bbox
    if w * h >= 0.35:
        return "spans most of the frame"
    cx, cy = x + w / 2, y + h / 2
    horiz = "left" if cx < 1 / 3 else "right" if cx > 2 / 3 else "center"
    vert = "top" if cy < 1 / 3 else "bottom" if cy > 2 / 3 else None
    if not vert:
        return horiz
    return vert if horiz == "center" else f"{vert}-{horiz}"


def describe_objects(objects: list[dict] | None) -> str:
    """A sentence naming each detected object and its coarse position, meant
    to be appended to the chunk's stored `text` at INGEST time (not just
    injected into the LLM prompt at query time) — a "where is the X"
    question needs this to be part of the same text both the LLM context
    AND the groundedness/citation-overlap scorers read, since those only
    ever look at `chunk["text"]`, never at prompt-time-only content. Empty
    string when there's nothing detected."""
    if not objects:
        return ""
    obj_desc = "; ".join(f"{o['label']} — {_spatial_phrase(o['bbox'])}" for o in objects)
    return f"Objects detected in this image, with their approximate position: {obj_desc}."


def encode_objects(objects: list[dict] | None) -> str | None:
    return json.dumps(objects) if objects else None


def decode_objects(raw) -> list[dict]:
    if not raw:
        return []
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return []
