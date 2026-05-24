

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict


@dataclass
class SpanRecord:

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
   #Un cas de test = une chaîne d'invocation reconstituée depuis un traceID
    trace_id: str
    invocation_chain: List[Tuple[str, str]]  
    duration_us: int = 0 


@dataclass
class EdgeWeight:

    source: str
    target: str
    freq: int               # nombre d'occurrences
    rate_ij: float          # fréquence relative
    lat_norm: float         # latence normalisée
    err_ij: float           # taux d'erreur
    w_ij: float             # poids combiné


@dataclass
class ServiceScore:
   #Scores structurels d'un service pour le calcul de Θ_dormant
    service_name: str
    C: float = 0.0          
    P: float = 0.0          
    F: float = 0.0         
    theta_dormant: float = 0.0
    is_dormant: bool = False


@dataclass
class MRInstance:
    mr_id: str              
    mr_type: str           
    service: str
    endpoint: str
    http_method: str
    phi: str              
    rho: str                
    source: str             
