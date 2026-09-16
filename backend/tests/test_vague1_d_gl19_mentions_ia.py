"""VAGUE 1 / file D — GL-19 : mentions IA (AI Act art. 50) dans l'application.

Obligation en vigueur depuis le 02/08/2026. Le site est conforme depuis le
15/09 ; l'application ne l'etait pas : mesure du 16/09 sur `f78e8ad`,

    grep -rn "IA\\b|intelligence artificielle|AI-generated|article 50" \\
        frontend/src docs/sds/templates backend/app/services/*generator*.py

ne rendait qu'une ligne, `markdown_to_docx.py:206` (« Document genere par
Digital Humans Platform »), qui ne dit pas que le contenu est genere par une
intelligence artificielle.

Ce que ce fichier exige, et qui manquait :

  1. une mention canonique unique (`app/utils/ai_disclosure`), FR et EN, qui
     nomme explicitement l'IA — pas « genere par la plateforme » ;
  2. les trois generateurs Word la portent **dans le corps** du document ET
     dans les **metadonnees** du fichier (`core_properties`), parce que le
     pied de page se perd au copier-coller, pas les proprietes ;
  3. le gabarit HTML du SDS la porte en pied et en `<meta name="generator">`.

Controle negatif : un document produit sans passer par le helper ne doit pas
etre considere conforme — sinon l'assertion « la mention est presente »
passerait sur n'importe quel document (regle 2).
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

docx = pytest.importorskip("docx", reason="python-docx absent")
from docx import Document  # noqa: E402

from app.utils.ai_disclosure import (  # noqa: E402
    MENTION_IA,
    appliquer_mention_docx,
    mention_ia,
    sauvegarder_docx_avec_mention,
)


def _texte_du_docx(chemin: Path) -> str:
    document = Document(str(chemin))
    return "\n".join(p.text for p in document.paragraphs)


def _proprietes(chemin: Path):
    return Document(str(chemin)).core_properties


# ─────────────────────────────────────────────────────────────────────
# 1. La mention elle-meme
# ─────────────────────────────────────────────────────────────────────


def test_la_mention_nomme_explicitement_l_intelligence_artificielle():
    """« genere par la plateforme » ne satisfait pas l'article 50."""
    for langue in ("fr", "en"):
        texte = mention_ia(langue).lower()
        assert ("intelligence artificielle" in texte) or ("artificial intelligence" in texte), (
            f"la mention {langue} ne nomme pas l'IA : {mention_ia(langue)!r}"
        )


def test_la_mention_existe_en_francais_et_en_anglais():
    assert set(MENTION_IA) >= {"fr", "en"}
    assert mention_ia("fr") != mention_ia("en")


def test_une_langue_inconnue_ne_rend_pas_une_mention_vide():
    """Regle 6 : pas de repli silencieux. Une langue inconnue rend le francais,
    jamais une chaine vide qui ferait disparaitre la mention du livrable."""
    assert mention_ia("zz") == mention_ia("fr")
    assert mention_ia(None) == mention_ia("fr")


# ─────────────────────────────────────────────────────────────────────
# 2. Word : corps + metadonnees
# ─────────────────────────────────────────────────────────────────────


def test_le_helper_ecrit_la_mention_dans_le_corps_et_les_metadonnees(tmp_path):
    document = Document()
    document.add_paragraph("Contenu du livrable.")
    appliquer_mention_docx(document, langue="fr")

    chemin = tmp_path / "avec_mention.docx"
    document.save(str(chemin))

    assert mention_ia("fr") in _texte_du_docx(chemin)
    proprietes = _proprietes(chemin)
    assert mention_ia("fr") in (proprietes.comments or "")
    assert "IA" in (proprietes.category or "") or "AI" in (proprietes.category or "")


def test_controle_negatif_un_document_sans_helper_n_est_pas_conforme(tmp_path):
    """Sans ce test, l'assertion ci-dessus passerait sur n'importe quel .docx."""
    document = Document()
    document.add_paragraph("Contenu du livrable.")
    chemin = tmp_path / "sans_mention.docx"
    document.save(str(chemin))

    assert mention_ia("fr") not in _texte_du_docx(chemin)
    assert mention_ia("fr") not in (_proprietes(chemin).comments or "")


def test_sauvegarder_docx_avec_mention_est_idempotent(tmp_path):
    """Deux passages ne doivent pas empiler deux mentions dans le meme document."""
    document = Document()
    document.add_paragraph("Contenu.")
    chemin = tmp_path / "idempotent.docx"
    sauvegarder_docx_avec_mention(document, str(chemin), langue="fr")
    sauvegarder_docx_avec_mention(document, str(chemin), langue="fr")

    assert _texte_du_docx(chemin).count(mention_ia("fr")) == 1


