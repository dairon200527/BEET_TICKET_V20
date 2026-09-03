"""The 4 fixed, code-owned ticket designs — Cine Colombia, Mundo
Aventura, Wellness Spa, Salitre Mágico — reproducing each brand's real
reference ticket (dimensions, colors, fixed texts, real transcribed
terms and conditions, and the brand's own logo image) as closely as the
existing layout engine (template_engine.py) allows.

SELECTION: a convenio picks one of these 4 by `clave` via
`convenios.plantilla_catalogo_clave` (nullable `VARCHAR(50)`, validated
against `existe()` — see routers/convenios.py's `actualizar()`). This is
the ONLY schema change this mechanism needed: a plain string column
storing the code-owned key directly, never a foreign key into
`plantillas` — there was no need to fake a `plantillas` row for a design
that isn't a real per-convenio upload, and this way the same `clave` can
be selected by any number of convenios with zero risk of ever colliding
with the real, pre-existing `plantillas.convenio_id`/`version` unique
constraint. `pdf_service.generar_ticket` checks this column FIRST,
before falling back to any legacy per-convenio `plantillas` row
(`plantilla_activa()`), then the generic ticket.

ADDING A 5TH DESIGN: add its `LAYOUT_*` dict and an entry in `CATALOGO`
below — nothing else in the database changes, since `clave` is never
constrained at the database level (only validated in Python against
`CATALOGO`'s keys). Brand image files (logos, headers, badges) go in
`app/static/plantillas_catalogo/` next to the existing ones, referenced
by filename from that new entry's `imagenes` dict.

Each entry's `layout` dict and `imagenes` mapping are fed straight into
`template_engine.generar_pdf_desde_layout` — the EXACT same rendering
path real purchases and the previous round's per-convenio "layout"
plantillas already used, so PREVIEW and the REAL ticket PDF can never
drift apart (they're the same function, same input).
"""
from __future__ import annotations

import base64
import os
from functools import lru_cache

from app.services import template_engine

_ASSETS_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "plantillas_catalogo")

