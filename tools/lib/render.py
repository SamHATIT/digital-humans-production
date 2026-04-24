"""Rendu Jinja2 des partials de la doc.

Une seule fonction publique : ``render_partial(name, context)`` qui charge
``templates/partials/<name>.html.j2`` et le rend avec ``context``.

Convention :
- Les partials NE gèrent PAS l'indentation (ils produisent du HTML aligné à gauche).
- C'est ``build_docs.replace_marker_preserving_indent`` qui reindente le bloc
  rendu pour qu'il s'intègre proprement dans la section hôte.
- Whitespace control Jinja2 (``trim_blocks``, ``lstrip_blocks``) activé pour
  éviter les lignes vides parasites générées par les ``{% for %}`` / ``{% if %}``.
"""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

# Racine repo déduite depuis l'emplacement de ce fichier (tools/lib/render.py).
REPO_ROOT = Path(__file__).resolve().parents[2]
PARTIALS_DIR = REPO_ROOT / "docs" / "refonte" / "templates" / "partials"


def _env() -> Environment:
    """Environnement Jinja2 partagé (construit une fois, réutilisé)."""
    return Environment(
        loader=FileSystemLoader(str(PARTIALS_DIR)),
        autoescape=select_autoescape(
            disabled_extensions=("j2",),  # Les .j2 produisent du HTML qu'on contrôle
            default_for_string=False,
            default=False,
        ),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
        undefined=StrictUndefined,  # Fail fast si une variable manque dans le contexte
    )


_ENV_CACHE: Environment | None = None


def get_env() -> Environment:
    """Accesseur lazy-singleton de l'environnement Jinja2."""
    global _ENV_CACHE
    if _ENV_CACHE is None:
        _ENV_CACHE = _env()
    return _ENV_CACHE


def render_partial(name: str, context: dict) -> str:
    """Rend ``templates/partials/<name>.html.j2`` avec ``context``.

    Args:
        name: Nom du partial sans extension (ex: ``"problems_status_cards"``).
        context: Dict de variables passées au template.

    Returns:
        Le HTML rendu, aligné à gauche (l'indentation est appliquée plus tard
        par ``build_docs.replace_marker_preserving_indent``).

    Raises:
        jinja2.TemplateNotFound: si le .j2 n'existe pas.
        jinja2.UndefinedError: si le template référence une variable absente
            du contexte (``StrictUndefined``).
    """
    tpl = get_env().get_template(f"{name}.html.j2")
    return tpl.render(**context)
