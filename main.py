import streamlit as st
from supabase import create_client
from insightface.app import FaceAnalysis
from PIL import Image
import numpy as np
from io import BytesIO
import cv2
from datetime import datetime, date
import time
from telegram import Bot, InputFile
import io
import asyncio
import threading
import os
from dotenv import load_dotenv

# --- Загрузка секретов ---
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
telegram_bot = Bot(token=TELEGRAM_BOT_TOKEN)

# --- Автоопределение смены ---
def get_current_shift():
    hour = datetime.now().hour
    if 6 <= hour < 12:
        return "Утро"
    elif 12 <= hour < 18:
        return "День"
    elif 18 <= hour < 23:
        return "Вечер"
    else:
        return "Ночь"

# --- Telegram уведомление ---
async def send_telegram_notification(name, shift, timestamp, image_array, is_exit=False):
    try:
        action = "⏰ Выход" if is_exit else "✅ Вход"
        message = f"{action} сотрудника:\n🧑‍💼 {name}\n📍 Смена: {shift}\n🕒 Время: {timestamp}"
        img_pil = Image.fromarray(image_array)
        img_byte_array = io.BytesIO()
        img_pil.save(img_byte_array, format='JPEG')
        img_byte_array.seek(0)
        await telegram_bot.send_photo(
            chat_id=TELEGRAM_CHAT_ID,
            photo=InputFile(img_byte_array, filename="photo.jpg"),
            caption=message
        )
    except Exception as e:
        st.error(f"❌ Ошибка Telegram: {e}")

def send_notification_async(name, shift, timestamp, image_array, is_exit=False):
    def task():
        asyncio.run(send_telegram_notification(name, shift, timestamp, image_array, is_exit))
    threading.Thread(target=task).start()

# --- Загрузка анализатора лиц ---
@st.cache_resource
def load_analyzer():
    analyzer = FaceAnalysis(name="buffalo_l")
    analyzer.prepare(ctx_id=-1, det_size=(640, 640))
    return analyzer

analyzer = load_analyzer()

# --- Загрузка известных лиц ---
@st.cache_resource
def load_known_faces():
    try:
        data = supabase.storage.from_('avatars').list()
        embeddings = {}
        for item in data:
            if not item['name'].lower().endswith(('.jpg', '.jpeg', '.png')):
                continue
            try:
                content = supabase.storage.from_('avatars').download(item['name'])
                img = Image.open(BytesIO(content)).convert('RGB')
                arr = np.array(img)
                faces = analyzer.get(arr)
                if faces:
                    embeddings[item['name']] = faces[0].normed_embedding
            except Exception as e:
                st.warning(f"⚠️ Ошибка при {item['name']}: {e}")
        return embeddings
    except Exception as e:
        st.error(f"❌ Ошибка загрузки лиц: {e}")
        return {}

# --- Интерфейс ---
st.title("📸 Учёт смен с распознаванием лиц и Telegram-уведомлением")
known_faces = load_known_faces()
if not known_faces:
    st.warning("⚠️ Нет доступных лиц для сравнения.")

ip_url = "http://192.168.0.150/ISAPI/Streaming/channels/101/picture"

def get_frame_from_camera():
    cap = cv2.VideoCapture(ip_url, cv2.CAP_FFMPEG)
    for _ in range(10):
        ret, frame = cap.read()
        if ret and frame is not None:
            cap.release()
            return frame
        time.sleep(0.2)
    cap.release()
    return None

def recognize_and_process(is_exit=False):
    frame = get_frame_from_camera()
    if frame is None:
        st.error("❌ Камера не отвечает.")
        return

    img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    st.image(img, caption="📷 Захвачено", use_column_width=True)

    faces = analyzer.get(img)
    if not faces:
        st.warning("⚠️ Лицо не найдено.")
        return

    user_emb = faces[0].normed_embedding
    results = [(name, np.linalg.norm(user_emb - emb)) for name, emb in known_faces.items()]
    if not results:
        st.warning("❌ Нет эмбеддингов для сравнения.")
        return

    match = min(results, key=lambda x: x[1])
    st.write(f"📏 Расстояние: {match[1]:.4f}")

    if match[1] >= 1.0:
        st.warning("❌ Совпадений не найдено.")
        return

    full_name = os.path.splitext(match[0])[0]
    st.success(f"✅ Совпадение: {full_name}")
    now = datetime.now().replace(second=0, microsecond=0).strftime("%Y-%m-%d %H:%M")
    today = date.today().isoformat()
    shift = get_current_shift()

    try:
        existing = supabase.table("shift_logs").select("*").eq("full_name", full_name).execute()
        today_logs = [r for r in existing.data if r.get("logged_at", "").startswith(today)]

        if is_exit:
            if not today_logs:
                st.warning(f"⚠️ Нет входа сегодня для: {full_name}")
                return

            last_log = sorted(today_logs, key=lambda x: x["logged_at"], reverse=True)[0]
            if last_log.get("shift_end"):
                st.warning(f"⚠️ Уже выходил: {last_log['shift_end']}")
                return

            update_res = supabase.table("shift_logs").update({
                "shift_end": now
            }).eq("id", last_log["id"]).execute()
            if update_res.data:
                st.success("📤 Уход записан.")
                send_notification_async(full_name, last_log["shift"], now, img, is_exit=True)

        else:
            if any(r.get("logged_at", "").startswith(today) for r in today_logs):
                st.warning(f"⚠️ Уже есть вход сегодня: {full_name}")
                return

            shift_log = {
                "full_name": full_name,
                "shift": shift,
                "logged_at": now
            }
            res_log = supabase.table("shift_logs").insert(shift_log).execute()
            if res_log.data:
                st.success(f"📘 Вход записан. Смена: {shift}")
                send_notification_async(full_name, shift, now, img)

    except Exception as e:
        st.error(f"❌ Ошибка записи: {e}")

# --- Кнопки ---
col1, col2 = st.columns(2)

with col1:
    if st.button("🚪 Начать смену (вход)"):
        recognize_and_process(is_exit=False)

with col2:
    if st.button("🏁 Закончить смену (выход)"):
        recognize_and_process(is_exit=True)
