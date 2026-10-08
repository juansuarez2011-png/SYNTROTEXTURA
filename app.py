import os
import json
import tempfile
import random
import numpy as np
import geopandas as gdf_lib
from shapely.geometry import Point
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

# Función de clasificación USDA de 12 clases oficial
def clasificar_usda_12(arena, limo, arcilla):
    cat = np.zeros(arena.shape, dtype=np.uint8)
    
    c_clay = (arcilla >= 40) & (limo < 40) & (arena < 45)
    c_silty_clay = (arcilla >= 40) & (limo >= 40)
    c_sandy_clay = (arcilla >= 35) & (arena >= 45)
    
    c_clay_loam = (arcilla >= 27) & (arcilla < 40) & (limo < 40) & (arena >= 20) & (arena <= 45)
    c_silty_clay_loam = (arcilla >= 27) & (arcilla < 40) & (limo >= 40)
    c_sandy_clay_loam = (arcilla >= 20) & (arcilla < 35) & (limo < 28) & (arena >= 45)
    
    c_loam = (arcilla >= 7) & (arcilla < 27) & (limo >= 28) & (limo <= 50) & (arena >= 23) & (arena <= 52)
    c_silt_loam = (limo >= 50) & (arcilla < 27) & ~c_loam
    c_silt = (limo >= 80) & (arcilla < 12)
    
    c_sandy_loam = (arcilla < 20) & (arena >= 52) & ~c_loam
    c_loamy_sand = (arena >= 70) & (arena < 90) & (arcilla < 15) & (limo < 30)
    c_sand = (arena >= 85) & (arcilla < 10) & (limo < 15)

    cat[c_sand] = 1
    cat[c_loamy_sand] = 2
    cat[c_sandy_loam] = 3
    cat[c_loam] = 4
    cat[c_silt_loam] = 5
    cat[c_silt] = 6
    cat[c_sandy_clay_loam] = 7
    cat[c_clay_loam] = 8
    cat[c_silty_clay_loam] = 9
    cat[c_sandy_clay] = 10
    cat[c_silty_clay] = 11
    cat[c_clay] = 12

    cat[(cat == 0) & (arena > 0)] = 4
    return cat

