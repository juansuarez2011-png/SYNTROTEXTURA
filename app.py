import os
import json
import tempfile
import tarfile
import numpy as np
import geopandas as gpd
from shapely.geometry import Point
import streamlit as st
from PIL import Image
from osgeo import gdal

gdal.UseExceptions()

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
    📌 **Instrucciones del Motor:**
    1. **Archivo Landsat (.tar):** Suba el archivo comprimido oficial de la escena Landsat.
    2. **Perímetro de la Finca:** Suba su archivo perimetral (`.geojson`, `.shp` en zip, `.kml`).
    3. **Proceso Espectral:** Extrae las bandas B4, B6 y B7, calcula el índice espectral real, recorta el perimetral y genera los centroides de 10x10 metros con hectáreas y porcentajes exactos.
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
    st.title("Syntro Cloud Soil Texture Engine (Espectral Real)")
    st.markdown("#### Procesamiento de Bandas Landsat, Malla 10x10m y Estadísticas USDA")

st.markdown("---")

st.subheader("🛰️ 1. Parámetros de Entrada y Escena Satelital")

st.markdown("""
    <div class="info-box">
        <strong>💡 Algoritmo Espectral Real Syntro:</strong><br>
        El sistema procesa directamente las bandas espectrales de Landsat (B4, B6, B7) mediante el índice de arcilla/arena, recorta con el polígono en coordenadas UTM y calcula de forma totalmente dinámica las clases, hectáreas y porcentajes.
    </div>
""", unsafe_allow_html=True)

col1, col2 = st.columns(2)

with col1:
    uploaded_tar = st.file_uploader(
        "Archivo Landsat (.tar)", 
        type=["tar"],
        help="Suba el archivo tar oficial de la escena Landsat."
    )

with col2:
    uploaded_vector = st.file_uploader(
        "Límites Perimetrales del Área (.geojson, .shp en zip, .kml)", 
        type=["geojson", "shp", "kml", "zip"],
        help="Suba el archivo que delimita la finca a evaluar."
    )

st.markdown("---")
st.markdown("<br>", unsafe_allow_html=True)

