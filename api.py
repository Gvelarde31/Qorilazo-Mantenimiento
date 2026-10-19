import os
import time
from datetime import datetime
import xmltodict
import requests
from fastapi import FastAPI, Request, Response, UploadFile

app = FastAPI(title="Servidor ODK Qorilazo - Producción V41")

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


def aplanar_dict(d):
    """Extrae el diccionario plano interno sin importar la clave raíz."""
    if not isinstance(d, dict):
        return {}
    keys = [k for k in d.keys() if not k.startswith("@")]
    if len(keys) == 1 and isinstance(d[keys[0]], dict):
        return aplanar_dict(d[keys[0]])
    return d


@app.get("/")
@app.head("/")
async def root():
    return {"status": "ok", "message": "Servidor ODK Qorilazo Activo v41"}


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
        <hash>md5:qorilazo2026v41</hash>
        <downloadUrl>{host_url}/openrosa/forms/checklist.xml</downloadUrl>
      </xform>
    </xforms>"""
    return Response(content=xml_content, media_type="text/xml", headers={"X-OpenRosa-Version": "1.0"})


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


@app.api_route("/openrosa/submission", methods=["GET", "HEAD", "POST"])
async def receive_submission(request: Request):
    if request.method in ["GET", "HEAD"]:
        return Response(status_code=204, headers={"X-OpenRosa-Version": "1.0"})

    try:
        form = await request.form()
        print("\n=== INICIO DE RECEPCION MULTIPART V41 ===")

        data = {}
        uploaded_media_map = {}
        codigo_placa = "EQ"
        ts = int(time.time())

        # 1. PARSEAR CUALQUIER ELEMENTO DEL MULTIPART
        for key, value in form.items():
            file_bytes = b""
            filename_attr = ""
            content_type_attr = "image/png"

            if isinstance(value, UploadFile):
                await value.seek(0)
                file_bytes = await value.read()
                filename_attr = value.filename or key
                content_type_attr = value.content_type or "image/png"
            elif isinstance(value, str):
                file_bytes = value.encode("utf-8")
                filename_attr = key

            if not file_bytes:
                continue

            # Intentar parsear como XML
            parsed_ok = False
            try:
                parsed_dict = xmltodict.parse(file_bytes)
                data = aplanar_dict(parsed_dict)
                codigo_placa = clean_val(data.get("codigo_placa")) or "EQ"
                parsed_ok = True
                print(f" -> [ÉXITO PARSEO XML]: Placa='{codigo_placa}', Operador='{data.get('nombre_operador')}'")
                print(f" -> Total claves extraídas del XML: {len(data)}")
            except Exception:
                parsed_ok = False

            # Si no es XML, subir como archivo multimedia a Storage
            if not parsed_ok and isinstance(value, UploadFile):
                fname = f"{codigo_placa}_{ts}_{filename_attr}"
                upload_url = f"{SUPABASE_URL}/storage/v1/object/inspecciones_odk/{fname}"

                st_headers = {
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": content_type_attr,
                    "x-upsert": "true"
                }
                res = requests.post(upload_url, headers=st_headers, data=file_bytes)

                if res.status_code in [200, 201]:
                    public_url = f"{SUPABASE_URL}/storage/v1/object/public/inspecciones_odk/{fname}"
                    uploaded_media_map[filename_attr] = public_url
                    uploaded_media_map[key] = public_url
                    print(f"    [STORAGE ÉXITO]: {public_url}")

        headers = get_supabase_headers()

        def resolve_url(field_name):
            val_in_xml = clean_val(data.get(field_name))
            if val_in_xml and val_in_xml in uploaded_media_map:
                return uploaded_media_map[val_in_xml]
            if field_name in uploaded_media_map:
                return uploaded_media_map[field_name]
            return None

        # 2. INSERCIÓN EN inspecciones_guardia
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
        if res_db.status_code in [200, 201]:
            inserted = res_db.json()
            if isinstance(inserted, list) and len(inserted) > 0:
                inspeccion_id = inserted[0].get("id")
                print(f"-> Registro principal guardado con ID: {inspeccion_id}")
        else:
            print(f"-> Error DB Principal: {res_db.text}")

        # 3. INSERCIÓN EN inspeccion_detalles
        if inspeccion_id:
            payload_detalles = []
            prefix_keys = ("doc_", "cabina_", "motor_", "seg_", "herr_")

            for k, raw_v in data.items():
                if k.startswith(prefix_keys) and not k.endswith(("_url", "_otros")):
                    val_str = clean_val(raw_v)
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
                print(f"Status Inserción Detalles: {res_det.status_code} ({len(payload_detalles)} registros enviados)")
            else:
                print("-> No se encontraron claves con prefijos de detalle en el XML.")

        # 4. INSERCIÓN EN inspeccion_neumaticos
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
