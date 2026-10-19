import os
import time
from datetime import datetime
import xmltodict
import requests
from fastapi import FastAPI, Request, Response, UploadFile

app = FastAPI(title="Servidor ODK Qorilazo - Producción")

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
    """Extrae texto plano de strings, números o dicts parseados por xmltodict."""
    if val is None:
        return ""
    if isinstance(val, dict):
        return str(val.get("#text", "")).strip()
    return str(val).strip()


def clean_float(val):
    try:
        cleaned = clean_val(val)
        if cleaned:
            return float(cleaned)
    except Exception:
        pass
    return None


def clean_date(val):
    s = clean_val(val)
    if s and len(s) >= 10:
        return s[:10]
    return datetime.now().strftime("%Y-%m-%d")


def normalizar_guardia(val):
    v = clean_val(val).upper()
    if v in ["ENTRANTE", "SALIENTE"]:
        return v
    return "ENTRANTE"


def normalizar_estado(val):
    v = clean_val(val).upper()
    if v in ["DEFECT", "DEFECTUOSO", "MALO"]:
        return "DEFECTUOSO"
    if v in ["OK", "BUENO"]:
        return "BUENO" if v == "BUENO" else "OK"
    if v in ["FALTA", "VENCE", "N/A"]:
        return v
    return "OK"


def normalizar_estado_neumatico(val):
    v = clean_val(val).upper()
    if v in ["DEFECT", "DEFECTUOSO", "MALO"]:
        return "DEFECTUOSO"
    if v in ["OK", "BUENO"]:
        return "BUENO"
    return "N/A"


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
    return "DOCUMENTACIÓN"


def aplanar_diccionario_xml(d):
    """
    Si el XML viene envuelto en nodos como <data id="..."> o <checklist_guardia...>,
    extrae el diccionario interno real que contiene los campos del formulario.
    """
    if not isinstance(d, dict):
        return {}
    
    # Buscar claves que no sean atributos de XML (que empiezan con @)
    valid_keys = [k for k in d.keys() if not k.startswith("@")]
    
    # Si hay una sola clave raíz envolvente (ej. 'data' o 'checklist_guardia_qorilazo_v1')
    if len(valid_keys) == 1 and isinstance(d[valid_keys[0]], dict):
        return aplanar_diccionario_xml(d[valid_keys[0]])
    
    return d


@app.get("/")
@app.head("/")
async def root():
    return {"status": "ok", "message": "Servidor ODK Qorilazo Activo v40"}


