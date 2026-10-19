import os
import time
import io
from datetime import datetime
import xmltodict
import requests
from fastapi import FastAPI, Request, Response

app = FastAPI(title="Servidor ODK Qorilazo - Producción V42")

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
    """Extrae recursivamente el diccionario real de datos sin importar envoltorios XML."""
    if not isinstance(d, dict):
        return {}
    
    # Filtrar atributos XML (@id, @version, etc.)
    keys = [k for k in d.keys() if not k.startswith("@")]
    
    # Si la raíz es una envolvente (ej. <data> o <checklist_guardia_qorilazo_v1>)
    if len(keys) == 1 and isinstance(d[keys[0]], dict):
        return aplanar_dict(d[keys[0]])
    
    return d


@app.get("/")
@app.head("/")
async def root():
    return {"status": "ok", "message": "Servidor ODK Qorilazo Activo v42"}


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
        <hash>md5:qorilazo2026v42</hash>
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
        print("\n=== INICIO DE RECEPCION MULTIPART V42 ===")
        form = await request.form()

        data = {}
        uploaded_media_map = {}
        codigo_placa = "EQ"
        ts = int(time.time())

        # Colección de todas las partes binarias recibidas
        binary_parts = []

        for key, value in form.items():
            file_bytes = b""
            filename_attr = key
            content_type_attr = "application/octet-stream"

            if hasattr(value, "read"):
                await value.seek(0)
                file_bytes = await value.read()
                filename_attr = getattr(value, "filename", key) or key
                content_type_attr = getattr(value, "content_type", "image/png") or "image/png"
            elif isinstance(value, str):
                file_bytes = value.encode("utf-8")

            if file_bytes:
                binary_parts.append({
                    "key": key,
                    "filename": filename_attr,
                    "content_type": content_type_attr,
                    "bytes": file_bytes,
                    "value_obj": value
                })

        # 1. EVALUAR Y PARSEAR EL XML PRIMERO
        xml_encontrado = False
        for part in binary_parts:
            b = part["bytes"]
            try:
                # Verificar si es XML intentando parsear con xmltodict
                parsed = xmltodict.parse(b)
                data = aplanar_dict(parsed)
                
                # Verificar si pudimos extraer el código de placa u otros campos del formulario
                if data and isinstance(data, dict):
                    codigo_placa = clean_val(data.get("codigo_placa")) or "EQ"
                    xml_encontrado = True
                    print(f" -> [ÉXITO PARSEO XML]: Placa='{codigo_placa}', Operador='{data.get('nombre_operador')}', Guardia='{data.get('guardia')}'")
                    print(f" -> Total de campos leídos del XML: {len(data)}")
                    break
            except Exception:
                continue

        if not xml_encontrado:
            print(" -> [ADVERTENCIA CRÍTICA]: No se pudo identificar ni parsear el XML en las partes recibidas.")

        # 2. SUBIR ARCHIVOS DE IMAGEN/FIRMA A SUPABASE STORAGE
        for part in binary_parts:
            b = part["bytes"]
            # Si esta parte es el XML, no la subimos como imagen
            try:
                xmltodict.parse(b)
                continue
            except Exception:
                pass

            filename_attr = part["filename"]
            key = part["key"]
            content_type_attr = part["content_type"]

            fname = f"{codigo_placa}_{ts}_{filename_attr}"
            upload_url = f"{SUPABASE_URL}/storage/v1/object/inspecciones_odk/{fname}"

            st_headers = {
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": content_type_attr,
                "x-upsert": "true"
            }
            res = requests.post(upload_url, headers=st_headers, data=b)

            if res.status_code in [200, 201]:
                public_url = f"{SUPABASE_URL}/storage/v1/object/public/inspecciones_odk/{fname}"
                uploaded_media_map[filename_attr] = public_url
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

        # 3. INSERCIÓN EN TABLA PRINCIPAL: inspecciones_guardia
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

        # 4. INSERCIÓN EN TABLA DE DETALLES: inspeccion_detalles
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
                print(f"Status Inserción Detalles: {res_det.status_code} ({len(payload_detalles)} ítems enviados)")
            else:
                print("-> No se encontraron claves de detalles en el diccionario XML.")

        # 5. INSERCIÓN EN TABLA DE NEUMÁTICOS: inspeccion_neumaticos
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
