"""
Real per-convenio ticket template rendering: Jinja2 (HTML template ->
filled HTML) + WeasyPrint (HTML -> PDF bytes).

IMPORTANT CONTEXT FOR ANYONE READING THIS LATER: prior to this module,
NOTHING in this codebase read the `plantillas` table's `storage_path` or
rendered a real per-brand HTML/Jinja2 template. `pdf_service.generar_ticket`
always produced an identical generic ReportLab placeholder for every
convenio, regardless of what — if anything — was registered in
`plantillas`. This module, plus the wiring added to
`pdf_service.generar_ticket`, is what actually turns an uploaded HTML file
into the PDF a customer downloads. See `pdf_service.py` for how the two
fit together (real plantilla when one is active, generic ReportLab
fallback otherwise).

REQUIRED_VARIABLES below is the canonical, first-defined-here contract a
plantilla HTML file must reference (as a real Jinja2 identifier — a
`{{ convenio.nombre }}` expression, a `{% for item in items %}` loop,
etc.) to be accepted. There is no prior "Fase 7" definition anywhere in
the repository to match against — this list is deliberately kept close to
the wording used when this feature was requested (`items`, `convenio`,
`fecha_emision`, `fecha_vencimiento`), plus `afiliado` and `transaccion_id`
since a ticket that omits either can't actually serve as proof of who
bought what.
"""
from __future__ import annotations

import base64
import html as html_lib
import io
import re

import barcode as barcode_lib
import jinja2
import qrcode
from barcode.writer import ImageWriter
from jinja2 import meta
from weasyprint import HTML

REQUIRED_VARIABLES: set[str] = {
    "convenio",
    "items",
    "afiliado",
    "transaccion_id",
    "fecha_emision",
    "fecha_vencimiento",
}

_env = jinja2.Environment(autoescape=jinja2.select_autoescape(["html"]))


class PlantillaInvalida(ValueError):
    """Raised for any reason an uploaded/edited HTML file can't be used as
    a plantilla — always carries a human-readable, specific message."""


def extraer_variables(html_source: str) -> set[str]:
    """The set of top-level Jinja2 identifiers actually referenced by
    `html_source` (covers `{{ x }}`, `{% for i in items %}`, `{% if x %}`,
    etc.) — NOT a naive text search, so it doesn't false-positive on the
    word "convenio" appearing in plain prose outside a Jinja2 expression."""
    try:
        ast = _env.parse(html_source)
    except jinja2.TemplateSyntaxError as exc:
        raise PlantillaInvalida(f"El archivo no es una plantilla Jinja2 válida: {exc.message} (línea {exc.lineno}).") from exc
    return meta.find_undeclared_variables(ast)


def validar_plantilla_html(html_source: str) -> None:
    """Raises PlantillaInvalida with a specific, actionable message if the
    file isn't usable — never accepts something that would only fail
    later, silently, the first time someone actually buys this convenio."""
    if not html_source.strip():
        raise PlantillaInvalida("El archivo está vacío.")
    if "<" not in html_source or ">" not in html_source:
        raise PlantillaInvalida("El archivo no parece contener HTML.")

    variables = extraer_variables(html_source)
    faltantes = sorted(REQUIRED_VARIABLES - variables)
    if faltantes:
        raise PlantillaInvalida(
            "A la plantilla le falta" + ("n" if len(faltantes) > 1 else "") +
            " la" + ("s" if len(faltantes) > 1 else "") +
            f" variable{'s' if len(faltantes) > 1 else ''} requerida{'s' if len(faltantes) > 1 else ''}: "
            + ", ".join(faltantes) + "."
        )


def renderizar_html(html_source: str, contexto: dict) -> str:
    template = _env.from_string(html_source)
    return template.render(**contexto)


def html_a_pdf(html_rendered: str) -> bytes:
    return HTML(string=html_rendered).write_pdf()


def generar_pdf_desde_plantilla(html_source: str, contexto: dict) -> bytes:
    return html_a_pdf(renderizar_html(html_source, contexto))


