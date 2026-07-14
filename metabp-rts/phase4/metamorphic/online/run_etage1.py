"""
Étage 1 — catalogue étendu de MR sur Train-Ticket SAIN.
10 MR / 5 familles : idempotence, cardinalité, auth, équivalence, cohérence inter-services.
Attendu : P_mr = 100%. Exécuté via le vrai MRRunner.
"""
import subprocess, re, requests, json
from mr_catalog_online import (
    MetamorphicRelation,
    extract_station_ids, extract_train_ids, extract_generic_ids,
    extract_consign_ids, extract_user_ids,
    rel_set_equal, rel_auth_denied, rel_cardinality_stable,
    rel_equiv_name_to_id, rel_cross_service_equal,
)
from mr_runner import MRRunner

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
        data = r.json().get("data") or {}
        self.uid = data.get("userId")
        self.session.headers.update({"Authorization": f"Bearer {data.get('token')}"})


c = TTClient()
STATIONS = "/api/v1/stationservice/stations"
TRAINS   = "/api/v1/trainservice/trains"
CONSIGNS = f"/api/v1/consignservice/consigns/account/{c.uid}"
CONTACTS = f"/api/v1/contactservice/contacts/account/{c.uid}"
CONTACTS_ALL = "/api/v1/contactservice/contacts"
ADMIN_CONTACTS = "/api/v1/adminbasicservice/adminbasic/contacts"
USERS = "/api/v1/userservice/users"

def T(method, ep, payload=None, hdr=None):
    return lambda ctx: (method, ep, payload, hdr or {})

def drop_token(ctx):
    return (ctx["src_method"], ctx["src_endpoint"], ctx["src_payload"], {"Authorization": ""})

# (famille, MR, contexte source)
cat = [
 ("idempotence", MetamorphicRelation("MR01_idem_stations","idem gares",
     T("GET",STATIONS), rel_set_equal(extract_station_ids)),
     {"src_method":"GET","src_endpoint":STATIONS,"src_payload":None}),
 ("idempotence", MetamorphicRelation("MR02_idem_trains","idem trains",
     T("GET",TRAINS), rel_set_equal(extract_train_ids)),
     {"src_method":"GET","src_endpoint":TRAINS,"src_payload":None}),
 ("idempotence", MetamorphicRelation("MR03_idem_consigns","idem consigns (60)",
     T("GET",CONSIGNS), rel_set_equal(extract_consign_ids)),
     {"src_method":"GET","src_endpoint":CONSIGNS,"src_payload":None}),
 ("cardinalité", MetamorphicRelation("MR04_card_contacts","cardinalité contacts",
     T("GET",CONTACTS), rel_cardinality_stable(extract_generic_ids)),
     {"src_method":"GET","src_endpoint":CONTACTS,"src_payload":None}),
 ("cardinalité", MetamorphicRelation("MR05_card_consigns","cardinalité consigns",
     T("GET",CONSIGNS), rel_cardinality_stable(extract_consign_ids)),
     {"src_method":"GET","src_endpoint":CONSIGNS,"src_payload":None}),
 ("auth", MetamorphicRelation("MR06_auth_contacts","auth contacts",
     drop_token, rel_auth_denied),
     {"src_method":"GET","src_endpoint":CONTACTS,"src_payload":None}),
 ("auth", MetamorphicRelation("MR08_auth_consigns","auth consigns",
     drop_token, rel_auth_denied),
     {"src_method":"GET","src_endpoint":CONSIGNS,"src_payload":None}),
 ("équivalence", MetamorphicRelation("MR09_equiv_name_id","équivalence name->id",
     T("POST","/api/v1/stationservice/stations/idlist",NAMES),
     rel_equiv_name_to_id(NAMES, None)),
     {"src_method":"GET","src_endpoint":STATIONS,"src_payload":None}),
 ("cohérence-inter-svc", MetamorphicRelation("MR10_xsvc_contacts","contacts == adminbasic/contacts",
     T("GET",ADMIN_CONTACTS), rel_cross_service_equal(extract_generic_ids, extract_generic_ids)),
     {"src_method":"GET","src_endpoint":CONTACTS_ALL,"src_payload":None}),
]

runner = MRRunner(c)
results, n_pass = [], 0
print(f"{'Famille':22s} | {'MR':22s} | résultat")
print("-"*78)
for fam, mr, ctx in cat:
    src = (ctx["src_method"], ctx["src_endpoint"], ctx["src_payload"], {})
    res = runner.run_pair(mr, src, ctx)
    results.append({**res,"famille":fam}); n_pass += int(res["passed"])
    print(f"{fam:22s} | {res['mr']:22s} | {'PASS' if res['passed'] else 'FAIL'}  {res['detail'][:34]}")

p = round(100*n_pass/len(results),2)
fams = sorted({r['famille'] for r in results})
print("-"*78)
print(f"ÉTAGE 1 : {n_pass}/{len(results)} PASS | P_mr={p}% | {len(fams)} familles : {fams}")
json.dump({"results":results,"p_mr":p,"n":len(results),"familles":fams},
          open("etage1_report.json","w"), indent=2, ensure_ascii=False)
print("rapport -> etage1_report.json")