TERMINOS_CINE = (
    "1. Cada CINECO PASS es válido para una boleta en localidad general para películas cinematográficas "
    "(excluyendo contenidos alternativos) o producto de comidas, únicamente según la información contenida "
    "en el CINECO PASS. 2. Redención máxima hasta la fecha de vencimiento del CINECO PASS en los días, "
    "ciudades y Multiplex, únicamente según la información contenida en el CINECO PASS. 3. Los CINECO PASS "
    "para películas en formato 2D no son válidos para películas en formato 3D ni 4D (DINAMIX). 4. El CINECO "
    "PASS no es redimible por boletería de las salas: (i) denominadas “Platino”, (ii) cuya "
    "silletería sea únicamente de localidad preferencial, (iii) IMAX, (iv) Mega Salas, y (v) Onyx, de los "
    "Multiplex de Cine Colombia. 5. Redención sujeta a disponibilidad de cupo y de productos de comidas en "
    "el Multiplex, los cuales podrán ser reemplazados por un producto de características similares. 6. Por "
    "disposiciones de Cine Colombia o de las autoridades competentes, las salas podrán cerrar en cualquier "
    "momento; la vigencia del CINECO PASS no se extenderá como consecuencia de dichos cierres. 7. Venta "
    "exclusiva de Cine Colombia directamente o a través de un tercero autorizado. 8. Válido únicamente en "
    "perfecto estado. 9. Una vez emitido el CINECO PASS, no se hacen reintegros de dinero ni cambios, ni "
    "antes ni después de su vencimiento. 10. Cine Colombia no se responsabiliza por la pérdida o redención "
    "del CINECO PASS por un tercero diferente a su adquiriente o beneficiario final. 11. Cada CINECO PASS "
    "constituye un acceso a un servicio ofrecido por Cine Colombia, de acuerdo con las condiciones impresas. "
    "12. Los CINECO PASS únicamente se venden a empresas."
)
LAYOUT_CINE_COLOMBIA = {
    "width": 190, "height": 262, "background_color": "#ffffff",
    "elements": [
        {"type": "rect", "x": 0, "y": 0, "width": 190, "height": 96, "color": "#0b0f1a"},
        {"type": "text", "x": 12, "y": 12, "width": 150, "height": 16, "content": "CINECO PASS",
         "fontSize": 24, "fontWeight": "bold", "color": "#ffffff"},
        {"type": "text", "x": 12, "y": 40, "width": 120, "height": 20, "field": "codigo",
         "fontSize": 16, "fontWeight": "bold", "color": "#0b0f1a", "background": "#ffffff",
         "borderRadius": 10, "padding": 5, "textAlign": "center"},
        {"type": "image", "x": 122, "y": 40, "width": 58, "height": 46, "image_key": "logo", "fit": "contain"},

        {"type": "text", "x": 14, "y": 104, "width": 40, "height": 7, "content": "ID Lote:", "fontSize": 8.5, "fontWeight": "bold", "color": "#222222"},
        {"type": "text", "x": 56, "y": 104, "width": 120, "height": 7, "field": "transaccion_id", "fontSize": 8.5, "color": "#222222"},
        {"type": "text", "x": 14, "y": 113, "width": 40, "height": 7, "content": "Emisión:", "fontSize": 8.5, "fontWeight": "bold", "color": "#222222"},
        {"type": "text", "x": 56, "y": 113, "width": 120, "height": 7, "field": "fecha", "fontSize": 8.5, "color": "#222222"},
        {"type": "text", "x": 14, "y": 122, "width": 40, "height": 7, "content": "Vencimiento:", "fontSize": 8.5, "fontWeight": "bold", "color": "#222222"},
        {"type": "text", "x": 56, "y": 122, "width": 120, "height": 7, "field": "fecha_vencimiento", "fontSize": 8.5, "color": "#222222"},
        {"type": "text", "x": 14, "y": 131, "width": 40, "height": 7, "content": "Referencia:", "fontSize": 8.5, "fontWeight": "bold", "color": "#222222"},
        {"type": "text", "x": 56, "y": 131, "width": 130, "height": 7, "content": "{{codigo}}-FORMATO TAQUILLA 2D - VÁLIDO EN TODO EL PAIS", "fontSize": 8.5, "color": "#222222"},

        {"type": "barcode", "x": 14, "y": 144, "width": 162, "height": 24},

        {"type": "rect", "x": 14, "y": 172, "width": 162, "height": 0.4, "color": "#cccccc"},
        {"type": "text", "x": 14, "y": 177, "width": 162, "height": 7, "content": "TÉRMINOS Y CONDICIONES CINECO PASS",
         "fontSize": 10, "fontWeight": "bold", "textAlign": "center", "color": "#0b0f1a"},
        {"type": "text", "x": 14, "y": 187, "width": 162, "height": 50, "content": TERMINOS_CINE,
         "fontSize": 6, "textAlign": "justify", "color": "#555555"},
        {"type": "rect", "x": 14, "y": 240, "width": 162, "height": 0.4, "color": "#cccccc"},
        {"type": "image", "x": 78, "y": 244, "width": 34, "height": 16, "image_key": "logo", "fit": "contain"},
    ],
}

LAYOUT_MUNDO_AVENTURA = {
    "width": 190, "height": 320, "background_color": "#ffffff",
    "elements": [
        {"type": "rect", "x": 0, "y": 0, "width": 190, "height": 46, "color": "#f20a6b"},
        {"type": "rect", "x": 0, "y": 36, "width": 190, "height": 10, "color": "#ff8a00", "opacity": 0.55},
        {"type": "text", "x": 55, "y": 5, "width": 80, "height": 6, "content": "26 AÑOS",
         "fontSize": 9, "fontWeight": "bold", "color": "#ffffff", "textAlign": "center"},
        {"type": "text", "x": 40, "y": 12, "width": 110, "height": 5, "content": "Creciendo a tu lado",
         "fontSize": 6.5, "color": "#ffffff", "textAlign": "center"},
        {"type": "image", "x": 62, "y": 17, "width": 66, "height": 30, "image_key": "logo", "fit": "contain"},

        {"type": "text", "x": 12, "y": 54, "width": 166, "height": 20,
         "content": "A continuación encontrarás tus códigos para ser redimidos en el parque, recuerda las "
                     "CONDICIONES Y RESTRICCIONES DEL USO DE CÓDIGOS QR enviadas a tu correo electrónico.",
         "fontSize": 8.5, "color": "#333333"},
        {"type": "text", "x": 12, "y": 80, "width": 166, "height": 7, "content": "Cantidad de unidades en esta compra:", "fontSize": 8.5, "fontWeight": "bold", "color": "#333333"},
        {"type": "text", "x": 12, "y": 89, "width": 166, "height": 10, "field": "cantidad", "fontSize": 13, "fontWeight": "bold", "color": "#e60a5c"},

        {"type": "list", "x": 10, "y": 104, "width": 170, "height": 206, "field": "unidades", "mode": "grid_qr",
         "gridColumns": 2, "fontSize": 8, "color": "#333333"},
    ],
}

