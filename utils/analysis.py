# analysis.py
import os
import re
import geopandas as gpd
import pandas as pd
import numpy as np
import streamlit as st

# Dictionary lokasi folder dan alokasi ODP per kecamatan, dikelompokkan per area
# Path sekarang relatif ke folder 'data' di root project
# Menambahkan kecamatan Kabupaten Malang dengan ODP aktual dan path sesuai screenshot terakhir
area_kecamatan_info = {
    "Kota Malang": {
        # Folder untuk Kota Malang langsung di dalam data
        "lowokwaru":     {"path": os.path.join("data", "Lowokwaru"),      "total_odp": 329},
        "blimbing":      {"path": os.path.join("data", "Blimbing"),       "total_odp": 42},
        "klojen":        {"path": os.path.join("data", "Klojen"),         "total_odp": 40},
        "kedungkandang": {"path": os.path.join("data", "Kedungkandang"),  "total_odp": 101},
        # PERHATIAN: Nama folder Sukun di screenshot terakhir adalah 'Kecamatan Sukun'
        "sukun":         {"path": os.path.join("data", "Kecamatan Sukun"), "total_odp": 5},
    },
    "Kabupaten Malang": {
        # Folder untuk Kabupaten Malang langsung di dalam data (sesuai screenshot terakhir)
        # Nama folder di disk tanpa "Kecamatan "
        "dau":           {"path": os.path.join("data", "Dau"),           "total_odp": 242}, # ODP Aktual
        "pakis":         {"path": os.path.join("data", "Pakis"),         "total_odp": 47},  # ODP Aktual
        "pakisaji":      {"path": os.path.join("data", "Pakisaji"),      "total_odp": 0},   # ODP Aktual
        "pujon":         {"path": os.path.join("data", "Pujon"),         "total_odp": 3}    # ODP Aktual
    }
}

