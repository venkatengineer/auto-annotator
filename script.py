import os
import sys
os.environ['GLOG_minloglevel'] = '2'
import cv2
import mediapipe as mp

# Class IDs (DO NOT CHANGE ORDER)
EyesOpen = 0
MouthClose = 1
NeckNormal = 2
EyesClose = 3
MouthOpen = 4
NeckDrooped = 5

mp_face_mesh = mp.solutions.face_mesh

# Eye landmarks
LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]

# Eyebrows
LEFT_BROW = [70, 63, 105, 66, 107]
RIGHT_BROW = [336, 296, 334, 293, 300]

# Mouth landmarks
MOUTH = [61, 291, 13, 14]

def normalize_bbox(xmin, ymin, xmax, ymax, w, h):
    cx = ((xmin + xmax) / 2) / w
    cy = ((ymin + ymax) / 2) / h
    bw = (xmax - xmin) / w
    bh = (ymax - ymin) / h
    return cx, cy, bw, bh


def eye_aspect_ratio(points):
    p1, p2, p3, p4, p5, p6 = points

    vertical1 = abs(p2[1] - p6[1])
    vertical2 = abs(p3[1] - p5[1])
    horizontal = abs(p1[0] - p4[0])

    if horizontal == 0:
        return 0

    return (vertical1 + vertical2) / (2 * horizontal)


def get_bbox(indices, landmarks, img_w, img_h):
    xs = []
    ys = []

    for idx in indices:
        lm = landmarks[idx]
        xs.append(int(lm.x * img_w))
        ys.append(int(lm.y * img_h))

    return min(xs), min(ys), max(xs), max(ys)


def process_image(path, face_mesh):
    image = cv2.imread(path)
    if image is None:
        return None

    h, w = image.shape[:2]
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    results = face_mesh.process(rgb)

    if not results.multi_face_landmarks:
        return None

    landmarks = results.multi_face_landmarks[0].landmark

    labels = []

    # ========= LEFT EYE =========
    left_eye_pts = [
        (
            int(landmarks[i].x * w),
            int(landmarks[i].y * h)
        ) for i in LEFT_EYE
    ]

    left_ear = eye_aspect_ratio(left_eye_pts)
    left_class = EyesOpen if left_ear > 0.20 else EyesClose

    left_indices = LEFT_EYE + LEFT_BROW
    xmin, ymin, xmax, ymax = get_bbox(left_indices, landmarks, w, h)

    # Expand the bottom of the eye bounding box by 25% of the eye box height
    eye_height = ymax - ymin
    ymax = min(h, ymax + int(eye_height * 0.25))

    cx, cy, bw, bh = normalize_bbox(xmin, ymin, xmax, ymax, w, h)
    labels.append(f"{left_class} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")

    # ========= RIGHT EYE =========
    right_eye_pts = [
        (
            int(landmarks[i].x * w),
            int(landmarks[i].y * h)
        ) for i in RIGHT_EYE
    ]

    right_ear = eye_aspect_ratio(right_eye_pts)
    right_class = EyesOpen if right_ear > 0.20 else EyesClose

    right_indices = RIGHT_EYE + RIGHT_BROW
    xmin, ymin, xmax, ymax = get_bbox(right_indices, landmarks, w, h)

    # Expand the bottom of the eye bounding box by 25% of the eye box height
    eye_height = ymax - ymin
    ymax = min(h, ymax + int(eye_height * 0.25))

    cx, cy, bw, bh = normalize_bbox(xmin, ymin, xmax, ymax, w, h)
    labels.append(f"{right_class} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")

    # ========= MOUTH =========
    mouth_points = [
        (
            int(landmarks[i].x * w),
            int(landmarks[i].y * h)
        ) for i in MOUTH
    ]

    left_corner = mouth_points[0]
    right_corner = mouth_points[1]
    upper = mouth_points[2]
    lower = mouth_points[3]

    vertical = abs(lower[1] - upper[1])
    horizontal = abs(right_corner[0] - left_corner[0])

    mar = vertical / horizontal if horizontal != 0 else 0

    mouth_class = MouthOpen if mar > 0.30 else MouthClose

    # Get bounding box using inner landmarks (MOUTH) plus outer boundaries (0 for top lip, 17 for bottom lip)
    xmin, ymin, xmax, ymax = get_bbox(MOUTH + [0, 17], landmarks, w, h)

    # Expand the top of the mouth bounding box to ensure upper lip coverage
    mouth_height = ymax - ymin
    ymin = max(0, ymin - int(mouth_height * 0.20))

    padding = 10
    xmin = max(0, xmin - padding)
    ymin = max(0, ymin - padding)
    xmax = min(w, xmax + padding)
    ymax = min(h, ymax + padding)

    cx, cy, bw, bh = normalize_bbox(xmin, ymin, xmax, ymax, w, h)
    labels.append(f"{mouth_class} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")

    # ========= NECK (HEAD POSTURE) =========
    # Get y-coordinates of forehead (10) and chin (152) to check depth tilt
    forehead_lm = landmarks[10]
    chin_lm = landmarks[152]
    
    dy = chin_lm.y - forehead_lm.y
    dz = forehead_lm.z - chin_lm.z
    
    # Scale-invariant tilt indicator (forehead z relative to chin z, normalized by vertical size)
    pitch_metric = dz / dy if dy != 0 else 0
    
    # Classify neck posture based on pitch angle (forward tilt)
    neck_class = NeckDrooped if pitch_metric < -0.15 else NeckNormal
    
    # Get bounding box of all face landmarks to cover the head width and height
    all_xs = [lm.x for lm in landmarks]
    all_ys = [lm.y for lm in landmarks]
    
    neck_xmin = min(all_xs) * w
    neck_xmax = max(all_xs) * w
    neck_ymin = min(all_ys) * h
    neck_ymax = max(all_ys) * h
    
    neck_height = neck_ymax - neck_ymin
    neck_width = neck_xmax - neck_xmin
    
    # Expand top by 35% of face height to cover the hair
    neck_ymin = max(0, neck_ymin - int(neck_height * 0.35))
    # Expand bottom by 15% of face height to go slightly below the chin
    neck_ymax = min(h, neck_ymax + int(neck_height * 0.15))
    # Add small horizontal padding to keep proportions clean
    neck_xmin = max(0, neck_xmin - int(neck_width * 0.05))
    neck_xmax = min(w, neck_xmax + int(neck_width * 0.05))
    
    neck_cx, neck_cy, neck_bw, neck_bh = normalize_bbox(neck_xmin, neck_ymin, neck_xmax, neck_ymax, w, h)
    labels.append(f"{neck_class} {neck_cx:.6f} {neck_cy:.6f} {neck_bw:.6f} {neck_bh:.6f}")

    return labels


