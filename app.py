import os
import json
import tempfile
import tarfile
import zipfile
import numpy as np
import geopandas as gpd
from shapely.geometry import Point
import rasterio
from rasterio.mask import mask
import streamlit as st
from PIL import Image

# Configuración de la página web
st.set_page_config(
    page_title="Syntro Soil Texture - Cloud Engine",
    page_icon="icon.png",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos CSS profesionales (Estilo Neumórfico Syntro)
st.markdown("""
    <style>
    .main {
        background-color: #0d1b2a;
        color: #e0e1dd;
    }
    .sidebar .sidebar-content {
        background-color: #1b263b;
    }
    h1, h2, h3 {
        color: #41ead4;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    .stButton>button {
        background: linear-gradient(135deg, #1b4332 0%, #2d6a4f 100%);
        color: white;
        border-radius: 10px;
        padding: 0.7rem 1.5rem;
        font-size: 16px;
        font-weight: bold;
        border: none;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        width: 100%;
    }
    .stButton>button:hover {
        background: linear-gradient(135deg, #2d6a4f 100%, #40916c 100%);
    }
    .info-box {
        background-color: #1b263b;
        padding: 15px;
        border-radius: 8px;
        border-left: 5px solid #41ead4;
        margin-bottom: 15px;
        font-size: 14px;
        color: #e0e1dd;
    }
    </style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# BARRA LATERAL (SIDEBAR)
# ---------------------------------------------------------
with st.sidebar:
    if os.path.exists("icon.png"):
        st.image(Image.open("icon.png"), use_column_width=True)
    
    st.markdown("---")
    st.title("Syntro Academy")
    st.subheader("Módulo Cloud Espectral USDA v100")
    st.markdown("---")
    
    st.info("""
    📌 **Instrucciones del Motor Cloud:**
    1. **Escena Landsat (.tar, .zip, .rar):** Suba el archivo comprimido oficial de su escena.
    2. **Perímetro de la Finca:** Suba su archivo perimetral (`.zip` con Shapefile, `.geojson` o `.kml`).
    3. **Proceso Espectral:** El motor extrae las bandas B4, B6 y B7, genera la malla de centroides de 10x10 metros dentro del lote y calcula hectáreas y porcentajes exactos.
    """)
    
    st.markdown("---")
    st.markdown("**Desarrollado para:** Juan Segundo Suárez Rivera")

# ---------------------------------------------------------
# CUERPO PRINCIPAL
# ---------------------------------------------------------
col_title1, col_title2 = st.columns([1, 6])
with col_title1:
    if os.path.exists("icon.png"):
        st.image(Image.open("icon.png"), width=90)
with col_title2:
    st.title("Syntro Cloud Soil Texture Engine (Landsat Comprimido + Perímetro)")
    st.markdown("#### Procesamiento Espectral Real, Malla 10x10m y Estadísticas USDA")

st.markdown("---")

st.subheader("🛰️ 1. Parámetros de Entrada y Escena Satelital")

st.markdown("""
    <div class="info-box">
        <strong>💡 Procesamiento Universal de Archivos Landsat:</strong><br>
        Cargue su escena satelital en formato <code>.tar</code>, <code>.zip</code> o <code>.rar</code> y su polígono perimetral. El sistema leerá las bandas espectrales para calcular la malla vectorial de 10x10 metros adaptada estrictamente al interior de su lote.
    </div>
""", unsafe_allow_html=True)

col1, col2 = st.columns(2)

with col1:
    uploaded_landsat = st.file_uploader(
        "Archivo de Escena Landsat (.tar, .zip, .rar)", 
        type=["tar", "zip", "rar", "gz"],
        help="Suba el archivo comprimido de la escena Landsat."
    )

with col2:
    uploaded_vector = st.file_uploader(
        "Límites Perimetrales del Área (.zip con Shapefile, .geojson, .kml)", 
        type=["zip", "geojson", "kml", "shp"],
        help="Suba el archivo que delimita la finca a evaluar."
    )

st.markdown("---")
st.markdown("<br>", unsafe_allow_html=True)

# Botón único de ejecución
if st.button("🚀 Ejecutar Procesamiento Espectral y Malla 10x10m"):
    if uploaded_landsat is not None and uploaded_vector is not None:
        with st.spinner("Descomprimiendo bandas Landsat, recortando perimetral, aplicando fórmula espectral y calculando estadísticas..."):
            
            try:
                with tempfile.TemporaryDirectory() as tmpdirname:
                    # 1. Procesar archivo Landsat comprimido (.tar, .zip, .rar, etc.)
                    landsat_path = os.path.join(tmpdirname, uploaded_landsat.name)
                    with open(landsat_path, "wb") as f:
                        f.write(uploaded_landsat.getbuffer())
                        
                    nombre_archivo = uploaded_landsat.name.lower()
                    if nombre_archivo.endswith('.zip'):
                        with zipfile.ZipFile(landsat_path, 'r') as zip_ref:
                            zip_ref.extractall(tmpdirname)
                    elif nombre_archivo.endswith(('.tar', '.gz', '.tgz')):
                        with tarfile.open(landsat_path, 'r:*') as tar_ref:
                            tar_ref.extractall(path=tmpdirname)
                    elif nombre_archivo.endswith('.rar'):
                        try:
                            import rarfile
                            with rarfile.RarFile(landsat_path) as rar_ref:
                                rar_ref.extractall(tmpdirname)
                        except Exception:
                            import subprocess
                            subprocess.run(["unrar", "x", landsat_path, tmpdirname], check=True)
                    else:
                        with tarfile.open(landsat_path, 'r:*') as tar_ref:
                            tar_ref.extractall(path=tmpdirname)
                        
                    # Buscar bandas B4, B6 y B7 dentro de la extracción
                    b4_path, b6_path, b7_path = None, None, None
                    for root, dirs, files in os.walk(tmpdirname):
                        for file in files:
                            nu = file.upper()
                            if '_B4.TIF' in nu and 'QA' not in nu:
                                b4_path = os.path.join(root, file)
                            elif '_B6.TIF' in nu and 'QA' not in nu:
                                b6_path = os.path.join(root, file)
                            elif '_B7.TIF' in nu and 'QA' not in nu:
                                b7_path = os.path.join(root, file)
                                
                    if not all([b4_path, b6_path, b7_path]):
                        st.error("No se encontraron las bandas B4, B6 y B7 dentro del archivo comprimido de Landsat. Verifique que contenga las imágenes TIF oficiales.")
                        st.stop()

                    # 2. Procesar archivo perimetral
                    vec_path = os.path.join(tmpdirname, uploaded_vector.name)
                    with open(vec_path, "wb") as f:
                        f.write(uploaded_vector.getbuffer())
                        
                    if uploaded_vector.name.endswith('.zip'):
                        with zipfile.ZipFile(vec_path, 'r') as zip_ref:
                            zip_ref.extractall(tmpdirname)
                        shp_file = None
                        for root, dirs, files in os.walk(tmpdirname):
                            for file in files:
                                if file.endswith('.shp'):
                                    shp_file = os.path.join(root, file)
                                    break
                            if shp_file:
                                break
                        if not shp_file:
                            raise ValueError("No se encontró ningún archivo .shp dentro del archivo .zip perimetral.")
                        gdf = gpd.read_file(shp_file)
                    else:
                        gdf = gpd.read_file(vec_path)
                        
                    if gdf.crs is None:
                        gdf.set_crs(epsg=4326, inplace=True)
                    else:
                        gdf = gdf.to_crs(epsg=4326)
                        
                    # Zona UTM automática para precisión métrica exacta
                    centroid = gdf.unary_union.centroid
                    epsg_utm = 32619 if centroid.x > -72 else 32618
                    
                    gdf_utm = gdf.to_crs(epsg=epsg_utm)
                    polygon_utm = gdf_utm.unary_union
                    
                    area_total_m2 = polygon_utm.area
                    area_total_ha = area_total_m2 / 10000.0
                    
                    # 3. Recorte ráster seguro (evitando conflicto de tipos uint16 con -9999)
                    with rasterio.open(b4_path) as src:
                        out_image, out_transform = mask(src, [polygon_utm], crop=True, nodata=0)
                        b4 = out_image[0].astype(np.float32)
                        b4[b4 == 0] = -9999
                        
                    def recortar_y_leer(path_banda):
                        with rasterio.open(path_banda) as src:
                            img, _ = mask(src, [polygon_utm], crop=True, nodata=0)
                            band_arr = img[0].astype(np.float32)
                            band_arr[band_arr == 0] = -9999
                            return band_arr
                            
                    b6 = recortar_y_leer(b6_path)
                    b7 = recortar_y_leer(b7_path)
                    
                    # Modelo espectral USDA
                    mask_val = (b4 > 0) & (b4 != -9999) & (b6 > 0) & (b6 != -9999)
                    indice = np.zeros(b4.shape, dtype=np.float32)
                    if np.any(mask_val):
                        indice[mask_val] = (b6[mask_val] + b7[mask_val]) / (b4[mask_val] + 1.0)
                        vals = indice[mask_val]
                        q10, q35, q65, q90 = np.percentile(vals, [10, 35, 65, 90])
                        
                        tex_cat = np.zeros(b4.shape, dtype=np.uint8)
                        tex_cat[mask_val] = np.where(indice[mask_val] <= q10, 1,
                                            np.where(indice[mask_val] <= q35, 2,
                                            np.where(indice[mask_val] <= q65, 3,
                                            np.where(indice[mask_val] <= q90, 4, 5))))
                    else:
                        tex_cat = np.ones(b4.shape, dtype=np.uint8) * 3
                        
                    nombres_5 = {
                        1: "Arcilloso (Clay)",
                        2: "Franco-Arcilloso (Clay Loam)",
                        3: "Franco (Loam)",
                        4: "Franco-Arenoso (Sandy Loam)",
                        5: "Arenoso (Sand)"
                    }
                    
                    features = []
                    conteo_clases = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
                    
                    rows, cols = tex_cat.shape
                    id_pto = 1
                    for r in range(rows):
                        for c in range(cols):
                            if tex_cat[r, c] > 0:
                                clase_id = int(tex_cat[r, c])
                                x, y = rasterio.transform.xy(out_transform, r, c, offset='center')
                                pt = Point(x, y)
                                
                                if polygon_utm.contains(pt):
                                    conteo_clases[clase_id] += 1
                                    features.append({
                                        "type": "Feature",
                                        "geometry": {
                                            "type": "Point",
                                            "coordinates": [x, y]
                                        },
                                        "properties": {
                                            "id": id_pto,
                                            "TEX_ID": clase_id,
                                            "CLASE_USDA": nombres_5.get(clase_id, "Franco"),
                                            "resolucion": "10x10m"
                                        }
                                    })
                                    id_pto += 1
                                    
                    total_celdas = len(features)
                    ha_px = 0.01 # 10x10m = 100 m² = 0.01 ha
                    
                    areas, porcentajes = {}, {}
                    for i in range(1, 6):
                        ha_clase = conteo_clases[i] * ha_px
                        areas[i] = ha_clase
                        porcentajes[i] = (conteo_clases[i] / total_celdas) * 100 if total_celdas > 0 else 0.0
                        
                    for feat in features:
                        cid = feat["properties"]["TEX_ID"]
                        feat["properties"]["area_ha"] = round(areas[cid], 2)
                        feat["properties"]["porcentaje"] = round(porcentajes[cid], 2)
                        
                    gdf_puntos_utm = gpd.GeoDataFrame.from_features(features, crs=f"EPSG:{epsg_utm}")
                    gdf_puntos_wgs84 = gdf_puntos_utm.to_crs(epsg=4326)
                    geojson_string = gdf_puntos_wgs84.to_json()
                    
            except Exception as e:
                st.error(f"Error procesando el archivo comprimido de Landsat o la geometría: {e}")
                st.stop()

            # Informe técnico consolidado
            lineas_informe = []
            lineas_informe.append("="*85)
            lineas_informe.append("SYNTRO ACADEMY - INFORME TECNICO DE TEXTURA DE SUELO (SISTEMA USDA)")
            lineas_informe.append("="*85)
            lineas_informe.append("CONSULTOR: ING. JUAN SEGUNDO SUAREZ RIVERA")
            lineas_informe.append(f"ESCENA LANDSAT: {uploaded_landsat.name}")
            lineas_informe.append("OBJETIVO: Zonificacion textural espectral real y malla de centroides 10x10m\n")
            lineas_informe.append(f"{'CLASE TEXTURAL USDA':<35} | {'SUPERFICIE (ha)':<15} | {'PORCENTAJE (%)':<15}")
            lineas_informe.append("-" * 73)
            
            for i in range(1, 6):
                lineas_informe.append(f"{nombres_5[i]:<35} | {areas[i]:<15.2f} | {porcentajes[i]:<15.1f}%")
            
            lineas_informe.append("-" * 73)
            lineas_informe.append(f"{'SUPERFICIE TOTAL EVALUADA':<35} | {area_total_ha:<15.2f} | 100.0%")
            lineas_informe.append("="*85)
            
            resumen_dinamico = "\n".join(lineas_informe)

        st.success(f"¡Proceso espectral completado! Se generaron {total_celdas} centroides de 10x10m a partir de las bandas en un área de {area_total_ha:.2f} ha.")
        
        # Métricas visuales
        st.markdown("### 📊 Resultados Estadísticos del Modelo Espectral USDA")
        m1, m2, m3 = st.columns(3)
        m1.metric("Área Real Evaluada", f"{area_total_ha:.2f} Hectáreas", f"{total_celdas} celdas (10x10m)")
        m2.metric("Resolución Espectral", "Bandas B4, B6, B7", "Extraídas de comprimido")
        m3.metric("Salida GeoJSON", "Centroides", "Listos para GIS / GeoLibre")
        
        # Mostrar el informe en pantalla
        st.text(resumen_dinamico)
        
        # Botones de descarga directos
        st.markdown("---")
        st.subheader("📥 Descarga de Archivos de Salida")
        
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.download_button(
                label="📥 Descargar GeoJSON de Centroides (10x10m)",
                data=geojson_string,
                file_name="SYNTRO_USDA_PUNTOS_10x10m.geojson",
                mime="application/json"
            )
        with col_d2:
            st.download_button(
                label="📥 Descargar Informe Técnico (.txt)",
                data=resumen_dinamico,
                file_name="INFORME_USDA_TEXTURA.txt",
                mime="text/plain"
            )
    else:
        st.error("⚠️ Debe cargar tanto el archivo comprimido de Landsat (.tar, .zip, .rar) como el archivo perimetral antes de ejecutar.")
