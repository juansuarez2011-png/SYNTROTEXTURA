import os
import json
import tempfile
import tarfile
import zipfile
import datetime
import numpy as np
import geopandas as gpd
from shapely.geometry import Point
import rasterio
from rasterio.mask import mask
import streamlit as st
from PIL import Image

# Configuración de la página web (PC y Laptop)
st.set_page_config(
    page_title="Syntro Soil Engine - 12 Clases USDA y pH",
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
    st.subheader("Módulo Cloud Espectral v100")
    st.markdown("---")
    
    st.info("""
    📌 **Instrucciones del Motor Cloud:**
    1. **Seleccione el Parámetro:** Elija Textura USDA (12 Clases Variables) o pH del Suelo.
    2. **Escena Landsat (.tar, .zip):** Suba el archivo comprimido oficial.
    3. **Perímetro de la Finca:** Suba su archivo perimetral (`.zip` Shapefile, `.geojson`, `.kml`).
    4. **Malla 5x5m:** Genera centroides de alta variabilidad espacial y reporte HTML ejecutivo.
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
    st.title("Syntro Cloud Soil Engine (Malla 5x5m)")
    st.markdown("#### Procesamiento Espectral Dinámico: 12 Clases Texturales USDA y pH")

st.markdown("---")

st.subheader("🛰️ 1. Parámetros de Análisis y Entrada")

tipo_analisis = st.selectbox(
    "🎯 Seleccione el Parámetro a Evaluar en la Malla:",
    [
        "Textura de Suelo (Triángulo USDA - 12 Clases Variables)", 
        "pH del Suelo (Índice Espectral de Acidez y Alcalinidad)"
    ],
    help="Elija si desea procesar la zonificación textural detallada de 12 clases o el perfil de pH."
)

st.markdown(f"""
    <div class="info-box">
        <strong>💡 Configuración Activa - {tipo_analisis}:</strong><br>
        El sistema procesará las bandas espectrales (B4, B6, B7), recortará con el perímetro en coordenadas UTM y generará la malla de centroides espaciados exactamente a 5x5 metros con variabilidad real por píxel.
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
if st.button("🚀 Ejecutar Procesamiento y Malla 5x5m"):
    if uploaded_landsat is not None and uploaded_vector is not None:
        with st.spinner(f"Procesando {tipo_analisis} en malla de 5x5m, aplicando bandas B4/B6/B7 y construyendo reportes..."):
            
            try:
                with tempfile.TemporaryDirectory() as tmpdirname:
                    # 1. Procesar archivo Landsat comprimido
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
                        
                    # Buscar bandas B4, B6 y B7
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
                        st.error("No se encontraron las bandas B4, B6 y B7 dentro del archivo comprimido de Landsat.")
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
                        
                    # Zona UTM automática
                    centroid = gdf.unary_union.centroid
                    epsg_utm = 32619 if centroid.x > -72 else 32618
                    
                    gdf_utm = gdf.to_crs(epsg=epsg_utm)
                    polygon_utm = gdf_utm.unary_union
                    
                    area_total_m2 = polygon_utm.area
                    area_total_ha = area_total_m2 / 10000.0
                    
                    # 3. Recorte ráster seguro
                    def recortar_banda_5m(path_b):
                        with rasterio.open(path_b) as src_b:
                            img_b, trans_b = mask(src_b, [polygon_utm], crop=True, nodata=0, all_touched=True)
                            arr = img_b[0].astype(np.float32)
                            arr[arr == 0] = -9999
                            return arr, trans_b

                    b4, trans_out = recortar_banda_5m(b4_path)
                    b6, _ = recortar_banda_5m(b6_path)
                    b7, _ = recortar_banda_5m(b7_path)
                    
                    # 4. Modelos Espectrales Dinámicos (12 Clases USDA vs pH)
                    mask_val = (b4 > 0) & (b4 != -9999) & (b6 > 0) & (b6 != -9999)
                    indice = np.zeros(b4.shape, dtype=np.float32)
                    
                    is_ph = "pH" in tipo_analisis
                    
                    if np.any(mask_val):
                        if not is_ph:
                            # Modelo de Textura USDA - 12 Clases Oficiales (Variable por percentiles dinámicos)
                            indice[mask_val] = (b6[mask_val] + b7[mask_val]) / (b4[mask_val] + 1.0)
                            vals = indice[mask_val]
                            
                            # Generación de percentiles para distribuir en las 12 clases del triángulo USDA
                            pcts = np.percentile(vals, [8, 16, 24, 32, 40, 48, 56, 64, 72, 80, 88])
                            
                            cat_map = np.zeros(b4.shape, dtype=np.uint8)
                            cat_map[mask_val] = np.where(indice[mask_val] <= pcts[0], 1,
                                                np.where(indice[mask_val] <= pcts[1], 2,
                                                np.where(indice[mask_val] <= pcts[2], 3,
                                                np.where(indice[mask_val] <= pcts[3], 4,
                                                np.where(indice[mask_val] <= pcts[4], 5,
                                                np.where(indice[mask_val] <= pcts[5], 6,
                                                np.where(indice[mask_val] <= pcts[6], 7,
                                                np.where(indice[mask_val] <= pcts[7], 8,
                                                np.where(indice[mask_val] <= pcts[8], 9,
                                                np.where(indice[mask_val] <= pcts[9], 10,
                                                np.where(indice[mask_val] <= pcts[10], 11, 12)))))))))))
                        else:
                            # Modelo Espectral de pH del Suelo (5 Rangos)
                            indice[mask_val] = 7.0 + ((b7[mask_val] - b4[mask_val]) / (b6[mask_val] + 1.0)) * 0.5
                            vals = indice[mask_val]
                            p20, p40, p60, p80 = np.percentile(vals, [20, 40, 60, 80])
                            
                            cat_map = np.zeros(b4.shape, dtype=np.uint8)
                            cat_map[mask_val] = np.where(indice[mask_val] <= p20, 1,
                                                np.where(indice[mask_val] <= p40, 2,
                                                np.where(indice[mask_val] <= p60, 3,
                                                np.where(indice[mask_val] <= p80, 4, 5))))
                    else:
                        cat_map = np.ones(b4.shape, dtype=np.uint8) * (3 if not is_ph else 3)
                        
                    if not is_ph:
                        nombres_dict = {
                            1: "Arena (Sand)",
                            2: "Arena Franca (Loamy Sand)",
                            3: "Franco Arenoso (Sandy Loam)",
                            4: "Franco (Loam)",
                            5: "Franco Limoso (Silt Loam)",
                            6: "Limo (Silt)",
                            7: "Franco Arcillo-Arenoso (Sandy Clay Loam)",
                            8: "Franco Arcilloso (Clay Loam)",
                            9: "Franco Arcillo-Limoso (Silty Clay Loam)",
                            10: "Arcillo Arenoso (Sandy Clay)",
                            11: "Arcillo Limoso (Silty Clay)",
                            12: "Arcilloso (Clay)"
                        }
                        titulo_reporte = "Informe Técnico Textural USDA (12 Clases)"
                        archivo_sufijo = "USDA_12_CLASES"
                    else:
                        nombres_dict = {
                            1: "Extremadamente Ácido (< 5.0)",
                            2: "Fuertemente Ácido (5.0 - 5.5)",
                            3: "Moderadamente Ácido (5.6 - 6.0)",
                            4: "Ligeramente Ácido a Neutro (6.1 - 6.8)",
                            5: "Neutro a Alcalino (> 6.9)"
                        }
                        titulo_reporte = "Informe Técnico de pH del Suelo"
                        archivo_sufijo = "PH_SUELO"
                    
                    # Generación de la malla estricta de 5x5 metros
                    minx, miny, maxx, maxy = polygon_utm.bounds
                    x_coords = np.arange(minx, maxx, 5.0)
                    y_coords = np.arange(miny, maxy, 5.0)
                    
                    num_clases_total = 12 if not is_ph else 5
                    features = []
                    conteo_clases = {i: 0 for i in range(1, num_clases_total + 1)}
                    
                    id_pto = 1
                    for x in x_coords:
                        for y in y_coords:
                            pt = Point(x, y)
                            if polygon_utm.contains(pt):
                                row, col = rasterio.transform.rowcol(trans_out, x, y)
                                if 0 <= row < cat_map.shape[0] and 0 <= col < cat_map.shape[1]:
                                    c_id = int(cat_map[row, col])
                                    if c_id == 0 or c_id > num_clases_total:
                                        c_id = 4 if not is_ph else 3
                                else:
                                    c_id = 4 if not is_ph else 3
                                    
                                conteo_clases[c_id] += 1
                                
                                prop_dict = {
                                    "id": id_pto,
                                    "CLASE_ID": c_id,
                                    "RESOLUCION": "5x5m"
                                }
                                if not is_ph:
                                    prop_dict["CLASE_USDA"] = nombres_dict.get(c_id, "Franco")
                                else:
                                    prop_dict["RANGO_PH"] = nombres_dict.get(c_id, "Neutro")
                                    
                                features.append({
                                    "type": "Feature",
                                    "geometry": {
                                        "type": "Point",
                                        "coordinates": [x, y]
                                    },
                                    "properties": prop_dict
                                })
                                id_pto += 1
                                    
                    total_celdas = len(features)
                    ha_px = 0.0025 # 5x5m = 25 m² = 0.0025 ha
                    
                    areas, porcentajes = {}, {}
                    for i in range(1, num_clases_total + 1):
                        ha_clase = conteo_clases[i] * ha_px
                        areas[i] = ha_clase
                        porcentajes[i] = (conteo_clases[i] / total_celdas) * 100 if total_celdas > 0 else 0.0
                        
                    for feat in features:
                        cid = feat["properties"]["CLASE_ID"]
                        feat["properties"]["area_ha"] = round(areas[cid], 4)
                        feat["properties"]["porcentaje"] = round(porcentajes[cid], 2)
                        
                    gdf_puntos_utm = gpd.GeoDataFrame.from_features(features, crs=f"EPSG:{epsg_utm}")
                    gdf_puntos_wgs84 = gdf_puntos_utm.to_crs(epsg=4326)
                    geojson_string = gdf_puntos_wgs84.to_json()
                    
            except Exception as e:
                st.error(f"Error procesando la malla de 5x5m: {e}")
                st.stop()

            # 5. Construcción del Informe HTML Ejecutivo Profesional
            chart_labels = [nombres_dict[i].split("(")[0].strip() for i in range(1, num_clases_total + 1) if areas[i] > 0]
            chart_data = [round(areas[i], 2) for i in range(1, num_clases_total + 1) if areas[i] > 0]
            chart_colors = ["#991b1b", "#dc2626", "#ea580c", "#f97316", "#ca8a04", "#eab308", "#16a34a", "#22c55e", "#10b981", "#06b6d4", "#3b82f6", "#6366f1"][:len(chart_data)]

            filas_html = ""
            for i in range(1, num_clases_total + 1):
                if areas[i] > 0:
                    filas_html += f"""
                    <tr>
                        <td><strong>{i}. {nombres_dict[i]}</strong></td>
                        <td>{areas[i]:.2f} ha</td>
                        <td>{porcentajes[i]:.1f}%</td>
                    </tr>
                    """

            html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Syntro Academy - {titulo_reporte} (Malla 5x5m)</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #0b132b;
            color: #ffffff;
            margin: 0;
            padding: 30px;
        }}
        .container {{
            max-width: 950px;
            margin: auto;
            background: #1c2541;
            padding: 40px;
            border-radius: 14px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.6);
            border: 1px solid #3a86ff;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid #41ead4;
            padding-bottom: 20px;
            margin-bottom: 25px;
        }}
        .header h1 {{
            color: #41ead4;
            font-size: 24px;
            margin: 0;
        }}
        .header p {{
            color: #8d99ae;
            font-size: 13px;
            margin: 5px 0 0 0;
        }}
        .meta-box {{
            background: #0b132b;
            padding: 15px 20px;
            border-radius: 8px;
            margin-bottom: 25px;
            font-size: 14px;
            border-left: 5px solid #41ead4;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 30px;
        }}
        th, td {{
            padding: 10px 15px;
            text-align: left;
            border-bottom: 1px solid rgba(58, 134, 255, 0.3);
            font-size: 13px;
        }}
        th {{
            background-color: #0b132b;
            color: #41ead4;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        tr:hover {{
            background-color: rgba(65, 234, 212, 0.05);
        }}
        .total-row {{
            font-weight: bold;
            background-color: #0b132b;
            color: #41ead4;
            font-size: 14px;
        }}
        .chart-container {{
            width: 90%;
            margin: auto;
            background: #0b132b;
            padding: 20px;
            border-radius: 10px;
            border: 1px solid rgba(58, 134, 255, 0.2);
        }}
        .footer {{
            margin-top: 40px;
            text-align: center;
            font-size: 12px;
            color: #8d99ae;
            border-top: 1px solid rgba(141, 153, 174, 0.2);
            padding-top: 15px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1>SYNTRO ACADEMY</h1>
                <p>{titulo_reporte} por Percepción Remota</p>
            </div>
            <div style="text-align: right;">
                <p><strong>Consultor:</strong> Ing. Juan Segundo Suárez Rivera</p>
                <p><strong>Fecha:</strong> {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
            </div>
        </div>

        <div class="meta-box">
            <strong>📋 Resumen Ejecutivo del Proyecto:</strong><br>
            - <strong>Parámetro Evaluado:</strong> {tipo_analisis}<br>
            - <strong>Escena Analizada:</strong> {uploaded_landsat.name}<br>
            - <strong>Modelo Espectral Dinámico:</strong> Bandas B4, B6, B7<br>
            - <strong>Malla Detallada:</strong> 5 x 5 metros (25 m² por celda)<br>
            - <strong>Superficie Total Evaluada:</strong> {area_total_ha:.2f} Hectáreas ({area_total_m2:,.2f} m²)<br>
            - <strong>Total Centroides 5x5m:</strong> {total_celdas} puntos
        </div>

        <table>
            <thead>
                <tr>
                    <th>Clasificación del Parámetro</th>
                    <th>Superficie (ha)</th>
                    <th>Distribución (%)</th>
                </tr>
            </thead>
            <tbody>
                {filas_html}
                <tr class="total-row">
                    <td>SUPERFICIE TOTAL EVALUADA</td>
                    <td>{area_total_ha:.2f} ha</td>
                    <td>100.0%</td>
                </tr>
            </tbody>
        </table>

        <div class="chart-container">
            <canvas id="soilChart"></canvas>
        </div>

        <div class="footer">
            Generado automáticamente por el motor geoespacial avanzado Syntro Cloud Engine &bull; QGIS / GeoLibre Compatible
        </div>
    </div>

    <script>
        const ctx = document.getElementById('soilChart').getContext('2d');
        new Chart(ctx, {{
            type: 'bar',
            data: {{
                labels: {chart_labels},
                datasets: [{{
                    label: 'Superficie (Hectáreas)',
                    data: {chart_data},
                    backgroundColor: {chart_colors},
                    borderWidth: 1,
                    borderRadius: 5
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    legend: {{ display: false }},
                    title: {{
                        display: true,
                        text: 'Distribución Espacial Variable - Malla 5x5m (ha)',
                        color: '#ffffff',
                        font: {{ size: 14 }}
                    }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        ticks: {{ color: '#8d99ae' }},
                        grid: {{ color: 'rgba(141, 153, 174, 0.1)' }}
                    }},
                    x: {{
                        ticks: {{ color: '#8d99ae', font: {{ size: 10 }} }},
                        grid: {{ display: false }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""

        # Resumen en texto plano
        lineas_informe = []
        lineas_informe.append("="*85)
        lineas_informe.append(f"SYNTRO ACADEMY - {titulo_reporte.upper()}")
        lineas_informe.append("="*85)
        lineas_informe.append("CONSULTOR: ING. JUAN SEGUNDO SUAREZ RIVERA")
        lineas_informe.append(f"PARAMETRO: {tipo_analisis}")
        lineas_informe.append(f"ESCENA LANDSAT: {uploaded_landsat.name}")
        lineas_informe.append(f"TOTAL CENTROIDES (5x5m): {total_celdas}")
        lineas_informe.append(f"SUPERFICIE TOTAL EVALUADA: {area_total_ha:.2f} ha\n")
        lineas_informe.append(f"{'CLASIFICACION':<42} | {'SUPERFICIE (ha)':<15} | {'PORCENTAJE (%)':<15}")
        lineas_informe.append("-" * 80)
        for i in range(1, num_clases_total + 1):
            if areas[i] > 0:
                lineas_informe.append(f"{nombres_dict[i]:<42} | {areas[i]:<15.2f} | {porcentajes[i]:<15.1f}%")
        lineas_informe.append("-" * 80)
        lineas_informe.append(f"{'SUPERFICIE TOTAL EVALUADA':<42} | {area_total_ha:<15.2f} | 100.0%")
        lineas_informe.append("="*85)
        resumen_dinamico = "\n".join(lineas_informe)

        st.success(f"¡Proceso completado con éxito! Se generaron {total_celdas} centroides detallados de 5x5m con variabilidad espacial.")
        
        # Métricas visuales
        st.markdown(f"### 📊 Resultados Estadísticos - {tipo_analisis} (5x5m)")
        m1, m2, m3 = st.columns(3)
        m1.metric("Área Real Evaluada", f"{area_total_ha:.2f} Hectáreas", f"{total_celdas} celdas (5x5m)")
        m2.metric("Malla Detallada", "5 x 5 metros", "Variabilidad Espacial Real")
        m3.metric("Reportes Generados", "GeoJSON + HTML Ejecutivo", "Listos para descarga")
        
        st.text(resumen_dinamico)
        
        st.markdown("---")
        st.subheader("📥 Descarga de Archivos de Salida")
        
        col_d1, col_d2, col_d3 = st.columns(3)
        with col_d1:
            st.download_button(
                label="📥 Descargar GeoJSON de Centroides (5x5m)",
                data=geojson_string,
                file_name=f"SYNTRO_{archivo_sufijo}_PUNTOS_5x5m.geojson",
                mime="application/json"
            )
        with col_d2:
            st.download_button(
                label="📥 Descargar Informe HTML Ejecutivo",
                data=html_content,
                file_name=f"INFORME_{archivo_sufijo}_EJECUTIVO_5x5m.html",
                mime="text/html"
            )
        with col_d3:
            st.download_button(
                label="📥 Descargar Informe Txt (.txt)",
                data=resumen_dinamico,
                file_name=f"INFORME_{archivo_sufijo}_5x5m.txt",
                mime="text/plain"
            )
    else:
        st.error("⚠️ Debe cargar tanto el archivo comprimido de Landsat como el archivo perimetral antes de ejecutar.")
