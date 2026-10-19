import os
import xmltodict
import requests
from fastapi import FastAPI, Request, Response, UploadFile
from fastapi.responses import Response

app = FastAPI(title="Servidor ODK Qorilazo")

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip('/')
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()

ESTADOS_VALIDOS = {"OK", "BUENO", "FALTA", "DEFECTUOSO", "DEFECT", "VENCE", "N/A"}

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
    estado_upper = clean_val(val).upper()
    if estado_upper in ESTADOS_VALIDOS:
        return estado_upper
    if estado_upper in ["NO APLICA", "NO_APLICA", "NONE", "NULL", ""]:
        return "N/A"
    return "BUENO"  # Valor por defecto seguro para el check constraint

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

# 1. Endpoint OpenRosa FormList (Versión 2026101825)
@app.get("/openrosa/formList")
async def form_list(request: Request):
    host_url = str(request.base_url).rstrip('/')
    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
    <xforms xmlns="http://openrosa.org/xforms/xformsList">
      <xform>
        <formID>checklist_guardia_qorilazo_v1</formID>
        <name>Check List Cambio de Guardia - Qorilazo</name>
        <majorMinorVersion>1</majorMinorVersion>
        <version>2026101825</version>
        <hash>md5:qorilazo2026v25</hash>
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

        # Subida de fotografías y firmas al Storage 'inspecciones_odk'
        archivos_subidos = []
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
                            archivos_subidos.append(public_url)
                            print(f"-> Imagen guardada en Storage: {public_url}")
                        else:
                            print(f"Error Storage {key} ({res.status_code}): {res.text}")
                except Exception as err_file:
                    print(f"Excepción subiendo {key}: {err_file}")

        # Asignación de URLs por orden de captura
        foto_comb_url = archivos_subidos[0] if len(archivos_subidos) > 0 else ""
        firma_oper_url = archivos_subidos[1] if len(archivos_subidos) > 1 else ""

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
            "foto_combustible_url": foto_comb_url,
            "foto_cabina_url": archivos_subidos[2] if len(archivos_subidos) > 2 else "",
            "foto_hallazgo_1_url": archivos_subidos[3] if len(archivos_subidos) > 3 else "",
            "foto_hallazgo_2_url": archivos_subidos[4] if len(archivos_subidos) > 4 else "",
            "firma_operador_url": firma_oper_url,
            "firma_supervisor_url": archivos_subidos[5] if len(archivos_subidos) > 5 else ""
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
                print(f"-> ID generado en Supabase: {inspeccion_id}")

        # 2. Inserción en inspeccion_detalles (normalizando 'estado' para cumplir con check constraint)
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
                if res_det.status_code not in [200, 201]:
                    print(f"-> DETALLE ERROR DETALLES: {res_det.text}")

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
                if res_neu.status_code not in [200, 201]:
                    print(f"-> DETALLE ERROR NEUMATICOS: {res_neu.text}")

    except Exception as e:
        print(f"Excepción en submission: {e}")

    # Respuesta OpenRosa exitosa para ODK Collect
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
