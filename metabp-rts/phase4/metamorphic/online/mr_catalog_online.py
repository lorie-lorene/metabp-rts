# phase4/metamorphic/online/mr_catalog_online.py
"""
Catalogue exécutable des MR de transformation (test métamorphique boîte-noire).
Chaque MR : source -> follow-up (T) + relation-oracle (R).
Aucune dépendance réseau ici : transform/relation sont des fonctions pures,
testables à sec. L'exécution HTTP est faite par le runner (brique 3).
"""
from dataclasses import dataclass
from typing import Callable, Any, Dict, List, Tuple


# --------- extraction paramétrable des tripId (à figer sur réponse réelle) ----
def extract_trip_ids_left(resp_json: dict) -> set:
    """trips/left : data[].tripId = {type, number}."""
    data = (resp_json or {}).get("data") or []
    out = set()
    for d in data:
        tid = d.get("tripId") or {}
        if isinstance(tid, dict):
            out.add(f"{tid.get('type','')}{tid.get('number','')}")
        elif isinstance(tid, str):
            out.add(tid)
    return out


def extract_trip_ids_plan(resp_json: dict) -> set:
    """travelPlan/* : data[].tripId = str (à confirmer)."""
    data = (resp_json or {}).get("data") or []
    out = set()
    for d in data:
        tid = d.get("tripId")
        if isinstance(tid, dict):
            out.add(f"{tid.get('type','')}{tid.get('number','')}")
        elif tid is not None:
            out.add(str(tid))
    return out


# --------- structure d'une MR ------------------------------------------------
@dataclass
class MetamorphicRelation:
    name: str
    description: str
    # transform : construit la requête follow-up à partir du contexte source
    #   -> renvoie (method, endpoint, payload, headers_override)
    transform: Callable[[Dict[str, Any]], Tuple[str, str, dict, dict]]
    # relation : (resp_source, resp_follow) -> (ok: bool, detail: str)
    relation: Callable[[Any, Any], Tuple[bool, str]]
    has_side_effect: bool = False   # MR5 = True (à isoler des runs de lecture)


# --------- relations-oracle (R) ---------------------------------------------
def rel_set_equal(extract):
    def _r(rs, rf):
        a, b = extract(rs["json"]), extract(rf["json"])
        return (a == b, f"|src|={len(a)} |follow|={len(b)} diff={a ^ b}")
    return _r

def rel_subset(extract_sub, extract_super):
    def _r(rs, rf):
        sub, sup = extract_sub(rf["json"]), extract_super(rs["json"])
        return (sub <= sup, f"hors_base={sub - sup}")
    return _r

def rel_auth_denied(rs, rf):
    ok = (200 <= rs["status"] < 300) and (rf["status"] in (401, 403))
    return (ok, f"src={rs['status']} follow={rf['status']}")

# --- extracteurs Train-Ticket réels (format confirmé sur système vivant) ----
def extract_station_ids(resp_json: dict) -> set:
    """stations : data[].id  (ex. 'shanghai')."""
    return {d.get("id") for d in (resp_json or {}).get("data") or [] if d.get("id")}


def extract_train_ids(resp_json: dict) -> set:
    """trains : data[].id."""
    return {d.get("id") for d in (resp_json or {}).get("data") or [] if d.get("id")}


def extract_contact_ids(resp_json: dict) -> set:
    """contacts : data[].id (UUID)."""
    return {d.get("id") for d in (resp_json or {}).get("data") or [] if d.get("id")}


def extract_assurance_idx(resp_json: dict) -> set:
    """assurances : data[].index (entier, pas 'id')."""
    return {d.get("index") for d in (resp_json or {}).get("data") or [] if d.get("index") is not None}


def rel_cardinality_stable(extract):
    """MR de stabilité de cardinalité : même NOMBRE d'éléments entre 2 appels."""
    def _r(rs, rf):
        a, b = extract(rs["json"]), extract(rf["json"])
        return (len(a) == len(b) and len(a) > 0, f"|src|={len(a)} |follow|={len(b)}")
    return _r


def build_name_id_map(stations_json: dict) -> dict:
    """{name -> id} depuis la liste stations (mapping de référence)."""
    return {d["name"]: d["id"] for d in (stations_json or {}).get("data") or []
            if d.get("name") and d.get("id")}


def rel_equiv_name_to_id(names, ref_map):
    """
    MR d'équivalence : idlist([names]) doit renvoyer [ref_map[name] pour name in names].
    rs = réponse stations (référence), rf = réponse idlist.
    """
    def _r(rs, rf):
        ref = build_name_id_map(rs["json"])
        expected = [ref.get(n) for n in names]
        got = (rf["json"] or {}).get("data") or []
        ok = (got == expected) and all(e is not None for e in expected)
        return (ok, f"attendu={expected} obtenu={got}")
    return _r


def extract_consign_ids(resp_json: dict) -> set:
    return {d.get("id") for d in (resp_json or {}).get("data") or [] if d.get("id")}


def extract_user_ids(resp_json: dict) -> set:
    return {d.get("userId") for d in (resp_json or {}).get("data") or [] if d.get("userId")}


def extract_generic_ids(resp_json: dict) -> set:
    """ids génériques (clé 'id'), pour contacts/adminbasic."""
    return {d.get("id") for d in (resp_json or {}).get("data") or [] if d.get("id")}


def rel_cross_service_equal(extract_a, extract_b):
    """
    MR de cohérence inter-services : deux endpoints exposant la même donnée
    doivent renvoyer le MÊME ensemble d'ids. rs=service A, rf=service B.
    """
    def _r(rs, rf):
        a, b = extract_a(rs["json"]), extract_b(rf["json"])
        return (a == b and len(a) > 0, f"|A|={len(a)} |B|={len(b)} diff={a ^ b}")
    return _r
