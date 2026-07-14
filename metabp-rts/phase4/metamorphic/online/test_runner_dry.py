from mr_catalog_online import (MetamorphicRelation, extract_trip_ids_left,
                               rel_set_equal, rel_auth_denied)
from transforms import t_left_to_parallel, t_drop_token
from mr_runner import MRRunner


# --- Faux client : imite queries.Query sans réseau -------------------------
class FakeResp:
    def __init__(self, status, body): self.status_code = status; self._b = body
    def json(self): return self._b

class FakeSession:
    def __init__(self, mode="sain"):
        self.headers = {"Authorization": "Bearer XYZ"}
        self.mode = mode
    def post(self, url, json=None, headers=None):
        base = {"data": [{"tripId": {"type": "G", "number": "1234"}}]}
        # endpoint parallèle : en mode "faute" on retire un trajet -> MR2 casse
        if "left_parallel" in url:
            if self.mode == "faute":
                return FakeResp(200, {"data": []})       # trajet manquant
            return FakeResp(200, base)
        # auth : si header Authorization vidé -> 401
        if headers is not None and headers.get("Authorization") == "":
            return FakeResp(401, {"error": "unauthorized"})
        return FakeResp(200, base)
    def get(self, url, headers=None):
        return self.post(url, headers=headers)

class FakeQuery:
    def __init__(self, mode="sain"):
        self.address = "http://fake"
        self.session = FakeSession(mode)


# --- MR sous test ----------------------------------------------------------
mr2 = MetamorphicRelation("MR2_left_parallel", "égalité ensembliste",
                          t_left_to_parallel, rel_set_equal(extract_trip_ids_left))
mr4 = MetamorphicRelation("MR4_auth", "auth binaire",
                          t_drop_token, rel_auth_denied)

ctx = {"src_method": "POST", "src_endpoint": "/api/v1/travelservice/trips/left",
       "src_payload": {"departureTime": "2026-07-14",
                       "startingPlace": "Shang Hai", "endPlace": "Su Zhou"},
       "date": "2026-07-14", "start": "Shang Hai", "end": "Su Zhou"}


print("--- SYSTÈME SAIN (étage 1 : toutes les MR doivent PASSER) ---")
r_sain = MRRunner(FakeQuery("sain")).run_suite([mr2, mr4], [ctx])
for r in r_sain["results"]:
    print(f"  {r['mr']:20s} passed={r['passed']}  {r['detail']}")
print(f"  => P_mr = {r_sain['p_mr']}%  (attendu 100.0)")

print("\n--- SYSTÈME FAUTIF (étage 2 : MR2 doit CASSER) ---")
r_faute = MRRunner(FakeQuery("faute")).run_suite([mr2, mr4], [ctx])
for r in r_faute["results"]:
    print(f"  {r['mr']:20s} passed={r['passed']}  {r['detail']}")
print(f"  => P_mr = {r_faute['p_mr']}%  (attendu 50.0 : MR2 échoue, MR4 tient)")
