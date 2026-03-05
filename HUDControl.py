import time
import cv2
import mediapipe as mp
import pyautogui
import psutil
import numpy as np
import math
import random
import speedtest

# ---------------- CONFIG & INITIALIZATION ----------------
mp_hands = mp.solutions.hands
mp_face = mp.solutions.face_detection
hands = mp_hands.Hands(min_detection_confidence=0.7, min_tracking_confidence=0.7)
face_detection = mp_face.FaceDetection(model_selection=1, min_detection_confidence=0.5)
draw = mp.solutions.drawing_utils

# Kamera Girişi (Bire çekildi)
cap = cv2.VideoCapture(0) 
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

# ---------------- STATE VARIABLES ----------------
smooth_x, smooth_y = 0.5, 0.5
alpha = 0.25
last_tab_time = 0
alt_pressed = False
fist_active = False
fist_start_y = 0
last_vol_time = 0
last_button_press = 0

sys_dash_active = False
hum_dash_active = False

# --- SCANNING & BIOMETRIC VARIABLES ---
scan_start_time = 0
scan_duration = 5.0 
locked_bpm = 0
is_calibrated = False
bpm_buffer = []
buffer_size = 150 

# ---------------- HELPER FUNCTIONS ----------------
def is_spiderman(hand):
    return hand.landmark[8].y < hand.landmark[6].y and \
           hand.landmark[20].y < hand.landmark[18].y and \
           hand.landmark[12].y > hand.landmark[10].y and \
           hand.landmark[16].y > hand.landmark[14].y

def is_fist(hand):
    tips = [8, 12, 16, 20]
    pips = [6, 10, 14, 18]
    return all(hand.landmark[t].y > hand.landmark[p].y for t, p in zip(tips, pips))

def get_dynamic_pinch(hand):
    p1, p2 = hand.landmark[4], hand.landmark[8]
    wrist, mid_base = hand.landmark[0], hand.landmark[9]
    hand_size = math.sqrt((wrist.x - mid_base.x)**2 + (wrist.y - mid_base.y)**2)
    dist = math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2)
    return 1.0 if (dist / hand_size) < 0.35 else 0.0

def calculate_final_bpm(buffer):
    if not buffer: return 72
    signal = np.array(buffer)
    signal = (signal - np.mean(signal)) / (np.std(signal) + 1e-6)
    fft_data = np.abs(np.fft.rfft(signal))
    freqs = np.fft.rfftfreq(len(buffer), 1/30)
    idx = np.where((freqs > 0.8) & (freqs < 2.5))[0]
    if len(idx) > 0:
        return int(freqs[idx[np.argmax(fft_data[idx])]] * 60)
    return 72

def get_internet_speed():
    st = speedtest.Speedtest()

    download_speed = st.download() / 1_000_000
    upload_speed = st.upload() / 1_000_000
    ping = st.results.ping
    return round(download_speed,2), round(upload_speed,2), round(ping,2)

    download,upload, ping = get_internet_speed()


print(f"Download: {download} Mbps")
print(f"Upload: {upload} Mbps")
print(f"Ping: {ping} ms")

# ---------------- MAIN LOOP ----------------
print("⚡ MATRIX FULL SYSTEM v5.5 - TARGET LOCKED EDITION ACTIVE (CAMERA 1)")

