"""
PDF generation for tickets and debt-assumption documents.

Every function here assumes the caller has ALREADY verified ownership and
cooperative scope — this module only turns already-authorized data into
PDF bytes, uploads them through `storage_service`, and returns the
storage reference. It never queries by a client-supplied id and never
persists a PDF (or a signature image) anywhere except through
`storage_service` — only the returned reference string is meant to be
stored on the corresponding model.

REAL BRAND TEMPLATES: `generar_ticket()` below checks, in order,
`convenio.plantilla_catalogo_clave` (one of the 4 fixed, code-owned
catalog designs in services/plantillas_catalogo.py), then the
convenio's `plantillas` table (an active, real per-convenio uploaded
plantilla — the highest `version` among the active ones — rendered with
real purchase data via services/template_engine.py). If neither exists,
OR something unexpected goes wrong rendering either one (corrupted
upload, storage outage), this falls back to the clearly-labeled generic
ReportLab PLACEHOLDER PDF below — a customer must never be blocked from
getting their (still real, still redeemable) ticket code just because a
brand template failed to render.
"""
from __future__ import annotations

import base64
import io
import json
import logging
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from app.models.convenio import Convenio
from app.models.plantilla import Plantilla
from app.models.unidad_inventario import UnidadInventario
from app.services import plantillas_base, plantillas_catalogo, storage_service, template_engine

logger = logging.getLogger("beetticket.pdf")

# Fixed, generic legal text — the real `cooperativas` table has no
# configurable "texto_asuncion_deuda" column in this schema (unlike an
# earlier design assumption; see SCHEMA_NOTES.md), so there is nowhere to
# read a per-cooperativa version from. Documented here rather than
# invented as a new column.
TEXTO_ASUNCION_DEUDA_GENERICO = (
    "El afiliado declara conocer y aceptar las condiciones de asunción de deuda "
    "asociadas a la compra realizada mediante cupo de crédito, autorizando el "
    "descuento correspondiente del cupo asignado por la cooperativa según lo "
    "pactado, y reconoce esta obligación como una deuda exigible frente a la "
    "entidad."
)


def _draw_kv_lines(c: canvas.Canvas, x: float, y: float, pairs: list[tuple[str, str]], line_height: float = 0.7 * cm) -> float:
    for label, value in pairs:
        c.setFont("Helvetica-Bold", 10)
        c.drawString(x, y, f"{label}:")
        c.setFont("Helvetica", 10)
        c.drawString(x + 4.5 * cm, y, str(value))
        y -= line_height
    return y


def _wrap_text(text: str, max_chars: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) > max_chars:
            if current:
                lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def plantilla_activa(convenio: Convenio) -> Plantilla | None:
    """Highest-`version` plantilla with `estado=true` for this convenio —
    the one "currently in effect" per the pre-existing UNIQUE(convenio_id,
    version) design (see models/plantilla.py). Uses the already-loaded
    `convenio.plantillas` relationship rather than a fresh query, since
    every caller already holds a live `convenio` ORM object in an open
    session (routers/convenios.py eager-loads it with `selectinload` for
    its `/catalogo` and `/{id}/imagen-marca` callers).

    Public (no leading underscore): this is also the single source of
    truth `routers/convenios.py` reuses to decide the catalog card's
    branding image, so a convenio's ticket PDF and its catalog card
    always agree on which plantilla is "the active one" — never two
    separate implementations of the same rule."""
    activas = [p for p in convenio.plantillas if p.estado]
    if not activas:
        return None
    return max(activas, key=lambda p: p.version)


