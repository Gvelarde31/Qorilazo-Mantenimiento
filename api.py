import os
import xmltodict
import requests
from fastapi import FastAPI, Request, Response, UploadFile
from fastapi.responses import Response

app = FastAPI(title="Servidor ODK Qorilazo")

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip('/')
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()

HEADERS_SUPABASE = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

def clean_val(val):
    if val is None:
        return ""
    if isinstance(val, dict):
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

# 1. Endpoint OpenRosa FormList (Versión 2026101813)
@app.get("/openrosa/formList")
async def form_list(request: Request):
    host_url = str(request.base_url).rstrip('/')
    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
    <xforms xmlns="http://openrosa.org/xforms/xformsList">
      <xform>
        <formID>checklist_guardia_qorilazo_v1</formID>
        <name>Check List Cambio de Guardia - Qorilazo</name>
        <majorMinorVersion>1</majorMinorVersion>
        <version>2026101813</version>
        <hash>md5:qorilazo2026v13</hash>
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

# 3. Endpoint OpenRosa Submission (Con foto_combustible_url incluida)
@app.post("/openrosa/submission")
async def receive_submission(request: Request):
    try:
        form = await request.form()
        xml_file = form.get("xml_submission_file")
        if not xml_file:
            return Response(status_code=400, content="Falta archivo XML")

        content = await xml_file.read()
        parsed = xmltodict.parse(content)
        data = parsed.get("data", {})

        # Subida de imágenes y firmas al Storage 'inspecciones_odk'
        urls_archivos = {}
        for key, value in form.items():
            if isinstance(value, UploadFile) and key != "xml_submission_file":
                file_bytes = await value.read()
                if len(file_bytes) > 0:
                    codigo_placa = clean_val(data.get("codigo_placa")) or "EQ"
                    filename = f"{codigo_placa}_{value.filename}"
                    upload_url = f"{SUPABASE_URL}/storage/v1/object/inspecciones_odk/{filename}"
                    
                    st_headers = {
                        "apikey": SUPABASE_KEY,
                        "Authorization": f"Bearer {SUPABASE_KEY}",
                        "Content-Type": value.content_type or "image/png"
                    }
                    res = requests.post(upload_url, headers=st_headers, data=file_bytes)
                    if res.status_code in [200, 201]:
                        urls_archivos[key] = f"{SUPABASE_URL}/storage/v1/object/public/inspecciones_odk/{filename}"

        # Mapeo completo asegurando foto_combustible_url
        payload = {
            "fecha_inspeccion": clean_val(data.get("fecha_inspeccion")),
            "guardia": clean_val(data.get("guardia")),
            "nombre_operador": clean_val(data.get("nombre_operador")),
            "equipo": clean_val(data.get("equipo")),
            "marca": clean_val(data.get("marca")),
            "codigo_placa": clean_val(data.get("codigo_placa")),
            "km_hr": clean_float(data.get("km_hr")),
            "adblue": clean_val(data.get("adblue")),
            "observaciones_estado_equipo": clean_val(data.get("observaciones_estado_equipo")),
            "observaciones_adicionales": clean_val(data.get("observaciones_adicionales")),
            
            # Se incluyen todas las URLs de imágenes (incluso si son vacías)
            "foto_combustible_url": urls_archivos.get("foto_combustible", ""),
            "foto_cabina_url": urls_archivos.get("foto_cabina", ""),
            "foto_hallazgo_1_url": urls_archivos.get("foto_hallazgo_1", ""),
            "foto_hallazgo_2_url": urls_archivos.get("foto_hallazgo_2", ""),
            "firma_operador_url": urls_archivos.get("firma_operador", ""),
            "firma_supervisor_url": urls_archivos.get("firma_supervisor", "")
        }

        # Guardar inspección en Supabase
        res_db = requests.post(
            f"{SUPABASE_URL}/rest/v1/inspecciones_guardia", 
            headers=HEADERS_SUPABASE, 
            json=payload
        )

        if res_db.status_code not in [200, 201]:
            print(f"Error Supabase DB: {res_db.status_code} - {res_db.text}")

        # Respuesta estándar OpenRosa
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

    except Exception as e:
        print(f"Excepción en submission: {e}")
        return Response(status_code=500, content=f"Error interno: {str(e)}")
