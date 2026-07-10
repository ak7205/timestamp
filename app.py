import io
from contextlib import contextmanager
import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps
from datetime import datetime
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim

# HEIC / HEIF support -----------------------------------------
# Pillow can't read HEIC/HEIF natively, pillow-heif patches it in.
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIC_SUPPORTED = True
except ImportError:
    HEIC_SUPPORTED = False

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
    draw.multiline_text((x+1, y+1), text, font=font, fill=(0, 0, 0, 120), spacing=spacing)
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


def open_any_image(img_file):
    """Open JPEG/PNG/HEIC/HEIF/WEBP/BMP/TIFF and fix EXIF orientation."""
    img = Image.open(img_file)
    img = ImageOps.exif_transpose(img)  # fix rotated phone photos
    return img.convert("RGBA")


def proses_watermark(img_file, teks):
    img_raw = open_any_image(img_file)

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
    addr_h = draw.multiline_textbbox((0, 0), alamat, font=font_reg, spacing=line_spacing)[3]
    coord_h = font_reg.size

    total_h = date_h + section_gap + addr_h + section_gap + coord_h
    start_y = h - total_h - margin_y

    line_x = margin_x - gap_line
    draw.rectangle([line_x, start_y, line_x+10, start_y+total_h], fill=(255, 200, 0, 255))

    y = start_y
    draw_text_shadow(draw, (margin_x, y), teks["datetime"], font_bold, "white")
    y += date_h + section_gap

    draw_text_shadow(draw, (margin_x, y), alamat, font_reg, "white", spacing=line_spacing)
    y += addr_h + section_gap

    draw_text_shadow(draw, (margin_x, y), teks["koordinat"], font_reg, "white")

    return img.convert("RGB")


def format_alamat_indonesia(addr: dict) -> str:

    kecamatan = (
        addr.get("subdistrict")
        or addr.get("district")
        or addr.get("city_district")
    )
    kabupaten = addr.get("county") or addr.get("city")
    provinsi = addr.get("state")

    parts = []

    if kecamatan:
        parts.append(f"Kecamatan {kecamatan}")

    if kabupaten:
        if not kabupaten.lower().startswith(("kabupaten", "kota")):
            kabupaten = f"Kabupaten {kabupaten}"
        parts.append(kabupaten)
    else:
        parts.append("Kabupaten [isi kabupaten]")

    if provinsi:
        parts.append(provinsi)

    return ", ".join(parts)


# =============================
# STREAMLIT UI
# =============================
st.set_page_config("CusTime by AK", "📸", layout="wide", initial_sidebar_state="collapsed")

