import os
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

@app.get("/")
@app.head("/")
async def root():
    return {"status": "ok", "message": "Servidor ODK Qorilazo activo"}

# 1. Endpoint OpenRosa FormList (Versión 2026101820)
@app.get("/openrosa/formList")
async def form_list(request: Request):
    host_url = str(request.base_url).rstrip('/')
    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
    <xforms xmlns="http://openrosa.org/xforms/xformsList">
      <xform>
        <formID>checklist_guardia_qorilazo_v1</formID>
        <name>Check List Cambio de Guardia - Qorilazo</name>
        <majorMinorVersion>1</majorMinorVersion>
        <version>2026101820</version>
        <hash>md5:qorilazo2026v20</hash>
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

# 3. Endpoint OpenRosa Submission (Procesamiento completo de las 3 tablas)
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

        # Captura y subida de imágenes/firmas al Storage 'inspecciones_odk'
        urls_archivos = {}
        for key, value in form.items():
            if isinstance(value, UploadFile) and key != "xml_submission_file":
                try:
                    file_bytes = await value.read()
                    if len(file_bytes) > 0:
                        filename = f"{codigo_placa}_{value.filename}"
                        upload_url = f"{SUPABASE_URL}/storage/v1/object/inspecciones_odk/{filename}"
                        
                        st_headers = {
                            "apikey": SUPABASE_KEY,
                            "Authorization": f"Bearer {SUPABASE_KEY}",
                            "Content-Type": value.content_type or "image/png"
                        }
                        res = requests.post(upload_url, headers=st_headers, data=file_bytes)
                        if res.status_code in [200, 201]:
                            public_url = f"{SUPABASE_URL}/storage/v1/object/public/inspecciones_odk/{filename}"
                            urls_archivos[key] = public_url
                            print(f"-> Imagen subida {key}: {public_url}")
                        else:
                            print(f"-> Error subiendo {key} ({res.status_code}): {res.text}")
                except Exception as err_file:
                    print(f"-> Excepción subiendo {key}: {err_file}")

        # 1. Registro Principal: inspecciones_guardia (incluyendo DNI y URLs de imágenes)
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
            "foto_combustible_url": urls_archivos.get("foto_combustible", ""),
            "foto_cabina_url": urls_archivos.get("foto_cabina", ""),
            "foto_hallazgo_1_url": urls_archivos.get("foto_hallazgo_1", ""),
            "foto_hallazgo_2_url": urls_archivos.get("foto_hallazgo_2", ""),
            "firma_operador_url": urls_archivos.get("firma_operador", ""),
            "firma_supervisor_url": urls_archivos.get("firma_supervisor", "")
        }

        res_db = requests.post(
            f"{SUPABASE_URL}/rest/v1/inspecciones_guardia", 
            headers=headers, 
            json=payload_main
        )

        inspeccion_id = None
        print(f"Respuesta Principal DB Status: {res_db.status_code}")
        if res_db.status_code in [200, 201]:
            inserted_records = res_db.json()
            if isinstance(inserted_records, list) and len(inserted_records) > 0:
                inspeccion_id = inserted_records[0].get("id")
                print(f"-> Inspección creada con ID: {inspeccion_id}")

        # 2. Inserción en Tabla Secundaria: inspeccion_detalles
        if inspeccion_id:
            payload_detalles = []
            prefix_keys = ["doc_", "cabina_", "motor_", "seg_", "herr_"]
            for k, v in data.items():
                if any(k.startswith(p) for p in prefix_keys) and not k.endswith("_url"):
                    payload_detalles.append({
                        "inspeccion_id": inspeccion_id,
                        "item_nombre": k,
                        "estado": clean_val(v)
                    })
            if payload_detalles:
                res_det = requests.post(f"{SUPABASE_URL}/rest/v1/inspeccion_detalles", headers=headers, json=payload_detalles)
                print(f"Respuesta Detalles DB Status: {res_det.status_code}")

        # 3. Inserción en Tabla Secundaria: inspeccion_neumaticos
        if inspeccion_id:
            payload_neumaticos = []
            posiciones = [f"pos_{i}" for i in range(1, 11)] + ["pos_repuesto"]
            for pos in posiciones:
                mm_val = clean_float(data.get(f"{pos}_mm"))
                est_val = clean_val(data.get(f"{pos}_est")) or "BUENO"
                payload_neumaticos.append({
                    "inspeccion_id": inspeccion_id,
                    "posicion": pos,
                    "cocada_mm": mm_val,
                    "estado": est_val
                })
            if payload_neumaticos:
                res_neu = requests.post(f"{SUPABASE_URL}/rest/v1/inspeccion_neumaticos", headers=headers, json=payload_neumaticos)
                print(f"Respuesta Neumáticos DB Status: {res_neu.status_code}")

    except Exception as e:
        print(f"Excepción en submission: {e}")

    # Respuesta OpenRosa OK para ODK Collect
    response_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <openrosa-response xmlns="http://openrosa.org/xforms/response">
        <message nature="submit_success">Inspección recibida y procesada.</message>
    </openrosa-response>"""

    return Response(
        content=response_xml, 
        status_code=201, 
        media_type="text/xml", 
        headers={"X-OpenRosa-Version": "1.0"}
    )
