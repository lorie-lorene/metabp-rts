# phase4/metamorphic/online/transforms.py
"""
Transformations T : à partir du contexte source, décrivent la requête follow-up.
Retour : (method, endpoint_relatif, payload, headers_override)
Le runner (brique 3) exécute réellement via la session de queries.Query.
"""

def t_left_to_parallel(ctx):
    # MR2 : même recherche, endpoint parallèle
    return ("POST", "/api/v1/travelservice/trips/left_parallel",
            {"departureTime": ctx["date"],
             "startingPlace": ctx["start"], "endPlace": ctx["end"]}, {})

def t_identity_left(ctx):
    # MR1 : ré-exécution à l'identique
    return ("POST", "/api/v1/travelservice/trips/left",
            {"departureTime": ctx["date"],
             "startingPlace": ctx["start"], "endPlace": ctx["end"]}, {})

def t_plan_cheapest(ctx):
    # MR3 : planification avancée sur la même paire
    return ("POST", "/api/v1/travelplanservice/travelPlan/cheapest",
            {"departureTime": ctx["date"],
             "startingPlace": ctx["start"], "endPlace": ctx["end"]}, {})

def t_drop_token(ctx):
    # MR4 : même requête source, token retiré
    return (ctx["src_method"], ctx["src_endpoint"], ctx["src_payload"],
            {"Authorization": ""})   # header override = pas d'auth