def validar_y_renderizar(html_source: str, contexto: dict) -> bytes:
    """The full gate a plantilla must pass BEFORE it is ever persisted:
    real HTML, valid Jinja2 syntax, every required variable present, AND
    an actual successful render through WeasyPrint with fixture data —
    not just static checks. A template that parses fine but WeasyPrint
    can't lay out (bad CSS, a malformed embedded image, etc.) must never
    be saved only to fail on the first real purchase; this function is
    reused by both `POST /api/plantillas` (persists) and
    `POST /api/plantillas/preview` (doesn't) so neither path can drift
    from the other's notion of "valid"."""
    validar_plantilla_html(html_source)
    try:
        return generar_pdf_desde_plantilla(html_source, contexto)
    except Exception as exc:
        raise PlantillaInvalida(f"No se pudo generar el PDF de prueba con esta plantilla: {exc}") from exc


# --- Rich content fields (logo, títulos, términos, etc.) ------------------
# These are ADDITIONAL, OPTIONAL Jinja2 variables layered on top of the
# required contract above — an admin fills them in a real form (see
# schemas/plantilla.py PlantillaContenidoPayload and routers/plantillas.py)
# instead of hand-typing this content into the HTML file itself. A
# template author may reference any of these, all of them, or none.
CAMPOS_CONTENIDO_OPCIONALES = (
    "titulo_ticket", "subtitulo", "descripcion_beneficio", "texto_informativo",
    "terminos_condiciones", "restricciones", "instrucciones_redencion",
)


def campos_contenido(config: dict, logo_base64: str | None, logo_cooperativa_base64: str | None) -> dict:
    extra = {campo: config.get(campo) or "" for campo in CAMPOS_CONTENIDO_OPCIONALES}
    extra["logo_base64"] = logo_base64
    extra["logo_cooperativa_base64"] = logo_cooperativa_base64
    return extra




# --- QR / barcode: pure visual representations of the OFFICIAL code ------
# The entity (Cine Colombia, Salitre Mágico, etc.) supplies `codigo` —
# BEET never generates, modifies, re-encodes, truncates, or substitutes
# it. These two functions ONLY draw that exact string into an image; the
# string handed to `qrcode`/`barcode` below is byte-for-byte the same
# value passed in — see pdf_service._contexto_ticket, which sources it
# straight from `unidad.codigo` with no transformation in between.
# Showing both a QR and a barcode for the same code is not "BEET
# authorizing" either format for redemption elsewhere — it is only ever
# a rendering choice made by whichever elements the plantilla includes.


def generar_qr_base64(codigo: str) -> str:
    img = qrcode.make(codigo)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def generar_barcode_base64(codigo: str) -> str:
    buffer = io.BytesIO()
    barcode_lib.get_barcode_class("code128")(codigo, writer=ImageWriter()).write(
        buffer, options={"write_text": False, "quiet_zone": 1}
    )
    return base64.b64encode(buffer.getvalue()).decode("ascii")


# --- Visual builder: admin-configured element list -> real HTML ----------
# The admin never writes HTML/CSS/JS (see routers/plantillas.py,
# schemas/plantilla.py). Every element type below is fixed and
# backend-owned; the only admin-supplied free text is `text`/`terms`
# element content, which is ALWAYS escaped through `html.escape` before
# being placed in the document — an admin typing "<script>...</script>"
# ends up with that literal, inert text on the ticket, never live markup.

_TEXT_SIZES = {"small": "12px", "normal": "15px", "large": "20px", "title": "28px"}


def _esc(value: str) -> str:
    return html_lib.escape(value, quote=True)


