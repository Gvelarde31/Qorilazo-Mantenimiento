import os
import time
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
    return {"status": "ok", "message": "Servidor ODK Qorilazo activo"}

# 1. Endpoint OpenRosa FormList (Versión 2026101830)
@app.get("/openrosa/formList")
async def form_list(request: Request):
    host_url = str(request.base_url).rstrip('/')
    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
    <xforms xmlns="http://openrosa.org/xforms/xformsList">
      <xform>
        <formID>checklist_guardia_qorilazo_v1</formID>
        <name>Check List Cambio de Guardia - Qorilazo</name>
        <majorMinorVersion>1</majorMinorVersion>
        <version>2026101830</version>
        <hash>md5:qorilazo2026v30</hash>
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
        xml_file = form.get("xml_submission_file")
        
        data = {}
        if xml_file:
            content = await xml_file.read()
            parsed = xmltodict.parse(content)
            data = parsed.get("data", {})

        headers = get_supabase_headers()
        codigo_placa = clean_val(data.get("codigo_placa")) or "EQ"
        ts = int(time.time())

        # Subida de fotografías y firmas a Supabase Storage con 'x-upsert'
        archivos_urls = []
        for key, value in form.items():
            if isinstance(value, UploadFile) and key != "xml_submission_file":
                try:
                    await value.seek(0)
                    file_bytes = await value.read()
                    print(f"-> Subiendo archivo '{key}': {len(file_bytes)} bytes")
                    
                    if len(file_bytes) > 0:
                        clean_fn = value.filename.replace(" ", "_")
                        filename = f"{codigo_placa}_{ts}_{clean_fn}"
                        upload_url = f"{SUPABASE_URL}/storage/v1/object/inspecciones_odk/{filename}"
                        
                        st_headers = {
                            "apikey": SUPABASE_KEY,
                            "Authorization": f"Bearer {SUPABASE_KEY}",
                            "Content-Type": value.content_type or "image/png",
                            "x-upsert": "true"
                        }
                        res = requests.post(upload_url, headers=st_headers, data=file_bytes)
                        print(f"   Status Storage ({key}): {res.status_code}")
                        
                        if res.status_code in [200, 201]:
                            public_url = f"{SUPABASE_URL}/storage/v1/object/public/inspecciones_odk/{filename}"
                            archivos_urls.append(public_url)
                            print(f"   [OK Storage] {public_url}")
                        else:
                            print(f"   [Error Storage] {res.status_code}: {res.text}")
                except Exception as err_file:
                    print(f"Excepción procesando {key}: {err_file}")

        # Asignación de URLs
        foto_combust = archivos_urls[0] if len(archivos_urls) > 0 else ""
        firma_operad = archivos_urls[1] if len(archivos_urls) > 1 else ""

        # 1. Registro Principal (inspecciones_guardia)
        payload_main = {
            "fecha_inspeccion": clean_val(data.get("fecha_inspeccion")),
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
        if res_db.status_code in [200, 201]:
            inserted = res_db.json()
            if isinstance(inserted, list) and len(inserted) > 0:
                inspeccion_id = inserted[0].get("id")
                print(f"-> Registro principal con ID: {inspeccion_id}")

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

    # Respuesta OpenRosa exitosa
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
