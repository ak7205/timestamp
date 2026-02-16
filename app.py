import io
from folium.plugins import draw
import streamlit as st
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim

# === SIMPAN KOORDINAT GLOBAL ===
if "lat" not in st.session_state:
    st.session_state.lat = -0.6747649110180753
    st.session_state.lng = 119.74794964511652

st.write("DEBUG LAT:", st.session_state.lat)
st.write("DEBUG LNG:", st.session_state.lng)


# --- FUNGSI PROSES GAMBAR ---
def wrap_text(text, font, max_width, draw):
    words = text.split()
    lines = []
    current_line = ""

    for word in words:
        test_line = current_line + word + " "
        if draw.textlength(test_line, font=font) <= max_width:
            current_line = test_line
        else:
            lines.append(current_line.strip())
            current_line = word + " "

    if current_line:
        lines.append(current_line.strip())

    return "\n".join(lines)

#--- FUNGSI DRAW TEXT DENGAN SHADOW ---
def draw_text_shadow(draw, pos, text, font, fill, shadow_offset=(1, 1), shadow_fill=(0, 0, 0, 100), spacing=0):
    x, y = pos

    # Shadow
    draw.multiline_text(
        (x + shadow_offset[0], y + shadow_offset[1]),
        text,
        font=font,
        fill=shadow_fill,
        spacing=spacing
    )

    # Main text
    draw.multiline_text(
        (x, y),
        text,
        font=font,
        fill=fill,
        spacing=spacing
    )

# --- FUNGSI FIT IMAGE TO FRAME ---
def fit_image_to_frame(img, target_ratio, long_edge=3000):
    iw, ih = img.size
    is_landscape = iw >= ih

    if is_landscape:
        frame_w = long_edge
        frame_h = int(frame_w / target_ratio)
    else:
        frame_h = long_edge
        frame_w = int(frame_h * target_ratio)

    scale = max(frame_w / iw, frame_h / ih)
    nw, nh = int(iw * scale), int(ih * scale)

    img = img.resize((nw, nh), Image.LANCZOS)

    left = (nw - frame_w) // 2
    top = (nh - frame_h) // 2

    return img.crop((left, top, left + frame_w, top + frame_h))

# --- FUNGSI UTAMA PROSES WATERMARK ---
def proses_watermark(img_file, teks):
    img_raw = Image.open(img_file).convert("RGBA")

    # auto ratio dari foto
    iw, ih = img_raw.size
    target_ratio = 4 / 3 if iw >= ih else 3 / 4

    # FIT ke frame
    img = fit_image_to_frame(img_raw, target_ratio)
    draw = ImageDraw.Draw(img)

    w, h = img.size
    is_landscape = w >= h


    # ===== FONT =====

    if is_landscape:
        font_bold = ImageFont.truetype(
        "fonts/RobotoCondensed-Bold.ttf",
        int(h * 0.040)
        )
        font_reg = ImageFont.truetype(
        "fonts/RobotoCondensed-Regular.ttf",
        int(h * 0.040)
        )
    
    else:
        font_bold = ImageFont.truetype(
        "fonts/RobotoCondensed-Bold.ttf",
        int(h * 0.030)
        )
        font_reg = ImageFont.truetype(
            "fonts/RobotoCondensed-Regular.ttf",
            int(h * 0.030)
        )

    # ===== MARGIN & MAX WIDTH =====

    if is_landscape:
        margin_x = int(w * 0.038)
        margin_y = int(h * 0.028)
        max_text_width = int(w * 0.42)
    else:
        margin_x = int(w * 0.05)
        margin_y = int(h * 0.02)
        max_text_width = int(w * 0.62)

    # ===== SPACING =====
    if is_landscape:
        line_spacing = 25       # antar baris alamat
        section_gap = 77        # ENTER antar bagian
        gap_line_text = 48      # jarak antara garis kuning dan teks (px)
    else:
        line_spacing = 8        # antar baris alamat (lebih kecil untuk portrait)
        section_gap = 42        # ENTER antar bagian
        gap_line_text = 25      # jarak antara garis kuning dan teks (px)

    # ===== WRAP ALAMAT =====
    alamat_wrapped = wrap_text(
        teks["alamat"],
        font_reg,
        max_text_width,
        draw
    )

    # ===== HITUNG TINGGI =====
    date_h = font_bold.size
    addr_bbox = draw.multiline_textbbox(
        (0, 0), alamat_wrapped, font=font_reg, spacing=line_spacing
    )
    addr_h = addr_bbox[3] - addr_bbox[1]
    coord_h = font_reg.size

    total_h = (
        date_h +
        section_gap +
        addr_h +
        section_gap +
        coord_h
    )

    start_y = h - total_h - margin_y

    # ===== GARIS KUNING =====
    line_x = margin_x - gap_line_text - 4
    # ===== SHADOW GARIS (TIPIS) =====
    draw.rectangle(
        [line_x + 1, start_y + 1, line_x + 5, start_y + total_h + 1],
        fill=(0, 0, 0, 20)
    )

