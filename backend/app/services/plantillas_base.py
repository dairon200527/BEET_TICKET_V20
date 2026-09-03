"""
Diseños base de plantillas: el ÚNICO origen posible del HTML/Jinja2 que
`template_engine` renderiza para un ticket. El administrador nunca sube,
pega, ni edita HTML — solo elige uno de los `template_key` definidos
aquí y llena los campos de contenido (ver schemas/plantilla.py,
routers/plantillas.py). Esto reemplaza por completo el flujo anterior de
"subir un archivo .html".

Los archivos fuente viven en ../../templates/plantillas_base/ — texto
plano versionado junto con el código, jamás datos de request ni de la
base de datos, así que no hay ninguna ruta por la que un admin (o
cualquier otro usuario) pueda inyectar HTML/JS ejecutable en un ticket:
el ÚNICO contenido libre que un admin escribe (título, descripción,
términos, etc.) se inserta como variables Jinja2 con autoescape activo
(ver template_engine._env), nunca como el propio código de la plantilla.
"""
from __future__ import annotations

from pathlib import Path

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates" / "plantillas_base"

DISENOS_BASE: dict[str, dict[str, str]] = {
    "diseno_base_1": {
        "nombre": "Diseño Base 1 — Tarjeta moderna",
        "descripcion": "Tarjeta centrada de una sola columna: logo(s) arriba, beneficio destacado, datos del afiliado y vigencia, y el código QR/de barras al final.",
        "archivo": "diseno_base_1.html",
    },
    "diseno_base_2": {
        "nombre": "Diseño Base 2 — Boleta con talón lateral",
        "descripcion": "Distribución en dos columnas imitando una boleta física: contenido principal a la izquierda y un talón lateral con el código QR/de barras, como si estuviera troquelado.",
        "archivo": "diseno_base_2.html",
    },
}


def listar_disenos() -> list[dict[str, str]]:
    return [
        {"template_key": key, "nombre": info["nombre"], "descripcion": info["descripcion"]}
        for key, info in DISENOS_BASE.items()
    ]


def es_diseno_valido(template_key: str) -> bool:
    return template_key in DISENOS_BASE


def obtener_html_diseno(template_key: str) -> str:
    """Raises KeyError for an unknown template_key — callers (see
    routers/plantillas.py) turn that into a clean 400, never a 500."""
    info = DISENOS_BASE[template_key]
    return (_TEMPLATES_DIR / info["archivo"]).read_text(encoding="utf-8")
