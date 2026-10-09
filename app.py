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

st.set_page_config(page_title="Syntro - Interpolación IDW", page_icon="🌍", layout="centered")

st.markdown("<h2 style='color: #4CAF50;'>Syntro Academy - Módulo de Interpolación IDW</h2>", unsafe_allow_html=True)
st.write("Bienvenido Juan Suárez. Sube tus puntos y tu polígono perimetral para generar el mapa inteligente optimizado.")

# Contenedor de subida de archivos
st.markdown("### 📁 Archivos de Entrada")
uploaded_puntos = st.file_uploader("Subir Archivo de Puntos (Shapefile comprimido .zip o GeoJSON)", type=["zip", "geojson", "json"])
uploaded_poli = st.file_uploader("Subir Polígono Perimetral del Área de Estudio (.zip o GeoJSON)", type=["zip", "geojson", "json"])

# Función auxiliar para guardar archivos subidos temporalmente
def guardar_archivo_temporal(uploaded_file):
    temp_dir = tempfile.mkdtemp()
    path = os.path.join(temp_dir, uploaded_file.name)
    with open(path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return path

# Si se cargan los puntos, detectamos los campos numéricos de forma inteligente
if uploaded_puntos is not None:
    try:
        puntos_path = guardar_archivo_temporal(uploaded_puntos)
        gdf_puntos = gpd.read_file(puntos_path)
        
        cols_numericas = gdf_puntos.select_dtypes(include=[np.number]).columns.tolist()
        
        st.markdown("### ⚙️ Parámetros de Interpolación")
        campo_seleccionado = st.selectbox("Seleccionar Campo Numérico (Z) a Interpolar", cols_numericas)
        
        calidad = st.slider("Calidad de la Malla (Resolución en píxeles)", min_value=200, max_value=1500, value=800, step=100)
        sigma = st.slider("Suavizado Espacial (Sigma)", min_value=1.0, max_value=30.0, value=15.0, step=0.5)
        
        if uploaded_poli is not None:
            if st.button("🚀 Ejecutar Procesamiento y Recorte"):
                with st.spinner("Procesando interpolación IDW y ajustando perimetral..."):
                    try:
                        poli_path = guardar_archivo_temporal(uploaded_poli)
                        gdf_poli = gpd.read_file(poli_path)
                        
                        # Auto-alineación de CRS
                        if gdf_puntos.crs is None:
                            gdf_puntos.set_crs("EPSG:4326", inplace=True)
                        if gdf_poli.crs is None:
                            gdf_poli.set_crs("EPSG:4326", inplace=True)
                            
                        if gdf_puntos.crs != gdf_poli.crs:
                            gdf_poli = gdf_poli.to_crs(gdf_puntos.crs)
                            
                        # Extracción de coordenadas y valores
                        x = gdf_puntos.geometry.x.values
                        y = gdf_puntos.geometry.y.values
                        z = gdf_puntos[campo_seleccionado].values
                        puntos = np.column_stack((x, y))
                        
                        minx, miny, maxx, maxy = gdf_poli.total_bounds
                        
                        pixel_width = (maxx - minx) / calidad
                        pixel_height = (maxy - miny) / calidad
                        
                        # Malla y cálculo IDW
                        grid_x, grid_y = np.mgrid[minx:maxx:complex(0, calidad), miny:maxy:complex(0, calidad)]
                        grid_coords = np.column_stack((grid_x.ravel(), grid_y.ravel()))
                        
                        arbol = cKDTree(puntos)
                        distancias, indices = arbol.query(grid_coords, k=20)
                        
                        distancias = np.maximum(distancias, 1e-12)
                        pesos = 1.0 / (distancias ** 2)
                        z_interp_flat = np.sum(pesos * z[indices], axis=1) / np.sum(pesos, axis=1)
                        grid_z = z_interp_flat.reshape(grid_x.shape)
                        
                        # Suavizado gaussiano
                        grid_z_suavizado = gaussian_filter(grid_z, sigma=sigma)
                        
                        # Archivo temporal para rasterio
                        temp_tif = os.path.join(tempfile.gettempdir(), "temp_grid.tif")
                        transform = from_origin(minx, maxy, pixel_width, pixel_height)
                        
                        with rasterio.open(
                            temp_tif, 'w', driver='GTiff',
                            height=grid_z_suavizado.shape[1], width=grid_z_suavizado.shape[0],
                            count=1, dtype=str(grid_z_suavizado.dtype),
                            crs=gdf_puntos.crs, transform=transform
                        ) as dst:
                            dst.write(np.flipud(grid_z_suavizado.T), 1)
                            
                        # Recorte (Mask) con el polígono
                        geometrias = [geom for geom in gdf_poli.geometry]
                        output_tif = os.path.join(tempfile.gettempdir(), f"Mapa_Inteligente_{campo_seleccionado}.tif")
                        
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
                            
                        st.success("¡Proceso completado con éxito!")
                        
                        with open(output_tif, "rb") as file:
                            st.download_button(
                                label="📥 Descargar Mapa GeoTIFF (COG)",
                                data=file,
                                file_name=f"Mapa_Inteligente_{campo_seleccionado}.tif",
                                mime="image/tiff"
                            )
                            
                    except Exception as e:
                        st.error(f"Error procesando los datos espaciales: {str(e)}")
        else:
            st.info("Por favor, carga también el archivo del polígono perimetral para poder recortar el mapa.")
            
    except Exception as e:
        st.error(f"Error leyendo el archivo de puntos: {str(e)}")