while cap.isOpened():
    success, img = cap.read()
    if not success: break
    img = cv2.flip(img, 1)
    h, w, _ = img.shape
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    
    hand_results = hands.process(rgb)
    face_results = face_detection.process(rgb)
    now = time.time()

    # --- BUTTON COORDINATES ---
    sys_btn_pos = (30, h//2 - 70)
    hum_btn_pos = (30, h//2 + 10)
    btn_w, btn_h = 280, 60

    # --- HUMAN VITALS SCANNING ---
    if hum_dash_active:
        time_elapsed = now - scan_start_time
        if time_elapsed < scan_duration:
            if face_results.detections:
                for det in face_results.detections:
                    bbox = det.location_data.relative_bounding_box
                    fx, fy, fw, fh = int(bbox.xmin*w), int(bbox.ymin*h), int(bbox.width*w), int(bbox.height*h)
                    roi = img[max(0,fy):min(h,fy+fh), max(0,fx):min(w,fx+fw)]
                    if roi.size > 0:
                        bpm_buffer.append(np.mean(roi[:,:,1]))
                    cv2.rectangle(img, (fx, fy), (fx+fw, fy+fh), (0, 255, 255), 2)
            display_bpm = "SCANNING..."
            panel_color = (0, 255, 255)
        else:
            if not is_calibrated:
                locked_bpm = calculate_final_bpm(bpm_buffer)
                is_calibrated = True
            display_bpm = f"{locked_bpm + random.uniform(-0.5, 0.5):.1f}"
            panel_color = (0, 0, 255)

        # Panel UI
        overlay = img.copy()
        cv2.rectangle(overlay, (w-400, 50), (w-50, 350), (20, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, img, 0.3, 0, img)
        cv2.rectangle(img, (w-400, 50), (w-50, 350), panel_color, 2)
        cv2.putText(img, "HUMAN VITALS", (w-380, 100), 0, 0.8, panel_color, 2)
        cv2.putText(img, f"BPM: {display_bpm}", (w-360, 210), 0, 1.5, panel_color, 4)
        if not is_calibrated:
            prog = int((time_elapsed / scan_duration) * 300)
            cv2.rectangle(img, (w-370, 300), (w-370+prog, 315), (0, 255, 0), -1)

    # --- SYSTEM VITALS DASHBOARD ---
    if sys_dash_active:
        overlay = img.copy()
        cv2.rectangle(overlay, (w//2-200, h//2-100), (w//2+200, h//2+100), (40, 10, 0), -1)
        cv2.addWeighted(overlay, 0.7, img, 0.3, 0, img)
        cv2.putText(img, f"CPU: {psutil.cpu_percent()}%", (w//2-150, h//2-20), 0, 0.8, (255, 255, 0), 2)
        cv2.putText(img, f"RAM: {psutil.virtual_memory().percent}%", (w//2-150, h//2+50), 0, 0.8, (255, 255, 0), 2)

    # --- HAND GESTURES & CONTROLS ---
    if hand_results.multi_hand_landmarks:
        spider_in_frame = any(is_spiderman(hl) for hl in hand_results.multi_hand_landmarks)
        if spider_in_frame and not alt_pressed:
            pyautogui.keyDown('alt'); alt_pressed = True
        elif not spider_in_frame and alt_pressed:
            pyautogui.keyUp('alt'); alt_pressed = False

        for hand_lms in hand_results.multi_hand_landmarks:
            idx = hand_lms.landmark[8]
            cx, cy = int(idx.x * w), int(idx.y * h)
            
            # Button Interaction
            pinch = get_dynamic_pinch(hand_lms) > 0.8
            if now - last_button_press > 1.0:
                if sys_btn_pos[0] < cx < sys_btn_pos[0]+btn_w and sys_btn_pos[1] < cy < sys_btn_pos[1]+btn_h:
                    if pinch: sys_dash_active = not sys_dash_active; last_button_press = now
                if hum_btn_pos[0] < cx < hum_btn_pos[0]+btn_w and hum_btn_pos[1] < cy < hum_btn_pos[1]+btn_h:
                    if pinch: 
                        hum_dash_active = not hum_dash_active
                        scan_start_time = now; bpm_buffer = []; is_calibrated = False; last_button_press = now

            # Volume & Alt-Tab Logic
            if is_fist(hand_lms) and not alt_pressed:
                wrist_y = hand_lms.landmark[0].y
                if not fist_active: fist_active, fist_start_y = True, wrist_y
                if now - last_vol_time > 0.05:
                    delta = fist_start_y - wrist_y
                    if delta > 0.03: pyautogui.press("volumeup"); last_vol_time = now
                    elif delta < -0.03: pyautogui.press("volumedown"); last_vol_time = now
            else: fist_active = False

            if alt_pressed and not is_spiderman(hand_lms):
                if hand_lms.landmark[8].x < 0.4 and (now - last_tab_time > 0.5):
                    pyautogui.press('tab'); last_tab_time = now
            
            draw.draw_landmarks(img, hand_lms, mp_hands.HAND_CONNECTIONS)

    # --- UI BUTTONS RENDER ---
    cv2.rectangle(img, sys_btn_pos, (sys_btn_pos[0]+btn_w, sys_btn_pos[1]+btn_h), (255, 255, 0), 1)
    cv2.putText(img, "SYSTEM VITALS", (sys_btn_pos[0]+20, sys_btn_pos[1]+40), 0, 0.7, (255, 255, 0), 2)
    cv2.rectangle(img, hum_btn_pos, (hum_btn_pos[0]+btn_w, hum_btn_pos[1]+btn_h), (0, 0, 255), 1)
    cv2.putText(img, "HUMAN VITALS", (hum_btn_pos[0]+20, hum_btn_pos[1]+40), 0, 0.7, (0, 0, 255), 2)

    cv2.imshow("Final Matrix HUD v5.5", img)
    if cv2.waitKey(1) & 0xFF == ord("q"): break

cap.release()
cv2.destroyAllWindows()