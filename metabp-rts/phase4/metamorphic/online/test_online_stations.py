import subprocess, re, requests
from mr_catalog_online import MetamorphicRelation, extract_station_ids, rel_set_equal
from mr_runner import MRRunner

B = "http://127.0.0.1:8080"

# --- client réel minimal compatible MRRunner (a .address et .session) ------
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
            json={"username":"fdse_microservice","password":"111111",
                  "verificationCode":code})
        tok = (r.json().get("data") or {}).get("token")
        self.session.headers.update({"Authorization": f"Bearer {tok}"})

# MR-idempotence : follow-up = même GET stations
def t_identity_stations(ctx):
    return ("GET", "/api/v1/stationservice/stations", None, {})

mr_idem = MetamorphicRelation(
    "MR_idempotence_stations", "égalité ensembliste des gares",
    t_identity_stations, rel_set_equal(extract_station_ids))

ctx = {"src_method":"GET",
       "src_endpoint":"/api/v1/stationservice/stations",
       "src_payload":None}

runner = MRRunner(TTClient())
res = runner.run_suite([mr_idem], [ctx])
for r in res["results"]:
    print(f"  {r['mr']:26s} passed={r['passed']}  {r['detail']}")
print(f"  P_mr = {res['p_mr']}%")
