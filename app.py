import os
import json
import tempfile
import numpy as np
import geopandas as gpd
from shapely.geometry import Point, box
import rasterio
from rasterio.mask import mask
from osgeo import gdal

gdal.UseExceptions()

def clasificar_usda_12_espectral(arena, limo, arcilla):
    """Clasificación oficial USDA de 12 clases texturales a partir de porcentajes."""
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

def ejecutar_proceso_syntro_10x10(ruta_vector_perimetro, b2_path, b4_path, b5_path, b6_path, b7_path, carpeta_salida):
    """
    Motor analítico Syntro: Recorta por perimetral, calcula bandas espectrales, 
    genera malla estricta de centroides de 10x10m y exporta GeoJSON e informe.
    """
    os.makedirs(carpeta_salida, exist_ok=True)
    
    # 1. Cargar polígono perimetral con GeoPandas
    gdf_poly = gpd.read_file(ruta_vector_perimetro)
    if gdf_poly.crs is None:
        gdf_poly.set_crs(epsg=4326, inplace=True)
    
    # Proyectar a UTM automáticamente según el centroide
    centroid = gdf_poly.unary_union.centroid
    epsg_utm = 32619 if centroid.x > -72 else 32618
    gdf_utm = gdf_poly.to_crs(epsg=epsg_utm)
    polygon_utm = gdf_utm.unary_union
    
    area_total_m2 = polygon_utm.area
    area_total_ha = area_total_m2 / 10000.0

    # 2. Leer bandas y recortar espacialmente
    with rasterio.open(b4_path) as src:
        out_image, out_transform = mask(src, [polygon_utm], crop=True, nodata=-9999)
        b4 = out_image[0].astype(np.float32)
        meta = src.meta.copy()

    def recortar_y_leer(path_banda):
        with rasterio.open(path_banda) as src:
            img, _ = mask(src, [polygon_utm], crop=True, nodata=-9999)
            return img[0].astype(np.float32)

    b2 = recortar_y_leer(b2_path)
    b5 = recortar_y_leer(b5_path)
    b6 = recortar_y_leer(b6_path)
    b7 = recortar_y_leer(b7_path)

    # 3. Modelado espectral de arcilla y arena
    mask_val = (b4 > 0) & (b4 != -9999) & (b6 > 0) & (b6 != -9999) & (b2 > 0)
    
    ind_arcilla = np.zeros(b4.shape, dtype=np.float32)
    ind_arcilla[mask_val] = (b7[mask_val] / (b6[mask_val] + 1.0)) * (1.0 + b4[mask_val] / 10000.0)

    ind_arena = np.zeros(b4.shape, dtype=np.float32)
    ind_arena[mask_val] = (b5[mask_val] / (b2[mask_val] + 1.0)) / (b7[mask_val] / 10000.0 + 0.1)

    valid_a, valid_s = ind_arcilla[mask_val], ind_arena[mask_val]
    p_arc_min, p_arc_max = np.percentile(valid_a, 2), np.percentile(valid_a, 98)
    p_san_min, p_san_max = np.percentile(valid_s, 2), np.percentile(valid_s, 98)

    raw_arcilla = np.clip((ind_arcilla - p_arc_min) / (p_arc_max - p_arc_min + 1e-6) * 65.0 + 10.0, 5, 75)
    raw_arena = np.clip((ind_arena - p_san_min) / (p_san_max - p_san_min + 1e-6) * 75.0 + 15.0, 10, 90)

    arcilla_p = np.zeros(b4.shape, dtype=np.float32)
    arena_p = np.zeros(b4.shape, dtype=np.float32)
    limo_p = np.zeros(b4.shape, dtype=np.float32)

    for r_idx, c_idx in zip(*np.where(mask_val)):
        ac = raw_arcilla[r_idx, c_idx]
        ar = raw_arena[r_idx, c_idx]
        if (ac + ar) > 95.0: 
            ar = 95.0 - ac 
        li = 100.0 - (ac + ar)
        arcilla_p[r_idx, c_idx] = ac
        arena_p[r_idx, c_idx] = ar
        limo_p[r_idx, c_idx] = li

    tex_cat = clasificar_usda_12_espectral(arena_p, limo_p, arcilla_p)

    nombres_12 = {
        1: "Arenoso (Sand)", 2: "Franco-Arenoso Fino (Loamy Sand)", 3: "Franco-Arenoso (Sandy Loam)",
        4: "Franco (Loam)", 5: "Franco-Limoso (Silt Loam)", 6: "Limoso (Silt)",
        7: "Franco-Arcillo-Arenoso (Sandy Clay Loam)", 8: "Franco-Arcilloso (Clay Loam)",
        9: "Franco-Arcillo-Limoso (Silty Clay Loam)", 10: "Arcillo-Arenoso (Sandy Clay)",
        11: "Arcillo-Limoso (Silty Clay)", 12: "Arcilloso (Clay)"
    }

    # 4. Generación estricta de centroides de 10x10 metros dentro del polígono
    minx, miny, maxx, maxy = polygon_utm.bounds
    x_coords = np.arange(minx, maxx, 10.0)
    y_coords = np.arange(miny, maxy, 10.0)

    features = []
    conteo_clases = {i: 0 for i in range(1, 13)}
    id_pto = 1

    # Transformación inversa para ubicar el píxel exacto en la matriz
    transform = out_transform
    inv_transform = ~transform

    for x in x_coords:
        for y in y_coords:
            pt = Point(x, y)
            if polygon_utm.contains(pt):
                # Convertir coordenadas UTM a índices de la matriz raster
                col, row = ~transform * (x, y)
                r_idx, c_idx = int(row), int(col)
                
                c_id = 4 # Valor por defecto (Franco)
                if 0 <= r_idx < tex_cat.shape[0] and 0 <= c_idx < tex_cat.shape[1]:
                    c_id = int(tex_cat[r_idx, c_idx])
                    if c_id == 0: 
                        c_id = 4

                conteo_clases[c_id] += 1

                features.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [x, y] # Se guardará en coordenadas UTM o WGS84 según se requiera
                    },
                    "properties": {
                        "id": id_pto,
                        "clase_id": c_id,
                        "textura": nombres_12.get(c_id, "Desconocido"),
                        "resolucion": "10x10m"
                    }
                })
                id_pto += 1

    total_celdas = len(features)
    ha_px = 0.01 # Cada celda de 10x10m = 100 m² = 0.01 hectáreas

    # 5. Cálculo de áreas y porcentajes reales
    areas, porcentajes = {}, {}
    for i in range(1, 13):
        ha_clase = conteo_clases[i] * ha_px
        areas[i] = ha_clase
        porcentajes[i] = (conteo_clases[i] / total_celdas) * 100 if total_celdas > 0 else 0.0

    # Agregar área y porcentaje a las propiedades de cada punto GeoJSON
    for feat in features:
        cid = feat["properties"]["clase_id"]
        feat["properties"]["area_ha"] = round(areas[cid], 2)
        feat["properties"]["porcentaje"] = round(porcentajes[cid], 2)

    geojson_data = {
        "type": "FeatureCollection",
        "features": features
    }

    path_geojson = os.path.join(carpeta_salida, "Centroides_10x10_USDA12.geojson")
    with open(path_geojson, "w", encoding="utf-8") as f:
        json.dump(geojson_data, f, indent=4)

    # 6. Generar informe técnico en texto / HTML
    path_txt = os.path.join(carpeta_salida, "Informe_Tecnico_Textura_USDA12.txt")
    with open(path_txt, "w", encoding="utf-8") as f:
        f.write("INFORME TÉCNICO DE TEXTURA DE SUELOS - 12 CLASES USDA (SYNRO)\n")
        f.write("============================================================\n")
        f.write(f"Área Total Perimetral: {area_total_ha:.2f} ha\n")
        f.write(f"Total Celdas Procesadas (10x10m): {total_celdas}\n")
        f.write("------------------------------------------------------------\n")
        for i in range(1, 13):
            if areas[i] > 0:
                f.write(f"- {nombres_12[i]}: {areas[i]:.2f} ha ({porcentajes[i]:.1f}%)\n")
        f.write("------------------------------------------------------------\n")
        f.write("Proceso completado exitosamente.\n")

    print(f"¡Proceso finalizado! Archivos guardados en: {carpeta_salida}")
    return path_geojson, path_txt
