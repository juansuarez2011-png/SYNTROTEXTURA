import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import logging
import time
import threading
import os
import numpy as np
import geopandas as gpd
from scipy.spatial import cKDTree
from scipy.ndimage import gaussian_filter
import rasterio
from rasterio.transform import from_origin
from rasterio.mask import mask

class InterpolacionIDWApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Syntro - Interpolación IDW Inteligente (Auto-Alineación)")
        self.root.geometry("700x720")
        self.root.configure(bg="#2b2b2b")
        
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TLabel", background="#2b2b2b", foreground="#ffffff", font=("Segoe UI", 10))
        # Corregido el error de sintaxis de los estilos aquí:
        style.configure("TButton", font=("Segoe UI", 10, "bold"), background="#4CAF50", foreground="white", borderwidth=3, relief="raised")
        style.map("TButton", background=[("active", "#45a049")])
        style.configure("Horizontal.TProgressbar", background="#4CAF50", troughcolor="#1e1e1e", bordercolor="#2b2b2b", lightcolor="#4CAF50", darkcolor="#4CAF50")
        
        self.archivo_puntos = tk.StringVar()
        self.archivo_poligono = tk.StringVar()
        self.carpeta_salida = tk.StringVar()
        self.columna_seleccionada = tk.StringVar()
        self.calidad_malla = tk.StringVar(value="800")
        self.sigma_suavizado = tk.StringVar(value="15.0")
        
        self.crear_widgets()
        self.setup_logging()
        
    def setup_logging(self):
        self.logger = logging.getLogger("InterpolacionIDWSyntro")
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        self.log_handler = TextHandler(self.log_text)
        self.log_handler.setFormatter(formatter)
        self.logger.addHandler(self.log_handler)
        self.logger.info("Bienvenido Juan Suárez. Módulo con auto-alineación CRS activo.")
        
    def crear_widgets(self):
        main_frame = tk.Frame(self.root, bg="#2b2b2b")
        main_frame.pack(padx=20, pady=20, fill=tk.BOTH, expand=True)
        
        lbl_titulo = tk.Label(main_frame, text="Interpolación IDW con Auto-Alineación (COG)", font=("Segoe UI", 14, "bold"), bg="#2b2b2b", fg="#4CAF50")
        lbl_titulo.grid(row=0, column=0, columnspan=3, pady=(0, 15))
        
        # Archivo Puntos
        ttk.Label(main_frame, text="Archivo de Puntos:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, textvariable=self.archivo_puntos, width=42).grid(row=1, column=1, padx=5, pady=5)
        tk.Button(main_frame, text="Seleccionar", command=self.cargar_puntos_inteligente, bg="#2196F3", fg="white", relief="raised", borderwidth=2).grid(row=1, column=2, pady=5)
        
        # Campo numérico (Combobox inteligente)
        ttk.Label(main_frame, text="Campo Numérico (Z):").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.combo_campos = ttk.Combobox(main_frame, textvariable=self.columna_seleccionada, width=40, state="readonly")
        self.combo_campos.grid(row=2, column=1, padx=5, pady=5, sticky=tk.W)
        
        # Polígono
        ttk.Label(main_frame, text="Polígono Área Estudio:").grid(row=3, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, textvariable=self.archivo_poligono, width=42).grid(row=3, column=1, padx=5, pady=5)
        tk.Button(main_frame, text="Seleccionar", command=lambda: self.seleccionar_archivo(self.archivo_poligono, "Polígono"), bg="#9C27B0", fg="white", relief="raised", borderwidth=2).grid(row=3, column=2, pady=5)
        
        # Calidad
        ttk.Label(main_frame, text="Calidad (píxeles, ej: 800):").grid(row=4, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, textvariable=self.calidad_malla, width=42).grid(row=4, column=1, padx=5, pady=5)
        
        # Suavizado Sigma
        ttk.Label(main_frame, text="Suavizado (Sigma):").grid(row=5, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, textvariable=self.sigma_suavizado, width=42).grid(row=5, column=1, padx=5, pady=5)
        
        # Carpeta Salida
        ttk.Label(main_frame, text="Carpeta de Salida:").grid(row=6, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, textvariable=self.carpeta_salida, width=42).grid(row=6, column=1, padx=5, pady=5)
        tk.Button(main_frame, text="Seleccionar", command=self.seleccionar_carpeta, bg="#2196F3", fg="white", relief="raised", borderwidth=2).grid(row=6, column=2, pady=5)
        
        # Botón Ejecutar
        self.btn_ejecutar = tk.Button(main_frame, text="Procesar y Alinear", command=self.ejecutar_hilo, bg="#ff9800", fg="white", font=("Segoe UI", 12, "bold"), relief="raised", borderwidth=3)
        self.btn_ejecutar.grid(row=7, column=0, columnspan=3, pady=15)
        
        # Barra de progreso y temporizador
        self.progress = ttk.Progressbar(main_frame, orient=tk.HORIZONTAL, length=550, mode='determinate', style="Horizontal.TProgressbar")
        self.progress.grid(row=8, column=0, columnspan=3, pady=10)
        
        self.lbl_timer = tk.Label(main_frame, text="Tiempo Transcurrido: 00:00:00", bg="#2b2b2b", fg="#ffffff", font=("Segoe UI", 10))
        self.lbl_timer.grid(row=9, column=0, columnspan=3, pady=5)
        
        # Log
        self.log_text = tk.Text(main_frame, height=8, width=80, bg="#1e1e1e", fg="#4CAF50", font=("Consolas", 9), relief="sunken", borderwidth=2)
        self.log_text.grid(row=10, column=0, columnspan=3, pady=10)
        
    def cargar_puntos_inteligente(self):
        archivo = filedialog.askopenfilename(title="Seleccionar Puntos", filetypes=[("Shapefile/GeoJSON", "*.shp *.geojson"), ("Todos", "*.*")])
        if archivo:
            self.archivo_puntos.set(archivo)
            self.logger.info(f"Puntos cargados: {os.path.basename(archivo)}")
            try:
                gdf = gpd.read_file(archivo)
                cols_numericas = gdf.select_dtypes(include=[np.number]).columns.tolist()
                
                if not cols_numericas:
                    messagebox.showwarning("Atención", "El archivo no contiene campos numéricos válidos.")
                    return
                
                self.combo_campos['values'] = cols_numericas
                self.combo_campos.set(cols_numericas[0])
                self.logger.info(f"Campos detectados: {cols_numericas}")
            except Exception as e:
                self.logger.error(f"Error al leer atributos: {str(e)}")
                messagebox.showerror("Error", f"No se pudieron leer las columnas:\n{str(e)}")
            
    def seleccionar_archivo(self, variable, tipo):
        archivo = filedialog.askopenfilename(title=f"Seleccionar {tipo}", filetypes=[("Shapefile/GeoJSON", "*.shp *.geojson"), ("Todos", "*.*")])
        if archivo:
            variable.set(archivo)
            self.logger.info(f"{tipo} cargado: {os.path.basename(archivo)}")
            
    def seleccionar_carpeta(self):
        carpeta = filedialog.askdirectory(title="Seleccionar Destino")
        if carpeta:
            self.carpeta_salida.set(carpeta)
            self.logger.info(f"Salida: {carpeta}")
            
    def ejecutar_hilo(self):
        if not self.archivo_puntos.get() or not self.archivo_poligono.get() or not self.carpeta_salida.get() or not self.columna_seleccionada.get():
            messagebox.showerror("Error", "Faltan archivos o debes seleccionar un campo numérico.")
            return
            
        self.btn_ejecutar.config(state=tk.DISABLED)
        self.progress["value"] = 0
        threading.Thread(target=self.proceso_interpolacion, daemon=True).start()
        
    def proceso_interpolacion(self):
        start_time = time.time()
        self.logger.info("Iniciando validación y reproyección espacial...")
        try:
            self.actualizar_progreso(10, start_time)
            
            gdf_puntos = gpd.read_file(self.archivo_puntos.get())
            gdf_poli = gpd.read_file(self.archivo_poligono.get())
            
            if gdf_puntos.crs is None:
                self.logger.warning("El archivo de puntos no tiene CRS definido. Asignando WGS84 por defecto.")
                gdf_puntos.set_crs("EPSG:4326", inplace=True)
                
            if gdf_poli.crs is None:
                self.logger.warning("El archivo de polígono no tiene CRS definido. Asignando WGS84 por defecto.")
                gdf_poli.set_crs("EPSG:4326", inplace=True)
                
            if gdf_puntos.crs != gdf_poli.crs:
                self.logger.info(f"Reproyectando polígono de {gdf_poli.crs} a {gdf_puntos.crs}...")
                gdf_poli = gdf_poli.to_crs(gdf_puntos.crs)
            else:
                self.logger.info("Los sistemas de coordenadas coinciden perfectamente.")
            
            campo = self.columna_seleccionada.get()
            self.logger.info(f"Interpolando variable: '{campo}'")
            
            self.actualizar_progreso(25, start_time)
            
            x = gdf_puntos.geometry.x.values
            y = gdf_puntos.geometry.y.values
            z = gdf_puntos[campo].values
            puntos = np.column_stack((x, y))
            
            minx, miny, maxx, maxy = gdf_poli.total_bounds
            
            calidad = int(self.calidad_malla.get())
            pixel_width = (maxx - minx) / calidad
            pixel_height = (maxy - miny) / calidad
            
            self.logger.info(f"Construyendo malla base de {calidad}x{calidad}...")
            grid_x, grid_y = np.mgrid[minx:maxx:complex(0, calidad), miny:maxy:complex(0, calidad)]
            grid_coords = np.column_stack((grid_x.ravel(), grid_y.ravel()))
            
            self.actualizar_progreso(40, start_time)
            
            self.logger.info("Ejecutando IDW (20 vecinos)...")
            arbol = cKDTree(puntos)
            distancias, indices = arbol.query(grid_coords, k=20) 
            
            distancias = np.maximum(distancias, 1e-12)
            pesos = 1.0 / (distancias ** 2)
            z_interp_flat = np.sum(pesos * z[indices], axis=1) / np.sum(pesos, axis=1)
            
            grid_z = z_interp_flat.reshape(grid_x.shape)
            
            self.actualizar_progreso(65, start_time)
            
            sigma_val = float(self.sigma_suavizado.get())
            self.logger.info(f"Aplicando filtro gaussiano (Sigma={sigma_val})...")
            grid_z_suavizado = gaussian_filter(grid_z, sigma=sigma_val)
            
            self.actualizar_progreso(75, start_time)
            
            temp_path = os.path.join(self.carpeta_salida.get(), "temp_grid_idw_smart.tif")
            transform = from_origin(minx, maxy, pixel_width, pixel_height)
            
            with rasterio.open(
                temp_path, 'w', driver='GTiff',
                height=grid_z_suavizado.shape[1], width=grid_z_suavizado.shape[0],
                count=1, dtype=str(grid_z_suavizado.dtype),
                crs=gdf_puntos.crs, transform=transform
            ) as dst:
                dst.write(np.flipud(grid_z_suavizado.T), 1)
                
            self.actualizar_progreso(85, start_time)
            
            self.logger.info("Recortando al perímetro exacto (Formato COG)...")
            geometrias = [geom for geom in gdf_poli.geometry]
            output_path = os.path.join(self.carpeta_salida.get(), f"Mapa_Inteligente_{campo}.tif")
            
            with rasterio.open(temp_path) as src:
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
            
            with rasterio.open(output_path, "w", **out_meta) as dest:
                dest.write(out_image)
                
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
            self.actualizar_progreso(100, start_time)
            self.logger.info("¡Proceso finalizado con éxito!")
            messagebox.showinfo("Éxito", f"Mapa inteligente generado en:\n{output_path}")
            
        except Exception as e:
            self.logger.error(f"Error crítico: {str(e)}")
            messagebox.showerror("Error", f"Fallo en el proceso:\n{str(e)}")
        finally:
            self.btn_ejecutar.config(state=tk.NORMAL)
            
    def actualizar_progreso(self, valor, start_time):
        self.progress["value"] = valor
        elapsed = int(time.time() - start_time)
        hrs, rem = divmod(elapsed, 3600)
        mins, secs = divmod(rem, 60)
        self.lbl_timer.config(text=f"Tiempo Transcurrido: {hrs:02d}:{mins:02d}:{secs:02d}")
        self.root.update_idletasks()

class TextHandler(logging.Handler):
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
        
    def emit(self, record):
        msg = self.format(record)
        def append():
            self.text_widget.configure(state='normal')
            self.text_widget.insert(tk.END, msg + '\n')
            self.text_widget.see(tk.END)
            self.text_widget.configure(state='disabled')
        self.text_widget.after(0, append)

if __name__ == "__main__":
    root = tk.Tk()
    app = InterpolacionIDWApp(root)
    root.mainloop()