def run_annotation(image_folder, label_folder):
    os.makedirs(label_folder, exist_ok=True)

    # Write classes definition files for annotations
    classes_list = [
        "EyesOpen",
        "MouthClose",
        "NeckNormal",
        "EyesClose",
        "MouthOpen",
        "NeckDrooped"
    ]
    with open(os.path.join(label_folder, "classes.txt"), "w") as f:
        f.write("\n".join(classes_list) + "\n")

    # Create FaceMesh instance once (with stderr silenced to hide C++ warnings)
    try:
        stderr_fd = sys.stderr.fileno()
        dup_stderr = os.dup(stderr_fd)
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, stderr_fd)
        try:
            face_mesh = mp_face_mesh.FaceMesh(
                static_image_mode=True,
                max_num_faces=1,
                refine_landmarks=True
            )
        finally:
            os.dup2(dup_stderr, stderr_fd)
            os.close(devnull)
            os.close(dup_stderr)
    except Exception:
        face_mesh = mp_face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=1,
            refine_landmarks=True
        )

    files = [f for f in os.listdir(image_folder) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
    total = len(files)
    
    yield f"Found {total} images to process in {image_folder}."

    for idx, file in enumerate(files):
        path = os.path.join(image_folder, file)
        labels = process_image(path, face_mesh)

        if labels is None:
            yield f"Skipped: {file}"
            continue

        label_file = os.path.join(
            label_folder,
            os.path.splitext(file)[0] + ".txt"
        )

        with open(label_file, "w") as f:
            f.write("\n".join(labels))

        yield f"Progress: {idx+1}/{total} | Done: {file}"

    face_mesh.close()
    yield "SUCCESS: Annotation completed successfully!"


if __name__ == "__main__":
    image_folder = os.environ.get("IMAGE_FOLDER", r"D:\CDAC\Venkat\nolight_dataset_awake4\images")
    label_folder = os.path.join(os.path.dirname(image_folder.rstrip(r"\/")), "anno")
    
    print(f"Starting auto-annotator CLI on {image_folder}...")
    for log in run_annotation(image_folder, label_folder):
        print(log)

