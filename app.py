# app.py
import streamlit as st
import matplotlib.pyplot as plt
import io

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    Table, TableStyle, Image
)
from reportlab.lib.units import inch

# Import fungsi proses data dan dictionary info area
from utils.analysis import process_all_data, area_info_for_app

# Matplotlib backend for Streamlit compatibility
plt.switch_backend('Agg')


# --------------------------------------------------
# CONFIG & CUSTOM CSS
# --------------------------------------------------
st.set_page_config(
    page_title="Kapten Naratel Dashboard",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Oswald:wght@400;600&display=swap');
html, body, [class*="css"] { background-color: #000; color: #fff; font-family: 'Oswald', sans-serif; }
h1,h2,h3,h4 { color: #FFD700; font-family:'Bebas Neue',sans-serif; letter-spacing:1px; }
.stSidebar { background-color:#111; width:300px; }
.stButton>button { background: linear-gradient(to right,#FFD700,#FFC300); color:#000; font-weight:bold; border-radius:8px; padding:.5em 1em;}
.card { background:#111; padding:1rem; margin-bottom:1rem; border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,0.5); }
[data-testid="stSidebar"] { position:fixed; top:0; left:0; height:100vh; z-index=1000; }
[data-testid="stAppViewContainer"] > div:nth-child(1) { margin-left:0!important; }
</style>
""", unsafe_allow_html=True)

# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------
with st.spinner("🔄 Memuat dan memproses data dari semua area..."):
    all_kecamatan_dfs = process_all_data(area_info_for_app)

if not all_kecamatan_dfs:
    st.error("❌ Gagal memuat data untuk semua kecamatan yang dikonfigurasi. Mohon cek folder data dan konfigurasi di analysis.py.")
    st.stop()

# --------------------------------------------------
# HELPER FUNCTIONS
# --------------------------------------------------
def get_rekomendasi(row):
    kategori = row["kategori_potensi"]
    som = row["SOM"]
    sam = row["SAM"]

    # === Mempersingkat teks rekomendasi lebih jauh ===
    if som > 0:
        if "High Potential" in kategori:
            return ("Promosi/Perluas Cover" # Sangat singkat
                    if som < sam * 0.6 else "Performa Baik") # Sangat singkat
        elif "Low Potential" in kategori:
             return "Strategi Lokal/Beda" # Sangat singkat
    else:
        return "Tidak Prioritas" # Sangat singkat
    # === Akhir Persingkatan ===


def plot_market_pie_agg(df):
    total_hp = df["homepass"].sum()
    total_sam = df["SAM"].sum()
    total_som = df["SOM"].sum()

    labels = ["Homepass","SAM","SOM"]
    values = [total_hp, total_sam, total_som]
    colors_pie = ["#6EC1E4","#FFD700","#FF5733"]

    if sum(values) == 0:
        fig, ax = plt.subplots(figsize=(6,6)) # Ukuran sama
        ax.text(0.5, 0.5, "Tidak Ada Data > 0", horizontalalignment='center', verticalalignment='center', transform=ax.transAxes, color="white")
        ax.axis('off')
        return fig

    # === Ukuran Figure untuk Streamlit UI - Pie Chart ===
    fig, ax = plt.subplots(figsize=(6,6)) # Square figure for pie chart

    pie_values = [v for v in values if v > 0]
    pie_labels_for_slices = [labels[i] for i, v in enumerate(values) if v > 0]
    pie_colors = [colors_pie[i] for i, v in enumerate(values) if v > 0]

    if pie_values:
        total_sum_all = sum(values)
        percentages_all = [v / total_sum_all * 100 for v in values]

        wedges, texts = ax.pie(pie_values,
                               startangle=140,
                               colors=pie_colors) # Tidak pakai autopct di sini

        ax.axis("equal")

        full_legend_labels = [f"{l}: {v} ({percentages_all[i]:.1f}%)" for i, (l, v) in enumerate(zip(labels, values))]

        # Add legend outside (seperti screenshot)
        ax.legend(wedges, full_legend_labels, loc="center left", bbox_to_anchor=(1,0.5), fontsize=8)

    else:
        fig, ax = plt.subplots(figsize=(6,6)) # Ukuran sama
        ax.text(0.5, 0.5, "Data Nol", horizontalalignment='center', verticalalignment='center', transform=ax.transAxes, color="white")
        ax.axis('off')

    plt.tight_layout()
    return fig


def create_pdf_report_kecamatan(area, kecamatan, df):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
                            leftMargin=40, rightMargin=40,
                            topMargin=60, bottomMargin=40)
    styles = getSampleStyleSheet()
    styles['Title'].fontName = 'Helvetica-Bold'
    styles['Heading2'].fontName = 'Helvetica-Bold'
    styles['Heading4'].fontName = 'Helvetica-Bold'
    styles['BodyText'].fontName = 'Helvetica'

    elems = []

    elems.append(Paragraph("Kapten Naratel – Laporan Pasar Homepass", styles['Title']))
    elems.append(Paragraph(f"Area {area} - Kecamatan {kecamatan.title()}", styles['Heading2']))
    elems.append(Spacer(1, 12))

    intro = (
        f"Ringkasan potensi pasar Homepass untuk semua kelurahan "
        f"di Kecamatan <b>{kecamatan.title()}</b> (Area <b>{area}</b>)."
    )
    elems.append(Paragraph(intro, styles['BodyText']))
    elems.append(Spacer(1, 12))

    table_data = [["Ranking", "Kelurahan", "Homepass", "ODP", "SAM", "SOM", "Kategori", "Rekomendasi"]]
    for _, row in df.iterrows():
        table_data.append([
            row["ranking"],
            row["kelurahan"],
            row["homepass"],
            row["ODP"],
            row["SAM"],
            row["SOM"],
            row["kategori_potensi"],
            get_rekomendasi(row) # Menggunakan rekomendasi yang sudah dipersingkat
        ])

    # === Sesuaikan lebar kolom untuk rekomendasi yang SANGAT singkat ===
    # Sesuaikan proporsi total lebar agar pas di halaman letter
    col_widths = [0.4*inch, 1.4*inch, 0.7*inch, 0.6*inch, 0.7*inch, 0.7*inch, 1*inch, 1.3*inch] # Rekomendasi lebih pendek
    total_width_target = 7.5 * inch
    total_current_width = sum(col_widths)
    if total_current_width > 0:
         col_widths_scaled = [w * (total_width_target / total_current_width) for w in col_widths]
    else:
         col_widths_scaled = [total_width_target / len(col_widths)] * len(col_widths)


    tbl = Table(table_data, colWidths=col_widths_scaled)
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#FFD700")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.black),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('ALIGN', (1,1), (1,-1), 'LEFT'),
        ('ALIGN', (6,1), (-1,-1), 'LEFT'), # Align Kategori ke kiri
        ('ALIGN', (-1,1), (-1,-1), 'LEFT'), # Align Rekomendasi ke kiri
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 7),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.whitesmoke, colors.lightgrey]),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('WORDWRAP', (-1, 1), (-1, -1), True), # Pastikan word wrap aktif
    ]))
    elems.append(tbl)
    elems.append(Spacer(1, 12))

    buf_bar = io.BytesIO()
    if not df.empty and "SOM" in df.columns and df["SOM"].sum() > 0:
        # === Ukuran Figure untuk PDF - Bar Chart ===
        fig_bar, ax = plt.subplots(figsize=(6,4)) # Bar chart rectangle
        colors_bar = df["kategori_potensi"].apply(
            lambda x: "#FFD700" if "High Potential" in x else ("#808080" if "Low Potential" in x else "#dc3545")
        )
        ax.bar(df["kelurahan"], df["SOM"], color=colors_bar)
        ax.set_title("SOM per Kelurahan")
        ax.set_ylabel("Jumlah SOM")
        ax.tick_params(axis='x', labelsize=8)
        plt.xticks(rotation=60, ha="right") # Rotasi 60 derajat
        plt.tight_layout()
        fig_bar.savefig(buf_bar, format="PNG", bbox_inches="tight")
        plt.close(fig_bar)
        buf_bar.seek(0)
        elems.append(Paragraph("Grafik SOM per Kelurahan:", styles['Heading4']))
        # === Ukuran Gambar di PDF agar sesuai Figure size ===
        elems.append(Image(buf_bar, width=6*inch, height=4*inch)) # Ukuran gambar 6x4 inch
        elems.append(Spacer(1, 12))
    else:
        elems.append(Paragraph("Tidak ada data SOM > 0 untuk grafik.", styles['BodyText']))
        elems.append(Spacer(1, 12))

    doc.build(elems)
    buf.seek(0)
    return buf


# --------------------------------------------------
# SIDEBAR NAVIGATION
# --------------------------------------------------
st.sidebar.title("🏡 Kapten Naratel")
page = st.sidebar.radio("Pilih Halaman", ["Homepage", "Analisis Pasar"])

# --------------------------------------------------
# HOMEPAGE
# --------------------------------------------------
if page == "Homepage":
    st.title("🏠 Beranda – Kapten Naratel")
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Apa itu TAM, SAM, dan SOM?")
    st.markdown("""
    - **TAM**: Total Addressable Market (Total potensi pasar)
    - **SAM**: Serviceable Available Market (Potensi pasar yang bisa dilayani dengan infrastruktur yang ada)
    - **SOM**: Serviceable Obtainable Market (Potensi pasar yang realistis bisa didapatkan)
    """)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Panduan Penggunaan")
    st.markdown("""
    1. Pilih **Analisis Pasar** di sidebar
    2. Pilih **Area** (Kota/Kabupaten)
    3. Pilih **Kecamatan** (daftar akan terfilter)
    4. Pilih **Kelurahan** (untuk detail)
    5. Lihat statistik, grafik & rekomendasi
    6. Unduh laporan PDF per Kecamatan
    """)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Tentang Data")
    ODP_CAPACITY = 16
    st.markdown(f"""
    Aplikasi ini memproses data Homepass GeoJSON dari folder `data` di root project.
    Data diolah untuk menghitung alokasi ODP (dengan kapasitas **{ODP_CAPACITY}** Homepass per ODP),
    menghitung SAM (ODP * Kapasitas), dan SOM (diasumsikan 30% dari SAM).
    Alokasi ODP per kelurahan dihitung proporsional berdasarkan jumlah Homepass
    dibanding total Homepass di kecamatan tersebut.
    """)
    st.markdown('</div>', unsafe_allow_html=True)


# --------------------------------------------------
# ANALISIS PASAR
# --------------------------------------------------
else:
    st.title("📍 Analisis Pasar Homepass Kapten Naratel")

    areas = list(area_info_for_app.keys())
    if not areas:
         st.error("❌ Tidak ada area yang dikonfigurasi atau ditemukan data. Mohon cek `area_kecamatan_info` di `analysis.py`.")
    else:
        selected_area = st.selectbox("Pilih Area:", areas)

        kecamatan_in_selected_area = list(area_info_for_app.get(selected_area, {}).keys())
        kecamatan_in_selected_area = [k for k in kecamatan_in_selected_area if k in all_kecamatan_dfs]

        kecamatan_in_selected_area.sort()

        if not kecamatan_in_selected_area:
            st.warning(f"Tidak ada data kecamatan yang berhasil dimuat untuk Area {selected_area}. Mohon cek folder data dan konfigurasi di analysis.py.")
        else:
            sel_kec = st.selectbox("Pilih Kecamatan:", kecamatan_in_selected_area)
            df_kec = all_kecamatan_dfs.get(sel_kec)

            if df_kec is None or df_kec.empty:
                 st.warning(f"Data untuk Kecamatan {sel_kec.title()} di Area {selected_area} tidak tersedia atau kosong.")
            else:
                if "kelurahan" in df_kec.columns and not df_kec["kelurahan"].empty:
                    sel_kel = st.selectbox("Pilih Kelurahan:", df_kec["kelurahan"])
                    data_kel_row = df_kec[df_kec["kelurahan"] == sel_kel].head(1)

                    if not data_kel_row.empty:
                         data_kel = data_kel_row.iloc[0]

                         st.subheader(f"📊 Statistik {sel_kel.title()}")
                         c1, c2, c3 = st.columns(3)
                         c1.metric("🏘️ Homepass", data_kel["homepass"])
                         c2.metric("🧮 ODP", data_kel["ODP"])
                         c3.metric("💰 SOM", data_kel["SOM"])
                         st.info(f"**Kategori:** {data_kel['kategori_potensi']}")
                         st.markdown(f"**🧠 Rekomendasi:** {get_rekomendasi(data_kel)}") # Rekomendasi dipersingkat

                         with st.expander("📋 Tabel Semua Kelurahan"):
                            st.dataframe(df_kec, use_container_width=True)

                         st.subheader("📈 Visualisasi")
                         left, right = st.columns(2) # Membagi ruang
                         with left:
                             st.markdown("#### 📊 Ringkasan Homepass, SAM, SOM (Kecamatan)")
                             # Pie chart figure size set in plot_market_pie_agg
                             fig_pie = plot_market_pie_agg(df_kec)
                             if fig_pie: st.pyplot(fig_pie)

                         with right:
                             st.markdown("#### 📶 SOM per Kelurahan")
                             if df_kec["SOM"].sum() > 0:
                                 # === Bar chart figure size - sesuaikan dengan yang di PDF ===
                                 fig_bar, ax = plt.subplots(figsize=(6,4)) # Figure size (lebar, tinggi)
                                 colors_bar = df_kec["kategori_potensi"].apply(
                                     lambda x: "#FFD700" if "High Potential" in x else ("#808080" if "Low Potential" in x else "#dc3545")
                                 )
                                 ax.bar(df_kec["kelurahan"], df_kec["SOM"], color=colors_bar)
                                 ax.set_title("SOM per Kelurahan")
                                 ax.set_ylabel("Jumlah SOM")
                                 ax.tick_params(axis='x', labelsize=8)
                                 plt.xticks(rotation=60, ha="right") # Rotasi 60 derajat untuk nama panjang
                                 plt.tight_layout()
                                 st.pyplot(fig_bar)
                                 plt.close(fig_bar)
                             else:
                                  st.info("Semua kelurahan di kecamatan ini memiliki SOM 0. Grafik SOM per Kelurahan tidak ditampilkan.")

                         st.subheader("📑 Unduh Laporan Kecamatan")
                         pdf_buf = create_pdf_report_kecamatan(selected_area, sel_kec, df_kec)
                         st.download_button(
                             f"📥 Download PDF Laporan {selected_area} - {sel_kec.title()}",
                             data=pdf_buf,
                             file_name=f"laporan_{selected_area.lower().replace(' ', '_')}_{sel_kec.lower()}.pdf", # Nama file PDF singkat
                             mime="application/pdf"
                         )
                    else:
                         st.warning(f"Data rinci untuk kelurahan '{sel_kel}' tidak ditemukan dalam DataFrame.")
                else:
                     st.warning(f"Tidak ada data kelurahan yang ditemukan untuk Kecamatan {sel_kec.title()} dalam DataFrame.")