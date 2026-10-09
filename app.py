import streamlit as st
import os
import tempfile
import numpy as np
import geopandas as gpd
from scipy.spatial import cKDTree
from scipy.ndimage import gaussian_filter
import rasterio
from rasterio.transform import from_origin
from rasterio.mask import mask
import datetime
from PIL import Image

# Configuración de página
st.set_page_config(page_title="Syntro Academy - Interpolación IDW", page_icon="🌍", layout="wide")

# --- BARRA LATERAL DE MARCA SYNTRO ---
with st.sidebar:
    logo_path = None
    for posible_logo in ["icon.png", "LOGO.png", "logo1-1.png"]:
        if os.path.exists(posible_logo):
            logo_path = posible_logo
            break
            
    if logo_path:
        img_logo = Image.open(logo_path)
        st.image(img_logo, use_column_width=True)
    else:
        st.markdown("""
            <div style="text-align: center; padding: 10px;">
                <h1 style='color: #4CAF50; margin-bottom: 0;'>SYNTRO</h1>
                <p style='color: #aaaaaa; font-size: 14px;'>Academy & Spatial Intelligence</p>
            </div>
        """, unsafe_allow_html=True)
        
    st.markdown("<hr style='border-color: #4CAF50;'>", unsafe_allow_html=True)
    st.markdown("### 👤 Sesión Activa")
    st.info("Usuario: **Juan Suárez**\n\nMódulo: **Interpolación IDW & Reportes Bio-espaciales**")
    
    st.markdown("---")
    st.markdown("### 📌 Instrucciones")
    st.markdown("1. Sube tu archivo vectorial de **Puntos de Muestreo** (Shapefile .zip o GeoJSON).\n2. Sube el polígono **Perimetral**.\n3. Selecciona el parámetro numérico y ajusta la calidad.\n4. Ejecuta y descarga tu ráster COG y el **Informe Técnico**.")

# --- CUERPO PRINCIPAL ---
st.markdown("<h2 style='color: #4CAF50;'>Módulo de Interpolación IDW de Alta Precisión</h2>", unsafe_allow_html=True)
st.write("Generación de superficies continuas optimizadas para GeoLibre y análisis biofinanciero de lotes.")

st.markdown("---")

col1, col2 = st.columns(2)

with col1:
    st.markdown("### 📁 Archivo de Puntos (Muestras)")
    uploaded_puntos = st.file_uploader("Subir Muestras Vectoriales (.zip o GeoJSON)", type=["zip", "geojson", "json"], key="puntos")

with col2:
    st.markdown("### 📐 Límites Perimetrales del Área")
    uploaded_poli = st.file_uploader("Subir Perimetral (.zip o GeoJSON)", type=["zip", "geojson", "json"], key="poli")