POLITICA_WELLNESS = (
    "Política de cancelación: le aconsejamos confirmar su cita con mínimo 24 horas de antelación. "
    "Las cancelaciones podrán ser realizadas hasta 24 horas antes de la reserva, de lo contrario su "
    "bono se dará como redimido."
)
LAYOUT_WELLNESS_SPA = {
    "width": 180, "height": 248, "background_color": "#111111",
    "elements": [
        {"type": "image", "x": 0, "y": 0, "width": 180, "height": 92, "image_key": "header", "fit": "cover"},
        {"type": "text", "x": 122, "y": 4, "width": 54, "height": 6, "field": "codigo", "fontSize": 7, "color": "#ffffff", "textAlign": "right"},
        {"type": "rect", "x": 0, "y": 90, "width": 180, "height": 158, "color": "#111111"},

        {"type": "image", "x": 58, "y": 96, "width": 64, "height": 62, "image_key": "logo", "fit": "contain"},

        {"type": "text", "x": 12, "y": 166, "width": 80, "height": 7, "content": "MENSAJE:", "fontSize": 8, "fontWeight": "bold", "color": "#ffffff"},

        {"type": "text", "x": 12, "y": 186, "width": 80, "height": 6, "content": "Reservas:", "fontSize": 7, "fontWeight": "bold", "color": "#ffffff", "textAlign": "center"},
        {"type": "text", "x": 12, "y": 193, "width": 80, "height": 6, "content": "322 685 7353  ·  PBX (601) 629 5200", "fontSize": 7, "color": "#ffffff", "textAlign": "center"},
        {"type": "text", "x": 12, "y": 201, "width": 80, "height": 6, "content": "www.wellnessspamovil.com", "fontSize": 7, "color": "#ffffff", "textAlign": "center"},
        {"type": "barcode", "x": 12, "y": 210, "width": 78, "height": 22},

        {"type": "text", "x": 100, "y": 166, "width": 70, "height": 6, "content": "UN REGALO PARA:", "fontSize": 7, "fontWeight": "bold", "color": "#ffffff"},
        {"type": "text", "x": 100, "y": 173, "width": 70, "height": 6, "content": "EL PORTADOR", "fontSize": 8, "color": "#ffffff"},
        {"type": "text", "x": 100, "y": 182, "width": 70, "height": 6, "content": "Nombre de:", "fontSize": 7, "fontWeight": "bold", "color": "#ffffff"},
        {"type": "text", "x": 100, "y": 189, "width": 70, "height": 6, "field": "nombre_afiliado", "fontSize": 8, "color": "#ffffff"},
        {"type": "text", "x": 100, "y": 198, "width": 70, "height": 6, "content": "TOTAL:", "fontSize": 7, "fontWeight": "bold", "color": "#ffffff"},
        {"type": "text", "x": 100, "y": 205, "width": 70, "height": 6, "field": "convenio", "fontSize": 8, "color": "#ffffff"},

        {"type": "text", "x": 100, "y": 213, "width": 70, "height": 6, "content": "EXPIRA:", "fontSize": 7, "fontWeight": "bold", "color": "#ffffff"},
        {"type": "text", "x": 100, "y": 220, "width": 70, "height": 6, "field": "fecha_vencimiento", "fontSize": 8, "color": "#ffffff"},

        {"type": "text", "x": 100, "y": 228, "width": 68, "height": 18, "content": POLITICA_WELLNESS,
         "fontSize": 5.6, "color": "#111111", "background": "#c8a04b", "borderRadius": 4, "padding": 2, "textAlign": "center"},
    ],
}

