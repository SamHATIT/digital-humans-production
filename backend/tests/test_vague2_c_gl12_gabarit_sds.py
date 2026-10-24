"""
Vague 2 / file C — GL-12 : gabarit SDS en français.

Re-mesure du 24/10 : le gabarit réellement chargé est
`docs/sds/templates/sds_shell.html.j2` + `docs/sds/templates/partials/*.j2`
(`TEMPLATES_DIR` de tools/build_sds.py, appelé par Emma en phase 5). Le chemin
`tools/templates/sds_shell.html.j2` cité par le backlog n'existe pas.
"""
from __future__ import annotations

import re
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
GABARITS = RACINE / "docs" / "sds" / "templates"
SHELL = GABARITS / "sds_shell.html.j2"


def test_le_sommaire_lateral_n_affiche_pas_les_compteurs_figes_de_l_execution_146():
    """Le sommaire latéral du shell est une copie statique du rendu de
    référence de l'exécution 146 : « Requirements Summary (25 BRs) »,
    « Custom Objects (17) », « Test Cases (83) »… affichés pour TOUTE
    exécution, quels que soient ses chiffres réels."""
    source = SHELL.read_text()
    debut = source.index("<ol class='toc-side-list'>")
    fin = source.index("</aside>", debut)
    lateral = source[debut:fin]
    figes = re.findall(r"\(\d+[^)]*\)", lateral)
    assert figes == [], f"compteurs figés dans le sommaire latéral : {figes}"
    corps = source[fin:]
    assert "derived from the 11 agent artifacts" not in corps, (
        "le nombre d'artefacts est écrit en dur (11, exécution 146)")


# ─────────────────────────────────────────────────────────────────────
# GL-12 — textes fixes bilingues, selon la langue du projet
# ─────────────────────────────────────────────────────────────────────

import sys  # noqa: E402
from datetime import datetime  # noqa: E402

import pytest  # noqa: E402

PARTIALS = sorted((GABARITS / "partials").glob("*.j2"))
FICHIERS = [SHELL] + PARTIALS

#: Fragments identiques dans les deux langues (marque, sigles, numéros romains).
NEUTRES = {"SDS ·", "— Digital·Humans Studio", "Digital", "Humans", "SDS", "SDS #",
           "ID", "BR", "UC ID", "UC IDs", "LWC", "KPI", "KPIs", "Env"}


def _i18n():
    outils = str(RACINE / "tools")
    if outils not in sys.path:
        sys.path.insert(0, outils)
    from lib import sds_i18n
    return sds_i18n


def _textes_litteraux(source: str):
    """Textes visibles écrits en dur : hors balises, hors Jinja, hors
    <style>/<script>/<pre class="mermaid">, hors commentaires."""
    s = re.sub(r"\{#.*?#\}", "", source, flags=re.S)
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    s = re.sub(r"<(style|script)\b.*?</\1>", "", s, flags=re.S | re.I)
    s = re.sub(r"<pre class=[\"']mermaid[\"'].*?</pre>", "", s, flags=re.S | re.I)
    s = re.sub(r"\{\{.*?\}\}|\{%.*?%\}", "\x00", s, flags=re.S)
    # Une balise peut contenir du Jinja (déjà remplacé) : on la retire ensuite.
    s = re.sub(r"<[^>]*>", "\x00", s, flags=re.S)
    textes = []
    for morceau in s.split("\x00"):
        t = " ".join(morceau.split())
        if re.search(r"[A-Za-zÀ-ÿ]{2,}", t) and not re.fullmatch(r"[ivxlc]+\.?", t) \
                and t not in NEUTRES:
            textes.append(t)
    return textes


def _cles(source: str):
    return {c.replace('\\"', '"') for c in re.findall(r'_\("((?:[^"\\]|\\.)*)"\)', source)}


@pytest.mark.parametrize("chemin", FICHIERS, ids=lambda p: p.name)
def test_aucun_texte_fixe_n_echappe_a_la_traduction(chemin):
    """Mesure du backlog : ~4 % de segments anglais dans un SDS français, tous
    issus du gabarit. Tout texte fixe passe désormais par `_()`."""
    restants = _textes_litteraux(chemin.read_text())
    assert restants == [], f"{chemin.name} : {len(restants)} textes en dur, ex. {restants[:5]}"


