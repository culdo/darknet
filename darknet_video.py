import os
import time

import cv2
import numpy as np
import requests

import darknet


def convertBack(x, y, w, h):
    xmin = int(round(x - (w / 2)))
    xmax = int(round(x + (w / 2)))
    ymin = int(round(y - (h / 2)))
    ymax = int(round(y + (h / 2)))
    return xmin, ymin, xmax, ymax


def cvDrawBoxes(detections, img):
    for detection in detections:
        x, y, w, h = detection[2][0], \
                     detection[2][1], \
                     detection[2][2], \
                     detection[2][3]
        xmin, ymin, xmax, ymax = convertBack(
            float(x), float(y), float(w), float(h))
        pt1 = (xmin, ymin)
        pt2 = (xmax, ymax)
        cv2.rectangle(img, pt1, pt2, (0, 255, 0), 1)
        cv2.putText(img,
                    detection[0].decode() +
                    " [" + str(round(detection[1] * 100, 2)) + "]",
                    (pt1[0], pt1[1] - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    [0, 255, 0], 2)
    return img


netMain = None
metaMain = None
altNames = None


def load_yolo():
    global metaMain, netMain, altNames
    configPath = "./cfg/yolov3-tiny.cfg"
    weightPath = "./bin/yolov3-tiny.weights"
    metaPath = "./cfg/coco.data"
    if not os.path.exists(configPath):
        raise ValueError("Invalid config path `" +
                         os.path.abspath(configPath) + "`")
    if not os.path.exists(weightPath):
        raise ValueError("Invalid weight path `" +
                         os.path.abspath(weightPath) + "`")
    if not os.path.exists(metaPath):
        raise ValueError("Invalid data file path `" +
                         os.path.abspath(metaPath) + "`")
    if netMain is None:
        netMain = darknet.load_net_custom(configPath.encode(
            "ascii"), weightPath.encode("ascii"), 0, 1)  # batch size = 1
    if metaMain is None:
        metaMain = darknet.load_meta(metaPath.encode("ascii"))
    if altNames is None:
        try:
            with open(metaPath) as metaFH:
                metaContents = metaFH.read()
                import re
                match = re.search("names *= *(.*)$", metaContents,
                                  re.IGNORECASE | re.MULTILINE)
                if match:
                    result = match.group(1)
                else:
                    result = None
                try:
                    if os.path.exists(result):
                        with open(result) as namesFH:
                            namesList = namesFH.read().strip().split("\n")
                            altNames = [x.strip() for x in namesList]
                except TypeError:
                    pass
        except Exception:
            pass


def video_capture(SaveVideo=False):
    cap = cv2.VideoCapture(0)
    # cap = cv2.VideoCapture("test.mp4")
    cap.set(3, 1280)
    cap.set(4, 720)
    if SaveVideo:
        out = cv2.VideoWriter(
            "output.avi", cv2.VideoWriter_fourcc(*"MJPG"), 10.0,
            (darknet.network_width(netMain), darknet.network_height(netMain)))
    print("Starting the YOLO loop...")

    while True:
        ret, frame_read = cap.read()
        frame_rgb = cv2.cvtColor(frame_read, cv2.COLOR_BGR2RGB)
        prev_time = time.time()
        detections, result_image = detect_image(frame_rgb)
        print(1 / (time.time() - prev_time))
        cv2.imshow('Demo', result_image)
        cv2.waitKey(3)
    cap.release()
    if SaveVideo:
        out.release()


def detect_image(darknet_image, frame_rgb):
    frame_resized = cv2.resize(frame_rgb,
                               (darknet.network_width(netMain),
                                darknet.network_height(netMain)),
                               interpolation=cv2.INTER_LINEAR)
    darknet.copy_image_from_bytes(darknet_image, frame_resized.tobytes())
    detections = darknet.detect_image(netMain, metaMain, darknet_image, frame_rgb.shape, thresh=0.25)
    result_img = cvDrawBoxes(detections, frame_rgb)
    result_img = cv2.cvtColor(result_img, cv2.COLOR_BGR2RGB)
    return detections, result_img


def detect_mjpeg(img_url):
    r = requests.get(img_url, stream=True)
    # Create an image we reuse for each detect
    darknet_image = darknet.make_image(darknet.network_width(netMain),
                                       darknet.network_height(netMain), 3)

    if r.status_code == 200:
        mybytes = bytes()
        for chunk in r.iter_content(chunk_size=1024):
            mybytes += chunk
            a = mybytes.find(b'\xff\xd8')
            b = mybytes.find(b'\xff\xd9')

            if a != -1 and b != -1:
                if not a < (b + 2):
                    # flush to head flag to find correct range
                    mybytes = mybytes[a:]
                else:
                    jpg = mybytes[a:b + 2]
                    frame_read = cv2.imdecode(np.fromstring(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                    prev_time = time.time()
                    detections, result_image = detect_image(darknet_image, frame_read)
                    print(1 / (time.time() - prev_time))
                    cv2.imshow('Demo', result_image)
                    cv2.waitKey(3)

                    # Clear mybytes buffer to prevent internal bound shift
                    mybytes = bytes()


if __name__ == "__main__":
    load_yolo()
    lab_door_cam = "http://192.168.0.52:8081/"
    detect_mjpeg(lab_door_cam)