TERMINOS_SALITRE = (
    "1. Términos y condiciones grupos: salitremagico.com.co/terminos-y-condiciones-grupos/\n"
    "2. Términos y condiciones fiestas infantiles: salitremagico.com.co/terminos-y-condiciones/\n"
    "3. Términos y condiciones cambios de fecha o cortesías: salitremagico.com.co/terminos-y-condiciones/\n"
    "4. Términos y condiciones generales de Salitre Mágico: salitremagico.com.co/terminos-y-condiciones/\n"
    "5. Políticas y tratamiento de datos personales: salitremagico.com.co/aviso-de-privacidad/"
)
LAYOUT_SALITRE_MAGICO = {
    "width": 190, "height": 286, "background_color": "#ffffff",
    "elements": [
        {"type": "image", "x": 0, "y": 0, "width": 190, "height": 64, "image_key": "header", "fit": "cover"},
        {"type": "image", "x": 128, "y": 6, "width": 54, "height": 28, "image_key": "logo", "fit": "contain"},

        # --- Panel de datos del ticket: un encabezado propio y 3 columnas
        # claramente separadas (código/evento/fecha · productos · QR), en
        # vez de amontonar todo pegado al borde superior del panel.
        {"type": "rect", "x": 0, "y": 64, "width": 190, "height": 96, "color": "#7b3fb0"},
        {"type": "text", "x": 12, "y": 72, "width": 166, "height": 7, "content": "DETALLES DE TU ENTRADA",
         "fontSize": 9, "fontWeight": "bold", "color": "#ffffff"},

        {"type": "text", "x": 12, "y": 86, "width": 80, "height": 6, "content": "Número de entrada:", "fontSize": 8, "fontWeight": "bold", "color": "#ffffff"},
        {"type": "text", "x": 12, "y": 94, "width": 80, "height": 10, "field": "codigo", "fontSize": 9, "color": "#7b3fb0", "background": "#ffffff", "borderRadius": 3, "padding": 3},
        {"type": "text", "x": 12, "y": 108, "width": 80, "height": 6, "content": "Evento:", "fontSize": 8, "fontWeight": "bold", "color": "#ffffff"},
        {"type": "text", "x": 12, "y": 116, "width": 80, "height": 10, "field": "convenio", "fontSize": 9, "color": "#7b3fb0", "background": "#ffffff", "borderRadius": 3, "padding": 3},
        {"type": "text", "x": 12, "y": 130, "width": 80, "height": 6, "content": "Válido desde / hasta:", "fontSize": 8, "fontWeight": "bold", "color": "#ffffff"},
        {"type": "text", "x": 12, "y": 138, "width": 38, "height": 9, "field": "fecha", "fontSize": 7.5, "color": "#7b3fb0", "background": "#ffffff", "borderRadius": 3, "padding": 2},
        {"type": "text", "x": 53, "y": 138, "width": 39, "height": 9, "field": "fecha_vencimiento", "fontSize": 7.5, "color": "#7b3fb0", "background": "#ffffff", "borderRadius": 3, "padding": 2},

        {"type": "text", "x": 96, "y": 86, "width": 56, "height": 6, "content": "Productos incluidos:", "fontSize": 8, "fontWeight": "bold", "color": "#ffffff"},
        {"type": "list", "x": 96, "y": 94, "width": 56, "height": 52, "field": "productos_incluidos", "mode": "table",
         "fontSize": 7, "color": "#ffffff", "columns": [{"key": "nombre", "label": "Producto"}, {"key": "cantidad", "label": "Cant."}]},

        {"type": "text", "x": 156, "y": 86, "width": 26, "height": 6, "content": "Escanea aquí", "fontSize": 6.5, "fontWeight": "bold", "textAlign": "center", "color": "#ffffff"},
        {"type": "qr", "x": 156, "y": 94, "width": 26, "height": 26},

        {"type": "text", "x": 0, "y": 168, "width": 190, "height": 12, "content": "¡HOLA!", "fontSize": 15,
         "fontWeight": "bold", "textAlign": "center", "color": "#e6118f"},
        {"type": "text", "x": 25, "y": 184, "width": 140, "height": 14, "content": "Bienvenido(a) a nuestros términos y condiciones.",
         "fontSize": 9, "fontWeight": "bold", "textAlign": "center", "color": "#ffffff", "background": "#ff5fa8", "borderRadius": 8, "padding": 3},

        # --- Términos y condiciones: encabezado de sección propio y texto
        # más grande (8.5 en vez de 7) dentro de un bloque más alto para
        # que siga cabiendo completo, sin recortarse.
        {"type": "text", "x": 12, "y": 206, "width": 166, "height": 8, "content": "TÉRMINOS Y CONDICIONES",
         "fontSize": 10, "fontWeight": "bold", "color": "#7b3fb0"},
        {"type": "rect", "x": 0, "y": 216, "width": 190, "height": 40, "color": "#eaf6fb"},
        {"type": "text", "x": 14, "y": 222, "width": 162, "height": 32, "content": TERMINOS_SALITRE,
         "fontSize": 8.5, "color": "#333366"},

        {"type": "text", "x": 12, "y": 266, "width": 110, "height": 8, "content": "Agrega tu QR a Google Pay o Apple Wallet", "fontSize": 7.5, "fontWeight": "bold", "color": "#7b3fb0"},
        {"type": "image", "x": 124, "y": 262, "width": 30, "height": 12, "image_key": "google", "fit": "contain"},
        {"type": "image", "x": 156, "y": 262, "width": 30, "height": 12, "image_key": "apple", "fit": "contain"},
    ],
}

