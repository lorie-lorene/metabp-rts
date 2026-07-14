from mr_catalog_online import extract_trip_ids_left, rel_set_equal

fake_src = {"json": {"data": [{"tripId": {"type": "G", "number": "1234"}}]}}
fake_fol = {"json": {"data": [{"tripId": {"type": "G", "number": "1234"}}]}}
ok, detail = rel_set_equal(extract_trip_ids_left)(fake_src, fake_fol)
print("MR2 dry-run (identique) :", ok, detail)   # attendu : True

# cas négatif : un trajet en plus côté follow-up → doit être False
fake_fol2 = {"json": {"data": [
    {"tripId": {"type": "G", "number": "1234"}},
    {"tripId": {"type": "D", "number": "9999"}},
]}}
ok2, detail2 = rel_set_equal(extract_trip_ids_left)(fake_src, fake_fol2)
print("MR2 dry-run (divergent) :", ok2, detail2)  # attendu : False
