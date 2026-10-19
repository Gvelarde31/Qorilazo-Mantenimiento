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

# 1. Endpoint OpenRosa FormList (Versión 2026101819)
@app.get("/openrosa/formList")
async def form_list(request: Request):
    host_url = str(request.base_url).rstrip('/')
    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
    <xforms xmlns="http://openrosa.org/xforms/xformsList">
      <xform>
        <formID>checklist_guardia_qorilazo_v1</formID>
        <name>Check List Cambio de Guardia - Qorilazo</name>
        <majorMinorVersion>1</majorMinorVersion>
        <version>2026101819</version>
        <hash>md5:qorilazo2026v19</hash>
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

# 3. Endpoint OpenRosa Submission (Guarda en las 3 tablas + sube URLs)
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

        # Captura y subida flexible de fotografías/firmas
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
                            
                            # Mapeo por coincidencia de nombre de archivo ODK
                            fn_lower = value.filename.lower()
                            if "combustible" in fn_lower or "combustible" in key:
                                urls_archivos["foto_combustible"] = public_url
                            elif "cabina" in fn_lower or "cabina" in key:
                                urls_archivos["foto_cabina"] = public_url
                            elif "hallazgo_1" in fn_lower or "hallazgo_1" in key:
                                urls_archivos["foto_hallazgo_1"] = public_url
                            elif "hallazgo_2" in fn_lower or "hallazgo_2" in key:
                                urls_archivos["foto_hallazgo_2"] = public_url
                            elif "firma_operador" in fn_lower or "firma_operador" in key:
                                urls_archivos["firma_operador"] = public_url
                            elif "firma_supervisor" in fn_lower or "firma_supervisor" in key:
                                urls_archivos["firma_supervisor"] = public_url
                        else:
                            print(f"Error Storage {key} ({res.status_code}): {res.text}")
                except Exception as err_file:
                    print(f"Excepción subiendo {key}: {err_file}")

        # 1. Inserción Principal: inspecciones_guardia
        payload_main = {
            "fecha_inspeccion": clean_val(data.get("fecha_inspeccion")),
            "guardia": clean_val(data.get("guardia")),
            "nombre_operador": clean_val(data.get("nombre_operador")),
            "equipo": clean_val(data.get("equipo")),
            "marca": clean_val(data.get("marca")),
            "codigo_placa": codigo_placa,
            "km_hr": clean_float(data.get("km_hr")),
            "adblue": clean_val(data.get("adblue")),
            "observaciones_estado_equipo": clean_val(data.get("observaciones_estado_equipo")),
            "observaciones_adicionales": clean_val(data.get("observaciones_adicionales")),
            "foto_combustible_url": urls_archivos.get("foto_combustible") or urls_archivos.get("foto_combustible_url", ""),
            "foto_cabina_url": urls_archivos.get("foto_cabina") or urls_archivos.get("foto_cabina_url", ""),
            "foto_hallazgo_1_url": urls_archivos.get("foto_hallazgo_1") or urls_archivos.get("foto_hallazgo_1_url", ""),
            "foto_hallazgo_2_url": urls_archivos.get("foto_hallazgo_2") or urls_archivos.get("foto_hallazgo_2_url", ""),
            "firma_operador_url": urls_archivos.get("firma_operador") or urls_archivos.get("firma_operador_url", ""),
            "firma_supervisor_url": urls_archivos.get("firma_supervisor") or urls_archivos.get("firma_supervisor_url", "")
        }

        res_db = requests.post(
            f"{SUPABASE_URL}/rest/v1/inspecciones_guardia", 
            headers=headers, 
            json=payload_main
        )

        inspeccion_id = None
        if res_db.status_code in [200, 201]:
            inserted_records = res_db.json()
            if isinstance(inserted_records, list) and len(inserted_records) > 0:
                inspeccion_id = inserted_records[0].get("id")

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
                requests.post(f"{SUPABASE_URL}/rest/v1/inspeccion_detalles", headers=headers, json=payload_detalles)

        # 3. Inserción en Tabla Secundaria: inspeccion_neumaticos
        if inspeccion_id:
            payload_neumaticos = []
            posiciones = [f"pos_{i}" for i in range(1, 11)] + ["pos_repuesto"]
            for pos in posiciones:
                mm_val = clean_float(data.get(f"{pos}_mm"))
                est_val = clean_val(data.get(f"{pos}_est")) or "BUENO"
                if mm_val > 0 or est_val:
                    payload_neumaticos.append({
                        "inspeccion_id": inspeccion_id,
                        "posicion": pos,
                        "cocada_mm": mm_val,
                        "estado": est_val
                    })
            if payload_neumaticos:
                requests.post(f"{SUPABASE_URL}/rest/v1/inspeccion_neumaticos", headers=headers, json=payload_neumaticos)

    except Exception as e:
        print(f"Excepción en submission: {e}")

    # Respuesta OpenRosa OK
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
