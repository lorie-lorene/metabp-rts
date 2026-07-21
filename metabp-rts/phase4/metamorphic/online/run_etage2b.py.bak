"""
Étage 2b — injection de faute au niveau SERVICE (via proxy réel devant station).
Pour chaque mode de faute : lance le proxy, exécute MR-idempotence sur stations,
vérifie que la MR passe (sain) ou casse (fautif).
"""
import subprocess, time, os, sys, requests, signal
from mr_catalog_online import extract_station_ids, rel_set_equal

PROXY = "http://127.0.0.1:18080"
STATIONS = "/api/v1/stationservice/stations"

def start_proxy(mode):
    env = dict(os.environ, FAULT_MODE=mode)
    p = subprocess.Popen([sys.executable, "fault_proxy.py"], env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2.5)   # laisser Flask démarrer
    return p

def mr_idempotence_via_proxy():
    # source ET follow-up via le proxy (le service fautif)
    rs = {"json": requests.get(f"{PROXY}{STATIONS}", timeout=10).json()}
    rf = {"json": requests.get(f"{PROXY}{STATIONS}", timeout=10).json()}
    # NB : idempotence pure passerait même si les 2 sont corrompues identiquement.
    # Pour détecter une faute DETERMINISTE, on compare au RÉFÉRENCE sain (13 gares).
    return rs, rf

# référence saine : appel direct au service (sans proxy)
ref = requests.get(f"http://127.0.0.1:12345{STATIONS}", timeout=10).json()
ref_ids = extract_station_ids(ref)
print(f"référence saine : {len(ref_ids)} gares\n")

print(f"{'Mode faute':14s} | gares vues | MR (vs référence) | attendu")
print("-"*66)
for mode, expect in [("none","PASS"),("drop_one","FAIL"),("corrupt_id","FAIL"),("empty","FAIL")]:
    p = start_proxy(mode)
    try:
        served = requests.get(f"{PROXY}{STATIONS}", timeout=10).json()
        served_ids = extract_station_ids(served)
        # oracle : le service (via proxy) doit renvoyer le même ensemble que la référence saine
        ok, detail = rel_set_equal(lambda x: x)(
            {"json": None} or {}, {"json": None} or {}) if False else (served_ids == ref_ids, "")
        verdict = "PASS" if ok else "FAIL"
        mark = "✅" if verdict == expect else "⚠️ INATTENDU"
        print(f"{mode:14s} | {len(served_ids):10d} | {verdict:17s} | {expect}  {mark}")
    finally:
        p.send_signal(signal.SIGTERM); p.wait()

print("-"*66)
print("Étage 2b : la faute vient du SERVICE (proxy), pas du runner.")