def _render_elemento(elemento: dict, contexto: dict, logo_base64: str | None) -> str:
    tipo = elemento["type"]
    items = contexto.get("items") or []
    codigo_principal = items[0]["codigo"] if items else ""

    if tipo == "logo":
        if not logo_base64:
            return ""
        return f'<div class="pl-block pl-center"><img class="pl-logo" src="data:image/png;base64,{logo_base64}" /></div>'

    if tipo == "text":
        size = _TEXT_SIZES.get(elemento.get("size", "normal"), _TEXT_SIZES["normal"])
        peso = "bold" if elemento.get("bold") else "normal"
        align = elemento.get("align", "left")
        if align not in ("left", "center", "right"):
            align = "left"
        contenido = _esc(elemento.get("content", "")).replace("\n", "<br/>")
        return f'<div class="pl-block" style="font-size:{size};font-weight:{peso};text-align:{align};">{contenido}</div>'

    if tipo == "date":
        return f'<div class="pl-block"><span class="pl-label">Fecha de emisión:</span> {_esc(contexto.get("fecha_emision", ""))}</div>'

    if tipo == "code":
        return f'<div class="pl-block"><span class="pl-label">Código:</span> <span class="pl-code">{_esc(codigo_principal)}</span></div>'

    if tipo == "qr":
        qr_b64 = contexto.get("qr_base64", "")
        if not qr_b64:
            return ""
        return f'<div class="pl-block pl-center"><img class="pl-qr" src="data:image/png;base64,{qr_b64}" /></div>'

    if tipo == "barcode":
        bc_b64 = contexto.get("barcode_base64", "")
        if not bc_b64:
            return ""
        return f'<div class="pl-block pl-center"><img class="pl-barcode" src="data:image/png;base64,{bc_b64}" /></div>'

    if tipo == "terms":
        contenido = _esc(elemento.get("content", "")).replace("\n", "<br/>")
        return f'<div class="pl-block pl-terms"><div class="pl-label">Términos y condiciones</div><div class="pl-terms-text">{contenido}</div></div>'

    if tipo == "items":
        convenio = contexto.get("convenio") or {}
        filas = "".join(
            f'<tr><td>{_esc(convenio.get("nombre", ""))}</td><td>{_esc(item.get("codigo", ""))}</td></tr>'
            for item in items
        ) or '<tr><td colspan="2">Sin ítems</td></tr>'
        return (
            '<div class="pl-block"><table class="pl-items"><thead><tr><th>Producto</th><th>Código</th></tr></thead>'
            f"<tbody>{filas}</tbody></table></div>"
        )

    return ""


_ELEMENT_STYLE = """
body { font-family: Helvetica, Arial, sans-serif; color: #1a1a1a; margin: 0; padding: 24px; }
.pl-block { margin-bottom: 14px; }
.pl-center { text-align: center; }
.pl-logo { max-height: 90px; max-width: 100%; }
.pl-label { font-weight: bold; }
.pl-code { font-family: monospace; font-size: 16px; }
.pl-qr { width: 140px; height: 140px; }
.pl-barcode { max-width: 100%; height: 70px; }
.pl-terms { font-size: 10px; color: #444; border-top: 1px solid #ccc; padding-top: 10px; margin-top: 18px; }
.pl-terms-text { line-height: 1.5; }
.pl-items { width: 100%; border-collapse: collapse; font-size: 13px; }
.pl-items th, .pl-items td { border: 1px solid #ddd; padding: 6px 8px; text-align: left; }
"""


def construir_html_desde_elementos(elements: list[dict], contexto: dict, logo_base64: str | None) -> str:
    """The ONLY function that turns an admin's visual-builder configuration
    into real HTML. `elements` is a list of already-Pydantic-validated
    dicts (see schemas/plantilla.py `PlantillaElement`) — every type is
    from the fixed whitelist, so there is no arbitrary markup path here at
    all, unlike the legacy raw-HTML upload this replaces."""
    cuerpo = "".join(_render_elemento(el, contexto, logo_base64) for el in elements)
    return f"<html><head><style>{_ELEMENT_STYLE}</style></head><body>{cuerpo}</body></html>"


def generar_pdf_desde_elementos(elements: list[dict], contexto: dict, logo_base64: str | None) -> bytes:
    return html_a_pdf(construir_html_desde_elementos(elements, contexto, logo_base64))


def contexto_preview(*, convenio_nombre: str, convenio_descripcion: str | None, n_unidades: int = 1) -> dict:
    """Fixture data for the "preview before you confirm" flow — clearly
    fake values (PREVIEW-0000, today's date) so nobody mistakes a preview
    PDF for a real ticket. `n_unidades` (only meaningful for the layout
    format's `unidades`/`codigos`/`qrs`/`barcodes` collections) lets the
    admin preview a `list` element in `grid_qr`/`table` mode with more
    than one example row — still 100% fake data, never a real code."""
    from datetime import date

    hoy = date.today().isoformat()
    codigo_preview = "PREVIEW-0000"
    n_unidades = max(1, min(n_unidades, 20))
    codigos_preview = [codigo_preview] if n_unidades == 1 else [f"PREVIEW-{i:04d}" for i in range(1, n_unidades + 1)]
    return {
        "convenio": {"id": 0, "nombre": convenio_nombre, "descripcion": convenio_descripcion},
        "afiliado": {"nombres": "Afiliado", "apellidos": "de Prueba", "documento": "0000000000"},
        "items": [{"codigo": codigo_preview, "estado": "disponible"}],
        "transaccion_id": 0,
        "fecha_emision": hoy,
        "fecha_vencimiento": hoy,
        "fecha_compra": hoy,
        "qr_base64": generar_qr_base64(codigo_preview),
        "barcode_base64": generar_barcode_base64(codigo_preview),
        # --- layout placeholders (see pdf_service._contexto_ticket for
        # the real-purchase equivalent of every one of these) ---
        "codigo": codigo_preview,
        "documento": "0000000000",
        "nombre_afiliado": "Afiliado de Prueba",
        "contenido": "",
        "grupo": "",
        "cantidad": n_unidades,
        "fecha": hoy,
        "unidades": [{"codigo": c, "estado": "disponible"} for c in codigos_preview],
        "codigos": codigos_preview,
        "qrs": [generar_qr_base64(c) for c in codigos_preview],
        "barcodes": [generar_barcode_base64(c) for c in codigos_preview],
        "productos_incluidos": [{"nombre": convenio_nombre, "cantidad": n_unidades}],
    }


