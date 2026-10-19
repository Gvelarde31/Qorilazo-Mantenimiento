import os
import time
from datetime import datetime
import xmltodict
import requests
from fastapi import FastAPI, Request, Response, UploadFile
from fastapi.responses import Response

app = FastAPI(title="Servidor ODK Qorilazo")

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip('/')
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()

def get_supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

def clean_val(val):
    if val is None or isinstance(val, dict):
        return ""
    return str(val).strip()

def clean_float(val):
    try:
        cleaned = clean_val(val)
        if cleaned:
            return float(cleaned)
    except Exception:
        pass
    return 0.0

def clean_date(val):
    s = clean_val(val)
    if s and len(s) >= 10:
        return s[:10]
    return datetime.now().strftime("%Y-%m-%d")

def normalizar_estado(val):
    v = clean_val(val).upper()
    if v in ["DEFECT", "DEFECTUOSO", "MALO"]:
        return "DEFECTUOSO"
    if v in ["OK", "BUENO"]:
        return "BUENO" if v == "BUENO" else "OK"
    if v in ["FALTA", "VENCE", "N/A"]:
        return v
    return "BUENO"

def obtener_categoria(k):
    if k.startswith("doc_"):
        return "DOCUMENTACIÓN"
    elif k.startswith("cabina_"):
        return "CABINA DE OPERACIÓN"
    elif k.startswith("motor_"):
        return "COMPARTIMIENTO DE MOTOR"
    elif k.startswith("seg_"):
        return "ELEMENTOS DE SEGURIDAD"
    elif k.startswith("herr_"):
        return "HERRAMIENTAS DE EQUIPO"
    return "GENERAL"

@app.get("/")
@app.head("/")
async def root():
    return {"status": "ok", "message": "Servidor ODK Qorilazo activo v37"}