def test_chaque_texte_fixe_a_sa_traduction_francaise():
    i18n = _i18n()
    cles = set().union(*(_cles(p.read_text()) for p in FICHIERS))
    assert cles, "aucun _() dans les gabarits"
    manquantes = sorted(cles - set(i18n.CATALOGUE_FR))
    assert manquantes == [], f"{len(manquantes)} textes sans traduction : {manquantes[:10]}"


def test_l_excuse_interne_sur_les_faux_positifs_a_disparu():
    """« The DATA_MODEL gaps are likely false positives — the validator is
    matching on raw object names » exposait au client le défaut CAL-08."""
    for chemin in FICHIERS:
        texte = chemin.read_text()
        for phrase in ("false positives", "known scoring issue", "validator is matching"):
            assert phrase not in texte, f"{chemin.name} contient encore « {phrase} »"


def test_la_mention_ia_francaise_est_celle_de_reference():
    from app.utils.ai_disclosure import mention_ia
    i18n = _i18n()
    assert i18n.CATALOGUE_FR[mention_ia("en")] == mention_ia("fr")


class _Vide(dict):
    """Données de section vides mais parcourables : toute clé absente rend une
    autre structure vide. Le rendu exerce ainsi les douze partials (en-têtes,
    phrases d'introduction, en-têtes de tableaux) sans base de données."""

    def __missing__(self, cle):
        return _Vide()

    def __getattr__(self, nom):
        if nom.startswith("__"):
            raise AttributeError(nom)
        return self[nom]

    def __str__(self):
        return ""


SECTIONS = ("initial_needs", "br_data", "uc_data", "uc_digest", "as_is", "data_model",
            "security_model", "queues", "reporting", "automation_design", "integration_points",
            "ui_components", "uc_traceability", "technical_considerations", "risks", "gap",
            "data_mig", "training", "qa", "devops")


def _rendre(langue, data_model_couverture=None):
    from jinja2 import ChainableUndefined, Environment, FileSystemLoader
    i18n = _i18n()
    env = Environment(loader=FileSystemLoader(str(GABARITS)), undefined=ChainableUndefined,
                      autoescape=False)
    for filtre in ("etext", "dot_join", "ftrim", "humanize", "mermaid_safe"):
        env.filters[filtre] = lambda v, *a, **k: v
    code = i18n.installer_i18n(env, langue)
    contexte = {
        "project": {"name": "Projet témoin", "language": langue},
        "execution": {"id": 7, "started_at": datetime(2026, 10, 24), "completed_at": None},
        "coverage": {"score": 92.5, "verdict": "NEEDS_MINOR_REVISION",
                     "scoring_method": "programmatic_only",
                     "by_category": {"data_model": {"score": 100, "missing": []}},
                     "critical_gaps": []},
        "deliverables": {"count": 11},
        "toc": [dict(e) for e in __import__("lib.collect_sds", fromlist=["TOC_ENTRIES"]).TOC_ENTRIES],
        "status": {"label": "APPROVED", "css_class": "brass"},
        "hero": {"title_html": "Projet témoin,<br><em>structured</em><br>as a single brief.",
                 "subtitle": i18n.SOUS_TITRE_PAR_DEFAUT_EN},
        "agents": {"involved": ["Sophie", "Marcus"]},
        "build": {"timestamp_human": "2026-10-24 · 12:00 UTC"},
    }
    contexte.update({section: _Vide() for section in SECTIONS})
    if data_model_couverture is not None:
        contexte["coverage"]["by_category"]["data_model"] = data_model_couverture
    i18n.localiser_contexte(contexte, code)
    return env.get_template("sds_shell.html.j2").render(**contexte)


def _visible(html):
    html = re.sub(r"<(style|script)\b.*?</\1>", " ", html, flags=re.S | re.I)
    return " ".join(re.sub(r"<[^>]*>", " ", html).split())