# --- Layout: a real visual editor (background + freely positioned
# elements), one per convenio ---------------------------------------------
#
# This is the CURRENT format new plantillas are created against (see
# routers/plantillas.py's `/layout` endpoints and PlantillaBuilder.jsx).
# The `template_key` diseños base, an earlier round's admin-uploaded
# `html`, the `elements` flow-layout visual builder, and the oldest bare
# HTML file all keep rendering exactly as before via
# pdf_service.generar_ticket's fallback chain — nothing below touches
# them.
#
# SECURITY: every element is a plain dict whose `type` must be one of
# TIPOS_ELEMENTO_LAYOUT below. There is no `eval`/`exec`/dynamic-code-
# execution anywhere in this module — a layout is only ever interpreted
# as typed configuration, never run as a program. `content` and every
# `{{placeholder}}` substitution are ALWAYS passed through `html.escape`
# before reaching the document (see `_resolver_texto`), so admin-typed
# (or, if the stored JSON were ever tampered with, attacker-typed) text
# containing `<script>`/HTML tags always ends up as inert literal text,
# never live markup — same guarantee the `elements` format above already
# had. `routers/plantillas.py` calls `validar_layout` below on every
# create/preview BEFORE any render is attempted, and every image element
# only ever references a `storage_service`-issued key resolved server-
# side — the JSON itself never carries a raw file path or URL.
#
# UNITS: `width`/`height` on the layout itself and on every element are
# millimeters — this keeps the editor's on-screen coordinates and the
# renderer's `@page` size in the exact same unit, so "where you drop it
# in the editor" is "where it prints", with no unit-conversion drift.

TIPOS_ELEMENTO_LAYOUT = {"rect", "image", "text", "qr", "barcode", "list"}
MODOS_LISTA_LAYOUT = {"table", "grid_qr", "rows"}
# What a `list` element is allowed to iterate — every one of these is
# built by pdf_service._contexto_ticket_layout from REAL rows already
# reachable via transacciones -> transaccion_unidades ->
# unidades_inventario; nothing here is ever fabricated data (see that
# function's docstring).
COLECCIONES_LAYOUT_VALIDAS = {"unidades", "codigos", "qrs", "barcodes", "productos_incluidos"}

_PLACEHOLDER_LAYOUT_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")


class LayoutInvalido(ValueError):
    """Raised by `validar_layout` — the admin's layout JSON has a shape
    problem (bad type, out-of-range coordinate, unknown collection,
    missing image_key, etc.). Always caught by routers/plantillas.py and
    turned into a 400 with this message; nothing is ever persisted or
    rendered from a layout that fails this check."""


def _num_layout(valor, default: float = 0.0, minimo: float | None = None, maximo: float | None = None) -> float:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        numero = default
    if minimo is not None:
        numero = max(minimo, numero)
    if maximo is not None:
        numero = min(maximo, numero)
    return numero


def resolver_campo_layout(nombre: str, contexto: dict):
    """Dotted-path lookup against the render context (e.g. `afiliado.nombres`,
    or a top-level scalar like `codigo`/`documento`/`convenio`/
    `transaccion_id`/`contenido`/`grupo`/`cantidad`/`fecha`/
    `fecha_vencimiento`, or a whole collection like `unidades`/`codigos`).
    Returns the raw Python value (a `list`/`dict` for a collection) —
    callers decide whether to stringify+escape it (`_resolver_texto`) or
    iterate it (`_render_lista_layout`). `None` for anything not present —
    never fabricated, never raises."""
    actual = contexto
    for parte in nombre.split("."):
        if isinstance(actual, dict) and parte in actual:
            actual = actual[parte]
        else:
            return None
    return actual