def guardar_archivo_temporal(uploaded_file):
    temp_dir = tempfile.mkdtemp()
    path = os.path.join(temp_dir, uploaded_file.name)
    with open(path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return path

campo_seleccionado = None
gdf_puntos = None

if uploaded_puntos is not None:
    try:
        puntos_path = guardar_archivo_temporal(uploaded_puntos)
        gdf_puntos = gpd.read_file(puntos_path)
        
        # Verificación geométrica para asegurar que sean puntos
        tipo_geom = gdf_puntos.geom_type.unique()
        if not any('Point' in str(t) for t in tipo_geom):
            st.error("⚠️ El archivo cargado no contiene geometrías de tipo Punto. Asegúrate de subir un archivo vectorial de puntos y no una escena Landsat o ráster.")
        else:
            cols_numericas = gdf_puntos.select_dtypes(include=[np.number]).columns.tolist()
            
            st.markdown("---")
            st.markdown("### 🎯 Seleccione el Parámetro a Evaluar en la Malla:")
            campo_seleccionado = st.selectbox("Parámetro de Interpolación", cols_numericas)
            
            st.info(f"💡 **Configuración Activa - {campo_seleccionado}:** El sistema procesará los puntos, aplicará IDW, suavizado gaussiano, recortará con el perímetro exacto y generará un ráster COG optimizado.")
            
    except Exception as e:
        st.error(f"Error al leer el archivo de puntos (Verifica que sea un Shapefile vectorial válido o GeoJSON): {str(e)}")

with st.expander("⚙️ Ajustes Avanzados de Calidad y Suavizado"):
    c_cal, c_sig = st.columns(2)
    with c_cal:
        calidad = st.slider("Calidad de Malla (Píxeles)", min_value=200, max_value=1500, value=800, step=100)
    with c_sig:
        sigma = st.slider("Suavizado Espacial (Sigma)", min_value=1.0, max_value=30.0, value=15.0, step=0.5)

st.markdown("---")

if st.button("🚀 Ejecutar Procesamiento y Malla IDW", type="primary"):
    if uploaded_puntos is None or uploaded_poli is None or not campo_seleccionado or gdf_puntos is None:
        st.warning("⚠️ Por favor, asegúrate de subir puntos válidos, el polígono perimetral y seleccionar un parámetro.")
    else:
        with st.spinner("Procesando malla espacial, aplicando suavizado y generando informe técnico..."):
            try:
                puntos_path = guardar_archivo_temporal(uploaded_puntos)
                poli_path = guardar_archivo_temporal(uploaded_poli)
                
                gdf_puntos = gpd.read_file(puntos_path)
                gdf_poli = gpd.read_file(poli_path)
                
                if gdf_puntos.crs is None:
                    gdf_puntos.set_crs("EPSG:4326", inplace=True)
                if gdf_poli.crs is None:
                    gdf_poli.set_crs("EPSG:4326", inplace=True)
                    
                if gdf_puntos.crs != gdf_poli.crs:
                    gdf_poli = gdf_poli.to_crs(gdf_puntos.crs)
                    
                x = gdf_puntos.geometry.x.values
                y = gdf_puntos.geometry.y.values
                z = gdf_puntos[campo_seleccionado].values
                puntos = np.column_stack((x, y))
                
                minx, miny, maxx, maxy = gdf_poli.total_bounds
                pixel_width = (maxx - minx) / calidad
                pixel_height = (maxy - miny) / calidad
                
                grid_x, grid_y = np.mgrid[minx:maxx:complex(0, calidad), miny:maxy:complex(0, calidad)]
                grid_coords = np.column_stack((grid_x.ravel(), grid_y.ravel()))
                
                arbol = cKDTree(puntos)
                distancias, indices = arbol.query(grid_coords, k=20)
                
                distancias = np.maximum(distancias, 1e-12)
                pesos = 1.0 / (distancias ** 2)
                z_interp_flat = np.sum(pesos * z[indices], axis=1) / np.sum(pesos, axis=1)
                grid_z = z_interp_flat.reshape(grid_x.shape)
                
                grid_z_suavizado = gaussian_filter(grid_z, sigma=sigma)
                
                temp_tif = os.path.join(tempfile.gettempdir(), "temp_grid.tif")
                transform = from_origin(minx, maxy, pixel_width, pixel_height)
                
                with rasterio.open(
                    temp_tif, 'w', driver='GTiff',
                    height=grid_z_suavizado.shape[1], width=grid_z_suavizado.shape[0],
                    count=1, dtype=str(grid_z_suavizado.dtype),
                    crs=gdf_puntos.crs, transform=transform
                ) as dst:
                    dst.write(np.flipud(grid_z_suavizado.T), 1)
                    
                geometrias = [geom for geom in gdf_poli.geometry]
                output_tif = os.path.join(tempfile.gettempdir(), f"Syntro_IDW_{campo_seleccionado}.tif")
                
                with rasterio.open(temp_tif) as src:
                    out_image, out_transform = mask(src, geometrias, crop=True, nodata=np.nan)
                    out_meta = src.meta.copy()
                    
                out_meta.update({
                    "driver": "COG",
                    "height": out_image.shape[1],
                    "width": out_image.shape[2],
                    "transform": out_transform,
                    "nodata": np.nan,
                    "compress": "deflate"
                })
                
                with rasterio.open(output_tif, "w", **out_meta) as dest:
                    dest.write(out_image)
                    
                val_validos = out_image[~np.isnan(out_image)]
                min_val = float(np.min(val_validos))
                max_val = float(np.max(val_validos))
                mean_val = float(np.mean(val_validos))
                std_val = float(np.std(val_validos))
                
                fecha_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                informe_texto = f"""==================================================
        SYNTRÓ ACADEMY - INFORME TÉCNICO ESPACIAL
==================================================
Fecha de Generación: {fecha_str}
Especialista: Ing. Juan Segundo Suárez Rivera
Variable Analizada: {campo_seleccionado}
--------------------------------------------------
PARÁMETROS DE MODELADO:
- Método de Interpolación: IDW (cKDTree con k=20)
- Suavizado Espacial (Sigma): {sigma}
- Resolución de Malla: {calidad}x{calidad} píxeles
- Sistema de Coordenadas (CRS): {gdf_puntos.crs}
--------------------------------------------------
ESTADÍSTICAS DESCRIPTIVAS DEL LOTE:
- Valor Mínimo: {min_val:.4f}
- Valor Máximo: {max_val:.4f}
- Valor Promedio (Media): {mean_val:.4f}
- Desviación Estándar: {std_val:.4f}
==================================================
Syntro Spatial Intelligence - Todos los derechos reservados.
"""
                informe_path = os.path.join(tempfile.gettempdir(), f"Informe_Syntro_{campo_seleccionado}.txt")
                with open(informe_path, "w", encoding="utf-8") as f:
                    f.write(informe_texto)
                    
                st.success("¡Proceso completado con éxito! Resultados listos para descarga:")
                
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    with open(output_tif, "rb") as file:
                        st.download_button(
                            label="📥 Descargar Mapa COG (.tif)",
                            data=file,
                            file_name=f"Syntro_IDW_{campo_seleccionado}.tif",
                            mime="image/tiff"
                        )
                with col_d2:
                    with open(informe_path, "rb") as file:
                        st.download_button(
                            label="📄 Descargar Informe Técnico (.txt)",
                            data=file,
                            file_name=f"Informe_Syntro_{campo_seleccionado}.txt",
                            mime="text/plain"
                        )
                        
            except Exception as e:
                st.error(f"Error procesando los datos espaciales: {str(e)}")
