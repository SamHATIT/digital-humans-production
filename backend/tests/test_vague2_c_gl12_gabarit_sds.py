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