def load_css():
    with open("style.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css()

components.html(
    """
    <script>
    function hideStreamlitBadge() {
        try {
            window.parent.document
                .querySelectorAll('[href*="streamlit.io"]')
                .forEach(el => {
                    const badge = el.closest('div') || el;
                    badge.style.display = 'none';
                });
        } catch (e) {}
    }
    hideStreamlitBadge();
    setInterval(hideStreamlitBadge, 1000);
    </script>
    """,
    height=0,
)

@contextmanager
def card(title, icon=""):
    """A real bordered container (native Streamlit nesting) with a title
    rendered as its first child - no separate empty HTML block above it."""
    with st.container(border=True):
        st.markdown(f'<div class="card-title">{icon} {title}</div>', unsafe_allow_html=True)
        yield

# ---- TOP BAR ----
st.markdown(
    """
    <div class="topbar">
        <div class="brand">
            <div class="brand-name">Cus<span class="accent">Time</span></div>
            <div class="brand-sub">by <b>AK</b></div>
        </div>
        <div class="topbar-badge">Custom Timestamp Foto</div>
    </div>
    """,
    unsafe_allow_html=True,
)

left, right = st.columns([1, 1], gap="medium")

with left:
    # =============================
    # UPLOAD CARD
    # =============================
    with card("1. Upload Foto", ""):
        accepted_types = ["jpg", "jpeg", "png", "webp", "bmp", "tiff", "tif"]
        if HEIC_SUPPORTED:
            accepted_types += ["heic", "heif"]

        uploaded_file = st.file_uploader(
            "Pilih atau seret foto ke sini",
            type=accepted_types,
            help="Mendukung JPEG, PNG, WEBP, BMP, TIFF"
            + (", HEIC, HEIF (foto iPhone)" if HEIC_SUPPORTED else ""),
        )

        if not HEIC_SUPPORTED:
            st.warning(
                "Dukungan HEIC/HEIF belum aktif. Install dengan: `pip install pillow-heif`, "
                "lalu restart aplikasi.",
                icon="⚠️",
            )

    # =============================
    # DATE / TIME CARD
    # =============================
    with card("2. Pilih Tanggal & Jam", ""):
        colA, colB = st.columns(2)
        with colA:
            input_date = st.date_input("Tanggal", datetime.now())
        with colB:
            col_h, col_m = st.columns(2)
            with col_h:
                jam = st.selectbox("Jam", [f"{i:02d}" for i in range(24)], index=datetime.now().hour)
            with col_m:
                menit = st.selectbox("Menit", [f"{i:02d}" for i in range(60)], index=datetime.now().minute)
            input_time_str = f"{jam}:{menit}"

    # =============================
    # LOCATION SEARCH
    # =============================
    with card("3. Pilih Lokasi Geotagging", ""):
        query = st.text_input(
            "Cari lokasi (alamat atau koordinat)",
            placeholder="🔍  Cari lokasi...",
            label_visibility="collapsed",
        )

        search_clicked = st.button("Cari Lokasi", use_container_width=True)

        if search_clicked:
            geo = Nominatim(user_agent="photo_timestamp")
            loc = geo.geocode(query + ", Indonesia", exactly_one=True, addressdetails=True)

            if not loc:
                locs = geo.geocode(query, exactly_one=False, limit=1)
                if locs:
                    loc = locs[0]

            if loc:
                st.session_state.lat = loc.latitude
                st.session_state.lng = loc.longitude
            else:
                st.warning("Lokasi tidak ditemukan. Coba tulis lebih lengkap, contoh: `Sirenja, Donggala`")

        m = folium.Map(location=[st.session_state.lat, st.session_state.lng], zoom_start=14, control_scale=True)
        folium.Marker(
            [st.session_state.lat, st.session_state.lng],
            tooltip="Lokasi terpilih",
            icon=folium.Icon(color="red"),
        ).add_to(m)

        map_data = st_folium(m, height=260, use_container_width=True)

        if map_data and map_data.get("last_clicked"):
            st.session_state.lat = map_data["last_clicked"]["lat"]
            st.session_state.lng = map_data["last_clicked"]["lng"]

        geo = Nominatim(user_agent="photo_timestamp")
        try:
            loc = geo.reverse(f"{st.session_state.lat}, {st.session_state.lng}", exactly_one=True, addressdetails=True)
            addr = loc.raw.get("address", {}) if loc else {}
        except Exception:
            addr = {}

        alamat_otomatis = format_alamat_indonesia(addr)

    # =============================
    # CUSTOM ALAMAT CARD
    # =============================
    with card("4. Custom Alamat (Opsional)", ""):
        input_address = st.text_area(
            "Alamat",
            value=alamat_otomatis,
            height=90,
            label_visibility="collapsed",
            placeholder="Masukkan alamat kustom...",
        )
        st.caption("Kosongkan / biarkan seperti semula untuk memakai alamat dari lokasi terpilih.")
        if not input_address.strip():
            input_address = alamat_otomatis

with right:
    # =============================
    # PREVIEW
    # =============================
    with card("5. Preview", ""):
        st.caption("")

        if uploaded_file:
            try:
                data = {
                    "datetime": input_date.strftime("%a, %d %b %Y") + " " + input_time_str,
                    "alamat": input_address,
                    "koordinat": (
                        f"{abs(st.session_state.lat):.6f}°"
                        f"{'S' if st.session_state.lat < 0 else 'N'}, "
                        f"{abs(st.session_state.lng):.6f}°"
                        f"{'E' if st.session_state.lng > 0 else 'W'}"
                    ),
                }

                with st.spinner("Memproses gambar..."):
                    result = proses_watermark(uploaded_file, data)

                st.image(result, use_container_width=True)

                buf = io.BytesIO()
                result.save(buf, format="JPEG", quality=95)

                btn_a, btn_b = st.columns(2)
                with btn_a:
                    st.button("👁️ Preview Ulang", use_container_width=True)
                with btn_b:
                    st.download_button(
                        "⬇️ Download Foto",
                        buf.getvalue(),
                        f"timestamp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg",
                        use_container_width=True,
                        type="primary",
                    )

                st.markdown(
                    '<p class="privacy-note">🛡️ Foto Anda tidak diunggah ke server luar — seluruh proses berjalan di aplikasi lokal Anda.</p>',
                    unsafe_allow_html=True,
                )
            except Exception as e:
                st.error(f"Gagal memproses gambar: {e}")
        else:
            st.markdown(
                '<div class="empty-state">📤<br>Upload foto untuk melihat preview</div>',
                unsafe_allow_html=True,
            )
            st.caption("")

# =============================
# FOOTER
# =============================
st.markdown(
    """
    <div class="footer">
        <div class="footer-brand">CusTime by AK</div>
        <div class="footer-tagline">Custom Timestamp Foto dengan Gaya Anda.</div>
    </div>
    """,
    unsafe_allow_html=True,
)
