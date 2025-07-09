import streamlit as st
import pandas as pd
import simplekml
import folium
from streamlit_folium import st_folium
import math
import io
import re

# --- Fungsi-Fungsi Helper ---
def get_destination_point(lon, lat, bearing, distance_km):
    R = 6371
    d = distance_km
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    bearing_rad = math.radians(bearing)
    lat2_rad = math.asin(math.sin(lat_rad) * math.cos(d / R) +
                         math.cos(lat_rad) * math.sin(d / R) * math.cos(bearing_rad))
    lon2_rad = lon_rad + math.atan2(math.sin(bearing_rad) * math.sin(d / R) * math.cos(lat_rad),
                                     math.cos(d / R) - math.sin(lat_rad) * math.sin(lat2_rad))
    return (math.degrees(lon2_rad), math.degrees(lat2_rad))

def get_kml_color_by_prb(prb_usage):
    try:
        prb = float(prb_usage)
        if prb > 80: return simplekml.Color.changealphaint(200, simplekml.Color.red)
        elif 50 <= prb <= 80: return simplekml.Color.changealphaint(200, simplekml.Color.yellow)
        else: return simplekml.Color.changealphaint(200, simplekml.Color.green)
    except (ValueError, TypeError): return simplekml.Color.changealphaint(200, simplekml.Color.grey)

def get_folium_color_by_prb(prb_usage):
    try:
        prb = float(prb_usage)
        if prb > 80: return 'red'
        elif 50 <= prb <= 80: return 'yellow'
        else: return 'blue'
    except (ValueError, TypeError): return 'grey'

def clean_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name)

# --- Konfigurasi Halaman ---
st.set_page_config(layout="wide")
st.title("Generator KML & Peta Interaktif BTS 🛰️")
st.markdown("""
Aplikasi ini memproses data BTS Anda dan menghasilkan file KML untuk setiap klaster. 
Visualisasi peta interaktif akan dimuat hanya jika Anda menekannya agar aplikasi tetap ringan.
""")

# --- Inisialisasi Session State ---
if 'show_visual' not in st.session_state:
    st.session_state.show_visual = False

def toggle_visualization():
    st.session_state.show_visual = not st.session_state.show_visual
# --- Sidebar ---
st.sidebar.header("Unggah File Anda")
uploaded_bts_file = st.sidebar.file_uploader("1. Unggah file data_bts (.csv)", type="csv")
uploaded_rev_file = st.sidebar.file_uploader("2. Unggah file data_revenue (.csv)", type="csv")

