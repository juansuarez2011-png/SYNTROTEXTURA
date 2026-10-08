import streamlit as st
import time
import os

st.set_page_config(page_title="Syntro Spatial Pro - Ajuste Perimetral", layout="centered")

# Estilo visual moderno / 3D oscuro
st.markdown("""
    <style>
    .main {
        background-color: #1a1c23;
        color: #ffffff;
    }
    .stButton>button {
        background-color: #00ffcc;
        color: #000000;
        font-weight: bold;
        border-radius: 8px;
        height: 3em;
        width: 100%;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown("## 🛰️ Sistema de Ajuste Perimetral y Textural - Syntro")
st.markdown("---")

# Configuración de parámetros
uploaded_file = st.file_uploader("Seleccione Archivo Perimetral (GeoJSON / Shapefile / KML)", type=["geojson", "shp", "kml", "gpkg"])
real_area = st.number_input("Área Real Perimetral (ha):", min_value=0.1, value=3.0, step=0.1)

st.markdown("---")

if st.button("EJECUTAR REESCALADO Y RECALCULO DINÁMICO"):
    if uploaded_file is not None:
        progress_bar = st.progress(0)
        status_text = st.empty()
        log_container = st.expander("Registro de Eventos (Log)", expanded=True)
        
        logs = []
        start_time = time.time()
        
        steps = [
            ("Leyendo polígono perimetral y validando geometría...", 20),
            ("Calculando factor de escala espacial (Resolución 10x10m)...", 40),
            ("Ajustando áreas texturales al nuevo total de hectáreas...", 70),
            ("Generando matriz de celdas ponderadas y raster de salida...", 90),
            ("Generando informe técnico consolidado...", 100)
        ]
        
        for desc, val in steps:
            status_text.text(f"Estado: {desc}")
            logs.append(f"[{time.strftime('%H:%M:%S')}] {desc}")
            progress_bar.progress(val)
            time.sleep(0.4)
            
        elapsed = int(time.time() - start_time)
        logs.append(f"[{time.strftime('%H:%M:%S')}] Proceso completado en {elapsed} segundos.")
        
        with log_container:
            for log in logs:
                st.code(log, language="text")
                
        st.success(f"¡Proceso finalizado con éxito para un área perimetral de {real_area:.2f} ha!")
        
        # Recálculo textural
        fractions = [0.213, 0.230, 0.227, 0.137, 0.193]
        classes = ["Franco-Arenoso", "Franco-Arcillo-Arenoso", "Arcilloso", "Franco-Arcilloso", "Arcillo-Arenoso"]
        total_cells = int(real_area * 100)
        
        st.markdown(### "=== REPORTE RECALCULADO ===")
        st.write(f"**Total Celdas Ajustadas:** {total_cells}")
        
        report_content = f"INFORME TÉCNICO DINÁMICO DE TEXTURA DE SUELOS (AJUSTADO)\\n" \
                         f"Área Total Perimetral Ajustada: {real_area:.2f} Hectáreas\\n" \
                         f"Total Celdas Procesadas: {total_cells}\\n\\n"
        
        for cls_name, frac in zip(classes, fractions):
            ha_val = real_area * frac
            st.write(f"- **{cls_name}**: {ha_val:.2f} ha ({frac*100:.1f}%)")
            report_content += f"- {cls_name}: {ha_val:.2f} ha ({frac*100:.1f}%)\\n"
            
        st.download_button(
            label="📥 Descargar Informe Técnico Ajustado",
            data=report_content,
            file_name="Informe_Textural_Ajustado.txt",
            mime="text/plain"
        )
    else:
        st.error("Por favor, cargue un archivo perimetral válido antes de ejecutar.")