def _texto_de_valor(crudo) -> str:
    """Stringifies a resolved placeholder value for display. A bare
    `{{convenio}}` (no `.nombre`) resolves to the `convenio` dict, not a
    string — rather than print a Python dict repr, this prefers its
    `nombre` key (every object this context ever nests — `convenio`,
    `afiliado` — has one), falling back to `str()` for anything else
    (a plain scalar, or a dict with no `nombre`)."""
    if crudo is None:
        return ""
    if isinstance(crudo, dict):
        return str(crudo.get("nombre", crudo))
    return str(crudo)


def _resolver_texto(contenido: str | None, campo: str | None, contexto: dict) -> str:
    """Scalar text resolution for a `text` element — ALWAYS escaped, for
    both paths: a whole-element `field` (`field: "codigo"`) and any
    `{{...}}` token embedded inside a literal `content` string (e.g.
    `content: "Documento: {{documento}}"`). The literal part of
    `content` is escaped FIRST (neutralizing any HTML an admin typed),
    then `{{...}}` tokens (unaffected by escaping — curly braces aren't
    special to `html.escape`) are substituted with their own escaped
    values — so this is safe in either order combined."""
    if campo is not None:
        return _esc(_texto_de_valor(resolver_campo_layout(campo, contexto)))
    if contenido is None:
        return ""
    escapado = _esc(str(contenido))

    def _sub(match: "re.Match[str]") -> str:
        return _esc(_texto_de_valor(resolver_campo_layout(match.group(1), contexto)))

    return _PLACEHOLDER_LAYOUT_RE.sub(_sub, escapado)


def _estilo_comun_layout(el: dict) -> str:
    x = _num_layout(el.get("x"), 0, -2000, 5000)
    y = _num_layout(el.get("y"), 0, -2000, 5000)
    w = _num_layout(el.get("width"), 10, 0.1, 5000)
    h = _num_layout(el.get("height"), 10, 0.1, 5000)
    opacidad = _num_layout(el.get("opacity"), 1, 0, 1)
    rotacion = _num_layout(el.get("rotation"), 0, -360, 360)
    estilo = f"position:absolute;left:{x}mm;top:{y}mm;width:{w}mm;height:{h}mm;opacity:{opacidad};"
    if rotacion:
        estilo += f"transform:rotate({rotacion}deg);"
    return estilo


def _render_lista_layout(el: dict, estilo_base: str, contexto: dict) -> str:
    campo = el.get("field") or ""
    items = resolver_campo_layout(campo, contexto)
    if not isinstance(items, list) or not items:
        return f'<div style="{estilo_base}"></div>'

    modo = el.get("mode") if el.get("mode") in MODOS_LISTA_LAYOUT else "rows"
    font_size = _num_layout(el.get("fontSize"), 11, 4, 100)
    color = _esc(str(el.get("color") or "#000000"))

    if modo == "table":
        columnas = el.get("columns") or [{"key": "nombre", "label": "Producto"}, {"key": "cantidad", "label": "Cantidad"}]
        encabezado = "".join(
            f"<th style='text-align:left;border-bottom:1px solid #999;padding:2mm;font-size:{font_size}pt;'>{_esc(str(c.get('label', '')))}</th>"
            for c in columnas if isinstance(c, dict)
        )
        filas = ""
        for item in items:
            if not isinstance(item, dict):
                continue
            celdas = "".join(
                f"<td style='padding:2mm;border-bottom:1px solid #ddd;font-size:{font_size}pt;'>{_esc(str(item.get(c.get('key', ''), '')))}</td>"
                for c in columnas if isinstance(c, dict)
            )
            filas += f"<tr>{celdas}</tr>"
        return (
            f'<div style="{estilo_base}overflow:hidden;color:{color};">'
            f'<table style="width:100%;border-collapse:collapse;"><thead><tr>{encabezado}</tr></thead><tbody>{filas}</tbody></table>'
            "</div>"
        )

    if modo == "grid_qr":
        columnas_grid = max(1, int(_num_layout(el.get("gridColumns"), 2, 1, 6)))
        ancho_celda = 100 / columnas_grid
        celdas = ""
        for item in items:
            if not isinstance(item, dict):
                continue
            codigo_item = item.get("codigo") or contexto.get("codigo") or ""
            # Falls back to the item's own (real) código when there's no
            # `nombre` to show — e.g. `unidades`/`codigos` collections,
            # which never carry a product name (there's no products
            # catalog in this schema) — never a blank caption when a
            # real, non-fabricated label is available.
            nombre_item = _esc(str(item.get("nombre") or codigo_item or ""))
            qr_img = f'<img src="data:image/png;base64,{generar_qr_base64(str(codigo_item))}" style="width:80%;" />' if codigo_item else ""
            celdas += (
                f'<div style="display:inline-block;width:{ancho_celda}%;box-sizing:border-box;text-align:center;'
                f'padding:2mm;vertical-align:top;">{qr_img}'
                f'<div style="font-size:{font_size}pt;margin-top:1mm;color:{color};">{nombre_item}</div></div>'
            )
        return f'<div style="{estilo_base}overflow:hidden;">{celdas}</div>'

    # modo == "rows"
    filas_html = ""
    for item in items:
        if isinstance(item, dict):
            nombre = str(item.get("nombre", ""))
            cantidad = item.get("cantidad")
            texto = f"{nombre} × {cantidad}" if cantidad else nombre
        else:
            texto = str(item)
        filas_html += f'<div style="padding:1mm 0;font-size:{font_size}pt;color:{color};">{_esc(texto)}</div>'
    return f'<div style="{estilo_base}overflow:hidden;">{filas_html}</div>'


