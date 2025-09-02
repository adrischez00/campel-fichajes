# backend/app/exportadores/export_pdf.py

import os
import re
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.units import cm, mm
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from fastapi.responses import StreamingResponse
from reportlab.pdfgen import canvas as _canvas
from app.exportadores.base import ExportadorBase
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle, Spacer
from collections import defaultdict
from datetime import datetime
from reportlab.platypus import HRFlowable
from zoneinfo import ZoneInfo
# ======================
# Canvas numerado (x de y)
# ======================
# ======================
# Canvas numerado (x de y)
# ======================
from reportlab.pdfgen import canvas as _canvas
from reportlab.lib.pagesizes import A4

class NumberedCanvas(_canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        # Guardamos el estado y PASAMOS a nueva página sin emitirla todavía
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()  # <-- clave: NO usar super().showPage()

    def save(self):
        total_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_page_number(total_pages)
            super().showPage()  # aquí sí se emite cada página una vez
        super().save()

    def _draw_page_number(self, total_pages: int):
        if self._pageNumber == 1:
            return  # No numerar portada
        w, h = A4
        self.setFont("Helvetica", 8)
        self.setFillColor(HexColor('#7F8C8D'))
        self.drawRightString(w - 2*cm, 1.5*cm, f"Página {self._pageNumber} de {total_pages}")


class ExportadorPDF(ExportadorBase):
    """
    Recibe los logs ya agrupados por día desde el frontend, p. ej.:

    [
      {
        "usuario": "user@dominio",
        "fecha": "21/07/2025",
        "intervalos": [
           {"entrada":"08:30","salida":"16:30","duracion":"8h 0m",
            "manualEntrada":true/false,"manualSalida":true/false,
            "motivoEntrada":"", "motivoSalida":""}
        ],
        "total": "8h 0m"
      },
      ...
    ]
    """

    def __init__(self, logs):
        self.logs = logs
        self.company_name = os.getenv("COMPANY_NAME", "Campel")

    def nombre_archivo(self):
        return "Informe_Fichajes.pdf"

    def tipo_mime(self):
        return "application/pdf"

    # ---------------------- Helpers ----------------------
    def _buscar_logo(self) -> str | None:
        from pathlib import Path
        base = Path(__file__).resolve()
        candidatos = [
            base.parents[1] / "static" / "logo.png",  # app/static/logo.png
            base.parents[2] / "static" / "logo.png",  # backend/static/logo.png
            Path.cwd() / "static" / "logo.png",
        ]
        if os.environ.get("LOGO_PATH"):
            candidatos.append(Path(os.environ["LOGO_PATH"]))
        for c in candidatos:
            if Path(c).is_file():
                return str(c)
        return None

    @staticmethod
    def _parse_fecha_ddmmyyyy(fecha_str: str):
        # "21/07/2025" -> datetime
        try:
            d, m, y = fecha_str.split("/")
            return datetime(int(y), int(m), int(d))
        except Exception:
            return fecha_str  # no romper si entra algo raro

    @staticmethod
    def _parse_duracion_a_minutos(txt: str) -> int:
        # "5h 38m" -> 338
        if not txt:
            return 0
        m = re.search(r"(\d+)h\s+(\d+)m", txt)
        if not m:
            return 0
        return int(m.group(1)) * 60 + int(m.group(2))

    @staticmethod
    def _formatea_minutos(mins: int) -> str:
        h, m = divmod(mins, 60)
        return f"{h}h {m}m"



    @staticmethod
    def _fmt_fecha(dt: datetime) -> str:
        return dt.strftime("%d/%m/%Y")
    
    @staticmethod
    def _key_fecha(g):
        f = (g.get("fecha") or "").strip()
        if not f:
            return (9999, 12, 31, "")
        try:
            f = f.replace("-", "/")
            d, m, y = f.split("/")
            return (int(y), int(m), int(d))
        except Exception:
            return (9999, 12, 31, f)

    @staticmethod  
    def _wrap_text(c: canvas.Canvas, text: str, font: str, size: int, max_w: float):
        """Partir texto por palabras para que quepa en max_w."""
        words = text.split()
        lines, cur = [], ""
        for w in words:
            test = (cur + " " + w).strip()
            if c.stringWidth(test, font, size) <= max_w:
                cur = test
            else:
                if cur: lines.append(cur)
                cur = w
        if cur: lines.append(cur)
        return lines


    # ---------------------- Exportar ----------------------
    def exportar(self):
        buffer = BytesIO()

        # Altura del encabezado interior y márgenes
        header_h = 2.6 * cm
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=2 * cm,
            rightMargin=2 * cm,
            topMargin=header_h + 1.0 * cm,  # deja aire bajo la franja
            bottomMargin=2 * cm,
        )

        # ===== Estilos =====
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(
            name='TituloPrincipal',
            fontSize=20, leading=24, alignment=TA_CENTER,
            spaceAfter=10, textColor=HexColor('#2E4053')
        ))
        styles.add(ParagraphStyle(
            name='UsuarioTitulo',
            fontSize=14, leading=18, spaceAfter=6, textColor=HexColor('#154360')
        ))
        styles.add(ParagraphStyle(
            name='DiaTitulo',
            fontSize=11, leading=16, spaceAfter=4, textColor=HexColor('#2471A3')
        ))
        styles.add(ParagraphStyle(
            name='Motivo',
            fontSize=9, leading=12, spaceAfter=4, leftIndent=10, textColor=HexColor('#7D3C98')
        ))
        styles.add(ParagraphStyle(
            name='Footer',
            fontSize=8, alignment=TA_RIGHT, textColor=HexColor('#666666')
        ))

        # ===== Estilos y helpers =====

        def ensure_style(name, **kwargs):
            if name not in styles.byName:
                styles.add(ParagraphStyle(name=name, **kwargs))

        # Títulos ya usados
        ensure_style('UsuarioTitulo', parent=styles['Heading2'], fontSize=14, leading=16,
                    textColor=HexColor('#0F3D57'), spaceBefore=12, spaceAfter=8)
        ensure_style('DiaTitulo', parent=styles['Heading3'], fontSize=12, leading=14,
                    textColor=HexColor('#0F3D57'), spaceBefore=6, spaceAfter=4)

        # Subtítulo de fecha en motivos
        ensure_style('FechaSub', parent=styles['Normal'], fontSize=10, leading=12,
                    textColor=HexColor('#555555'), leftIndent=0, spaceBefore=2, spaceAfter=2)

        # Texto de cada motivo
        ensure_style('Motivo', parent=styles['Normal'], fontSize=10, leading=14)

        # Leyenda del bloque
        ensure_style('MotivosLeyenda', parent=styles['Normal'], fontSize=9,
                    textColor=HexColor('#555555'), spaceAfter=6)

        # Chip para [ENTRADA]/[SALIDA]
        ensure_style('Chip', parent=styles['Normal'], fontSize=8, leading=10, textColor=HexColor('#0F3D57'))

        # Estilos extra para el bloque de motivos
        ensure_style('HoraStrong', parent=styles['Normal'], fontSize=10, leading=14)
        ensure_style('MotivoCell', parent=styles['Normal'], fontSize=10, leading=14, spaceBefore=1, spaceAfter=1)
        ensure_style('Chip', parent=styles['Normal'], fontSize=8, leading=10, textColor=HexColor('#0F3D57'))  # ya lo tienes
        ensure_style('UsuarioMeta', parent=styles['Normal'], fontSize=9, leading=12,
             textColor=HexColor('#64748B'))
        
        # Encabezado de usuario (suave y profesional)
        ensure_style('UsuarioTituloSoft', parent=styles['Heading3'], fontSize=12, leading=16,
                    textColor=HexColor('#234055'))   # tono más calmado
        ensure_style('UsuarioMeta', parent=styles['Normal'], fontSize=9, leading=12,
                    textColor=HexColor('#6B7C8C'))

        def chip_paragraph(texto):
            # El fondo y borde se aplican en la TableStyle; aquí solo el texto en negrita
            return Paragraph(f"<b>{texto}</b>", styles['Chip'])


        # ===== Preparar datos (por usuario) =====
        por_usuario = defaultdict(list)
        fechas_parseadas = []

        for g in self.logs:
            usuario = g.get("usuario", "")
            por_usuario[usuario].append(g)
            f = g.get("fecha")
            try:
                d, m, y = f.split("/")
                fechas_parseadas.append(datetime(int(y), int(m), int(d)))
            except Exception:
                pass

        # Rango para portada
        if fechas_parseadas:
            inicio = min(fechas_parseadas)
            fin = max(fechas_parseadas)
            rango_txt = f"{self._fmt_fecha(inicio)} – {self._fmt_fecha(fin)}"
        else:
            rango_txt = "—"

        # ===== Paleta/tema tablas =====
        header_bg = colors.Color(0.90, 0.95, 1.00)
        alt_row   = colors.whitesmoke
        border    = colors.Color(0.75, 0.80, 0.88)

        # Anchos de columnas para la tabla del día
        day_colw = [3*cm, 3*cm, 3*cm, 3*cm, 3*cm]   # Entrada/Salida/Duración/Entrada manual/Salida manual
        day_table_width = sum(day_colw)            # 15 cm

        logo_path = self._buscar_logo()
        tz = os.getenv("LOCAL_TZ", "Europe/Madrid")
        generado_txt = datetime.now(ZoneInfo(tz)).strftime("%d/%m/%Y %H:%M")
        subtitulo_legal = "Cumple con la normativa laboral vigente (Real Decreto-ley 8/2019 y actualizaciones 2025/2026)"


        def _draw_badge(c: canvas.Canvas, x_right: float, y_top: float, text: str):
            padding_x, padding_y = 0.5*cm, 0.45*cm
            c.saveState()
            c.setFont("Helvetica-Bold", 8)
            lines = text.split("\n")
            max_w = max(c.stringWidth(line, "Helvetica-Bold", 8) for line in lines)
            box_w = max_w + padding_x*2
            box_h = (len(lines)*0.45*cm) + padding_y*2
            c.setFillColor(HexColor('#E8F5E9'))
            c.setStrokeColor(HexColor('#A5D6A7'))
            c.roundRect(x_right - box_w, y_top - box_h, box_w, box_h, 6, stroke=1, fill=1)
            c.setFillColor(HexColor('#1B5E20'))
            y = y_top - padding_y - 0.2*cm
            for line in lines:
                c.drawRightString(x_right - padding_x, y, line)
                y -= 0.45*cm
            c.restoreState()


        # ===== Portada =====
        def dibujar_portada(c: canvas.Canvas, _doc):
            width, height = A4
            c.saveState()

            # Fondo
            c.setFillColor(HexColor('#F7FAFC'))
            c.rect(0, 0, width, height, stroke=0, fill=1)

            # Franja lateral
            strip_w = 3.0*cm
            c.setFillColor(HexColor('#EAF2F8')); c.rect(0, 0, strip_w, height, stroke=0, fill=1)
            c.setFillColor(HexColor('#D6E6F2')); c.rect(strip_w - 0.25*cm, 0, 0.25*cm, height, stroke=0, fill=1)

            # Logo en la franja
            if logo_path:
                try:
                    c.drawImage(logo_path, 0.6*cm, height - 3.6*cm,
                                width=strip_w - 1.2*cm, height=2.8*cm,
                                preserveAspectRatio=True, mask='auto')
                except Exception:
                    pass

            # Marca de agua (logo grande, un poco más alta)
            if logo_path:
                try:
                    c.saveState()
                    c.setFillAlpha(0.06)
                    mw = width - strip_w - 2.5*cm
                    mh = 8.0*cm
                    c.drawImage(logo_path,
                                strip_w + (width - strip_w - mw)/2,
                                height/2 - mh/2 + 2.8*cm,  # ↑ subido ~2 cm
                                width=mw, height=mh,
                                preserveAspectRatio=True, mask='auto')
                    c.restoreState()
                except Exception:
                    pass

            # Bloque de texto
            margin_x = strip_w + 2.0*cm
            right_margin = 2.0*cm
            title_y = height - 5.2*cm
            content_w = width - margin_x - right_margin

            # Empresa
            c.setFillColor(HexColor('#2E4053')); c.setFont("Helvetica-Bold", 13)
            c.drawString(margin_x, title_y, f"{self.company_name}")

            # Título
            c.setFont("Helvetica-Bold", 28); c.setFillColor(HexColor('#1F2D3D'))
            c.drawString(margin_x, title_y - 1.2*cm, "Informe de fichajes")

            # Línea divisoria (ligeramente más marcada)
            c.setStrokeColor(HexColor('#C6D6E4')); c.setLineWidth(1.2)
            c.line(margin_x, title_y - 1.6*cm, margin_x + content_w, title_y - 1.6*cm)

            # Subtítulo legal (auto-wrap)
            legal = "Cumple con la normativa laboral vigente (Real Decreto-ley 8/2019 y actualizaciones 2025/2026)"
            c.setFont("Helvetica", 11); c.setFillColor(HexColor('#4A5B6B'))
            lines = self._wrap_text(c, legal, "Helvetica", 11, content_w)
            base_y = title_y - 2.6*cm
            leading = 14  # px aprox
            for i, line in enumerate(lines[:2]):  # máx. 2 líneas
                c.drawString(margin_x, base_y - i*leading, line)
            after_legal_y = base_y - (len(lines[:2]) * leading) - 0.6*cm

            # Rango y generado
            c.setFont("Helvetica", 10); c.setFillColor(HexColor('#5E6B76'))
            c.drawString(margin_x, after_legal_y, f"Rango de fechas: {rango_txt}")
            c.drawString(margin_x, after_legal_y - 1.0*cm, f"Generado el: {generado_txt}")

            # Badge (alineado al borde superior derecho)
            try:
                _draw_badge(c, width - right_margin, height - 2.0*cm, "Cumple normativa\n2025/2026")
            except Exception:
                pass

            # Pie
            c.setFont("Helvetica", 9); c.setFillColor(HexColor('#93A1AD'))
            c.drawRightString(width - right_margin, 2.0*cm, "Documento oficial · Registro de jornada · Uso interno")

            c.restoreState()



        # ===== Encabezado/pie para páginas interiores =====
        def encabezado_pie(c: canvas.Canvas, _doc):
            width, height = A4

            # Franja del encabezado
            c.setFillColor(HexColor('#EAF2F8'))
            c.rect(0, height - header_h, width, header_h, stroke=0, fill=1)

            # Logo dentro de la franja, centrado verticalmente
            if logo_path:
                try:
                    logo_size = 1.8 * cm
                    c.drawImage(
                        logo_path,
                        2 * cm, height - header_h + (header_h - logo_size)/2,
                        width=logo_size, height=logo_size,
                        preserveAspectRatio=True, mask='auto'
                    )
                except Exception:
                    pass

            # Título
            c.setFillColor(HexColor('#2E4053'))
            c.setFont("Helvetica-Bold", 14)
            # baseline ~ 1.0cm por debajo del borde superior de la franja
            c.drawString(2*cm + 1.8*cm + 0.6*cm, height - 1.1*cm, "Informe de fichajes")

            # Sello "Generado"
            c.setFont("Helvetica", 8)
            c.setFillColor(HexColor('#5D6D7E'))
            c.drawRightString(width - 2*cm, height - 1.1*cm, f"Generado: {generado_txt}")

            # Pie legal + (nº página lo pone NumberedCanvas)
            pie_extra = []
            if os.getenv("COMPANY_WEB"): pie_extra.append(os.getenv("COMPANY_WEB"))
            if os.getenv("COMPANY_EMAIL"): pie_extra.append(os.getenv("COMPANY_EMAIL"))
            pie_extra_txt = " · ".join(pie_extra)

            c.setFont("Helvetica", 8)
            c.setFillColor(HexColor('#7F8C8D'))
            base_pie = "Documento generado automáticamente – Cumple normativa laboral 2025/2026"
            if pie_extra_txt:
                base_pie = base_pie + " · " + pie_extra_txt
            c.drawString(2*cm, 1.5*cm, base_pie)

        # ===== Flowables =====
        contenido = []
        # 1) Portada
        contenido.append(Spacer(1, 1))
        contenido.append(PageBreak())

        # 2) Título de sección
        contenido.append(Paragraph("Informe de fichajes", styles['TituloPrincipal']))

        # 3) Cuerpo: por usuario -> por día
        motivos_globales = []

        for idx_u, (usuario, grupos) in enumerate(sorted(por_usuario.items(), key=lambda x: x[0].lower())):
            if idx_u > 0:
                contenido.append(Spacer(1, 8))

            contenido.append(Paragraph(f"<b>{usuario}</b>", styles['UsuarioTitulo']))
            contenido.append(Spacer(1, 2))


            grupos_orden = sorted(grupos, key=self._key_fecha)

            total_usuario_min = 0
            dias_con_fichajes = 0

            for g in grupos_orden:
                fecha = g.get("fecha", "")
                contenido.append(Paragraph(fecha, styles['DiaTitulo']))

                # Tabla día
                data = [["Entrada", "Salida", "Duración", "Entrada manual", "Salida manual"]]
                for it in g.get("intervalos", []):
                    entrada  = it.get("entrada", "")
                    salida   = it.get("salida", "")
                    duracion = it.get("duracion", "")
                    manual_e = bool(it.get("manualEntrada"))
                    manual_s = bool(it.get("manualSalida"))
                    motivo_e = (it.get("motivoEntrada") or "").strip()
                    motivo_s = (it.get("motivoSalida") or "").strip()

                    # Recoger motivos para el final
                    if manual_e and motivo_e:
                        motivos_globales.append((usuario, f"{fecha} {entrada} – Entrada manual: \"{motivo_e}\""))
                    if manual_s and motivo_s:
                        motivos_globales.append((usuario, f"{fecha} {salida} – Salida manual: \"{motivo_s}\""))

                    data.append([
                        entrada, salida, duracion,
                        ("✓" if manual_e else ""), ("✓" if manual_s else "")
                    ])

                if len(data) > 1:
                    tabla = Table(data, colWidths=day_colw, hAlign='LEFT')
                    tabla.setStyle(TableStyle([
                        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 0), (-1, -1), 9),
                        ('BACKGROUND', (0, 0), (-1, 0), header_bg),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#154360')),
                        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                        ('LINEABOVE', (0, 0), (-1, 0), 0.6, border),
                        ('LINEBELOW', (0, 0), (-1, 0), 0.6, border),
                        ('ALIGN', (0, 1), (2, -1), 'CENTER'),
                        ('ALIGN', (3, 1), (4, -1), 'CENTER'),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('TEXTCOLOR', (3, 1), (4, -1), colors.HexColor('#27AE60')),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, alt_row]),
                        ('BOX', (0, 0), (-1, -1), 0.4, border),
                        ('INNERGRID', (0, 0), (-1, -1), 0.2, border),
                        ('LEFTPADDING', (0, 0), (-1, -1), 5),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
                        ('TOPPADDING', (0, 0), (-1, -1), 3),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                    ]))
                    contenido.append(tabla)

                    # Total del día
                    total_dia = g.get("total") or ""
                    if total_dia:
                        dias_con_fichajes += 1
                        total_usuario_min += self._parse_duracion_a_minutos(total_dia)
                        total_tbl = Table([["", "", "Total trabajado:", total_dia, ""]], colWidths=day_colw, hAlign='LEFT')
                        total_tbl.setStyle(TableStyle([
                            ('SPAN', (0, 0), (1, 0)),
                            ('SPAN', (3, 0), (4, 0)),
                            ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
                            ('FONTNAME', (2, 0), (3, 0), 'Helvetica-Bold'),
                            ('BACKGROUND', (2, 0), (3, 0), colors.Color(0.96, 0.98, 0.96)),
                            ('TEXTCOLOR', (2, 0), (3, 0), colors.HexColor('#1B5E20')),
                            ('BOX', (2, 0), (3, 0), 0.5, colors.HexColor('#A5D6A7')),
                            ('LEFTPADDING', (0, 0), (-1, -1), 6),
                            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                            ('TOPPADDING', (0, 0), (-1, -1), 3),
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                        ]))
                        contenido.append(total_tbl)

                contenido.append(Spacer(1, 8))

            # ------- Resumen del usuario -------
            if dias_con_fichajes:
                total_txt = self._formatea_minutos(total_usuario_min)
                resCell = ParagraphStyle('resCell', fontSize=9, leading=11,
                                         textColor=colors.HexColor('#1F3A93'))

                # Usa el mismo ancho total que la tabla del día
                colw_res = [day_table_width - (3.0*cm + 3.6*cm), 3.0*cm, 3.6*cm]
                fila = [
                    Paragraph(f"Resumen del usuario: <b>{usuario}</b>", resCell),
                    Paragraph(f"Días con fichajes: <b>{dias_con_fichajes}</b>", resCell),
                    Paragraph(f"Total horas: <b>{total_txt}</b>", resCell),
                ]
                resumen = Table([fila], colWidths=colw_res, hAlign='LEFT')
                resumen.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), colors.Color(0.985, 0.99, 1.0)),
                    ('BOX', (0, 0), (-1, -1), 0.3, border),
                    ('LEFTPADDING', (0, 0), (-1, -1), 6),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('ALIGN', (1, 0), (2, 0), 'RIGHT'),
                ]))
                contenido.append(resumen)
                contenido.append(Spacer(1, 12))

        # Leyenda (una vez)
        contenido.append(Paragraph("Leyenda: ✓ = fichaje manual", styles['Motivo']))
        contenido.append(Spacer(1, 6))

        # ===== Motivos al final =====
        if motivos_globales:
            contenido.append(PageBreak())
            contenido.append(Paragraph("📝 Motivos de fichajes manuales", styles['UsuarioTitulo']))
            contenido.append(Paragraph(
                "Se listan únicamente los fichajes <b>manuales</b>. Formato: hora · tipo · motivo. Horas en zona local.",
                styles['MotivosLeyenda'])
            )

            # usuario -> fecha_norm -> [(hora, tipo, motivo)]
            motivos_por_usuario = defaultdict(lambda: defaultdict(list))

            FECHA_RE = re.compile(r'^\s*(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{1,2}:\d{2})\s*$')
            def parse_line(txt):
                partes = txt.split(" – ", 1)
                if len(partes) != 2:
                    return ("", "", "Manual", (txt or "(motivo no indicado)"))
                fecha_hora = partes[0].strip()
                resto = partes[1].strip()

                low = resto.lower()
                if "entrada" in low:
                    tipo = "Entrada"
                elif "salida" in low:
                    tipo = "Salida"
                else:
                    tipo = "Manual"

                m = resto.split(":", 1)
                motivo = (m[1].strip() if len(m) == 2 else "") or "(motivo no indicado)"
                motivo = motivo.strip().strip('"').strip('“').strip('”').strip()

                mm = FECHA_RE.match(fecha_hora)
                if mm:
                    d, mo, y, hhmm = mm.groups()
                    fecha_norm = f"{int(d):02d}/{int(mo):02d}/{y}"
                    hora = hhmm
                else:
                    try:
                        dt = datetime.strptime(fecha_hora, "%d/%m/%Y %H:%M")
                        fecha_norm = dt.strftime("%d/%m/%Y")
                        hora = dt.strftime("%H:%M")
                    except Exception:
                        fecha_norm, hora = (fecha_hora or ""), ""
                return (fecha_norm, hora, tipo, motivo)

            # Rellenar estructura
            for usuario, texto in motivos_globales:
                fecha, hora, tipo, motivo = parse_line(texto)
                motivos_por_usuario[usuario][fecha].append((hora, tipo, motivo))

            def _key_fecha(f):
                try:
                    return datetime.strptime(f, "%d/%m/%Y")
                except Exception:
                    return datetime.max

            # Render
            for i_u, usuario in enumerate(sorted(motivos_por_usuario.keys(), key=lambda x: x.lower())):
                # Separador muy sutil entre usuarios (no antes del primero)
                if i_u > 0:
                    contenido.append(HRFlowable(width="100%", thickness=0.4,
                                                color=HexColor('#E9F0F6'),
                                                spaceBefore=10, spaceAfter=8))

                # “Card” de usuario con fondo muy claro, borde suave y banda lateral fina
                total_regs = sum(len(v) for v in motivos_por_usuario[usuario].values())
                user_header = Table(
                    [[
                        "",  # banda lateral
                        Paragraph(f"<b>{usuario}</b>", styles['UsuarioTituloSoft']),
                        Paragraph(f"{total_regs} fichajes manuales", styles['UsuarioMeta'])
                    ]],
                    colWidths=[0.22*cm, None, 4.2*cm],
                    hAlign='LEFT'
                )
                user_header.setStyle(TableStyle([
                    # Fondo suave y borde fino
                    ('BACKGROUND', (1,0), (2,0), HexColor('#F8FBFE')),
                    ('BOX',        (1,0), (2,0), 0.5, HexColor('#E3ECF3')),
                    # Banda lateral (más clara que antes)
                    ('BACKGROUND', (0,0), (0,0), HexColor('#9CB6C8')),
                    # Paddings equilibrados
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                    ('LEFTPADDING',  (1,0), (1,0), 10),
                    ('RIGHTPADDING', (2,0), (2,0), 10),
                    ('TOPPADDING',   (1,0), (2,0), 6),
                    ('BOTTOMPADDING',(1,0), (2,0), 6),
                    ('ALIGN', (2,0), (2,0), 'RIGHT'),
                ]))
                contenido.append(user_header)
                contenido.append(Spacer(1, 8))   # ← más aire debajo del usuario

                # === Fechas del usuario ===
                for fecha in sorted(motivos_por_usuario[usuario].keys(), key=_key_fecha):
                    try:
                        fecha_fmt = self._fmt_fecha(datetime.strptime(fecha, "%d/%m/%Y"))
                    except Exception:
                        fecha_fmt = fecha or "—"

                    bloque_fecha = []
                    bloque_fecha.append(Paragraph(fecha_fmt, styles['FechaSub']))
                    bloque_fecha.append(Spacer(1, 2))

                    # Filas: Hora | Chip | Motivo
                    data = []
                    registros = sorted(motivos_por_usuario[usuario][fecha], key=lambda x: (x[0] or ""))
                    for hora, tipo, motivo in registros:
                        chip = chip_paragraph("ENTRADA" if tipo == "Entrada" else ("SALIDA" if tipo == "Salida" else "MANUAL"))
                        data.append([
                            Paragraph(f"<b>{hora or '—'}</b>", styles['HoraStrong']),
                            chip,
                            Paragraph(motivo, styles['MotivoCell']),
                        ])

                    tabla = Table(data, colWidths=[1.8*cm, 2.1*cm, None], hAlign='LEFT')
                    tabla.setStyle(TableStyle([
                        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                        ('LEFTPADDING', (0,0), (-1,-1), 3),
                        ('RIGHTPADDING',(0,0), (-1,-1), 5),
                        ('TOPPADDING',  (0,0), (-1,-1), 2),
                        ('BOTTOMPADDING',(0,0),(-1,-1), 2),

                        ('BACKGROUND', (1,0), (1,-1), HexColor('#EFF6FA')),   # chip más suave
                        ('BOX',        (1,0), (1,-1), 0.4, HexColor('#8BA8BC')),
                        ('ALIGN',      (1,0), (1,-1), 'CENTER'),

                        ('BACKGROUND', (2,0), (2,-1), HexColor('#F7FAFD')),   # motivo muy sutil
                        ('ALIGN',      (2,0), (2,-1), 'LEFT'),

                        ('ROWBACKGROUNDS', (0,0), (-1,-1), [colors.white, colors.Color(0.985, 0.99, 1.0)]),
                        ('LINEBELOW',     (0,0), (-1,-1), 0.25, HexColor('#EDF0F2')),
                    ]))

                    bloque_fecha.append(tabla)

                    # Añadimos el bloque de fecha con salto sutil después
                    if len(data) >= 15:
                        for elem in bloque_fecha:
                            contenido.append(elem)
                    else:
                        contenido.append(KeepTogether(bloque_fecha))

                    contenido.append(Spacer(1, 6))  # ← más aire entre fechas

                # aire final tras cada usuario (para que no “se pegue” el siguiente bloque)
                contenido.append(Spacer(1, 10))


         # ===== Construcción final del PDF =====
        doc.build(
            contenido,
            onFirstPage=dibujar_portada,
            onLaterPages=encabezado_pie,
            canvasmaker=NumberedCanvas
        )

        buffer.seek(0)
        return StreamingResponse(
            buffer,
            media_type=self.tipo_mime(),
            headers={"Content-Disposition": f"attachment; filename={self.nombre_archivo()}"}
        )