# 1. Endpoint OpenRosa FormList
@app.get("/openrosa/formList")
@app.head("/openrosa/formList")
async def form_list(request: Request):
    if request.method == "HEAD":
        return Response(status_code=204, headers={"X-OpenRosa-Version": "1.0"})

    host_url = str(request.base_url).rstrip('/')
    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
    <xforms xmlns="http://openrosa.org/xforms/xformsList">
      <xform>
        <formID>checklist_guardia_qorilazo_v1</formID>
        <name>Check List Cambio de Guardia - Qorilazo</name>
        <majorMinorVersion>1</majorMinorVersion>
        <version>2026101904</version>
        <hash>md5:qorilazo2026v40</hash>
        <downloadUrl>{host_url}/openrosa/forms/checklist.xml</downloadUrl>
      </xform>
    </xforms>"""
    return Response(content=xml_content, media_type="text/xml", headers={"X-OpenRosa-Version": "1.0"})


# 2. Endpoint OpenRosa Download Form
@app.get("/openrosa/forms/checklist.xml")
@app.head("/openrosa/forms/checklist.xml")
async def download_form(request: Request):
    if request.method == "HEAD":
        return Response(status_code=204, headers={"X-OpenRosa-Version": "1.0"})

    if os.path.exists("Checklist_Cambio_Guardia_Qorilazo.xml"):
        with open("Checklist_Cambio_Guardia_Qorilazo.xml", "r", encoding="utf-8") as f:
            xml_data = f.read()
        return Response(content=xml_data, media_type="text/xml", headers={"X-OpenRosa-Version": "1.0"})
    return Response(status_code=404, content="Archivo XML no encontrado")


# 3. Endpoint OpenRosa Submission
@app.api_route("/openrosa/submission", methods=["GET", "HEAD", "POST"])
async def receive_submission(request: Request):
    if request.method in ["GET", "HEAD"]:
        return Response(status_code=204, headers={"X-OpenRosa-Version": "1.0"})

    try:
        form = await request.form()
        print("=== INICIO DE RECEPCION MULTIPART V40 ===")

        data = {}
        uploaded_media_map = {}
        codigo_placa = "EQ"
        ts = int(time.time())

        # Pasada 1: Identificación robusta del XML y subida de imágenes
        for key, value in form.items():
            if isinstance(value, UploadFile):
                await value.seek(0)
                file_bytes = await value.read()

                if len(file_bytes) == 0:
                    continue

                # Intentar parsear como XML sin importar el nombre del parámetro
                is_xml = False
                try:
                    text_preview = file_bytes[:100].decode("utf-8", errors="ignore").strip()
                    if text_preview.startswith("<?xml") or text_preview.startswith("<"):
                        parsed = xmltodict.parse(file_bytes)
                        data = aplanar_diccionario_xml(parsed)
                        codigo_placa = clean_val(data.get("codigo_placa")) or "EQ"
                        is_xml = True
                        print(f" -> [ÉXITO DE PARSEO XML] Operador: '{data.get('nombre_operador')}', Placa: '{codigo_placa}'")
                except Exception:
                    is_xml = False

                # Si no es XML, es una imagen/firma multimedia
                if not is_xml:
                    filename = f"{codigo_placa}_{ts}_{value.filename}"
                    upload_url = f"{SUPABASE_URL}/storage/v1/object/inspecciones_odk/{filename}"

                    st_headers = {
                        "apikey": SUPABASE_KEY,
                        "Authorization": f"Bearer {SUPABASE_KEY}",
                        "Content-Type": value.content_type or "image/png",
                        "x-upsert": "true"
                    }
                    res = requests.post(upload_url, headers=st_headers, data=file_bytes)

                    if res.status_code in [200, 201]:
                        public_url = f"{SUPABASE_URL}/storage/v1/object/public/inspecciones_odk/{filename}"
                        uploaded_media_map[value.filename] = public_url
                        uploaded_media_map[key] = public_url
                        print(f"    [STORAGE ÉXITO]: {public_url}")
                    else:
                        print(f"    [STORAGE ERROR]: {res.text}")

        headers = get_supabase_headers()

        def resolve_url(field_name):
            val_in_xml = clean_val(data.get(field_name))
            if val_in_xml and val_in_xml in uploaded_media_map:
                return uploaded_media_map[val_in_xml]
            if field_name in uploaded_media_map:
                return uploaded_media_map[field_name]
            return None

        # Pasada 2: Inserción en `inspecciones_guardia`
        payload_main = {
            "fecha_inspeccion": clean_date(data.get("fecha_inspeccion")),
            "guardia": normalizar_guardia(data.get("guardia")),
            "nombre_operador": clean_val(data.get("nombre_operador")),
            "dni_operador": clean_val(data.get("dni_operador")),
            "equipo": clean_val(data.get("equipo")),
            "marca": clean_val(data.get("marca")),
            "codigo_placa": codigo_placa,
            "km_hr": clean_float(data.get("km_hr")),
            "adblue": clean_val(data.get("adblue")),
            "observaciones_estado_equipo": clean_val(data.get("observaciones_estado_equipo")),
            "observaciones_adicionales": clean_val(data.get("observaciones_adicionales")),
            "foto_combustible_url": resolve_url("foto_combustible"),
            "foto_cabina_url": resolve_url("foto_cabina"),
            "foto_hallazgo_1_url": resolve_url("foto_hallazgo_1"),
            "foto_hallazgo_2_url": resolve_url("foto_hallazgo_2"),
            "firma_operador_url": resolve_url("firma_operador"),
            "firma_supervisor_url": resolve_url("firma_supervisor")
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

        # Pasada 3: Inserción en `inspeccion_detalles`
        if inspeccion_id:
            payload_detalles = []
            prefix_keys = ("doc_", "cabina_", "motor_", "seg_", "herr_")
            
            for k, raw_v in data.items():
                if k.startswith(prefix_keys) and not k.endswith(("_url", "_otros")):
                    val_str = clean_val(raw_v)
                    if val_str:
                        payload_detalles.append({
                            "inspeccion_id": inspeccion_id,
                            "categoria": obtener_categoria(k),
                            "item_nombre": k,
                            "estado": normalizar_estado(val_str),
                            "fecha_vencimiento": None
                        })

            if payload_detalles:
                res_det = requests.post(
                    f"{SUPABASE_URL}/rest/v1/inspeccion_detalles",
                    headers=headers,
                    json=payload_detalles
                )
                print(f"Status Inserción Detalles: {res_det.status_code} ({len(payload_detalles)} ítems registrados)")
            else:
                print("-> No se encontraron ítems de detalles para registrar.")

        # Pasada 4: Inserción en `inspeccion_neumaticos`
        if inspeccion_id:
            payload_neumaticos = []
            posiciones = [f"pos_{i}" for i in range(1, 11)] + ["pos_repuesto"]
            for pos in posiciones:
                mm_val = clean_float(data.get(f"{pos}_mm"))
                est_val = normalizar_estado_neumatico(data.get(f"{pos}_est"))
                payload_neumaticos.append({
                    "inspeccion_id": inspeccion_id,
                    "posicion": pos,
                    "remanente_mm": mm_val,
                    "estado": est_val
                })
            if payload_neumaticos:
                res_neu = requests.post(
                    f"{SUPABASE_URL}/rest/v1/inspeccion_neumaticos",
                    headers=headers,
                    json=payload_neumaticos
                )
                print(f"Status Inserción Neumáticos: {res_neu.status_code}")

    except Exception as e:
        print(f"Excepción en submission: {e}")

    # Respuesta OpenRosa
    response_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <openrosa-response xmlns="http://openrosa.org/xforms/response">
        <message nature="submit_success">Inspección registrada exitosamente.</message>
    </openrosa-response>"""

    return Response(
        content=response_xml,
        status_code=201,
        media_type="text/xml",
        headers={"X-OpenRosa-Version": "1.0"}
    )