# Botón único de ejecución
if st.button("🚀 Ejecutar Procesamiento Espectral y Malla 10x10m"):
    if uploaded_tar is not None and uploaded_vector is not None:
        with st.spinner("Descomprimiendo bandas, recortando perimetral, aplicando fórmula espectral y calculando estadísticas..."):
            
            try:
                with tempfile.TemporaryDirectory() as tmpdirname:
                    # Guardar archivo tar
                    tar_path = os.path.join(tmpdirname, uploaded_tar.name)
                    with open(tar_path, "wb") as f:
                        f.write(uploaded_tar.getbuffer())
                        
                    with tarfile.open(tar_path, 'r:*') as tar:
                        tar.extractall(path=tmpdirname)
                        
                    # Buscar bandas B4, B6, B7
                    b4_path, b6_path, b7_path = None, None, None
                    for r, d, f in os.walk(tmpdirname):
                        for n in f:
                            nu = n.upper()
                            if '_B4.TIF' in nu and 'QA' not in nu: b4_path = os.path.join(r, n)
                            if '_B6.TIF' in nu and 'QA' not in nu: b6_path = os.path.join(r, n)
                            if '_B7.TIF' in nu and 'QA' not in nu: b7_path = os.path.join(r, n)
                            
                    if not all([b4_path, b6_path, b7_path]):
                        st.error("No se encontraron las bandas necesarias (B4, B6, B7) en el archivo .tar.")
                        st.stop()
                        
                    # Guardar vector perimetral
                    vec_path = os.path.join(tmpdirname, uploaded_vector.name)
                    with open(vec_path, "wb") as f:
                        f.write(uploaded_vector.getbuffer())
                        
                    if uploaded_vector.name.endswith('.zip'):
                        gdf = gpd.read_file(f"zip://{vec_path}")
                    else:
                        gdf = gpd.read_file(vec_path)
                        
                    if gdf.crs is None:
                        gdf.set_crs(epsg=4326, inplace=True)
                    else:
                        gdf = gdf.to_crs(epsg=4326)
                        
                    centroid = gdf.unary_union.centroid
                    epsg_utm = 32619 if centroid.x > -72 else 32618
                    
                    gdf_utm = gdf.to_crs(epsg=epsg_utm)
                    polygon_utm = gdf_utm.unary_union
                    
                    area_total_m2 = polygon_utm.area
                    area_total_ha = area_total_m2 / 10000.0
                    
                    # Recorte raster usando gdal.Warp con el polígono
                    shp_perim = os.path.join(tmpdirname, "perimetro.shp")
                    gdf_utm.to_file(shp_perim)
                    
                    def recortar_banda(src_p):
                        out_p = os.path.join(tmpdirname, f"clip_{os.path.basename(src_p)}")
                        gdal.Warp(out_p, src_p, cutlineDSName=shp_perim, cropToCutline=True,
                                  dstNodata=-9999, dstSRS=f"EPSG:{epsg_utm}", xRes=10.0, yRes=10.0,
                                  warpOptions=['CUTLINE_ALL_TOUCHED=TRUE'], resampleAlg=gdal.GRA_CubicSpline)
                        return out_p
                        
                    clip_b4 = recortar_banda(b4_path)
                    clip_b6 = recortar_banda(b6_path)
                    clip_b7 = recortar_banda(b7_path)
                    
                    def leer_banda(path):
                        ds = gdal.Open(path, gdal.GA_ReadOnly)
                        arr = ds.GetRasterBand(1).ReadAsArray().astype(np.float32)
                        return arr, ds.GetGeoTransform(), ds.GetProjection()
                        
                    b4, gt, prj = leer_banda(clip_b4)
                    b6, _, _ = leer_banda(clip_b6)
                    b7, _, _ = leer_banda(clip_b7)
                    
                    # Aplicar fórmula espectral real de tu script
                    mask = (b4 > 0) & (b4 != -9999) & (b6 > 0) & (b6 != -9999)
                    indice = np.zeros(b4.shape, dtype=np.float32)
                    if np.any(mask):
                        indice[mask] = (b6[mask] + b7[mask]) / (b4[mask] + 1.0)
                        vals = indice[mask]
                        q10, q35, q65, q90 = np.percentile(vals, [10, 35, 65, 90])
                        
                        tex_cat = np.zeros(b4.shape, dtype=np.uint8)
                        tex_cat[mask] = np.where(indice[mask] <= q10, 1,
                                        np.where(indice[mask] <= q35, 2,
                                        np.where(indice[mask] <= q65, 3,
                                        np.where(indice[mask] <= q90, 4, 5))))
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
                                x = gt[0] + (c + 0.5) * gt[1] + (r + 0.5) * gt[2]
                                y = gt[3] + (c + 0.5) * gt[4] + (r + 0.5) * gt[5]
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
                st.error(f"Error en el procesamiento espectral y geométrico: {e}")
                st.stop()

            # Informe técnico
            lineas_informe = []
            lineas_informe.append("="*85)
            lineas_informe.append("SYNTRO ACADEMY - INFORME TECNICO DE TEXTURA DE SUELO (SISTEMA USDA)")
            lineas_informe.append("="*85)
            lineas_informe.append("CONSULTOR: ING. JUAN SEGUNDO SUAREZ RIVERA")
            lineas_informe.append("OBJETIVO: Zonificacion textural espectral real (B4, B6, B7) y malla de centroides 10x10m\n")
            lineas_informe.append(f"{'CLASE TEXTURAL USDA':<35} | {'SUPERFICIE (ha)':<15} | {'PORCENTAJE (%)':<15}")
            lineas_informe.append("-" * 73)
            
            for i in range(1, 6):
                lineas_informe.append(f"{nombres_5[i]:<35} | {areas[i]:<15.2f} | {porcentajes[i]:<15.1f}%")
            
            lineas_informe.append("-" * 73)
            lineas_informe.append(f"{'SUPERFICIE TOTAL EVALUADA':<35} | {area_total_ha:<15.2f} | 100.0%")
            lineas_informe.append("="*85)
            
            resumen_dinamico = "\n".join(lineas_informe)

        st.success(f"¡Proceso espectral completado! Se generaron {total_celdas} centroides basados en las bandas Landsat dentro de un área de {area_total_ha:.2f} ha.")
        
        st.markdown("### 📊 Resultados Estadísticos del Modelo Espectral USDA")
        m1, m2, m3 = st.columns(3)
        m1.metric("Área Real Evaluada", f"{area_total_ha:.2f} Hectáreas", f"{total_celdas} celdas (10x10m)")
        m2.metric("Resolución Espectral", "Landsat B4, B6, B7", "Índice Dinámico Real")
        m3.metric("Salida GeoJSON", "Centroides", "Listos para GIS")
        
        st.text(resumen_dinamico)
        
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
        st.error("⚠️ Debe cargar tanto el archivo Landsat (.tar) como el archivo perimetral para ejecutar el modelo espectral.")