# ─────────────────────────────────────────────────────────────────────
# 3. Les trois generateurs Word reellement utilises
# ─────────────────────────────────────────────────────────────────────


def test_markdown_to_docx_porte_la_mention(tmp_path):
    """Chemin reel : `pm_orchestrator_service_v2` appelle cette fonction pour
    produire le .docx du SDS (`_generate_sds_document`)."""
    from app.services.markdown_to_docx import convert_markdown_to_docx

    chemin = tmp_path / "sds.docx"
    rendu = convert_markdown_to_docx(
        "# Titre\n\nUn paragraphe de specification.\n",
        str(chemin),
        project_name="Projet de test",
    )

    assert Path(rendu).exists()
    assert mention_ia("fr") in _texte_du_docx(Path(rendu))
    assert mention_ia("fr") in (_proprietes(Path(rendu)).comments or "")


def test_le_generateur_professionnel_porte_la_mention(tmp_path):
    from app.services.document_generator import ProfessionalDocumentGenerator

    generateur = ProfessionalDocumentGenerator()
    generateur.create_document()
    generateur.doc.add_paragraph("Section de specification.")
    chemin = tmp_path / "pro.docx"
    generateur.save(str(chemin))

    assert mention_ia("fr") in _texte_du_docx(chemin)
    assert mention_ia("fr") in (_proprietes(chemin).comments or "")


def test_le_generateur_de_gabarit_sds_porte_la_mention(tmp_path):
    """`SDSTemplateGenerator.generate()` charge la base ; seule sa
    finalisation (mention + sauvegarde) est jouee ici, sur l'objet reel."""
    from app.services.sds_template_generator import SDSTemplateGenerator

    generateur = SDSTemplateGenerator.__new__(SDSTemplateGenerator)
    generateur.doc = Document()
    generateur.doc.add_paragraph("Section 1.")
    chemin = tmp_path / "gabarit.docx"
    generateur._finaliser_document(str(chemin))

    assert mention_ia("fr") in _texte_du_docx(chemin)
    assert mention_ia("fr") in (_proprietes(chemin).comments or "")


# ─────────────────────────────────────────────────────────────────────
# 4. Le SDS HTML (gabarit Jinja2 reellement rendu par tools/build_sds.py)
# ─────────────────────────────────────────────────────────────────────


def _rendre_le_gabarit_sds() -> str:
    """Rend le **vrai** `sds_shell.html.j2`, celui que `tools/build_sds.py`
    charge en production, avec des partials neutralises.

    Le contexte reel vient de la base (`lib/collect_sds.build_render_context`)
    et les douze partials exigent chacun leurs donnees ; les reconstituer ici
    ferait de ce test un test des donnees, pas du gabarit. Ce qui est verifie
    est une propriete du **shell** — c'est lui qui porte l'en-tete et le pied,
    donc la mention, quelles que soient les sections incluses.
    """
    from jinja2 import (
        ChainableUndefined,
        ChoiceLoader,
        DictLoader,
        Environment,
        FileSystemLoader,
    )

    racine = Path(__file__).resolve().parents[2]
    gabarits = racine / "docs" / "sds" / "templates"
    partials_neutres = {
        f"partials/{chemin.name}": "" for chemin in (gabarits / "partials").glob("*.j2")
    }
    assert partials_neutres, "aucun partial trouve : le chemin des gabarits a change"

    env = Environment(
        loader=ChoiceLoader(
            [DictLoader(partials_neutres), FileSystemLoader(str(gabarits))]
        ),
        undefined=ChainableUndefined,
        autoescape=False,
    )
    for filtre in ("etext", "dot_join", "ftrim", "humanize", "mermaid_safe"):
        env.filters.setdefault(filtre, lambda valeur: valeur)
    return env.get_template("sds_shell.html.j2").render(
        project={"name": "Projet de test"},
        execution={"id": 1, "started_at": datetime(2026, 9, 16), "completed_at": None},
        coverage={"score": 85},
    )


def test_le_sds_html_porte_la_mention_en_pied_et_en_metadonnee():
    rendu = _rendre_le_gabarit_sds()

    assert 'name="generator"' in rendu, "le gabarit HTML n'a pas de <meta generator>"
    debut_pied = rendu.rfind("<footer")
    assert debut_pied != -1, "le gabarit HTML n'a plus de pied de page"
    assert mention_ia("en") in rendu[debut_pied:] or mention_ia("fr") in rendu[debut_pied:], (
        "la mention IA est absente du pied du SDS HTML"
    )
