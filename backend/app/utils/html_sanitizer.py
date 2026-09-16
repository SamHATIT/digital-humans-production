"""Assainissement du HTML des livrables — SEC-10 (audit Astra L187).

Un livrable est produit par des agents a partir d'un brief fourni par le
client : son contenu est orientable, ce n'est pas une frontiere de confiance.
Il etait pourtant servi tel quel par `/api/deliverables/{id}/render`, puis
transforme en `blob:` ouvert dans l'origine du Studio, ou un script lit
`localStorage.token`.

**Liste blanche, pas liste noire.** On ne retire pas ce qui est connu comme
dangereux (`<script>`, `onerror`, `javascript:`) : on ne garde que ce qui est
connu comme sur. Une liste noire laisse passer ce qu'on n'a pas prevu — c'est
le raisonnement deja retenu pour GARDE-PROD-001.

**Aucune dependance nouvelle.** `bleach` et `nh3` sont absents du venv
partage par les quatre agents de la vague 1, et la mission interdit d'y
installer quoi que ce soit. L'implementation s'appuie sur `html.parser` de la
bibliotheque standard.

**Ce que cet assainisseur ne fait pas**, dit explicitement : il ne rend pas
sur un document HTML complet une garantie equivalente a un moteur dedie
(pas de reparation d'arbre, pas de normalisation d'entites exotiques). Il
est la deuxieme barriere ; la premiere est de ne plus ouvrir ce contenu en
document de premier niveau dans l'origine du Studio (cf. `openAuthenticated`
dans frontend/src/services/api.ts), la troisieme les en-tetes de la reponse.
"""
from __future__ import annotations

import html as _html
from html.parser import HTMLParser
from typing import Dict, List, Optional, Set, Tuple

#: Balises conservees : structure, texte, tableaux, listes, liens, images.
BALISES_AUTORISEES: Set[str] = {
    "html", "head", "title", "body", "div", "section", "article", "header",
    "footer", "main", "aside", "nav", "h1", "h2", "h3", "h4", "h5", "h6",
    "p", "br", "hr", "span", "strong", "b", "em", "i", "u", "small", "sub",
    "sup", "blockquote", "code", "pre", "ul", "ol", "li", "dl", "dt", "dd",
    "table", "thead", "tbody", "tfoot", "tr", "th", "td", "caption",
    "colgroup", "col", "a", "img", "figure", "figcaption", "abbr", "time",
    "mark", "del", "ins",
}

#: Balises dont le CONTENU est jete avec elles (sinon le code s'afficherait).
BALISES_A_VIDER: Set[str] = {"script", "style", "template", "noscript"}

#: Attributs conserves, par balise puis pour toutes.
ATTRIBUTS_AUTORISES: Dict[str, Set[str]] = {
    "*": {"title", "lang", "dir", "colspan", "rowspan", "scope", "align"},
    "a": {"href", "name", "target", "rel"},
    "img": {"src", "alt", "width", "height"},
    "time": {"datetime"},
    "col": {"span"},
    "colgroup": {"span"},
}

#: Schemes d'URL acceptes. `javascript:`, `data:` et `vbscript:` sont exclus
#: (un `data:text/html` est un document a part entiere).
SCHEMES_AUTORISES: Set[str] = {"http", "https", "mailto", "tel"}

_VIDES = {"br", "hr", "img", "col"}


def _url_est_sure(valeur: str) -> bool:
    brut = valeur.strip()
    if not brut:
        return False
    # Les entites et espaces inseres servent a masquer le scheme
    # (`java&#115;cript:`), donc on decode avant de juger.
    decode = _html.unescape(brut)
    decode = "".join(c for c in decode if c.isprintable() and not c.isspace())
    if decode.startswith("#") or decode.startswith("/"):
        return True
    if ":" not in decode:
        return True  # URL relative
    scheme = decode.split(":", 1)[0].lower()
    return scheme in SCHEMES_AUTORISES


class _Assainisseur(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self._sortie: List[str] = []
        self._profondeur_jetee = 0

    # -- helpers ---------------------------------------------------------
    def _attributs(self, balise: str, attrs: List[Tuple[str, Optional[str]]]) -> str:
        permis = ATTRIBUTS_AUTORISES["*"] | ATTRIBUTS_AUTORISES.get(balise, set())
        morceaux = []
        for nom, valeur in attrs:
            nom_bas = (nom or "").lower()
            # Tout `on*` est refuse quoi qu'il arrive : la liste blanche le
            # ferait deja, on le dit pour que la lecture soit sans ambiguite.
            if nom_bas.startswith("on") or nom_bas not in permis:
                continue
            valeur = valeur or ""
            if nom_bas in {"href", "src"} and not _url_est_sure(valeur):
                continue
            morceaux.append(f' {nom_bas}="{_html.escape(valeur, quote=True)}"')
        if balise == "a" and any(m.startswith(' target=') for m in morceaux):
            if not any(m.startswith(' rel=') for m in morceaux):
                morceaux.append(' rel="noopener noreferrer"')
        return "".join(morceaux)

    # -- HTMLParser ------------------------------------------------------
    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in BALISES_A_VIDER:
            self._profondeur_jetee += 1
            return
        if self._profondeur_jetee or tag not in BALISES_AUTORISEES:
            return
        fermeture = " />" if tag in _VIDES else ">"
        self._sortie.append(f"<{tag}{self._attributs(tag, attrs)}{fermeture}")

    def handle_startendtag(self, tag, attrs):
        tag = tag.lower()
        if self._profondeur_jetee or tag in BALISES_A_VIDER or tag not in BALISES_AUTORISEES:
            return
        self._sortie.append(f"<{tag}{self._attributs(tag, attrs)} />")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in BALISES_A_VIDER:
            self._profondeur_jetee = max(0, self._profondeur_jetee - 1)
            return
        if self._profondeur_jetee or tag not in BALISES_AUTORISEES or tag in _VIDES:
            return
        self._sortie.append(f"</{tag}>")

    def handle_data(self, data):
        if self._profondeur_jetee:
            return
        self._sortie.append(_html.escape(data, quote=False))

    def handle_entityref(self, name):
        if not self._profondeur_jetee:
            self._sortie.append(f"&{name};")

    def handle_charref(self, name):
        if not self._profondeur_jetee:
            self._sortie.append(f"&#{name};")

    def handle_comment(self, data):
        # Les commentaires conditionnels sont un vecteur connu : on les jette.
        return

    def handle_decl(self, decl):
        if decl.lower().startswith("doctype"):
            self._sortie.append("<!DOCTYPE html>")

    def handle_pi(self, data):
        return

    def unknown_decl(self, data):
        return

    @property
    def resultat(self) -> str:
        return "".join(self._sortie)


def assainir_html(contenu: str) -> str:
    """Rend `contenu` inerte en ne gardant qu'une liste blanche de balises."""
    if not contenu:
        return ""
    parseur = _Assainisseur()
    parseur.feed(contenu)
    parseur.close()
    return parseur.resultat


#: En-tetes a poser sur toute reponse qui sert du HTML de livrable.
#: `sandbox` sans `allow-scripts` ni `allow-same-origin` place le document
#: dans une origine opaque, meme s'il est ouvert en premier niveau.
ENTETES_HTML_INERTE = {
    "Content-Security-Policy": (
        "sandbox; default-src 'none'; img-src data: https:; style-src 'unsafe-inline'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}