# The single source of truth: the ONLY 4 fixed brand designs this app
# knows about, keyed by their internal `clave` (never a database column
# — see the module docstring). Order here is the order
# `GET /api/plantillas/catalogo` lists them in.
CATALOGO = {
    "cine_colombia": {
        "nombre": "Cine Colombia",
        "layout": LAYOUT_CINE_COLOMBIA,
        "imagenes": {"logo": "cine_logo_real.png"},
    },
    "mundo_aventura": {
        "nombre": "Mundo Aventura",
        "layout": LAYOUT_MUNDO_AVENTURA,
        "imagenes": {"logo": "mundo_logo_real.png"},
    },
    "wellness_spa": {
        "nombre": "Wellness Spa",
        "layout": LAYOUT_WELLNESS_SPA,
        "imagenes": {"header": "wellness_header.png", "logo": "wellness_logo_real.png"},
    },
    "salitre_magico": {
        "nombre": "Salitre Mágico",
        "layout": LAYOUT_SALITRE_MAGICO,
        "imagenes": {
            "header": "salitre_header.png", "logo": "salitre_wordmark_real.png",
            "google": "badge_google.png", "apple": "badge_apple.png",
        },
    },
}


class ClaveInvalida(ValueError):
    """Raised whenever code asks for a `clave` that isn't one of the 4
    fixed catalog entries above — always caught and turned into a 400/404
    by whichever router/service triggered it, never a 500."""


@lru_cache(maxsize=None)
def _imagenes_base64(clave: str) -> dict[str, str]:
    """Base64-encodes a catalog design's bundled image files once per
    process — they're static files shipped with the code (see
    app/static/plantillas_catalogo/), never uploaded/changed at runtime,
    so caching is safe and avoids re-reading disk on every ticket."""
    entrada = CATALOGO[clave]
    resultado: dict[str, str] = {}
    for key, filename in entrada["imagenes"].items():
        with open(os.path.join(_ASSETS_DIR, filename), "rb") as f:
            resultado[key] = base64.b64encode(f.read()).decode("ascii")
    return resultado


def existe(clave: str) -> bool:
    return clave in CATALOGO


def nombre_de(clave: str) -> str:
    if clave not in CATALOGO:
        raise ClaveInvalida(clave)
    return CATALOGO[clave]["nombre"]


def logo_bytes(clave: str) -> bytes | None:
    """Raw bytes of this design's `logo` brand image — used by
    routers/convenios.py's `/imagen-marca` endpoint so a convenio that
    selected a catalog design shows its REAL brand logo (never the
    generic diagonal-stripes placeholder) on the affiliate catalog card,
    benefit detail page, etc. `None` if the clave is invalid or this
    design has no `logo` image key (never raises)."""
    entrada = CATALOGO.get(clave)
    if entrada is None:
        return None
    filename = entrada["imagenes"].get("logo")
    if not filename:
        return None
    with open(os.path.join(_ASSETS_DIR, filename), "rb") as f:
        return f.read()


def generar_pdf(clave: str, contexto: dict) -> bytes:
    """Renders a real PDF for this catalog design via the SAME layout
    engine (`template_engine.generar_pdf_desde_layout`) every other
    layout-format plantilla already used — a real ticket and this
    design's preview are always pixel-identical, since they're the same
    function call."""
    if clave not in CATALOGO:
        raise ClaveInvalida(clave)
    entrada = CATALOGO[clave]
    return template_engine.generar_pdf_desde_layout(entrada["layout"], contexto, _imagenes_base64(clave))