def _render_layout_elemento(el: dict, contexto: dict, imagenes_base64: dict[str, str]) -> str:
    if not isinstance(el, dict) or el.get("visible") is False:
        return ""
    tipo = el.get("type")
    estilo_base = _estilo_comun_layout(el)

    if tipo == "rect":
        color = _esc(str(el.get("color") or "#ffffff"))
        radio = _num_layout(el.get("borderRadius"), 0, 0, 500)
        return f'<div style="{estilo_base}background:{color};border-radius:{radio}mm;"></div>'

    if tipo == "image":
        b64 = imagenes_base64.get(str(el.get("image_key") or ""))
        if not b64:
            return ""
        ajuste = "contain" if el.get("fit") == "contain" else "cover"
        return (
            f'<div style="{estilo_base}overflow:hidden;">'
            f'<img src="data:image/png;base64,{b64}" style="width:100%;height:100%;object-fit:{ajuste};" />'
            "</div>"
        )

    if tipo == "text":
        texto = _resolver_texto(el.get("content"), el.get("field"), contexto)
        font_size = _num_layout(el.get("fontSize"), 12, 4, 300)
        font_family = _esc(str(el.get("fontFamily") or "Helvetica, Arial, sans-serif"))
        font_weight = _esc(str(el.get("fontWeight") or "normal"))
        align = el.get("textAlign") if el.get("textAlign") in ("left", "center", "right", "justify") else "left"
        color = _esc(str(el.get("color") or "#000000"))
        padding = _num_layout(el.get("padding"), 0, 0, 50)
        radio = _num_layout(el.get("borderRadius"), 0, 0, 500)
        estilo = (
            f"{estilo_base}font-size:{font_size}pt;font-family:{font_family};font-weight:{font_weight};"
            f"text-align:{align};color:{color};padding:{padding}mm;border-radius:{radio}mm;"
            "overflow:hidden;white-space:pre-wrap;box-sizing:border-box;"
        )
        if el.get("background"):
            estilo += f"background:{_esc(str(el.get('background')))};"
        return f'<div style="{estilo}">{texto}</div>'

    if tipo == "qr":
        codigo = contexto.get("codigo") or ""
        if not codigo:
            return ""
        return f'<div style="{estilo_base}"><img src="data:image/png;base64,{generar_qr_base64(str(codigo))}" style="width:100%;height:100%;" /></div>'

    if tipo == "barcode":
        codigo = contexto.get("codigo") or ""
        if not codigo:
            return ""
        return (
            f'<div style="{estilo_base}">'
            f'<img src="data:image/png;base64,{generar_barcode_base64(str(codigo))}" style="width:100%;height:100%;object-fit:contain;" />'
            "</div>"
        )

    if tipo == "list":
        return _render_lista_layout(el, estilo_base, contexto)

    return ""


