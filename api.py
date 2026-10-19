import os
import time
from datetime import datetime
import xmltodict
import requests
from fastapi import FastAPI, Request, Response, UploadFile

app = FastAPI(title="Servidor ODK Qorilazo - Debug")

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


@app.get("/")
@app.head("/")
async def root():
    return {"status": "ok", "message": "Servidor ODK Qorilazo Debug Active"}


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
        <hash>md5:qorilazo2026v39</hash>
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
        print("\n=================== DEBUG DUMP DE RECEPCION ===================")

        for key, value in form.items():
            if isinstance(value, UploadFile):
                await value.seek(0)
                file_bytes = await value.read()

                if key == "xml_submission_file" or value.filename.lower().endswith(".xml"):
                    print("\n--- 1. CONTENIDO RAW DEL XML ---")
                    xml_str = file_bytes.decode("utf-8", errors="ignore")
                    print(xml_str[:1000])  # Primeros 1000 caracteres

                    print("\n--- 2. ESTRUCTURA PARSEADA CON XMLTODICT ---")
                    parsed = xmltodict.parse(file_bytes)
                    print(f"Claves Nivel 1: {list(parsed.keys())}")
                    
                    root_key = list(parsed.keys())[0]
                    content = parsed[root_key]
                    if isinstance(content, dict):
                        print(f"Claves Nivel 2 ({root_key}): {list(content.keys())}")
                        print("\n--- 3. VALORES EXTRAÍDOS DIRECTAMENTE ---")
                        print(f"nombre_operador: {content.get('nombre_operador')}")
                        print(f"guardia: {content.get('guardia')}")
                        print(f"codigo_placa: {content.get('codigo_placa')}")
                        print(f"doc_fotocheck: {content.get('doc_fotocheck')}")
                        print(f"cabina_asiento: {content.get('cabina_asiento')}")
                    else:
                        print(f"El contenido de {root_key} NO es un diccionario: {type(content)}")
                        
        print("===============================================================\n")

    except Exception as e:
        print(f"Excepción en debug submission: {e}")

    response_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <openrosa-response xmlns="http://openrosa.org/xforms/response">
        <message nature="submit_success">Debug completado.</message>
    </openrosa-response>"""

    return Response(
        content=response_xml,
        status_code=201,
        media_type="text/xml",
        headers={"X-OpenRosa-Version": "1.0"}
    )