def logo_storage_path_de_plantilla(plantilla: Plantilla) -> str | None:
    """The convenio-branding image's storage key from a plantilla's stored
    config — `None` if nothing was ever uploaded, if the config can't be
    read back, or for the oldest legacy format (a bare HTML file with no
    JSON wrapper at all, hence no `logo_storage_path` concept). All 3
    JSON-based formats this app has ever written (`template_key` diseños
    base, an earlier round's admin-uploaded `html`, and the `elements`
    visual builder) share this same key — see generar_ticket() below,
    which reads it identically for each."""
    contenido = storage_service.download_bytes(plantilla.storage_path)
    if contenido is None:
        return None
    try:
        config = json.loads(contenido.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(config, dict):
        return None
    return config.get("logo_storage_path")


def _contexto_ticket(convenio: Convenio, unidad: UnidadInventario, variables: dict) -> dict:
    """Builds the real-plantilla render context from the same
    `convenio`/`unidad`/`variables` shape the generic placeholder already
    used — no caller needs to change. `unidad.codigo` is the OFFICIAL code
    the entity (Cine Colombia, Salitre Mágico, etc.) supplied — it is
    NEVER modified, re-encoded, or substituted; `qr_base64`/`barcode_base64`
    below are only visual representations of this exact same string (see
    template_engine.py's module docstring on that function pair).

    LAYOUT FORMAT EXTRA FIELDS: everything from `# --- layout placeholders`
    down is ONLY consumed by `template_engine`'s layout renderer
    (`resolver_campo_layout`/`{{...}}` tokens) — the pre-existing Jinja2
    formats above (`template_key`/`html`/`elements`) simply ignore keys
    they don't reference, so adding these here is 100% additive.

    `contenido`/`grupo` come straight from the unit's own real columns
    (both nullable, `""` when unset) — a layout referencing
    `{{contenido}}`/`{{grupo}}` gets whatever was actually loaded for
    that unit, never a fabricated value.

    `unidades`/`codigos`/`qrs`/`barcodes` are built from
    `variables["unidades_hermanas"]` — a list of EVERY unit belonging to
    the same transacción (see routers/tickets.py, which queries
    `transaccion_unidades` by `transaccion_id`), each a real row from
    `unidades_inventario`. This is what lets a layout draw one QR per
    unit (e.g. a purchase of `cantidad=4`) instead of only the single
    unit this specific PDF happens to be for. Falls back to a one-item
    list built from THIS unit alone when the caller doesn't pass it
    (e.g. the preview endpoint, which has no real transacción at all).

    `productos_incluidos` is a single row built ONLY from
    `convenio.nombre` + the transacción's `cantidad` — there is no
    `beneficios`/products catalog in this schema (by explicit design;
    see the architecture audit), so this never invents a product name
    that isn't `convenio.nombre` itself."""
    codigo_oficial = unidad.codigo
    hermanas = variables.get("unidades_hermanas") or [{"codigo": codigo_oficial, "estado": unidad.estado.value}]
    codigos = [h.get("codigo", "") for h in hermanas if h.get("codigo")]
    cantidad = variables.get("cantidad")

    return {
        "convenio": {"id": convenio.id, "nombre": convenio.nombre, "descripcion": convenio.descripcion},
        "afiliado": {
            "nombres": variables.get("afiliado_nombre", ""),
            "documento": variables.get("afiliado_documento", ""),
        },
        "items": [{"codigo": codigo_oficial, "estado": unidad.estado.value}],
        "transaccion_id": variables.get("transaccion_id"),
        "fecha_emision": datetime.now(timezone.utc).date().isoformat(),
        "fecha_vencimiento": convenio.fecha_fin.isoformat() if convenio.fecha_fin else None,
        "fecha_compra": variables.get("fecha_compra", ""),
        "qr_base64": template_engine.generar_qr_base64(codigo_oficial),
        "barcode_base64": template_engine.generar_barcode_base64(codigo_oficial),
        # --- layout placeholders (see docstring above) ---
        "codigo": codigo_oficial,
        "documento": variables.get("afiliado_documento", ""),
        "nombre_afiliado": variables.get("afiliado_nombre", ""),
        "contenido": unidad.contenido or "",
        "grupo": unidad.grupo or "",
        "cantidad": cantidad if cantidad is not None else len(hermanas),
        "fecha": datetime.now(timezone.utc).date().isoformat(),
        "unidades": hermanas,
        "codigos": codigos,
        "qrs": [template_engine.generar_qr_base64(c) for c in codigos],
        "barcodes": [template_engine.generar_barcode_base64(c) for c in codigos],
        "productos_incluidos": [{"nombre": convenio.nombre, "cantidad": cantidad if cantidad is not None else len(hermanas)}],
    }


def _logo_base64_o_none(storage_path: str | None) -> str | None:
    if not storage_path:
        return None
    logo_bytes = storage_service.download_bytes(storage_path)
    if logo_bytes is None:
        return None
    return base64.b64encode(logo_bytes).decode("ascii")


def _imagenes_base64_desde_config(config: dict) -> dict[str, str]:
    """Resolves every `layout` format image reference (background,
    logos, decorative graphics — see routers/plantillas.py's `/layout`
    endpoints) through `storage_service`, keyed exactly as the layout's
    `image_key`s expect. A key whose storage object is missing/unreadable
    is silently omitted — `template_engine._render_layout_elemento`
    already treats a missing key as "don't draw this element", never an
    error that would block the whole ticket."""
    resultado: dict[str, str] = {}
    for key, storage_path in (config.get("imagenes") or {}).items():
        if not storage_path:
            continue
        contenido = storage_service.download_bytes(storage_path)
        if contenido is not None:
            resultado[key] = base64.b64encode(contenido).decode("ascii")
    return resultado


def generar_ticket(convenio: Convenio, unidad: UnidadInventario, variables: dict) -> bytes:
    """`variables` keys used here: `afiliado_nombre`, `afiliado_documento`,
    `transaccion_id`, `fecha_compra` (already-formatted string), `cantidad`
    (the transacción's total units — optional, defaults to
    `len(unidades_hermanas)`), and `unidades_hermanas` (optional: every
    unit belonging to the same transacción, for a layout that draws one
    QR/row per unit — see routers/tickets.py). Kept as a plain dict (not
    the ORM objects) so a future brand-specific generator only needs this
    shape, never a live DB session.

    RESOLUTION ORDER (highest priority first):
      1. `convenio.plantilla_catalogo_clave` — one of the 4 fixed,
         code-owned catalog designs (app.services.plantillas_catalogo),
         selected via `PATCH /api/convenios/{id}` (the "Seleccionar
         plantilla" screen). Rendered straight from code, no database
         row involved.
      2. Otherwise, any real per-convenio plantilla active for this
         convenio (`plantilla_activa()` below, via the real
         `plantillas.convenio_id` relationship) — the CURRENT format is a
         real visual-editor layout (`config.get("type") == "layout"`),
         or, for backward compatibility, an earlier round's diseño-base
         format (`"template_key"` key), admin-uploaded-HTML format
         (`"html"` key), flow-layout visual-builder format (`"elements"`
         key), or the oldest format (a bare HTML file, no JSON wrapper).
      3. The generic placeholder below — if there's no selection AND no
         active legacy plantilla, or if rendering fails for any reason
         at any step above."""
    clave = convenio.plantilla_catalogo_clave
    if clave and plantillas_catalogo.existe(clave):
        try:
            contexto = _contexto_ticket(convenio, unidad, variables)
            return plantillas_catalogo.generar_pdf(clave, contexto)
        except Exception:
            logger.exception(
                "No se pudo renderizar la plantilla del catálogo (convenio_id=%s, clave=%s); "
                "intentando el mecanismo anterior / el ticket genérico.",
                convenio.id, clave,
            )

    plantilla = plantilla_activa(convenio)
    if plantilla is not None:
        try:
            contenido = storage_service.download_bytes(plantilla.storage_path)
            if contenido is None:
                raise FileNotFoundError(plantilla.storage_path)
            contexto = _contexto_ticket(convenio, unidad, variables)

            try:
                config = json.loads(contenido.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                config = None

            if config is not None and config.get("type") == "layout":
                # Current format: a real visual-editor layout (background
                # + freely positioned elements — see
                # PlantillaBuilder.jsx and template_engine.py's layout
                # engine). `imagenes` maps each element's `image_key` to
                # its storage_service reference.
                imagenes_base64 = _imagenes_base64_desde_config(config)
                return template_engine.generar_pdf_desde_layout(config["layout"], contexto, imagenes_base64)

            if config is not None and "template_key" in config:
                # Current format: one of the fixed diseños base (see
                # plantillas_base.py) + the admin's content-form fields +
                # logo(s) — never an admin-uploaded HTML file.
                logo_base64 = _logo_base64_o_none(config.get("logo_storage_path"))
                logo_coop_base64 = _logo_base64_o_none(config.get("logo_cooperativa_storage_path"))
                contexto.update(template_engine.campos_contenido(config, logo_base64, logo_coop_base64))
                html_diseno = plantillas_base.obtener_html_diseno(config["template_key"])
                return template_engine.generar_pdf_desde_plantilla(html_diseno, contexto)

            if config is not None and "html" in config:
                # Current format: real HTML/Jinja2 file + the admin's
                # content-form fields (título, términos, instrucciones,
                # etc.) + logo(s) — see routers/plantillas.py `crear()`.
                logo_base64 = _logo_base64_o_none(config.get("logo_storage_path"))
                logo_coop_base64 = _logo_base64_o_none(config.get("logo_cooperativa_storage_path"))
                contexto.update(template_engine.campos_contenido(config, logo_base64, logo_coop_base64))
                return template_engine.generar_pdf_desde_plantilla(config["html"], contexto)

            if config is not None and "elements" in config:
                # Previous round's visual-builder format — kept for
                # backward compatibility with any plantilla created
                # while that format was current.
                logo_base64 = _logo_base64_o_none(config.get("logo_storage_path"))
                return template_engine.generar_pdf_desde_elementos(config["elements"], contexto, logo_base64)

            # Oldest legacy format: a raw HTML/Jinja2 file with no JSON wrapper at all.
            html_source = contenido.decode("utf-8")
            return template_engine.generar_pdf_desde_plantilla(html_source, contexto)
        except Exception:
            logger.exception(
                "No se pudo renderizar la plantilla real (convenio_id=%s, plantilla_id=%s); "
                "usando el ticket genérico como respaldo.", convenio.id, plantilla.id,
            )

    return _generar_ticket_generico(convenio, unidad, variables)


def _generar_ticket_generico(convenio: Convenio, unidad: UnidadInventario, variables: dict) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    _, height = letter

    c.setFillColorRGB(0.98, 0.75, 0.1)
    c.rect(0, height - 1.1 * cm, letter[0], 1.1 * cm, fill=1, stroke=0)
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(letter[0] / 2, height - 0.75 * cm, "TICKET PROVISIONAL — PENDIENTE DE PLANTILLA OFICIAL DE MARCA")

    c.setFont("Helvetica-Bold", 18)
    c.drawString(2 * cm, height - 2.3 * cm, "BEET Ticket")
    c.setFont("Helvetica", 12)
    c.drawString(2 * cm, height - 3 * cm, f"Beneficio: {convenio.nombre}")

    y = height - 4.3 * cm
    y = _draw_kv_lines(
        c,
        2 * cm,
        y,
        [
            ("Afiliado", variables.get("afiliado_nombre", "")),
            ("Documento", variables.get("afiliado_documento", "")),
            ("Convenio", convenio.nombre),
            ("Código", unidad.codigo),
            ("Estado de la unidad", unidad.estado.value),
            ("Transacción", str(variables.get("transaccion_id", ""))),
            ("Fecha de compra", variables.get("fecha_compra", "")),
            ("Generado", datetime.now(timezone.utc).isoformat()),
        ],
    )

    y -= 0.4 * cm
    c.setFont("Helvetica-Oblique", 9)
    for line in _wrap_text(
        "Este es un ticket provisional generado automáticamente mientras se recibe la plantilla "
        "de diseño oficial de la marca. El código anterior es real y válido para redención.",
        95,
    ):
        c.drawString(2 * cm, y, line)
        y -= 0.5 * cm

    c.setFont("Helvetica-Oblique", 8)
    c.drawString(2 * cm, 1.5 * cm, "Documento generado automáticamente por BEET Ticket. Uso personal e intransferible.")

    c.showPage()
    c.save()
    return buffer.getvalue()


_AZUL_BEET = colors.HexColor("#1C26E5")
_GRIS_TEXTO = colors.HexColor("#374151")
_GRIS_ETIQUETA = colors.HexColor("#6B7280")
_GRIS_CLARO = colors.HexColor("#F3F4F8")
_GRIS_BORDE = colors.HexColor("#D1D5DB")


def generar_documento_asuncion_deuda(*, variables: dict, firma_png: bytes | None) -> bytes:
    """`variables` keys used here: `afiliado_nombre`, `afiliado_documento`,
    `transaccion_id`, `total` (already-formatted string), `numero_cuotas`,
    `fecha`.

    Styled to match the BEET brand (same blue as the frontend's
    `--brand-primary`) instead of a bare wall of Helvetica text — a
    header band, a "Datos del compromiso" summary card, a clearly
    separated terms section, and a bordered signature box. This is a
    legal document an affiliate may need to produce in a dispute, so it
    needs to read as an official, well-organized record, not a debug
    printout."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # --- Header band ---
    c.setFillColor(_AZUL_BEET)
    c.rect(0, height - 2.6 * cm, width, 2.6 * cm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(2 * cm, height - 1.1 * cm, "BEET Ticket")
    c.setFont("Helvetica", 10.5)
    c.drawString(2 * cm, height - 1.85 * cm, "Documento de asunción de deuda")
    c.setFont("Helvetica-Bold", 9)
    c.drawRightString(width - 2 * cm, height - 1.1 * cm, f"N.° {variables.get('transaccion_id', '')}")
    c.setFont("Helvetica", 8)
    c.drawRightString(width - 2 * cm, height - 1.85 * cm, str(variables.get("fecha", "")))

    # --- "Datos del compromiso" summary card ---
    card_top = height - 3.4 * cm
    card_h = 4.0 * cm
    c.setFillColor(_GRIS_CLARO)
    c.roundRect(2 * cm, card_top - card_h, width - 4 * cm, card_h, 6, fill=1, stroke=0)
    c.setFillColor(_AZUL_BEET)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(2.5 * cm, card_top - 0.75 * cm, "Datos del compromiso")

    filas = [
        ("Afiliado", variables.get("afiliado_nombre", ""), "Valor total", variables.get("total", "")),
        ("Documento", variables.get("afiliado_documento", ""), "Cuotas", str(variables.get("numero_cuotas", ""))),
        ("Transacción", str(variables.get("transaccion_id", "")), "Fecha", str(variables.get("fecha", ""))),
    ]
    col1_x, col1_val_x = 2.5 * cm, 5.1 * cm
    col2_x, col2_val_x = 2.5 * cm + (width - 4 * cm) / 2, 2.5 * cm + (width - 4 * cm) / 2 + 2.6 * cm
    for i, (l1, v1, l2, v2) in enumerate(filas):
        fila_y = card_top - 1.65 * cm - i * 0.85 * cm
        c.setFillColor(_GRIS_ETIQUETA)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(col1_x, fila_y, l1.upper())
        c.drawString(col2_x, fila_y, l2.upper())
        c.setFillColor(colors.black)
        c.setFont("Helvetica", 9.5)
        c.drawString(col1_val_x, fila_y, str(v1))
        c.drawString(col2_val_x, fila_y, str(v2))

    # --- Terms section ---
    term_title_y = card_top - card_h - 1 * cm
    c.setFillColor(_AZUL_BEET)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(2 * cm, term_title_y, "Términos y condiciones")
    c.setStrokeColor(_AZUL_BEET)
    c.setLineWidth(1.2)
    c.line(2 * cm, term_title_y - 0.18 * cm, 2 * cm + 4.3 * cm, term_title_y - 0.18 * cm)

    lineas = _wrap_text(TEXTO_ASUNCION_DEUDA_GENERICO, 100)
    line_h = 0.48 * cm
    box_top = term_title_y - 0.5 * cm
    box_h = len(lineas) * line_h + 0.8 * cm
    c.setFillColor(_GRIS_CLARO)
    c.roundRect(2 * cm, box_top - box_h, width - 4 * cm, box_h, 6, fill=1, stroke=0)
    c.setFillColor(_GRIS_TEXTO)
    c.setFont("Helvetica", 9)
    text_y = box_top - 0.55 * cm
    for linea in lineas:
        c.drawString(2.5 * cm, text_y, linea)
        text_y -= line_h

    # --- Signature ---
    sig_title_y = box_top - box_h - 1 * cm
    c.setFillColor(_AZUL_BEET)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(2 * cm, sig_title_y, "Firma del afiliado")

    sig_box_h = 3.2 * cm
    sig_box_top = sig_title_y - 0.4 * cm
    c.setFillColor(colors.white)
    c.setStrokeColor(_GRIS_BORDE)
    c.setLineWidth(0.8)
    c.roundRect(2 * cm, sig_box_top - sig_box_h, 8 * cm, sig_box_h, 6, fill=1, stroke=1)
    if firma_png:
        try:
            img = ImageReader(io.BytesIO(firma_png))
            c.drawImage(
                img, 2.3 * cm, sig_box_top - sig_box_h + 0.3 * cm,
                width=7.4 * cm, height=sig_box_h - 0.6 * cm, preserveAspectRatio=True, mask="auto",
            )
        except Exception:
            c.setFillColor(_GRIS_ETIQUETA)
            c.setFont("Helvetica-Oblique", 9)
            c.drawCentredString(6 * cm, sig_box_top - sig_box_h / 2, "(firma no disponible para previsualización)")
    else:
        c.setFillColor(_GRIS_ETIQUETA)
        c.setFont("Helvetica-Oblique", 9)
        c.drawCentredString(6 * cm, sig_box_top - sig_box_h / 2, "(sin firma registrada)")

    c.setFillColor(_GRIS_ETIQUETA)
    c.setFont("Helvetica", 8)
    c.drawString(2 * cm, sig_box_top - sig_box_h - 0.5 * cm, f"Firmado electrónicamente el {variables.get('fecha', '')}")

    # --- Footer ---
    c.setStrokeColor(colors.HexColor("#E5E7EB"))
    c.setLineWidth(0.6)
    c.line(2 * cm, 1.7 * cm, width - 2 * cm, 1.7 * cm)
    c.setFillColor(colors.HexColor("#9CA3AF"))
    c.setFont("Helvetica-Oblique", 7.5)
    c.drawString(
        2 * cm, 1.3 * cm,
        "Documento generado automáticamente por BEET Ticket. Constituye prueba de aceptación electrónica de la asunción de deuda.",
    )

    c.showPage()
    c.save()
    return buffer.getvalue()


def upload_ticket_pdf(*, cooperativa_id: int, transaccion_id: int, unidad_id: int, pdf_bytes: bytes) -> str:
    object_key = storage_service.generate_object_key("tickets", cooperativa_id, "unidad", unidad_id, ".pdf")
    return storage_service.upload_bytes(object_key, pdf_bytes, "application/pdf")


def upload_debt_document_pdf(*, cooperativa_id: int, transaccion_id: int, pdf_bytes: bytes) -> str:
    object_key = storage_service.generate_object_key(
        "documentos-asuncion-deuda", cooperativa_id, "transaccion", transaccion_id, ".pdf"
    )
    return storage_service.upload_bytes(object_key, pdf_bytes, "application/pdf")


def upload_signature_png(*, cooperativa_id: int, transaccion_id: int, png_bytes: bytes) -> str:
    object_key = storage_service.generate_object_key("firmas", cooperativa_id, "transaccion", transaccion_id, ".png")
    return storage_service.upload_bytes(object_key, png_bytes, "image/png")
