import streamlit as st
import requests
from PIL import Image
import io
from urllib.parse import quote_plus
import os

# --- Настройки камеры ---
CAMERA_USER = "admin"
CAMERA_PASS = "Shagzod1$"
CAMERA_IP = "192.168.0.150"
CAMERA_PORT = "80"  # или другой, если проброс
CAMERA_PATH = "/Streaming/channels/1/picture"

# --- Кодируем пароль для URL ---
encoded_pass = quote_plus(CAMERA_PASS)
camera_url = f"http://{CAMERA_USER}:{encoded_pass}@{CAMERA_IP}:{CAMERA_PORT}{CAMERA_PATH}"

st.title("📷 Просмотр IP-камеры (HTTP Snapshot)")
st.markdown(f"🔗 Камера URL: `{camera_url}`")

def get_camera_frame():
    try:
        response = requests.get(camera_url, timeout=5)
        if response.status_code == 200:
            return Image.open(io.BytesIO(response.content))
        else:
            st.error(f"❌ Ошибка HTTP: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"🚫 Ошибка подключения: {e}")
        return None

if st.button("📸 Получить кадр"):
    img = get_camera_frame()
    if img:
        st.image(img, caption="Текущий кадр с камеры", use_column_width=True)