# 1. Endpoint OpenRosa FormList (Versión 2026101904)
@app.get("/openrosa/formList")
async def form_list(request: Request):
    host_url = str(request.base_url).rstrip('/')
    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
    <xforms xmlns="http://openrosa.org/xforms/xformsList">
      <xform>
        <formID>checklist_guardia_qorilazo_v1</formID>
        <name>Check List Cambio de Guardia - Qorilazo</name>
        <majorMinorVersion>1</majorMinorVersion>
        <version>2026101904</version>
        <hash>md5:qorilazo2026v37</hash>
        <downloadUrl>{host_url}/openrosa/forms/checklist.xml</downloadUrl>
      </xform>
    </xforms>"""
    return Response(content=xml_content, media_type="text/xml", headers={"X-OpenRosa-Version": "1.0"})

# 2. Endpoint OpenRosa Download Form
@app.get("/openrosa/forms/checklist.xml")
async def download_form():
    if os.path.exists("Checklist_Cambio_Guardia_Qorilazo.xml"):
        with open("Checklist_Cambio_Guardia_Qorilazo.xml", "r", encoding="utf-8") as f:
            xml_data = f.read()
        return Response(content=xml_data, media_type="text/xml", headers={"X-OpenRosa-Version": "1.0"})
    return Response(status_code=404, content="Archivo XML no encontrado")

# 3. Endpoint OpenRosa Submission
@app.post("/openrosa/submission")
async def receive_submission(request: Request):
    try:
        form = await request.form()
        print("=== INICIO DE RECEPCION MULTIPART V37 ===")

        data = {}
        archivos_urls = []
        codigo_placa = "EQ"
        ts = int(time.time())

        # Recorrer todos los elementos enviados
        for key, value in form.items():
            if isinstance(value, UploadFile):
                await value.seek(0)
                file_bytes = await value.read()
                
                if key == "xml_submission_file" or value.filename.endswith(".xml"):
                    try:
                        parsed = xmltodict.parse(file_bytes)
                        data = parsed.get("data", {})
                        codigo_placa = clean_val(data.get("codigo_placa")) or "EQ"
                        print(f" -> XML procesado correctamente para Placa: {codigo_placa}")
                    except Exception as err_xml:
                        print(f" Error parseando XML: {err_xml}")
                else:
                    print(f" -> Procesando imagen/firma: '{key}' ({value.filename}) - {len(file_bytes)} bytes")
                    if len(file_bytes) > 0:
                        filename = f"{codigo_placa}_{ts}_{value.filename}"
                        upload_url = f"{SUPABASE_URL}/storage/v1/object/inspecciones_odk/{filename}"

                        st_headers = {
                            "apikey": SUPABASE_KEY,
                            "Authorization": f"Bearer {SUPABASE_KEY}",
                            "Content-Type": value.content_type or "image/png",
                            "x-upsert": "true"
                        }
                        res = requests.post(upload_url, headers=st_headers, data=file_bytes)
                        print(f"    [STORAGE HTTP STATUS]: {res.status_code}")

                        if res.status_code in [200, 201]:
                            public_url = f"{SUPABASE_URL}/storage/v1/object/public/inspecciones_odk/{filename}"
                            archivos_urls.append(public_url)
                            print(f"    [ÉXITO STORAGE]: {public_url}")
                        else:
                            print(f"    [ERROR STORAGE]: {res.text}")

        headers = get_supabase_headers()

        foto_combust = archivos_urls[0] if len(archivos_urls) > 0 else ""
        firma_operad = archivos_urls[1] if len(archivos_urls) > 1 else ""

        print(f"-> Foto Combustible URL: '{foto_combust}'")
        print(f"-> Firma Operador URL: '{firma_operad}'")

        # 1. Guardar en inspecciones_guardia
        payload_main = {
            "fecha_inspeccion": clean_date(data.get("fecha_inspeccion")),
            "guardia": clean_val(data.get("guardia")),
            "nombre_operador": clean_val(data.get("nombre_operador")),
            "dni_operador": clean_val(data.get("dni_operador")),
            "equipo": clean_val(data.get("equipo")),
            "marca": clean_val(data.get("marca")),
            "codigo_placa": codigo_placa,
            "km_hr": clean_float(data.get("km_hr")),
            "adblue": clean_val(data.get("adblue")),
            "observaciones_estado_equipo": clean_val(data.get("observaciones_estado_equipo")),
            "observaciones_adicionales": clean_val(data.get("observaciones_adicionales")),
            "foto_combustible_url": foto_combust,
            "foto_cabina_url": archivos_urls[2] if len(archivos_urls) > 2 else "",
            "foto_hallazgo_1_url": archivos_urls[3] if len(archivos_urls) > 3 else "",
            "foto_hallazgo_2_url": archivos_urls[4] if len(archivos_urls) > 4 else "",
            "firma_operador_url": firma_operad,
            "firma_supervisor_url": archivos_urls[5] if len(archivos_urls) > 5 else ""
        }

        res_db = requests.post(
            f"{SUPABASE_URL}/rest/v1/inspecciones_guardia", 
            headers=headers, 
            json=payload_main
        )

        inspeccion_id = None
        print(f"Status Inserción Principal: {res_db.status_code}")
        if res_db.status_code not in [200, 201]:
            print(f"-> Error Principal DB: {res_db.text}")
        else:
            inserted = res_db.json()
            if isinstance(inserted, list) and len(inserted) > 0:
                inspeccion_id = inserted[0].get("id")
                print(f"-> Registro principal guardado con ID: {inspeccion_id}")

        # 2. Inserción en inspeccion_detalles
        if inspeccion_id:
            payload_detalles = []
            prefix_keys = ["doc_", "cabina_", "motor_", "seg_", "herr_"]
            for k, v in data.items():
                if any(k.startswith(p) for p in prefix_keys) and not k.endswith("_url"):
                    payload_detalles.append({
                        "inspeccion_id": inspeccion_id,
                        "categoria": obtener_categoria(k),
                        "item_nombre": k,
                        "estado": normalizar_estado(v),
                        "fecha_vencimiento": None
                    })
            if payload_detalles:
                res_det = requests.post(f"{SUPABASE_URL}/rest/v1/inspeccion_detalles", headers=headers, json=payload_detalles)
                print(f"Status Inserción Detalles: {res_det.status_code}")

        # 3. Inserción en inspeccion_neumaticos
        if inspeccion_id:
            payload_neumaticos = []
            posiciones = [f"pos_{i}" for i in range(1, 11)] + ["pos_repuesto"]
            for pos in posiciones:
                mm_val = clean_float(data.get(f"{pos}_mm"))
                est_val = normalizar_estado(data.get(f"{pos}_est"))
                payload_neumaticos.append({
                    "inspeccion_id": inspeccion_id,
                    "posicion": pos,
                    "remanente_mm": mm_val,
                    "estado": est_val
                })
            if payload_neumaticos:
                res_neu = requests.post(f"{SUPABASE_URL}/rest/v1/inspeccion_neumaticos", headers=headers, json=payload_neumaticos)
                print(f"Status Inserción Neumáticos: {res_neu.status_code}")

    except Exception as e:
        print(f"Excepción en submission: {e}")

    # Respuesta OpenRosa OK
    response_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <openrosa-response xmlns="http://openrosa.org/xforms/response">
        <message nature="submit_success">Inspección recibida y registrada exitosamente.</message>
    </openrosa-response>"""

    return Response(
        content=response_xml, 
        status_code=201, 
        media_type="text/xml", 
        headers={"X-OpenRosa-Version": "1.0"}
    )
