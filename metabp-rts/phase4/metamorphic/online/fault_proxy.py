"""
Proxy d'injection de fautes devant ts-station-service (port 12345).
Relaie les requêtes et, selon FAULT_MODE, corrompt la réponse au niveau SERVICE.
Modes : none | drop_one | corrupt_id | empty
Usage : FAULT_MODE=drop_one python fault_proxy.py   (écoute sur :18080)
Le MRRunner cible http://127.0.0.1:18080 pour l'endpoint stations.
"""
import os, json, requests
from flask import Flask, request, Response

app = Flask(__name__)
TARGET = "http://127.0.0.1:12345"          # ts-station-service en direct
FAULT = os.environ.get("FAULT_MODE", "none")


def inject(body_bytes):
    """applique la faute sur le corps JSON de la réponse."""
    if FAULT == "none":
        return body_bytes
    try:
        j = json.loads(body_bytes)
    except Exception:
        return body_bytes
    data = j.get("data")
    if isinstance(data, list) and data:
        if FAULT == "drop_one":
            j["data"] = data[1:]                      # supprime 1 gare
        elif FAULT == "corrupt_id" and isinstance(data[0], dict):
            if "id" in data[0]:
                data[0]["id"] = "CORRUPTED"           # corrompt un id
        elif FAULT == "empty":
            j["data"] = []                            # réponse vide
    return json.dumps(j).encode()


@app.route("/", defaults={"path": ""}, methods=["GET", "POST", "PUT", "DELETE"])
@app.route("/<path:path>", methods=["GET", "POST", "PUT", "DELETE"])
def proxy(path):
    url = f"{TARGET}/{path}"
    resp = requests.request(
        method=request.method, url=url,
        headers={k: v for k, v in request.headers if k.lower() != "host"},
        data=request.get_data(), params=request.args, timeout=15)
    body = resp.content
    ctype = resp.headers.get("Content-Type", "")
    if "application/json" in ctype:
        body = inject(body)
    return Response(body, status=resp.status_code, content_type=ctype)


if __name__ == "__main__":
    print(f"[fault_proxy] FAULT_MODE={FAULT} | :18080 -> {TARGET}")
    app.run(host="0.0.0.0", port=18080, threaded=True)
