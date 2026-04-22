import time
import os
import logging
import zipfile
import tempfile
import shutil
import uuid
import platform

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from xml_reader import leer_xml
from insercion_xml import insertar_detalle, limpiar_factura
from comparacion import obtener_diferencias
from excel import generar_excel
from config import (
    PATH_ENTRADA,
    PATH_PROCESADOS,
    PATH_LOGS
)

# -----------------------------
# CONFIGURACIÓN DE LOGS
# -----------------------------
os.makedirs(PATH_LOGS, exist_ok=True)

logging.basicConfig(
    filename=os.path.join(PATH_LOGS, "servicio.log"),
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

# -----------------------------
# FUNCIÓN PARA DESBLOQUEAR ARCHIVOS (WINDOWS)
# -----------------------------
def desbloquear_archivo_windows(ruta):
    """
    Elimina la marca 'Zone.Identifier' que Windows pone a los archivos
    descargados de internet y que causa errores de lectura.
    """
    if platform.system() != "Windows":
        return

    # La marca se guarda en un 'Stream' oculto llamado :Zone.Identifier
    stream_oculto = f"{ruta}:Zone.Identifier"
    
    if os.path.exists(stream_oculto):
        try:
            os.remove(stream_oculto)
            logging.info(f"Archivo desbloqueado automáticamente: {os.path.basename(ruta)}")
        except Exception as e:
            # Si falla borrar el stream, no detenemos el proceso, pero lo avisamos
            logging.warning(f"No se pudo desbloquear el archivo (puede que no esté bloqueado): {e}")

# -----------------------------
# LÓGICA CORE DE PROCESAMIENTO
# -----------------------------
def procesar_archivo_xml(ruta_xml_origen):
    logging.info(f"Procesando XML: {os.path.basename(ruta_xml_origen)}")

    try:
        factura, nit, detalle = leer_xml(ruta_xml_origen)

        if not factura or not nit:
            logging.error(f"Fallo lectura XML en {ruta_xml_origen}: No se obtuvo Factura o NIT")
            return None, None

        limpiar_factura(factura, nit)
        insertar_detalle(detalle)
        df = obtener_diferencias(factura, nit)
        generar_excel(df, factura, nit)

        logging.info(f"Factura {factura} | NIT {nit} procesada correctamente")
        return factura, nit

    except Exception as e:
        logging.error(f"Excepcion procesando {ruta_xml_origen}: {e}")
        return None, None

# -----------------------------
# PROCESAMIENTO RECURSIVO DE ZIPs
# -----------------------------
def procesar_zip(ruta_zip):
    logging.info(f"Iniciando procesamiento ZIP: {ruta_zip}")
    
    # 1. Intentamos desbloquear el ZIP principal antes de abrirlo
    desbloquear_archivo_windows(ruta_zip)

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Abrimos el ZIP
            with zipfile.ZipFile(ruta_zip, "r") as zip_ref:
                zip_ref.extractall(tmpdir)

            xml_encontrados = 0

            for root, _, files in os.walk(tmpdir):
                for archivo in files:
                    ruta_archivo = os.path.join(root, archivo)
                    archivo_lower = archivo.lower()
                    
                    # Desbloqueamos también los archivos extraídos por si acaso
                    desbloquear_archivo_windows(ruta_archivo)

                    # CASO 1: XML
                    if archivo_lower.endswith(".xml"):
                        xml_encontrados += 1
                        nombre_seguro = f"temp_{uuid.uuid4().hex[:8]}.xml"
                        ruta_segura = os.path.join(root, nombre_seguro)
                        os.rename(ruta_archivo, ruta_segura)
                        
                        try:
                            procesar_archivo_xml(ruta_segura)
                        except Exception as e:
                            logging.error(f"Error procesando XML interno {archivo}: {e}")

                    # CASO 2: ZIP ANIDADO (Recursividad)
                    elif archivo_lower.endswith(".zip"):
                        logging.info(f"Encontrado ZIP anidado: {archivo}. Procesando recursivamente...")
                        procesar_zip(ruta_archivo)
                        xml_encontrados += 1

            if xml_encontrados == 0:
                logging.warning(f"El archivo {os.path.basename(ruta_zip)} no contenía XMLs ni ZIPs válidos.")

    except zipfile.BadZipFile:
        logging.warning(f"Fallo al abrir ZIP {ruta_zip}. Probando si es XML directo...")
        try:
            procesar_archivo_xml(ruta_zip)
        except:
            logging.error("El archivo está corrupto y no es ZIP ni XML.")

# -----------------------------
# HANDLER DE WATCHDOG
# -----------------------------
class Handler(FileSystemEventHandler):

    def on_created(self, event):
        if event.is_directory:
            return

        try:
            ruta_origen = event.src_path
            nombre_archivo = os.path.basename(ruta_origen).lower()

            # Esperamos a que termine de copiarse
            time.sleep(2) 

            # --- PASO CRITICO: DESBLOQUEAR ---
            desbloquear_archivo_windows(ruta_origen)
            # ---------------------------------

            if nombre_archivo.endswith(".xml"):
                factura, nit = procesar_archivo_xml(ruta_origen)

                if factura and nit:
                    nuevo_nombre = f"{factura}_{nit}.xml"
                    destino = os.path.join(PATH_PROCESADOS, nuevo_nombre)
                else:
                    destino = os.path.join(PATH_PROCESADOS, os.path.basename(ruta_origen))

                shutil.move(ruta_origen, destino)
                logging.info(f"XML movido a procesados: {destino}")

            elif nombre_archivo.endswith(".zip"):
                procesar_zip(ruta_origen)
                
                destino = os.path.join(PATH_PROCESADOS, os.path.basename(ruta_origen))
                if os.path.exists(destino):
                    base, ext = os.path.splitext(destino)
                    destino = f"{base}_{uuid.uuid4().hex[:4]}{ext}"
                
                shutil.move(ruta_origen, destino)
                logging.info(f"ZIP Principal movido a procesados: {destino}")

        except Exception as e:
            logging.error(f"Error critico en Handler: {str(e)}")

# -----------------------------
# INICIO DEL SERVICIO
# -----------------------------
if __name__ == "__main__":
    logging.info("=== Servicio conciliador XML iniciado ===")

    os.makedirs(PATH_ENTRADA, exist_ok=True)
    os.makedirs(PATH_PROCESADOS, exist_ok=True)

    observer = Observer()
    observer.schedule(Handler(), PATH_ENTRADA, recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        observer.stop()
        logging.info("Servicio detenido manualmente")

    observer.join()