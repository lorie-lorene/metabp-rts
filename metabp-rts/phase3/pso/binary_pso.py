"""
Binary Particle Swarm Optimization

    Sélectionne le sous-ensemble optimal de chemins dans Tier2_dédupliqué
    qui maximise la couverture des services tout en minimisant le nombre
    de chemins sélectionnés.

FITNESS FUNCTION :
    fitness(p) =   w_coverage * couverture_services(p) + w_cit * sum_cit_couverts(p)- w_size * taille_normalisée(p)

    couverture_services : fraction de services distincts couverts
    sum_cit_couverts    : somme des scores CIT des services couverts (priorise les services impactés par ΔS)
    taille_normalisée   : |sélection| / N  (à minimiser)

MISE À JOUR DES VITESSES (Binary PSO) :
    v_i(t+1) = w  * v_i(t)
             + c1 * r1 * (pbest_i - x_i)
             + c2 * r2 * (gbest_i - x_i)

    P(xi=1) = sigmoid(v_i)
    xi = 1 si random() < P(xi=1), 0 sinon

"""

import json
import logging
import math
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class BinaryPSO:
    

    def __init__(
        self,
        n_particles: int = 30,
        max_iterations: int = 100,
        patience: int = 20,
        w: float = 0.7,
        c1: float = 1.5,
        c2: float = 1.5,
        w_coverage: float = 0.6,
        w_size: float = 0.3,
        w_cit: float = 0.1,
        threshold: float = 0.5,
        init_strategy: str = "greedy",
        seed: Optional[int] = 42,
    ):
        self.n_particles    = n_particles
        self.max_iterations = max_iterations
        self.patience       = patience
        self.w              = w
        self.c1             = c1
        self.c2             = c2
        self.w_coverage     = w_coverage
        self.w_size         = w_size
        self.w_cit          = w_cit
        self.threshold      = threshold
        self.init_strategy  = init_strategy

        if seed is not None:
            random.seed(seed)

    def _sigmoid(self, v: float) -> float:
        """Fonction sigmoïde bornée pour éviter les overflows."""
        v = max(-20.0, min(20.0, v))
        return 1.0 / (1.0 + math.exp(-v))

    def _extract_services(self, tp: Dict) -> List[str]:
        """Extrait les services depuis un chemin."""
        if "services" in tp and tp["services"]:
            return tp["services"]
        chain = tp.get("invocation_chain", [])
        if chain:
            seen = []
            for pair in chain:
                for svc in pair:
                    if svc not in seen:
                        seen.append(svc)
            return seen
        return []

    def _fitness(
        self,
        position: List[int],
        paths: List[Dict],
        all_services: List[str],
        cit: Dict[str, float],
        n_paths: int,
    ) -> float:
       
        selected_indices = [i for i, x in enumerate(position) if x == 1]

        if not selected_indices:
            return 0.0

        # Services couverts par la sélection
        covered = set()
        cit_sum = 0.0
        for i in selected_indices:
            svcs = self._extract_services(paths[i])
            covered.update(svcs)

        # Somme des CIT des services couverts
        for svc in covered:
            cit_sum += cit.get(svc, 0.0)

        # Couverture normalisée [0, 1]
        coverage = len(covered) / max(len(all_services), 1)

        # CIT normalisé [0, 1]
        max_possible_cit = sum(cit.values()) if cit else 1.0
        cit_normalized = cit_sum / max(max_possible_cit, 1.0)

        # Taille normalisée [0, 1] — à minimiser
        size = len(selected_indices) / max(n_paths, 1)

        fitness = (
            self.w_coverage * coverage
            + self.w_cit    * cit_normalized
            - self.w_size   * size
        )
        return round(fitness, 8)

    def _greedy_init(
        self,
        paths: List[Dict],
        all_services: List[str],
        n_paths: int,
    ) -> List[int]:
       
        covered    = set()
        selected   = [0] * n_paths
        remaining  = list(range(n_paths))

        while remaining and covered != set(all_services):
            # Trouver le chemin qui couvre le plus de services nouveaux
            best_idx   = -1
            best_gain  = -1

            for i in remaining:
                svcs = set(self._extract_services(paths[i]))
                gain = len(svcs - covered)
                if gain > best_gain:
                    best_gain = gain
                    best_idx  = i

            if best_idx == -1 or best_gain == 0:
                break

            selected[best_idx] = 1
            covered.update(self._extract_services(paths[best_idx]))
            remaining.remove(best_idx)

        return selected

    def optimize(
        self,
        paths: List[Dict],
        cit: Dict[str, float],
        all_services: Optional[List[str]] = None,
    ) -> Dict:
      
        n_paths = len(paths)
        if n_paths == 0:
            logger.warning("BinaryPSO — aucun chemin à optimiser")
            return {
                "selected_indices": [],
                "selected_paths":   [],
                "gbest_fitness":    0.0,
                "n_iterations":     0,
                "converged":        True,
                "history":          [],
                "stats":            {"n_input": 0, "n_selected": 0},
            }

        # Extraire tous les services connus
        if all_services is None:
            svc_set = set()
            for tp in paths:
                svc_set.update(self._extract_services(tp))
            all_services = sorted(svc_set)

        logger.info(
            "BinaryPSO — démarrage : %d chemins | %d services | "
            "%d particules | max_iter=%d",
            n_paths, len(all_services), self.n_particles, self.max_iterations,
        )

        positions = []
        velocities = []

        for p in range(self.n_particles):
            if self.init_strategy == "greedy" and p == 0:
                # Première particule : initialisation gloutonne
                pos = self._greedy_init(paths, all_services, n_paths)
            else:
                # Autres particules : aléatoire (50% de chance pour chaque bit)
                pos = [1 if random.random() < 0.5 else 0 for _ in range(n_paths)]

            vel = [random.uniform(-2, 2) for _ in range(n_paths)]
            positions.append(pos)
            velocities.append(vel)

        # pbest = meilleure position personnelle de chaque particule
        pbest_positions = [list(p) for p in positions]
        pbest_fitness   = [
            self._fitness(p, paths, all_services, cit, n_paths)
            for p in positions
        ]

        # gbest = meilleure position globale
        gbest_idx      = pbest_fitness.index(max(pbest_fitness))
        gbest_position = list(positions[gbest_idx])
        gbest_fitness  = pbest_fitness[gbest_idx]

        history       = []
        no_improve    = 0
        converged     = False
        n_iter        = 0

        for t in range(self.max_iterations):
            n_iter = t + 1

            for p in range(self.n_particles):
                for i in range(n_paths):
                    r1 = random.random()
                    r2 = random.random()

                    # Mise à jour de la vitesse
                    velocities[p][i] = (
                        self.w  * velocities[p][i]
                        + self.c1 * r1 * (pbest_positions[p][i] - positions[p][i])
                        + self.c2 * r2 * (gbest_position[i]      - positions[p][i])
                    )

                    # Binarisation via sigmoid
                    prob = self._sigmoid(velocities[p][i])
                    positions[p][i] = 1 if random.random() < prob else 0

                # Évaluer la nouvelle position
                fit = self._fitness(positions[p], paths, all_services, cit, n_paths)

                # Mise à jour pbest
                if fit > pbest_fitness[p]:
                    pbest_fitness[p]   = fit
                    pbest_positions[p] = list(positions[p])

            # Mise à jour gbest
            best_p    = max(range(self.n_particles), key=lambda p: pbest_fitness[p])
            best_fit  = pbest_fitness[best_p]

            if best_fit > gbest_fitness:
                gbest_fitness  = best_fit
                gbest_position = list(pbest_positions[best_p])
                no_improve     = 0
            else:
                no_improve += 1

            # Enregistrer l'historique
            n_selected = sum(gbest_position)
            history.append({
                "iteration":  n_iter,
                "gbest":      round(gbest_fitness, 6),
                "n_selected": n_selected,
                "no_improve": no_improve,
            })

            # Log tous les 10 iter
            if n_iter % 10 == 0 or n_iter == 1:
                logger.info(
                    "PSO iter=%d | gbest=%.4f | sélectionnés=%d | "
                    "no_improve=%d/%d",
                    n_iter, gbest_fitness, n_selected,
                    no_improve, self.patience,
                )

            # Convergence
            if no_improve >= self.patience:
                converged = True
                logger.info(
                    "BinaryPSO — convergence à iter=%d (pas d'amélioration "
                    "depuis %d itérations)",
                    n_iter, self.patience,
                )
                break

        if not converged:
            logger.warning(
                "BinaryPSO — max_iterations=%d atteint sans convergence.",
                self.max_iterations,
            )

        # ── Résultat 
        selected_indices = [i for i, x in enumerate(gbest_position) if x == 1]
        selected_paths   = [paths[i] for i in selected_indices]

        # Services couverts par la sélection finale
        covered = set()
        for tp in selected_paths:
            covered.update(self._extract_services(tp))

        coverage = round(len(covered) / max(len(all_services), 1), 4)

        logger.info(
            "BinaryPSO — terminé : %d/%d chemins sélectionnés | "
            "couverture=%d/%d services (%.1f%%) | fitness=%.4f",
            len(selected_indices), n_paths,
            len(covered), len(all_services), coverage * 100,
            gbest_fitness,
        )

        return {
            "selected_indices": selected_indices,
            "selected_paths":   selected_paths,
            "gbest_fitness":    round(gbest_fitness, 6),
            "n_iterations":     n_iter,
            "converged":        converged,
            "history":          history,
            "stats": {
                "n_input":         n_paths,
                "n_selected":      len(selected_indices),
                "reduction_rate":  round(1 - len(selected_indices) / max(n_paths, 1), 4),
                "reduction_pct":   f"{(1 - len(selected_indices)/max(n_paths,1))*100:.1f}%",
                "n_services_total":   len(all_services),
                "n_services_covered": len(covered),
                "coverage_rate":      coverage,
                "coverage_pct":       f"{coverage*100:.1f}%",
                "gbest_fitness":      round(gbest_fitness, 6),
                "n_iterations":       n_iter,
                "converged":          converged,
            },
        }

    def save(self, result: Dict, selected_path: str, history_path: str) -> None:
        """Sauvegarde Tier2_sel et l'historique PSO."""
        p1 = Path(selected_path)
        p1.parent.mkdir(parents=True, exist_ok=True)
        with open(p1, "w", encoding="utf-8") as f:
            json.dump(result["selected_paths"], f, indent=2, ensure_ascii=False)
        logger.info("PSO Tier2_sel → %s (%d chemins)", p1, len(result["selected_paths"]))

        p2 = Path(history_path)
        with open(p2, "w", encoding="utf-8") as f:
            json.dump({
                "stats":   result["stats"],
                "history": result["history"],
            }, f, indent=2, ensure_ascii=False)
        logger.info("PSO historique → %s", p2)
