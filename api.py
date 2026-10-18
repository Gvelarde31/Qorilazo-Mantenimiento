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
    "Content-Type": "application/json"
}

def obtener_datos_supabase(tabla):
    try:
        url = f"{SUPABASE_URL}/rest/v1/{tabla}?select=*"
        res = requests.get(url, headers=HEADERS_SUPABASE, timeout=10)
        print(f"DEBUG Supabase {tabla} - Status Code: {res.status_code}")
        if res.status_code == 200:
            datos = res.json()
            print(f"DEBUG Supabase {tabla} - Cantidad registros: {len(datos)}")
            return datos
        else:
            print(f"ERROR Supabase {tabla}: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"EXCEPCION Supabase {tabla}: {e}")
    return []

# 1. Endpoint OpenRosa FormList (Versión 2026101810)
@app.get("/openrosa/formList")
async def form_list(request: Request):
    host_url = str(request.base_url).rstrip('/')
    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
    <xforms xmlns="http://openrosa.org/xforms/xformsList">
      <xform>
        <formID>checklist_guardia_qorilazo_v1</formID>
        <name>Check List Cambio de Guardia - Qorilazo</name>
        <majorMinorVersion>1</majorMinorVersion>
        <version>2026101810</version>
        <hash>md5:qorilazo2026v10</hash>
        <downloadUrl>{host_url}/openrosa/forms/checklist.xml</downloadUrl>
      </xform>
    </xforms>"""
    return Response(content=xml_content, media_type="text/xml", headers={"X-OpenRosa-Version": "1.0"})

# 2. Endpoint OpenRosa Download Form
@app.get("/openrosa/forms/checklist.xml")
async def download_form():
    operadores = obtener_datos_supabase("operadores")
    lista_maestra = obtener_datos_supabase("lista_maestra")

    # Mapeo de Operadores (buscando en la columna 'nombre_apellidos')
    items_operadores = ""
    for op in operadores:
        nombre = (op.get("nombre_apellidos") or op.get("nombre") or op.get("operador") or "").strip()
        if nombre:
            items_operadores += f"<item><label>{nombre}</label><value>{nombre}</value></item>\n"

    # Mapeo de Placas (buscando en la columna 'placa')
    items_placas = ""
    for eq in lista_maestra:
        placa = (eq.get("placa") or eq.get("codigo_placa") or eq.get("codigo_interno") or "").strip()
        if placa:
            items_placas += f"<item><label>{placa}</label><value>{placa}</value></item>\n"

    # Respaldos en caso de consulta vacía
    if not items_operadores:
        items_operadores = "<item><label>OPERADOR GENERAL</label><value>OPERADOR GENERAL</value></item>\n"
    if not items_placas:
        items_placas = "<item><label>EQUIPO PRUEBA (EQ-001)</label><value>EQ-001</value></item>\n"

    if os.path.exists("Checklist_Cambio_Guardia_Qorilazo.xml"):
        with open("Checklist_Cambio_Guardia_Qorilazo.xml", "r", encoding="utf-8") as f:
            xml_data = f.read()

        xml_data = xml_data.replace("<!-- ITEMS_OPERADORES -->", items_operadores)
        xml_data = xml_data.replace("<!-- ITEMS_PLACAS -->", items_placas)

        return Response(content=xml_data, media_type="text/xml", headers={"X-OpenRosa-Version": "1.0"})

    return Response(status_code=404, content="Archivo XML no encontrado")

# 3. Endpoint OpenRosa Submission
@app.post("/openrosa/submission")
async def receive_submission(request: Request):
    form = await request.form()
    xml_file = form.get("xml_submission_file")
    if not xml_file:
        return Response(status_code=400)

    content = await xml_file.read()
    data_dict = xmltodict.parse(content).get("data", {})

    urls_archivos = {}
    for key, value in form.items():
        if isinstance(value, UploadFile) and key != "xml_submission_file":
            file_bytes = await value.read()
            filename = f"{data_dict.get('codigo_placa', 'EQ')}_{value.filename}"
            upload_url = f"{SUPABASE_URL}/storage/v1/object/inspecciones_odk/{filename}"
            st_headers = {
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": value.content_type or "image/png"
            }
            res = requests.post(upload_url, headers=st_headers, data=file_bytes)
            if res.status_code in [200, 201]:
                urls_archivos[key] = f"{SUPABASE_URL}/storage/v1/object/public/inspecciones_odk/{filename}"

    payload = {
        "fecha_inspeccion": data_dict.get("fecha_inspeccion"),
        "guardia": data_dict.get("guardia"),
        "codigo_placa": data_dict.get("codigo_placa"),
        "km_hr": float(data_dict.get("km_hr", 0) or 0),
        "nombre_operador": data_dict.get("nombre_operador"),
        "dni_operador": data_dict.get("dni_operador"),
        "foto_combustible_url": urls_archivos.get("foto_combustible", ""),
        "foto_cabina_url": urls_archivos.get("foto_cabina", ""),
        "foto_hallazgo_1_url": urls_archivos.get("foto_hallazgo_1"),
        "foto_hallazgo_2_url": urls_archivos.get("foto_hallazgo_2"),
        "firma_operador_url": urls_archivos.get("firma_operador", ""),
        "firma_supervisor_url": urls_archivos.get("firma_supervisor")
    }

    requests.post(f"{SUPABASE_URL}/rest/v1/inspecciones_guardia", headers=HEADERS_SUPABASE, json=payload)

    response_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <openrosa-response xmlns="http://openrosa.org/xforms/response">
        <message nature="submit_success">Inspección recibida correctamente.</message>
    </openrosa-response>"""

    return Response(content=response_xml, status_code=201, media_type="text/xml", headers={"X-OpenRosa-Version": "1.0"})