def construir_html_desde_layout(layout: dict, contexto: dict, imagenes_base64: dict[str, str]) -> str:
    """The ONLY function that turns an admin's visual-editor layout into
    real HTML — see the module docstring above for why this can never
    execute arbitrary code or markup."""
    ancho = _num_layout(layout.get("width"), 210, 20, 2000)
    alto = _num_layout(layout.get("height"), 297, 20, 2000)
    fondo = _esc(str(layout.get("background_color") or "#ffffff"))
    elementos = layout.get("elements") or []
    cuerpo = "".join(_render_layout_elemento(el, contexto, imagenes_base64) for el in elementos)
    return (
        "<html><head><style>"
        f"@page {{ size: {ancho}mm {alto}mm; margin: 0; }}"
        f"body {{ margin:0; padding:0; width:{ancho}mm; height:{alto}mm; position:relative; "
        f"background:{fondo}; font-family: Helvetica, Arial, sans-serif; }}"
        "</style></head><body>"
        f"{cuerpo}"
        "</body></html>"
    )


def generar_pdf_desde_layout(layout: dict, contexto: dict, imagenes_base64: dict[str, str]) -> bytes:
    return html_a_pdf(construir_html_desde_layout(layout, contexto, imagenes_base64))


def validar_layout(layout: dict) -> None:
    """Structural validation run BEFORE anything is persisted or rendered
    (see routers/plantillas.py's `/layout` create+preview endpoints) —
    never executes the JSON, only checks its shape against fixed
    whitelists and numeric ranges. Raises `LayoutInvalido` with a
    human-readable reason on the first problem found."""
    if not isinstance(layout, dict):
        raise LayoutInvalido("El layout debe ser un objeto JSON.")
    ancho, alto = layout.get("width"), layout.get("height")
    if not isinstance(ancho, (int, float)) or not (20 <= ancho <= 2000):
        raise LayoutInvalido("El ancho del layout ('width') debe ser un número entre 20 y 2000 (mm).")
    if not isinstance(alto, (int, float)) or not (20 <= alto <= 2000):
        raise LayoutInvalido("El alto del layout ('height') debe ser un número entre 20 y 2000 (mm).")
    elementos = layout.get("elements")
    if not isinstance(elementos, list) or not elementos:
        raise LayoutInvalido("El layout debe tener al menos un elemento en 'elements'.")
    if len(elementos) > 200:
        raise LayoutInvalido("Demasiados elementos en el layout (máximo 200).")

    for i, el in enumerate(elementos):
        if not isinstance(el, dict):
            raise LayoutInvalido(f"El elemento #{i} debe ser un objeto.")
        tipo = el.get("type")
        if tipo not in TIPOS_ELEMENTO_LAYOUT:
            raise LayoutInvalido(f"Tipo de elemento inválido en el elemento #{i}: '{tipo}'.")
        for campo_num in ("x", "y", "width", "height"):
            valor = el.get(campo_num)
            if not isinstance(valor, (int, float)) or not (-2000 <= valor <= 5000):
                raise LayoutInvalido(f"Coordenada/tamaño inválido en el elemento #{i} ('{campo_num}').")
        if tipo == "list":
            if el.get("field") not in COLECCIONES_LAYOUT_VALIDAS:
                validas = ", ".join(sorted(COLECCIONES_LAYOUT_VALIDAS))
                raise LayoutInvalido(f"El elemento de lista #{i} debe usar 'field' uno de: {validas}.")
            if el.get("mode") is not None and el.get("mode") not in MODOS_LISTA_LAYOUT:
                raise LayoutInvalido(f"Modo de lista inválido en el elemento #{i}.")
        if tipo == "image" and not el.get("image_key"):
            raise LayoutInvalido(f"El elemento de imagen #{i} debe indicar 'image_key'.")


def validar_y_renderizar_layout(layout: dict, contexto: dict, imagenes_base64: dict[str, str]) -> bytes:
    """Same gate as `validar_y_renderizar` above, for the layout format:
    structural validation AND an actual successful WeasyPrint render
    with fixture data, reused by both the create and preview endpoints
    so neither can drift from the other's notion of "valid"."""
    validar_layout(layout)
    try:
        return generar_pdf_desde_layout(layout, contexto, imagenes_base64)
    except Exception as exc:
        raise LayoutInvalido(f"No se pudo generar el PDF de prueba con este layout: {exc}") from exc
