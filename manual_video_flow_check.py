import argparse
import asyncio
import os
import time
import uuid
from pathlib import Path

import requests
from dotenv import load_dotenv

from camera_trigger import queue_camera_trigger


DEFAULT_CUSTOMER_UUID = "ad5aa3b9-46de-40a8-8c2a-450a57286b86"


def generate_entrance_log_uuid(payload):
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, str(payload)))


def login(hostname, username, password):
    response = requests.post(
        f"{hostname.rstrip('/')}/api/token/",
        headers={"Content-Type": "application/json"},
        json={"email": username, "password": password},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()["access"]


def verify_customer(hostname, token, payload):
    response = requests.post(
        f"{hostname.rstrip('/')}/verify_customer/",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def wait_for_local_video(recording_dir, entrance_log_uuid, timeout_seconds=30):
    final_path = Path(recording_dir) / f"{entrance_log_uuid}.mp4"
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if final_path.exists():
            return final_path
        time.sleep(0.5)
    return None


async def wait_for_s3_upload(bucket_name, object_key, timeout_seconds=90):
    import aioboto3
    from botocore.config import Config
    from botocore.exceptions import ClientError

    session = aioboto3.Session()
    deadline = time.time() + timeout_seconds
    async with session.client(
        "s3",
        aws_access_key_id=os.getenv("S3_ACCESS_KEY"),
        aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY"),
        endpoint_url=os.getenv("S3_ENDPOINT_URL"),
        config=Config(
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
            s3={"addressing_style": "path"},
        ),
    ) as s3_client:
        while time.time() < deadline:
            try:
                await s3_client.head_object(Bucket=bucket_name, Key=object_key)
                return True
            except ClientError as exc:
                error_code = str(exc.response.get("Error", {}).get("Code", ""))
                if error_code not in {"404", "NoSuchKey", "NotFound"}:
                    raise
            await asyncio.sleep(1)
    return False


def build_payload(args):
    direction = args.direction or os.getenv("DIRECTION") or "IN"
    entrance_uuid = args.entrance_uuid or os.getenv("ENTRANCE_UUID") or os.getenv("ENTRANCE_UUID_A")
    if not entrance_uuid:
        raise RuntimeError("No se pudo determinar ENTRANCE_UUID. Pasalo por argumento o configuralo en .env.")

    payload = {
        "customer_uuid": args.customer_uuid,
        "entrance_uuid": entrance_uuid,
        "direction": direction,
        "timestamp": int(time.time()),
    }
    payload["uuid"] = generate_entrance_log_uuid(payload)
    return payload


def ensure_required_env():
    required_keys = ("HOSTNAME", "USERNAME", "PASSWORD", "RECORDING_DIR")
    missing_keys = [key for key in required_keys if not str(os.getenv(key) or "").strip()]
    if missing_keys:
        raise RuntimeError(f"Faltan variables en .env: {', '.join(missing_keys)}")


def parse_args():
    parser = argparse.ArgumentParser(description="Manual smoke check for QR -> backend -> MQTT -> recorder -> S3 flow.")
    parser.add_argument("--customer-uuid", default=DEFAULT_CUSTOMER_UUID, help="UUID del cliente/QR que se va a verificar.")
    parser.add_argument("--entrance-uuid", default="", help="UUID de la entrada. Si no se indica, se usa ENTRANCE_UUID del .env.")
    parser.add_argument("--direction", default="", help="Direccion enviada al backend. Si no se indica, se usa DIRECTION del .env.")
    parser.add_argument("--skip-upload-check", action="store_true", help="No esperar confirmacion en S3.")
    return parser.parse_args()


def main():
    load_dotenv(Path(__file__).resolve().parent / ".env")
    args = parse_args()
    ensure_required_env()

    payload = build_payload(args)
    recording_dir = os.getenv("RECORDING_DIR")

    print("Usando customer_uuid:", payload["customer_uuid"])
    print("Entrancelog UUID esperado:", payload["uuid"])
    print("Entrada:", payload["entrance_uuid"])
    print("Direccion:", payload["direction"])

    queue_camera_trigger(recording_dir, payload["uuid"])
    print("Trigger local de camara creado. Esperando 0.4s para que mqtt_sender lo procese...")
    time.sleep(float(os.getenv("CAMERA_SLEEP_DURATION", "0.4")))

    token = login(os.getenv("HOSTNAME"), os.getenv("USERNAME"), os.getenv("PASSWORD"))
    response = verify_customer(os.getenv("HOSTNAME"), token, payload)
    print("Respuesta backend:", response)

    local_video_path = wait_for_local_video(recording_dir, payload["uuid"])
    if local_video_path:
        print("Video local detectado:", local_video_path)
    else:
        print("No aparecio video local final en el tiempo esperado.")

    if args.skip_upload_check:
        return

    upload_ready = all(str(os.getenv(key) or "").strip() for key in ("GYM_UUID", "S3_ACCESS_KEY", "S3_SECRET_ACCESS_KEY", "S3_ENDPOINT_URL"))
    if not upload_ready:
        print("Saltando comprobacion S3: faltan credenciales/configuracion de subida.")
        return

    uploaded = asyncio.run(wait_for_s3_upload(os.getenv("GYM_UUID"), f"{payload['uuid']}.mp4"))
    if uploaded:
        print("Objeto subido a S3:", f"{payload['uuid']}.mp4")
    else:
        print("No se confirmo la subida a S3 en el tiempo esperado.")


if __name__ == "__main__":
    main()
