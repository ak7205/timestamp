import io
import streamlit as st
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim

# =============================
# SESSION STATE DEFAULT
# =============================
if "lat" not in st.session_state:
    st.session_state.lat = -0.6747649   # Donggala
    st.session_state.lng = 119.7479496

# =============================
# IMAGE UTILITIES
# =============================
def wrap_text(text, font, max_width, draw):
    words = text.split()
    lines, current = [], ""

    for w in words:
        test = current + w + " "
        if draw.textlength(test, font=font) <= max_width:
            current = test
        else:
            lines.append(current.strip())
            current = w + " "
    if current:
        lines.append(current.strip())

    return "\n".join(lines)


def draw_text_shadow(draw, pos, text, font, fill, spacing=0):
    x, y = pos
    draw.multiline_text((x+1, y+1), text, font=font, fill=(0,0,0,120), spacing=spacing)
    draw.multiline_text((x, y), text, font=font, fill=fill, spacing=spacing)


def fit_image_to_frame(img, ratio, long_edge=3000):
    iw, ih = img.size
    landscape = iw >= ih

    if landscape:
        fw, fh = long_edge, int(long_edge / ratio)
    else:
        fh, fw = long_edge, int(long_edge * ratio)

    scale = max(fw/iw, fh/ih)
    img = img.resize((int(iw*scale), int(ih*scale)), Image.LANCZOS)

    left = (img.width - fw)//2
    top = (img.height - fh)//2
    return img.crop((left, top, left+fw, top+fh))


def proses_watermark(img_file, teks):
    img_raw = Image.open(img_file).convert("RGBA")

    iw, ih = img_raw.size
    ratio = 4/3 if iw >= ih else 3/4
    img = fit_image_to_frame(img_raw, ratio)

    draw = ImageDraw.Draw(img)
    w, h = img.size
    landscape = w >= h

    size = int(h * (0.04 if landscape else 0.03))
    font_bold = ImageFont.truetype("fonts/RobotoCondensed-Bold.ttf", size)
    font_reg = ImageFont.truetype("fonts/RobotoCondensed-Regular.ttf", size)

    margin_x = int(w * (0.04 if landscape else 0.05))
    margin_y = int(h * (0.03 if landscape else 0.02))
    max_width = int(w * (0.42 if landscape else 0.62))

    line_spacing = 25 if landscape else 10
    section_gap = 70 if landscape else 40
    gap_line = 40 if landscape else 25

    alamat = wrap_text(teks["alamat"], font_reg, max_width, draw)

    date_h = font_bold.size
    addr_h = draw.multiline_textbbox((0,0), alamat, font=font_reg, spacing=line_spacing)[3]
    coord_h = font_reg.size

    total_h = date_h + section_gap + addr_h + section_gap + coord_h
    start_y = h - total_h - margin_y

    line_x = margin_x - gap_line
    draw.rectangle([line_x, start_y, line_x+10, start_y+total_h], fill=(255,200,0,255))

    y = start_y
    draw_text_shadow(draw, (margin_x, y), teks["datetime"], font_bold, "white")
    y += date_h + section_gap

    draw_text_shadow(draw, (margin_x, y), alamat, font_reg, "white", spacing=line_spacing)
    y += addr_h + section_gap

    draw_text_shadow(draw, (margin_x, y), teks["koordinat"], font_reg, "white")

    return img.convert("RGB")

# =============================
# STREAMLIT UI
# =============================
st.set_page_config("Photo Timestamp GPS", "📸", layout="wide")

def load_css():
    with open("style.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css()

def card_start():
    st.markdown('<div class="card">', unsafe_allow_html=True)

def card_end():
    st.markdown('</div>', unsafe_allow_html=True)

st.title("📸 Photo Timestamp GPS")
st.caption("Tambahkan tanggal, alamat, dan koordinat ke foto")

# =============================
# INPUT CARD
# =============================
card_start()
uploaded_file = st.file_uploader("Upload Foto", ["jpg","jpeg","png"])
colA, colB = st.columns(2)
with colA:
    input_date = st.date_input("Tanggal", datetime.now())
with colB:
    input_time = st.time_input("Waktu", datetime.now())
card_end()

# =============================
# LOCATION SEARCH
# =============================
st.markdown("### 📍 Lokasi")

query = st.text_input("Cari lokasi", placeholder="Contoh: Donggala, Sulawesi Tengah")
if st.button("Cari"):
    geo = Nominatim(user_agent="photo_timestamp")
    loc = geo.geocode(query)
    if loc:
        st.session_state.lat = loc.latitude
        st.session_state.lng = loc.longitude
        st.success(loc.address)
    else:
        st.warning("Lokasi tidak ditemukan")

m = folium.Map(
    location=[st.session_state.lat, st.session_state.lng],
    zoom_start=14
)
m.add_child(folium.LatLngPopup())

map_data = st_folium(m, height=300)

if map_data and map_data.get("last_clicked"):
    st.session_state.lat = map_data["last_clicked"]["lat"]
    st.session_state.lng = map_data["last_clicked"]["lng"]

st.info(
    f"Koordinat: {st.session_state.lat:.5f}, {st.session_state.lng:.5f}"
)

geo = Nominatim(user_agent="photo_timestamp")
try:
    loc = geo.reverse(f"{st.session_state.lat}, {st.session_state.lng}")
    address = loc.address if loc else ""
except:
    address = ""

input_address = st.text_area("Alamat", value=address)

# =============================
# PREVIEW
# =============================
st.markdown("### 👀 Preview")

if uploaded_file:
    data = {
        "datetime": input_date.strftime("%a, %d %b %Y") + " " + input_time.strftime("%H:%M"),
        "alamat": input_address,
        "koordinat": (
            f"{abs(st.session_state.lat):.6f}°"
            f"{'S' if st.session_state.lat < 0 else 'N'}, "
            f"{abs(st.session_state.lng):.6f}°"
            f"{'E' if st.session_state.lng > 0 else 'W'}"
        )
    }

    result = proses_watermark(uploaded_file, data)
    st.image(result, use_container_width=True)

    buf = io.BytesIO()
    result.save(buf, format="JPEG")
    st.download_button(
        "⬇️ Download",
        buf.getvalue(),
        f"timestamp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    )
else:
    st.info("Upload foto untuk melihat preview")