def test_un_sds_francais_se_lit_en_francais():
    i18n = _i18n()
    rendu = _rendre("fr")
    visible = _visible(rendu)
    assert '<html lang="fr">' in rendu
    for attendu in ("Sommaire", "Présentation du projet", "Rapport de couverture",
                    "RÉVISION MINEURE", "Exécution nº", "octobre 2026", "APPROUVÉ",
                    "Contenu genere par une intelligence artificielle"):
        assert attendu in visible, f"« {attendu} » absent du rendu français"
    longues = [cle for cle, fr in i18n.CATALOGUE_FR.items() if cle != fr and len(cle) >= 14]
    anglais = [cle for cle in longues if cle in visible]
    assert anglais == [], f"textes fixes restés en anglais : {anglais[:8]}"
    # Le contrôle ne vaut que si le rendu exerce les partials : en anglais, la
    # même structure doit faire apparaître la grande majorité de ces textes.
    visible_en = _visible(_rendre("en"))
    rendus_en = [cle for cle in longues if cle in visible_en]
    assert len(rendus_en) >= 200, f"rendu trop pauvre pour conclure : {len(rendus_en)}/{len(longues)}"
    assert "structured" not in visible and "October" not in visible


def test_controle_negatif_un_sds_anglais_reste_en_anglais():
    rendu = _rendre("en")
    visible = _visible(rendu)
    assert '<html lang="en">' in rendu
    for attendu in ("Contents", "Project Overview", "Coverage Report", "October 2026",
                    "Content generated by artificial intelligence"):
        assert attendu in visible, f"« {attendu} » absent du rendu anglais"
    assert "Sommaire" not in visible and "Présentation du projet" not in visible


def test_une_phrase_sans_traduction_arrete_le_rendu_francais():
    """Règle 6 : un SDS à moitié traduit ne part pas en silence."""
    i18n = _i18n()
    _, _v = i18n.traducteur("fr")
    with pytest.raises(i18n.TraductionManquante):
        _("Phrase ajoutée au gabarit sans traduction")
    assert _v("VALEUR_INCONNUE") == "VALEUR_INCONNUE"   # une donnée se montre telle quelle


def test_une_langue_sans_catalogue_est_rendue_en_anglais_et_le_dit(caplog):
    i18n = _i18n()
    with caplog.at_level("WARNING"):
        assert i18n.langue_du_projet("de") == "en"
    assert "sans catalogue" in caplog.text


# ─────────────────────────────────────────────────────────────────────
# Reprise R2 (revue 1) : les rapprochements de CAL-08 sont montrés au lecteur
# ─────────────────────────────────────────────────────────────────────

COUVERTURE_AVEC_RAPPROCHEMENTS = {
    "score": 100, "missing": [],
    "renamed": [{"reference": "credit_note__c", "objet": "avoir__c", "methode": "sens"},
                {"reference": "client_account", "objet": "clientaccount", "methode": "normalisation"}],
    "non_objects": ["case_escalation_flow", "report"],
}


@pytest.mark.parametrize("langue,titre,methode", [
    ("fr", "Objets rapprochés sous un autre nom", "même sens"),
    ("en", "Objects matched under another name", "same meaning"),
])
def test_les_renommages_et_non_objets_sont_rendus_dans_le_rapport_de_couverture(langue, titre, methode):
    """CAL-08 écrit `data_model.renamed` et `non_objects` : un rapprochement
    compté couvert doit être visible du lecteur du SDS pour être vérifié."""
    visible = _visible(_rendre(langue, COUVERTURE_AVEC_RAPPROCHEMENTS))
    assert titre in visible
    assert "credit_note__c" in visible and "avoir__c" in visible
    assert "client_account" in visible and methode in visible
    assert "case_escalation_flow" in visible


def test_controle_negatif_sans_rapprochement_aucune_section():
    visible = _visible(_rendre("fr", {"score": 100, "missing": [], "renamed": [], "non_objects": []}))
    assert "Objets rapprochés sous un autre nom" not in visible
    assert "Non comptés comme objets" not in visible