@st.cache_data(ttl=600)
def process_all_data(area_kec_info: dict, odp_capacity: int = 16) -> dict:
    """
    Iterasi melalui area dan kecamatan dalam area_kec_info,
    baca GeoJSON, hitung Homepass, alokasi ODP, SAM, SOM, kategori.
    Kembalikan dict {nama_kecamatan: DataFrame} untuk SEMUA kecamatan.
    """
    all_results = {}

    # Iterasi melalui setiap area
    for area_name, kecamatan_list in area_kec_info.items():
        # Iterasi melalui setiap kecamatan di dalam area
        for kecamatan_name, info in kecamatan_list.items():
            folder_path = info["path"]
            total_odp   = info["total_odp"]

            # Optional Debug: st.write(f"Processing {kecamatan_name.title()} from {area_name} (Folder: {folder_path})...")

            if not os.path.exists(folder_path):
                st.error(f"Folder data tidak ditemukan untuk {kecamatan_name.title()} di: `{folder_path}`. Lewati pemrosesan kecamatan ini.")
                continue

            # List semua file .geojson
            try:
                geojson_files = [f for f in os.listdir(folder_path) if f.lower().endswith(".geojson")]
                if not geojson_files:
                    st.warning(f"Tidak ada file .geojson ditemukan di folder {folder_path} ({kecamatan_name.title()}). Lewati pemrosesan kecamatan ini.")
                    continue
            except Exception as e:
                 st.error(f"Gagal membaca isi folder {folder_path} ({kecamatan_name.title()}): {e}. Lewati pemrosesan kecamatan ini.")
                 continue

            data = []

            for file in geojson_files:
                file_path = os.path.join(folder_path, file)
                try:
                    gdf = gpd.read_file(file_path)
                except Exception as e:
                    st.warning(f"Gagal membaca file GeoJSON: {file_path} ({kecamatan_name.title()}) - {e}. Lewati file ini.")
                    continue

                # --- START: Improved kelurahan name parsing ---
                base_name = os.path.splitext(file)[0]
                kel = base_name.strip() # Default to base name

                # Try to find "kelurahan X" pattern first (case-insensitive)
                match = re.search(r'kelurahan\s+(.+)', base_name, re.IGNORECASE)
                if match:
                    kel = match.group(1).strip()
                else:
                     # Fallback: remove specific known prefixes based on observed patterns
                     temp_name = kel.lower()
                     kec_lower = kecamatan_name.lower()
                     prefixes_to_remove = [
                          f"homepass kecamatan {kec_lower} kelurahan ",
                          f"homepass kecamatan {kec_lower} ",
                          f"{kec_lower}_",
                          f"kecamatan {kec_lower} ", # Possible prefix based on folder name?
                          "kelurahan_",
                          "homepass kelurahan ",
                          "homepass ",
                     ]
                     for prefix in prefixes_to_remove:
                          if temp_name.startswith(prefix):
                               temp_name = temp_name[len(prefix):].strip()
                               break

                     if temp_name:
                          kel = temp_name

                kel = kel.title() # Apply title case
                # --- END: Improved kelurahan name parsing ---

                homepass_count = len(gdf)
                data.append({"kelurahan": kel, "homepass": homepass_count})

            # Bangun DataFrame dan hitung alokasi hanya jika ada data homepass yang berhasil dibaca
            if not data:
                 st.warning(f"Tidak ada data homepass yang valid ditemukan untuk {kecamatan_name.title()}. Lewati pemrosesan alokasi.")
                 continue

            df = pd.DataFrame(data)
            total_homepass = df["homepass"].sum()

            # === START: Handle ODP=0 or Homepass=0 ===
            if total_odp > 0 and total_homepass > 0:
                df["odp_float"] = df["homepass"] / total_homepass * total_odp
                df["odp_floor"] = np.floor(df["odp_float"]).astype(int)
                df["sisa"] = df["odp_float"] - df["odp_floor"]
                sisa_odp = total_odp - df["odp_floor"].sum()

                df = df.sort_values(["sisa", "homepass"], ascending=[False, False]).reset_index(drop=True)
                if sisa_odp > 0:
                    num_rows = len(df)
                    odp_to_add_count = min(sisa_odp, num_rows)
                    df.loc[:odp_to_add_count-1, "odp_floor"] += 1

                df["ODP"] = df["odp_floor"]
                df["SAM"] = df["ODP"] * odp_capacity
                df["SOM"] = (df["SAM"] * 0.3).round(0).astype(int)
                df = df.drop(columns=["odp_float", "odp_floor", "sisa"])

            else:
                 #st.info(f"Total ODP ({total_odp}) atau Total Homepass ({total_homepass}) adalah 0 untuk {kecamatan.title()}. ODP, SAM, SOM akan diset 0.")
                 df["ODP"] = 0
                 df["SAM"] = 0
                 df["SOM"] = 0
            # === END: Handle ODP=0 or Homepass=0 ===

            # === START: Ranking dan Kategori Potensi (Remove Emojis) ===
            df = df.sort_values("SOM", ascending=False).reset_index(drop=True)
            if df["SOM"].sum() == 0:
                 df["ranking"] = np.arange(1, len(df) + 1)
                 # Menghapus emoji
                 df["kategori_potensi"] = "Tidak Ada Potensi"
            else:
                df["ranking"] = df["SOM"].rank(method='min', ascending=False).astype(int)
                mean_som = df["SOM"][df["SOM"] > 0].mean() if (df["SOM"] > 0).any() else 0
                df["kategori_potensi"] = df["SOM"].apply(
                    # Menghapus emoji
                    lambda x: "High Potential" if x > mean_som and mean_som > 0 else ("Low Potential" if x > 0 else "Tidak Ada Potensi")
                )
            # === END: Ranking dan Kategori Potensi ===


            all_results[kecamatan_name] = df[
                ["ranking", "kelurahan", "homepass", "ODP", "SAM", "SOM", "kategori_potensi"]
            ]

    # Filter out kecamatans that failed to process
    processed_kecamatans = {k: v for k, v in all_results.items() if k in area_kecamatan_info["Kota Malang"].keys() or k in area_kecamatan_info["Kabupaten Malang"].keys()}
    processed_kecamatans = {k: v for k, v in processed_kecamatans.items() if not v.empty}

    if not processed_kecamatans:
        st.error("❌ Gagal memproses data untuk semua kecamatan yang dikonfigurasi. Mohon cek folder data dan file GeoJSON.")

    return processed_kecamatans

# Ekspor dictionary area_kecamatan_info agar bisa diakses di app.py
area_info_for_app = area_kecamatan_info