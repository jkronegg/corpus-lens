#!/usr/bin/env python3
"""
Analyse chiffrée: durée (dépôt initiative -> votation) selon la position des autorités.

Usage:
  python -u ".agents/skills/analyse-swissvotes-votations/scripts/analyse_duree_opposition.py"
  python -u ".agents/skills/analyse-swissvotes-votations/scripts/analyse_duree_opposition.py" --permutations 20000
"""

import argparse
import csv
import math
import random
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parents[3]
_DEFAULT_CSV = _PROJECT_ROOT / ".agents" / "skills" / "analyse-swissvotes-votations" / "assets" / "DATASET CSV 08-04-2026.csv"
_DEFAULT_OUTPUT = _PROJECT_ROOT / "sortie" / "analyse_duree_opposition_initiatives.md"


@dataclass
class Observation:
    anr: str
    year: int
    duration_days: int
    br_pos: str
    bv_pos: str
    domain: str


def _parse_date(value: str) -> datetime | None:
    raw = (value or "").strip()
    if not raw or raw in (".", "0", "9999"):
        return None
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            pass
    return None


def _escape_yaml(value: str) -> str:
    return (value or "").replace('"', "'")


def _quantile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        return math.nan
    if q <= 0:
        return float(sorted_values[0])
    if q >= 1:
        return float(sorted_values[-1])
    pos = (len(sorted_values) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return float(sorted_values[lo])
    w = pos - lo
    return float(sorted_values[lo] * (1.0 - w) + sorted_values[hi] * w)


def _normal_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _mann_whitney_two_sided(x: list[float], y: list[float]) -> tuple[float, float, float]:
    n1 = len(x)
    n2 = len(y)
    if n1 == 0 or n2 == 0:
        return math.nan, math.nan, math.nan

    pooled = [(v, 0) for v in x] + [(v, 1) for v in y]
    pooled.sort(key=lambda t: t[0])

    ranks = [0.0] * len(pooled)
    i = 0
    tie_sizes: list[int] = []
    while i < len(pooled):
        j = i + 1
        while j < len(pooled) and pooled[j][0] == pooled[i][0]:
            j += 1
        avg_rank = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks[k] = avg_rank
        tie_sizes.append(j - i)
        i = j

    r1 = sum(r for r, (_, grp) in zip(ranks, pooled) if grp == 0)
    u1 = r1 - n1 * (n1 + 1) / 2.0
    u2 = n1 * n2 - u1
    u = min(u1, u2)

    n = n1 + n2
    tie_term = sum(t * t * t - t for t in tie_sizes)
    var_u = (n1 * n2 / 12.0) * ((n + 1) - tie_term / (n * (n - 1))) if n > 1 else math.nan
    if not var_u or var_u <= 0:
        return u1, math.nan, math.nan

    mean_u = n1 * n2 / 2.0
    z = (u - mean_u + 0.5) / math.sqrt(var_u)
    p_two_sided = 2.0 * (1.0 - _normal_cdf(abs(z)))
    return u1, z, max(0.0, min(1.0, p_two_sided))


def _cliffs_delta(x: list[float], y: list[float]) -> float:
    if not x or not y:
        return math.nan
    gt = 0
    lt = 0
    for a in x:
        for b in y:
            if a > b:
                gt += 1
            elif a < b:
                lt += 1
    return (gt - lt) / (len(x) * len(y))


def _permutation_test_diff_median(
    x: list[float],
    y: list[float],
    n_perm: int,
    seed: int = 42,
) -> tuple[float, float]:
    if not x or not y:
        return math.nan, math.nan

    rng = random.Random(seed)
    obs = _median(y) - _median(x)

    combined = x + y
    n1 = len(x)
    extreme = 0
    for _ in range(n_perm):
        rng.shuffle(combined)
        a = combined[:n1]
        b = combined[n1:]
        stat = _median(b) - _median(a)
        if abs(stat) >= abs(obs):
            extreme += 1

    p_value = (extreme + 1) / (n_perm + 1)
    return obs, p_value


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else math.nan


def _median(values: list[float]) -> float:
    if not values:
        return math.nan
    s = sorted(values)
    n = len(s)
    m = n // 2
    if n % 2 == 1:
        return float(s[m])
    return (s[m - 1] + s[m]) / 2.0


def _std(values: list[float]) -> float:
    if not values:
        return math.nan
    mu = _mean(values)
    return math.sqrt(sum((v - mu) ** 2 for v in values) / len(values))


def _summary(values: list[float]) -> dict[str, float]:
    s = sorted(values)
    return {
        "n": float(len(s)),
        "mean": _mean(s),
        "median": _median(s),
        "std": _std(s),
        "min": float(s[0]) if s else math.nan,
        "q1": _quantile(s, 0.25),
        "q3": _quantile(s, 0.75),
        "max": float(s[-1]) if s else math.nan,
    }


def _format_summary_row(label: str, values: list[float]) -> str:
    d = _summary(values)
    return (
        f"| {label} | {int(d['n'])} | {d['mean']:.0f} | {d['median']:.0f} | "
        f"{d['std']:.0f} | {d['min']:.0f} | {d['q1']:.0f} | {d['q3']:.0f} | {d['max']:.0f} |"
    )


def _load_observations(csv_path: Path) -> list[Observation]:
    out: list[Observation] = []
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            if (row.get("rechtsform", "").strip()) != "3":
                continue

            submit = _parse_date(row.get("dat-submit", ""))
            vote = _parse_date(row.get("datum", ""))
            if not submit or not vote:
                continue

            days = (vote - submit).days
            if days < 0:
                continue

            domain = (row.get("d1e1", "") or "").strip()
            if not domain or domain in (".", "0"):
                domain = "inconnu"

            out.append(
                Observation(
                    anr=(row.get("anr", "") or "").strip(),
                    year=vote.year,
                    duration_days=days,
                    br_pos=(row.get("br-pos", "") or "").strip(),
                    bv_pos=(row.get("bv-pos", "") or "").strip(),
                    domain=domain,
                )
            )
    return out


def _decade(year: int) -> str:
    d = (year // 10) * 10
    return f"{d}s"


def _stratified_difference(
    obs: list[Observation],
    group_fn,
    min_group_size: int = 3,
) -> tuple[float, int]:
    strata: dict[str, dict[str, list[int]]] = {}
    for o in obs:
        g = group_fn(o)
        if g not in ("pro", "contre"):
            continue
        key = _decade(o.year)
        strata.setdefault(key, {"pro": [], "contre": []})
        strata[key][g].append(o.duration_days)

    weighted_num = 0.0
    weighted_den = 0
    for bucket in strata.values():
        pro = bucket["pro"]
        contre = bucket["contre"]
        if len(pro) < min_group_size or len(contre) < min_group_size:
            continue
        diff = _median(contre) - _median(pro)
        weight = len(pro) + len(contre)
        weighted_num += diff * weight
        weighted_den += weight

    if weighted_den == 0:
        return math.nan, 0
    return weighted_num / weighted_den, weighted_den


def _interpret_cliffs(delta: float) -> str:
    ad = abs(delta)
    if ad < 0.147:
        return "négligeable"
    if ad < 0.33:
        return "faible"
    if ad < 0.474:
        return "modéré"
    return "fort"


def _build_report(obs: list[Observation], csv_rel: str, n_perm: int) -> str:
    all_durations = [o.duration_days for o in obs]

    br_pro = [o.duration_days for o in obs if o.br_pos == "1"]
    br_contre = [o.duration_days for o in obs if o.br_pos == "2"]

    bv_pro = [o.duration_days for o in obs if o.bv_pos == "1"]
    bv_contre = [o.duration_days for o in obs if o.bv_pos == "2"]

    inst_pro = [o.duration_days for o in obs if o.br_pos == "1" and o.bv_pos == "1"]
    inst_contre = [o.duration_days for o in obs if (o.br_pos == "2" or o.bv_pos == "2")]

    u_br, z_br, p_br = _mann_whitney_two_sided(br_pro, br_contre)
    u_bv, z_bv, p_bv = _mann_whitney_two_sided(bv_pro, bv_contre)

    delta_br = _cliffs_delta(br_pro, br_contre)
    delta_bv = _cliffs_delta(bv_pro, bv_contre)

    med_diff_br, p_perm_br = _permutation_test_diff_median(br_pro, br_contre, n_perm)
    med_diff_bv, p_perm_bv = _permutation_test_diff_median(bv_pro, bv_contre, n_perm)

    adj_br, n_adj_br = _stratified_difference(obs, lambda o: "pro" if o.br_pos == "1" else ("contre" if o.br_pos == "2" else "autre"), min_group_size=1)
    adj_bv, n_adj_bv = _stratified_difference(obs, lambda o: "pro" if o.bv_pos == "1" else ("contre" if o.bv_pos == "2" else "autre"), min_group_size=1)

    br_balance = f"{len(br_pro)} favorables vs {len(br_contre)} opposés"
    bv_balance = f"{len(bv_pro)} favorables vs {len(bv_contre)} opposés"

    adj_br_str = f"**{adj_br:.0f} jours** (base pondérée: {n_adj_br} observations)" if not math.isnan(adj_br) else "non estimable (pas de chevauchement temporel suffisant)"
    adj_bv_str = f"**{adj_bv:.0f} jours** (base pondérée: {n_adj_bv} observations)" if not math.isnan(adj_bv) else "non estimable (pas de chevauchement temporel suffisant)"

    today = datetime.now().strftime("%Y-%m-%d")
    title = "Analyse chiffrée — durée dépôt→votation selon position des autorités"

    lines = [
        "---",
        f'title: "{_escape_yaml(title)}"',
        f'date_creation: "{today}"',
        'author: "skill analyse-swissvotes-votations"',
        "sources:",
        f'  - "{_escape_yaml(csv_rel)}"',
        "---",
        "",
        "# Analyse chiffrée — la durée est-elle plus longue quand les autorités sont contre ?",
        "",
        "## Périmètre et variable testée",
        "",
        "- Population: initiatives populaires (`rechtsform = 3`) avec `dat-submit` et `datum` valides.",
        "- Variable dépendante: `durée = datum - dat-submit` (en jours).",
        "- Groupes d'intérêt: position du Conseil fédéral (`br-pos`) et du Parlement (`bv-pos`).",
        "- Codage: `1 = favorable`, `2 = opposé`.",
        "",
        "## Taille de l'échantillon",
        "",
        f"- Initiatives valides analysées: **{len(obs)}**.",
        f"- Durée globale médiane: **{_median(all_durations):.0f} jours** ; moyenne: **{_mean(all_durations):.0f} jours**.",
        "",
        "## Statistiques descriptives par groupe",
        "",
        "### Conseil fédéral (`br-pos`)",
        "",
        "| Groupe | N | Moyenne (j) | Médiane (j) | Écart-type | Min | Q1 | Q3 | Max |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        _format_summary_row("CF favorable (1)", br_pro),
        _format_summary_row("CF opposé (2)", br_contre),
        "",
        "### Parlement (`bv-pos`)",
        "",
        "| Groupe | N | Moyenne (j) | Médiane (j) | Écart-type | Min | Q1 | Q3 | Max |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        _format_summary_row("Parlement favorable (1)", bv_pro),
        _format_summary_row("Parlement opposé (2)", bv_contre),
        "",
        "### Opposition institutionnelle (lecture synthétique)",
        "",
        "| Groupe | N | Moyenne (j) | Médiane (j) | Écart-type | Min | Q1 | Q3 | Max |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        _format_summary_row("CF et Parlement favorables", inst_pro),
        _format_summary_row("CF ou Parlement opposé", inst_contre),
        "",
        "## Tests d'hypothèse et taille d'effet",
        "",
        "### Conseil fédéral",
        "",
        f"- Différence de médiane (opposé - favorable): **{med_diff_br:.0f} jours** (test permutation, {n_perm} permutations).",
        f"- Test de permutation (bilatéral): **p = {p_perm_br:.4f}**.",
        f"- Mann-Whitney U: U = {u_br:.1f}, z = {z_br:.2f}, p = {p_br:.4f}.",
        f"- Taille d'effet (Cliff's delta): **{delta_br:.3f}** ({_interpret_cliffs(delta_br)}).",
        "",
        "### Parlement",
        "",
        f"- Différence de médiane (opposé - favorable): **{med_diff_bv:.0f} jours** (test permutation, {n_perm} permutations).",
        f"- Test de permutation (bilatéral): **p = {p_perm_bv:.4f}**.",
        f"- Mann-Whitney U: U = {u_bv:.1f}, z = {z_bv:.2f}, p = {p_bv:.4f}.",
        f"- Taille d'effet (Cliff's delta): **{delta_bv:.3f}** ({_interpret_cliffs(delta_bv)}).",
        "",
        "## Contrôle temporel (stratification par décennie)",
        "",
        "- Indicateur: différence de médiane `contre - favorable`, calculée dans chaque décennie puis agrégée (pondérée par effectif).",
        f"- Conseil fédéral: {adj_br_str}.",
        f"- Parlement: {adj_bv_str}.",
        "",
        "## Robustesse et équilibre des groupes",
        "",
        f"- Répartition CF: {br_balance}.",
        f"- Répartition Parlement: {bv_balance}.",
        "- Les groupes 'favorables' sont très petits; les tests ont donc une puissance statistique limitée.",
        "",
        "## Conclusion",
        "",
    ]

    conclusion_lines = []
    if not math.isnan(med_diff_br) and not math.isnan(med_diff_bv):
        trend_br = "plus longue" if med_diff_br > 0 else "plus courte"
        trend_bv = "plus longue" if med_diff_bv > 0 else "plus courte"
        conclusion_lines.append(
            f"- Pour le Conseil fédéral, la durée est **{trend_br}** quand il est opposé (écart médian: {med_diff_br:.0f} jours)."
        )
        conclusion_lines.append(
            f"- Pour le Parlement, la durée est **{trend_bv}** quand il est opposé (écart médian: {med_diff_bv:.0f} jours)."
        )

    sig_br = p_perm_br < 0.05 if not math.isnan(p_perm_br) else False
    sig_bv = p_perm_bv < 0.05 if not math.isnan(p_perm_bv) else False
    if sig_br or sig_bv:
        conclusion_lines.append(
            "- Les tests indiquent qu'au moins une partie de cet écart est statistiquement robuste (au seuil 5 %)."
        )
    else:
        conclusion_lines.append(
            "- Les écarts observés ne sont pas tous robustes au seuil 5 %; l'interprétation causale doit rester prudente."
        )

    conclusion_lines.extend(
        [
            "- Même en présence d'un allongement associé à l'opposition, cela ne prouve pas à lui seul une stratégie intentionnelle de blocage: des facteurs de période, de complexité juridique et de charge institutionnelle peuvent contribuer à l'effet.",
            "",
            "## Limites",
            "",
            "- Analyse observationnelle (non expérimentale): corrélation ≠ causalité.",
            "- Contrôle partiel des facteurs confondants (stratification temporelle, sans modèle multivarié complet).",
            "- Les codages Swissvotes hors `1/2` ne sont pas inclus dans les comparaisons principales.",
            "",
        ]
    )

    lines.extend(conclusion_lines)
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyse la durée dépôt->votation selon l'opposition des autorités."
    )
    parser.add_argument("--csv", type=Path, default=_DEFAULT_CSV, help="Chemin du CSV Swissvotes")
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT, help="Fichier Markdown de sortie")
    parser.add_argument("--permutations", type=int, default=20000, help="Nombre de permutations pour le test sur différence de médiane")
    args = parser.parse_args()

    if args.permutations < 1000:
        raise SystemExit("[ERREUR] --permutations doit être >= 1000 pour une estimation stable.")
    if not args.csv.exists():
        raise SystemExit(f"[ERREUR] CSV introuvable: {args.csv}")

    observations = _load_observations(args.csv)
    if not observations:
        raise SystemExit("[ERREUR] Aucune observation valide extraite.")

    try:
        csv_rel = args.csv.resolve().relative_to(_PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        csv_rel = args.csv.resolve().as_posix()

    report = _build_report(observations, csv_rel, args.permutations)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")

    print(f"[OK] Fichier Markdown écrit: {args.output}")
    print(f"[INFO] Observations: {len(observations)}")


if __name__ == "__main__":
    main()