# ===== GARIS KUNING =====
    draw.rectangle(
        [line_x, start_y, line_x + 12, start_y + total_h],
        fill=(255, 200, 0, 255)
    )

    y = start_y

    # ===== TANGGAL (BOLD) =====
    draw_text_shadow(
        draw,
        (margin_x, y),
        teks["datetime"],
        font=font_bold,
        fill="white"
)
    y += date_h + section_gap

    # ===== ALAMAT =====
    draw_text_shadow(
        draw,
        (margin_x, y),
        alamat_wrapped,
        font=font_reg,
        fill="white",
        spacing=line_spacing
    )

    y += addr_h + section_gap

    # ===== KOORDINAT =====
    draw_text_shadow(
        draw,
        (margin_x, y),
        teks["koordinat"],
        font=font_reg,
        fill="white"
    )

    return img.convert("RGB")


# --- INTERFACE STREAMLIT ---
st.set_page_config(
    page_title="Photo Timestamp GPS",
    page_icon="📸",
    layout="wide",
    initial_sidebar_state="collapsed"
)

def load_css(file_name):
    with open(file_name) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css("style.css")

def card_start():
    st.markdown('<div class="card">', unsafe_allow_html=True)

def card_end():
    st.markdown('</div>', unsafe_allow_html=True)

st.title("📸 Photo Timestamp GPS")
st.caption("Tambahkan tanggal, alamat, dan koordinat langsung ke foto")

col1, spacer, col2 = st.columns([4, 1, 5])

with spacer:
    pass

with col1:
    card_start()
    st.markdown("### 📥 Input")
    uploaded_file = st.file_uploader("Upload Foto", type=['jpg','jpeg','png'])
    input_date = st.date_input("Tanggal", datetime.now())
    input_time = st.time_input("Waktu", datetime.now())
    card_end()
    
st.markdown("### 🔍 Cari Lokasi")

query = st.text_input(
    "Masukkan nama lokasi",
    placeholder="Contoh: Donggala, Sulawesi Tengah"
)

btn_search = st.button("Cari Lokasi")
if btn_search and query:
    geolocator = Nominatim(user_agent="photo_timestamp_app")
    try:
        location = geolocator.geocode(query)
        if location:
            st.session_state.lat = location.latitude
            st.session_state.lng = location.longitude
            st.success(f"Lokasi ditemukan: {location.address}")
        else:
            st.warning("Lokasi tidak ditemukan")
    except Exception as e:
        st.error("Gagal mencari lokasi")


m = folium.Map(
    location=[st.session_state.lat, st.session_state.lng],
    zoom_start=14
)

m.add_child(folium.LatLngPopup())
map_data = st_folium(m, height=280)

if map_data and map_data.get("last_clicked"):
    st.session_state.lat = map_data["last_clicked"]["lat"]
    st.session_state.lng = map_data["last_clicked"]["lng"]


    st.info(f"Koordinat terpilih: {lat:.5f}, {lng:.5f}")

    # Otomatis cari alamat berdasarkan koordinat (Reverse Geocoding)
    geolocator = Nominatim(user_agent="my_app")
    try:
        location = geolocator.reverse(f"{lat}, {lng}")
        address = location.address if location else "Alamat tidak ditemukan"
    except:
        address = "Gagal mengambil alamat"
    
    input_address = st.text_area("Edit Alamat (Jika perlu)", address)

    with col2:
        st.markdown("### 👀 Preview")
        if uploaded_file:
            data_final = {
            "datetime": input_date.strftime("%a, %d %b %Y") + " " + input_time.strftime("%H:%M"),
            "alamat": input_address,
            "koordinat": f"{abs(lat):.6f}°{'S' if lat < 0 else 'N'}, {abs(lng):.6f}°{'E' if lng > 0 else 'W'}"
        }

        result_img = proses_watermark(uploaded_file, data_final)
        card_start()
        st.markdown("### Hasil")
        st.image(result_img, use_container_width=True)
        buf = io.BytesIO()
        result_img.save(buf, format="JPEG")
        st.download_button(
            "⬇️ Download Foto",
            data=buf.getvalue(),
            file_name=f"timestamp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg",
            use_container_width=True
        )
        card_end()
    else:
    st.info("Silakan upload foto terlebih dahulu untuk melihat preview.")
        
        