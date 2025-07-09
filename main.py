import streamlit as st
import requests
from PIL import Image
import io
from urllib.parse import quote_plus
from requests.auth import HTTPBasicAuth

# --- Настройки камеры ---
CAMERA_IP = "192.168.0.150"  # или публичный IP
CAMERA_PORT = "80"
CAMERA_PATH = "/ISAPI/Streaming/channels/101/picture"

CAMERA_USER = "admin"
CAMERA_PASS = "Shagzod1$"  # 💡 можно подключить через dotenv

# --- Сборка полного URL ---
camera_url = f"http://{CAMERA_IP}:{CAMERA_PORT}{CAMERA_PATH}"

st.title("📷 Кадр с IP-камеры (Hikvision)")
st.markdown(f"🔗 URL: `{camera_url}`")

def get_camera_frame():
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(
            camera_url,
            auth=HTTPBasicAuth(CAMERA_USER, CAMERA_PASS),
            timeout=5,
            headers=headers
        )
        if response.status_code == 200:
            return Image.open(io.BytesIO(response.content))
        else:
            st.error(f"❌ HTTP ошибка: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"🚫 Ошибка подключения: {e}")
        return None

if st.button("📸 Получить кадр"):
    img = get_camera_frame()
    if img:
        st.image(img, caption="📷 Текущий кадр", use_column_width=True)
