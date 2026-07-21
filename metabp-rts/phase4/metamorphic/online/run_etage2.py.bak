"""
Étage 2 — détection de fautes (contribution T2).
On rejoue le catalogue étage 1 en injectant des fautes contrôlées dans les
réponses (simulant une régression de service), et on vérifie que les MR CASSENT.
Métrique : taux de détection = fraction des fautes qui déclenchent >=1 violation.
"""
import subprocess, re, requests, json, copy

B = "http://127.0.0.1:8080"
NAMES = ["Shang Hai", "Su Zhou"]


class TTClient:
    def __init__(self):
        self.address = B
        self.session = requests.Session()
        self.session.get(f"{B}/api/v1/verifycode/generate")
        logs = subprocess.check_output(
            ["sudo","docker","logs","--tail","5",
             "train-ticket-master-ts-verification-code-service-1"],
            stderr=subprocess.STDOUT).decode()
        code = (re.findall(r':\s+([A-Z0-9]{4})\s+___', logs) or ["1234"])[-1]
        r = self.session.post(f"{B}/api/v1/users/login",
            headers={"Content-Type":"application/json","Origin":B,
                     "Referer":f"{B}/client_login.html"},
            json={"username":"fdse_microservice","password":"111111","verificationCode":code})
        d = r.json().get("data") or {}
        self.uid = d.get("userId")
        self.session.headers.update({"Authorization": f"Bearer {d.get('token')}"})

    def call(self, method, ep, payload=None, drop_auth=False):
        h = dict(self.session.headers)
        if drop_auth: h["Authorization"] = ""
        r = (self.session.post if method=="POST" else self.session.get)(
            f"{B}{ep}", json=payload, headers=h) if method=="POST" else \
            self.session.get(f"{B}{ep}", headers=h)
        try: body = r.json()
        except: body = None
        return {"status": r.status_code, "json": body}


# --- fautes injectables (simulent une régression du service) ----------------
def fault_drop_one(resp):
    """supprime le 1er élément de data (régression : donnée manquante)."""
    r = copy.deepcopy(resp)
    if r["json"] and isinstance(r["json"].get("data"), list) and r["json"]["data"]:
        r["json"]["data"] = r["json"]["data"][1:]
    return r

def fault_corrupt_id(resp):
    """altère l'id du 1er élément (régression : donnée corrompue)."""
    r = copy.deepcopy(resp)
    d = (r["json"] or {}).get("data")
    if isinstance(d, list) and d and isinstance(d[0], dict):
        for k in ("id","userId"):
            if k in d[0]: d[0][k] = "CORRUPTED"; break
    return r

def fault_auth_bypass(resp):
    """simule un contournement d'auth : renvoie 200 au lieu de 403."""
    r = copy.deepcopy(resp); r["status"] = 200
    if r["json"] is None: r["json"] = {"data":[]}
    return r


def fault_corrupt_string_list(resp):
    """corrompt le 1er id dans une data = liste de chaînes (ex. idlist)."""
    r = copy.deepcopy(resp)
    d = (r["json"] or {}).get("data")
    if isinstance(d, list) and d and isinstance(d[0], str):
        r["json"]["data"] = ["CORRUPTED"] + list(d[1:])
    return r

def fault_reorder(resp):
    """réordonne data (pour tester si l'oracle est robuste à l'ordre)."""
    r = copy.deepcopy(resp)
    d = (r["json"] or {}).get("data")
    if isinstance(d, list) and len(d) > 1: r["json"]["data"] = d[::-1]
    return r


from mr_catalog_online import (
    extract_station_ids, extract_train_ids, extract_generic_ids, extract_consign_ids,
    rel_set_equal, rel_auth_denied, rel_cardinality_stable,
    rel_equiv_name_to_id, rel_cross_service_equal, build_name_id_map,
)

c = TTClient()
CONSIGNS = f"/api/v1/consignservice/consigns/account/{c.uid}"
CONTACTS = f"/api/v1/contactservice/contacts/account/{c.uid}"

# Chaque scénario : (nom_faute, MR ciblée, fonction d'exécution -> bool detected)
def run_mr(src_call, follow_call, relation, fault=None, fault_on="follow"):
    rs = c.call(*src_call)
    rf = c.call(*follow_call)
    if fault:
        if fault_on == "follow": rf = fault(rf)
        else: rs = fault(rs)
    ok, detail = relation(rs, rf)
    return (not ok), detail   # detected = MR violée

scenarios = [
 ("stations: gare supprimée", "idempotence/équivalence",
  lambda: run_mr(("GET","/api/v1/stationservice/stations"),
                 ("GET","/api/v1/stationservice/stations"),
                 rel_set_equal(extract_station_ids), fault_drop_one)),
 ("consigns(60): élément supprimé", "idempotence",
  lambda: run_mr(("GET",CONSIGNS),("GET",CONSIGNS),
                 rel_set_equal(extract_consign_ids), fault_drop_one)),
 ("contacts: id corrompu", "idempotence",
  lambda: run_mr(("GET",CONTACTS),("GET",CONTACTS),
                 rel_set_equal(extract_generic_ids), fault_corrupt_id)),
 ("contacts: contournement auth", "auth",
  lambda: run_mr(("GET",CONTACTS),("GET",CONTACTS,None,True),
                 rel_auth_denied, fault_auth_bypass)),
 ("stations idlist: mapping corrompu", "équivalence",
  lambda: run_mr(("GET","/api/v1/stationservice/stations"),
                 ("POST","/api/v1/stationservice/stations/idlist",NAMES),
                 rel_equiv_name_to_id(NAMES,None), fault_corrupt_string_list)),
 ("xsvc contacts: désynchro", "cohérence-inter-svc",
  lambda: run_mr(("GET","/api/v1/contactservice/contacts"),
                 ("GET","/api/v1/adminbasicservice/adminbasic/contacts"),
                 rel_cross_service_equal(extract_generic_ids,extract_generic_ids), fault_drop_one)),
 ("stations: réordonnancement (contrôle)", "idempotence",
  lambda: run_mr(("GET","/api/v1/stationservice/stations"),
                 ("GET","/api/v1/stationservice/stations"),
                 rel_set_equal(extract_station_ids), fault_reorder)),
]

print(f"{'Faute injectée':38s} | {'Famille':20s} | détectée ?")
print("-"*80)
n_det = 0
for name, fam, fn in scenarios:
    detected, detail = fn()
    n_det += int(detected)
    print(f"{name:38s} | {fam:20s} | {'✅ OUI' if detected else '❌ NON'}")

print("-"*80)
print(f"Fautes détectées : {n_det}/{len(scenarios)}  (taux = {round(100*n_det/len(scenarios),1)}%)")
print("Note : le réordonnancement NE doit PAS être détecté (oracle ensembliste robuste à l'ordre).")