# --- Proses Utama ---
if uploaded_bts_file and uploaded_rev_file:
    try:
        df_bts1 = pd.read_csv(uploaded_bts_file)
        rev_ioh_df = pd.read_csv(uploaded_rev_file)
        
        df_bts1.columns = [col.lower() for col in df_bts1.columns]
        rev_ioh_df.columns = [col.lower() for col in rev_ioh_df.columns]
        if 'site id' in rev_ioh_df.columns:
            rev_ioh_df.rename(columns={'site id': 'site_id'}, inplace=True)
        
        if 'site_id' not in df_bts1.columns or 'site_id' not in rev_ioh_df.columns:
            st.error("Error: Kolom 'site_id' tidak ditemukan.")
        else:
            combined_table = pd.merge(df_bts1, rev_ioh_df, on='site_id', how='right')
            combined_table.dropna(how='all', inplace=True)
            st.success("✔️ File berhasil diunggah dan digabungkan.")
            
            required_cols = ['longitude', 'latitude', 'azimuth', 'beam', 'prb', 'sa cluster', 'site_id']
            if not all(col in combined_table.columns for col in required_cols):
                missing_cols = [col for col in required_cols if col not in combined_table.columns]
                st.error(f"Error: Kolom berikut tidak ditemukan: {', '.join(missing_cols)}.")
            else:
                df_proc = combined_table.copy()
                cols_to_convert = ['longitude', 'latitude', 'azimuth', 'beam', 'prb']
                for col in cols_to_convert:
                    df_proc[col] = pd.to_numeric(df_proc[col], errors='coerce')
                df_proc.dropna(subset=cols_to_convert, inplace=True)

                st.header("📥 Unduh File KML per Klaster")
                kml_clusters = df_proc['sa cluster'].dropna().unique()
                if len(kml_clusters) == 0:
                    st.warning("Tidak ada klaster unik yang ditemukan untuk dibuatkan file KML.")
                else:
                    for cluster in kml_clusters:
                        cluster_df = df_proc[df_proc['sa cluster'] == cluster]
                        kml = simplekml.Kml(name=f"Visualisasi Beam - {cluster}")
                        
                        # Definisikan konstanta untuk pembuatan poligon
                        BEAM_DISTANCE_KM = 0.5
                        ARC_POINTS = 20
                        
                        for _, row in cluster_df.iterrows():
                            # Ambil data dari baris
                            lon, lat = row['longitude'], row['latitude']
                            azimuth, beam_width = row['azimuth'], row['beam']
                            
                            # Buat poligon baru di KML
                            pol = kml.newpolygon(name=str(row['site_id']))
                            
                            # Tambahkan deskripsi
                            pol.description = f"""
                            <b>Site Sector:</b> {row.get('site_sectorid', 'N/A')}<br>
                            <b>Site Name:</b> {row.get('sitename', 'N/A')}<br>
                            <b>Site ID:</b> {row['site_id']}<br>
                            <b>Enobid:</b> {row.get('enbid', 'N/A')}<br>
                            <b>Longitude:</b> {lon}<br>
                            <b>Latitude:</b> {lat}<br>
                            <b>Azimuth:</b> {azimuth}°<br>
                            <b>EUT:</b> {row.get('eut', 'N/A')}<br>
                            <b>CQI:</b> {row.get('cqi', 'N/A')}<br>
                            <b>TLP Partner:</b> {row.get('tlp', 'N/A')}<br>
                            <b>FLP Partner:</b> {row.get('flp', 'N/A')}<br>
                            <b>Transmission:</b> {row.get('transport_fo_mw', 'N/A')}<br>
                            <b>Revenue IOH:</b> {row.get('prepaid_revenue_nett', 'N/A')}<br>
                            <b>VLR IOH:</b> {row.get('vlr_subs_3id', 'N/A')}<br>
                            <b>Battery:</b> {row.get('capacity_bank', 'N/A')}<br>
                            <b>Height:</b> {row.get('ant_height', 'N/A')}<br>
                            <b>Area:</b> {row.get('area', 'N/A')}<br>
                            <b>Config Bandwith:</b> {row.get('config_bandwidth', 'N/A')}<br>
                            <b>Beam Width:</b> {beam_width}°<br>
                            <b>PRB Usage:</b> {row['prb']}%<br>
                            <b>Cluster:</b> {cluster}
                            """

                            # Logika untuk membuat koordinat poligon sektor
                            start_angle = azimuth - (beam_width / 2)
                            coords = [(lon, lat)] # Titik awal adalah tower
                            step = beam_width / ARC_POINTS
                            for i in range(ARC_POINTS + 1):
                                angle = start_angle + i * step
                                if angle < 0: angle += 360
                                if angle >= 360: angle -= 360
                                coords.append(get_destination_point(lon, lat, angle, BEAM_DISTANCE_KM))
                            coords.append((lon, lat)) 
                            
                           
                            pol.outerboundaryis = coords
                            pol.style.polystyle.color = get_kml_color_by_prb(row['prb'])
                            pol.style.polystyle.outline = 1
                            pol.style.linestyle.color = simplekml.Color.black
                            pol.style.linestyle.width = 1

                        st.download_button(
                            label=f"Unduh KML untuk Klaster: {clean_filename(str(cluster))}",
                            data=kml.kml(),
                            file_name=f"{clean_filename(str(cluster))}_bts_coverage.kml",
                            mime="application/vnd.google-earth.kml+xml",
                            key=f"kml_{cluster}"
                        )
                
                st.markdown("---")

                st.button(
                    "Tampilkan/Sembunyikan Visualisasi Peta 🗺️",
                    on_click=toggle_visualization
                )
                
                # --- VISUALISASI PETA INTERAKTIF ---
                if st.session_state.show_visual and not df_proc.empty:
                    st.header("️Visualisasi Peta Interaktif")
                    # (Sisa kode visualisasi tidak ada perubahan)
                    unique_clusters_map = sorted(df_proc['sa cluster'].dropna().unique())
                    options = ['Tampilkan Semua'] + unique_clusters_map
                    selected_cluster = st.selectbox(
                        "Pilih Daerah (Cluster) untuk ditampilkan di peta:",
                        options=options,
                        key="map_select"
                    )

                    if selected_cluster == 'Tampilkan Semua':
                        df_to_display = df_proc
                    else:
                        df_to_display = df_proc[df_proc['sa cluster'] == selected_cluster]

                    if not df_to_display.empty:
                        map_center = [df_to_display['latitude'].mean(), df_to_display['longitude'].mean()]
                        m = folium.Map(location=map_center, zoom_start=12, tiles="cartodbdark_matter")

                        for _, row in df_to_display.iterrows():
                            lon, lat, azimuth, beam_width = row['longitude'], row['latitude'], row['azimuth'], row['beam']
                            start_angle = azimuth - (beam_width / 2)
                            coords_folium = [(lat, lon)] # Folium: (lat, lon)
                            step = beam_width / 20
                            for i in range(20 + 1):
                                angle = start_angle + i * step
                                dest_lon, dest_lat = get_destination_point(lon, lat, angle, 0.5)
                                coords_folium.append((dest_lat, dest_lon))
                            coords_folium.append((lat, lon))
                            
                            popup_html = f"""
                            <b>Site Sector:</b> {row.get('site_sectorid', 'N/A')}<br>
                            <b>Site Name:</b> {row.get('sitename', 'N/A')}<br>
                            <b>Site ID:</b> {row.get('site_id', 'N/A')}<br>
                            <b>Enobid:</b> {row.get('enbid', 'N/A')}<br>
                            <b>Longitude:</b> {row.get('longitude', 'N/A')}<br>
                            <b>Latitude:</b> {row.get('latitude', 'N/A')}<br>
                            <b>Azimuth:</b> {row.get('azimuth', 'N/A')}°<br>
                            <b>EUT:</b> {row.get('eut', 'N/A')}<br>
                            <b>CQI:</b> {row.get('cqi', 'N/A')}<br>
                            <b>TLP Partner:</b> {row.get('tlp', 'N/A')}<br>
                            <b>FLP Partner:</b> {row.get('flp', 'N/A')}<br>
                            <b>Transmission:</b> {row.get('transport_fo_mw', 'N/A')}<br>
                            <b>Revenue IOH:</b> {row.get('prepaid_revenue_nett', 'N/A')}<br>
                            <b>VLR IOH:</b> {row.get('vlr_subs_3id', 'N/A')}<br>
                            <b>Battery:</b> {row.get('capacity_bank', 'N/A')}<br>
                            <b>Height:</b> {row.get('ant_height', 'N/A')}<br>
                            <b>Area:</b> {row.get('area', 'N/A')}<br>
                            <b>Config Bandwith:</b> {row.get('config_bandwidth', 'N/A')}<br>
                            <b>Beam Width:</b> {row.get('beam', 'N/A')}°<br>
                            <b>PRB Usage:</b> {row.get('prb', 'N/A')}%<br>
                            <b>Cluster:</b> {row.get('sa cluster', 'N/A')}
                            """
                            popup = folium.Popup(popup_html, max_width=300)

                            folium.Polygon(
                                locations=coords_folium,
                                color=get_folium_color_by_prb(row['prb']),
                                weight=2,
                                fill=True,
                                fill_color=get_folium_color_by_prb(row['prb']),
                                fill_opacity=0.5,
                                popup=popup,
                                tooltip=f"Site: {row['site_id']}"
                            ).add_to(m)

                        st_folium(m, width=None, height=500, use_container_width=True)
                    else:
                        st.warning("Tidak ada data untuk ditampilkan pada pilihan ini.")

    except Exception as e:
        st.error(f"Terjadi kesalahan saat memproses file: {e}")
else:
    st.info("Silakan unggah kedua file CSV di sidebar untuk memulai.")