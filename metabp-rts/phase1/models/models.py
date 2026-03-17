"""
models.py
=========
BLOC      : Partagé — tous les blocs Phase 1
ROLE      : Définit les dataclasses partagées entre tous les modules :
            SpanRecord, TestPath, EdgeWeight, MRInstance, ServiceScore.
ENTREES   : (aucune entrée — définitions uniquement)
SORTIES   : Classes importables par tous les modules Phase 1
LIBRAIRIES: dataclasses, typing
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict


@dataclass
class SpanRecord:
    """Représente un span Jaeger parsé."""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    service_name: str
    operation_name: str
    duration_us: int        # microsecondes
    error: bool
    start_time_us: int      # timestamp microsecondes


@dataclass
class TestPath:
    """Un cas de test = une chaîne d'invocation reconstituée depuis un traceID."""
    trace_id: str
    invocation_chain: List[Tuple[str, str]]   # [(si, sj), ...]


@dataclass
class EdgeWeight:
    """Poids complet d'un arc (si → sj) du graphe G."""
    source: str
    target: str
    freq: int               # nombre d'occurrences
    rate_ij: float          # fréquence relative
    lat_norm: float         # latence normalisée
    err_ij: float           # taux d'erreur
    w_ij: float             # poids combiné


@dataclass
class ServiceScore:
    """Scores structurels d'un service pour le calcul de Θ_dormant."""
    service_name: str
    C: float = 0.0          # Centralité structurelle
    P: float = 0.0          # Coefficient de propagation
    F: float = 0.0          # Fragilité opérationnelle (remplace SIL)
    theta_dormant: float = 0.0
    is_dormant: bool = False


@dataclass
class MRInstance:
    """Une instance de relation métamorphique pour un endpoint donné."""
    mr_id: str              # ex: MR-PAY-01
    mr_type: str            # Idempotence | Permutation | Monotonie | ...
    service: str
    endpoint: str
    http_method: str
    phi: str                # transformation d'entrée (description)
    rho: str                # relation de sortie attendue (description)
    source: str             # "openapi" | "jaeger_fallback"