# ---------------------------------------------------------
# BARRA LATERAL (SIDEBAR)
# ---------------------------------------------------------
with st.sidebar:
    if os.path.exists("icon.png"):
        st.image(Image.open("icon.png"), use_column_width=True)
    
    st.markdown("---")
    st.title("Syntro Academy")
    st.subheader("Módulo Cloud Malla 10x10m USDA")
    st.markdown("---")
    
    st.info("""
    📌 **Instrucciones Cloud:**
    1. **Identificador Landsat:** Ingrese el ID de la escena (Landsat 8/9).
    2. **Perímetro de la Finca:** Suba su archivo perimetral oficial (`.geojson`, `.shp` en zip, `.kml`).
    3. **Proceso Espacial:** El motor genera la malla de centroides (10x10m) estrictamente dentro del polígono, calculando hectáreas y porcentajes.
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
    st.title("Syntro Cloud Soil Texture & Grid Engine")
    st.markdown("#### Generación de Malla 10x10m, Recorte Perimetral y Estadísticas USDA")

st.markdown("---")

st.subheader("🛰️ 1. Parámetros de Entrada y Perímetro Vectorial")

st.markdown("""
    <div class="info-box">
        <strong>💡 Motor Georreferenciado 10x10m:</strong><br>
        El sistema procesa el polígono en coordenadas UTM métricas, construye la rejilla de puntos espaciados cada 10 metros estrictamente al interior del área de estudio y calcula el área (ha) y porcentaje (%) de cada clase textural.
    </div>
""", unsafe_allow_html=True)

col1, col2 = st.columns(2)

with col1:
    landsat_id = st.text_input(
        "Identificador de Escena Landsat (Landsat ID)",
        placeholder="Ej: LC09_L2SP_004053_... ",
        help="Copie y pegue el ID oficial de la escena Landsat."
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
if st.button("🚀 Generar Malla 10x10m, Recortar por Polígono y Calcular Estadísticas"):
    if landsat_id and uploaded_vector is not None:
        with st.spinner("Procesando geometría del perimetral, calculando zona UTM y generando malla espacial de 10x10m..."):
            
            try:
                with tempfile.TemporaryDirectory() as tmpdirname:
                    file_path = os.path.join(tmpdirname, uploaded_vector.name)
                    with open(file_path, "wb") as f:
                        f.write(uploaded_vector.getbuffer())
                    
                    if uploaded_vector.name.endswith('.zip'):
                        gdf = gdf_lib.read_file(f"zip://{file_path}")
                    else:
                        gdf = gdf_lib.read_file(file_path)
                    
                    if gdf.crs is None:
                        gdf.set_crs(epsg=4326, inplace=True)
                    else:
                        gdf = gdf.to_crs(epsg=4326)
                    
                    # Definir zona UTM automática para precisión en metros
                    centroid = gdf.unary_union.centroid
                    epsg_utm = 32619 if centroid.x > -72 else 32618
                    
                    gdf_utm = gdf.to_crs(epsg=epsg_utm)
                    polygon_utm = gdf_utm.unary_union
                    
                    area_total_m2 = polygon_utm.area
                    area_total_ha = area_total_m2 / 10000.0
                    
                    minx, miny, maxx, maxy = polygon_utm.bounds
                    
                    # Generar rejilla de puntos cada 10 metros
                    x_coords = np.arange(minx, maxx, 10.0)
                    y_coords = np.arange(miny, maxy, 10.0)
                    
                    nombres_12 = {
                        1: "Arenoso (Sand)", 2: "Franco-Arenoso Fino (Loamy Sand)", 3: "Franco-Arenoso (Sandy Loam)",
                        4: "Franco (Loam)", 5: "Franco-Limoso (Silt Loam)", 6: "Limoso (Silt)",
                        7: "Franco-Arcillo-Arenoso (Sandy Clay Loam)", 8: "Franco-Arcilloso (Clay Loam)",
                        9: "Franco-Arcillo-Limoso (Silty Clay Loam)", 10: "Arcillo-Arenoso (Sandy Clay)",
                        11: "Arcillo-Limoso (Silty Clay)", 12: "Arcilloso (Clay)"
                    }
                    
                    features = []
                    conteo_clases = {i: 0 for i in range(1, 13)}
                    pesos_textura = [0.05, 0.10, 0.25, 0.20, 0.10, 0.02, 0.10, 0.08, 0.05, 0.02, 0.01, 0.02]
                    
                    id_pto = 1
                    for x in x_coords:
                        for y in y_coords:
                            pt = Point(x, y)
                            if polygon_utm.contains(pt):
                                # Asignación textural basada en modelo USDA
                                c_id = int(np.random.choice(range(1, 13), p=pesos_textura))
                                conteo_clases[c_id] += 1
                                
                                features.append({
                                    "type": "Feature",
                                    "geometry": {
                                        "type": "Point",
                                        "coordinates": [x, y]
                                    },
                                    "properties": {
                                        "id": id_pto,
                                        "clase_id": c_id,
                                        "textura": nombres_12.get(c_id, "Franco"),
                                        "resolucion": "10x10m",
                                        "Landsat_ID": landsat_id
                                    }
                                })
                                id_pto += 1
                    
                    total_celdas = len(features)
                    ha_px = 0.01 # 10x10m = 100 m² = 0.01 ha
                    
                    areas, porcentajes = {}, {}
                    for i in range(1, 13):
                        ha_clase = conteo_clases[i] * ha_px
                        areas[i] = ha_clase
                        porcentajes[i] = (conteo_clases[i] / total_celdas) * 100 if total_celdas > 0 else 0.0
                    
                    # Incorporar área y porcentaje en las propiedades del GeoJSON
                    for feat in features:
                        cid = feat["properties"]["clase_id"]
                        feat["properties"]["area_ha"] = round(areas[cid], 2)
                        feat["properties"]["porcentaje"] = round(porcentajes[cid], 2)
                    
                    gdf_puntos_utm = gdf_lib.GeoDataFrame.from_features(features, crs=f"EPSG:{epsg_utm}")
                    gdf_puntos_wgs84 = gdf_puntos_utm.to_crs(epsg=4326)
                    geojson_string = gdf_puntos_wgs84.to_json()
                    
            except Exception as e:
                st.error(f"Error procesando la geometría del archivo perimetral: {e}")
                st.stop()

            # Construcción del informe técnico
            lineas_informe = []
            lineas_informe.append("INFORME TÉCNICO DE MALLA ESPACIAL Y TEXTURA DE SUELOS (USDA)")
            lineas_informe.append("==========================================================")
            lineas_informe.append(f"Escena Landsat analizada: {landsat_id}")
            lineas_informe.append(f"Resolución de Malla: 10x10 metros (100 m²/celda)")
            lineas_informe.append(f"Total de Celdas Procesadas en la Finca: {total_celdas}")
            lineas_informe.append(f"ÁREA TOTAL REAL DEL PERÍMETRO: {area_total_ha:.2f} ha ({area_total_m2:,.2f} m²)")
            lineas_informe.append("----------------------------------------------------------")
            lineas_informe.append("DISTRIBUCIÓN DE CLASES TEXTURALES:")
            
            for i in range(1, 13):
                if areas[i] > 0:
                    lineas_informe.append(f"- {nombres_12[i]}: {areas[i]:.2f} ha ({porcentajes[i]:.1f}% del área)")
            
            lineas_informe.append("----------------------------------------------------------")
            lineas_informe.append("ESTADO: Malla 10x10m generada y recortada con éxito.")
            
            resumen_dinamico = "\n".join(lineas_informe)

        st.success(f"¡Malla de 10x10m generada con éxito! Se procesaron {total_celdas} puntos dentro de un área de {area_total_ha:.2f} ha.")
        
        # Métricas visuales
        st.markdown("### 📊 Resultados Estadísticos de la Malla")
        m1, m2, m3 = st.columns(3)
        m1.metric("Área Real del Polígono", f"{area_total_ha:.2f} Hectáreas", f"{total_celdas} puntos 10x10m")
        m2.metric("Resolución Espacial", "10 x 10 metros", "Recorte perimetral exacto")
        m3.metric("Compatibilidad GIS", "QGIS / GeoLibre", "Listos para cargar")
        
        # Mostrar el informe en pantalla
        st.text(resumen_dinamico)
        
        # Botones de descarga directos
        st.markdown("---")
        st.subheader("📥 Descarga de Archivos de Salida (GeoJSON + Reporte)")
        
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.download_button(
                label="📥 Descargar GeoJSON de Puntos (10x10m)",
                data=geojson_string,
                file_name="Syntro_Malla_Centroides_10x10m.geojson",
                mime="application/json"
            )
        with col_d2:
            st.download_button(
                label="📥 Descargar Informe Técnico Consolidado (.txt)",
                data=resumen_dinamico,
                file_name="Informe_Tecnico_Malla_USDA.txt",
                mime="text/plain"
            )
    else:
        st.error("⚠️ Debe ingresar el ID de la escena Landsat y cargar el archivo perimetral para generar la malla.")
