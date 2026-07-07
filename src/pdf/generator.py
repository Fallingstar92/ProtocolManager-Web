import sys
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from services.czech_names import to_instrumental_full_name


def app_resource_path(relative_path: str) -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative_path

    return Path(__file__).resolve().parents[2] / relative_path


def app_writable_path(relative_path: str) -> Path:
    if getattr(sys, "frozen", False):
        return Path.home() / ".local" / "share" / "ProtocolManager" / relative_path

    return Path(__file__).resolve().parents[2] / relative_path


EXPORTS_DIR = app_writable_path("exports")
LOGO_PATH = app_resource_path("assets/logo.png")

FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def register_fonts() -> None:
    pdfmetrics.registerFont(TTFont("AppFont", FONT_REGULAR))
    pdfmetrics.registerFont(TTFont("AppFont-Bold", FONT_BOLD))

    registerFontFamily(
        "AppFont",
        normal="AppFont",
        bold="AppFont-Bold",
    )


def draw_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("AppFont", 7)
    canvas.setFillColor(colors.HexColor("#666666"))

    jira = getattr(doc, "jira", "")
    if jira:
        canvas.drawString(doc.leftMargin, 10 * mm, f"Jira: {jira}")

    canvas.restoreState()


def generate_protocol_pdf(data: dict, output_path: Path | None = None) -> Path:
    register_fonts()

    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

    if output_path is None:
        output_path = EXPORTS_DIR / "preview.pdf"

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=25 * mm,
        leftMargin=25 * mm,
        topMargin=16 * mm,
        bottomMargin=12 * mm,
    )

    styles = _build_styles()
    story = []

    logo = Image(str(LOGO_PATH), width=43 * mm, height=13 * mm)

    header = Table(
        [[
            Paragraph(
                f"PŘEDÁVACÍ PROTOKOL č. {data['protocol_number']}",
                styles["title"],
            ),
            logo,
        ]],
        colWidths=[118 * mm, 43 * mm],
    )

    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))

    story.append(header)
    story.append(Spacer(1, 12 * mm))

    represented_by = to_instrumental_full_name(data["sender_name"])

    intro = (
        "<b>APOLLO SOFT s.r.o.</b>, IČ: 28179781<br/>"
        "sídlem: V parku 2294/2, Chodov, 148 00 Praha 4<br/>"
        "Zapsaná v obchodním rejstříku Městského soudu v Praze, oddíl C, vložka 266997<br/>"
        f"Zastoupena {represented_by} support@apollogames.com<br/>"
        '(dále jen “<b>dodavatel</b>”)'
    )
    story.append(Paragraph(intro, styles["normal"]))

    story.append(Spacer(1, 7 * mm))
    story.append(Paragraph("<b>a</b>", styles["normal"]))
    story.append(Spacer(1, 6 * mm))

    customer_address = "<br/>".join(data["customer_address"])
    customer = (
        f"<b>{data['customer_name']}</b><br/>"
        f"{customer_address}<br/>"
        '(dále jen “<b>odběratel</b>”)'
    )
    story.append(Paragraph(customer, styles["normal"]))

    story.append(Spacer(1, 7 * mm))
    story.append(Paragraph(
        "Odběratel tímto potvrzuje převzetí níže uvedených předmětů od dodavatele:",
        styles["normal"],
    ))

    story.append(Spacer(1, 5 * mm))

    for item in data["items"]:
        count = item.get("count") or "1"
        item_type = item.get("type") or "položka"
        value = item.get("value") or ""

        story.append(Paragraph(
            f"• &nbsp;&nbsp;{count}x {item_type}",
            styles["item_bold"],
        ))

        if value:
            story.append(Spacer(1, 4 * mm))
            story.append(Paragraph(value, styles["item_value"]))

        story.append(Spacer(1, 4 * mm))

    story.append(Spacer(1, 6 * mm))

    return_text = (
        "Původní díl (y) se přebírající zavazuje vrátit předávajícímu na výše uvedenou adresu, "
        "a to do 30-ti kalendářních dnů, od data převzetí tohoto předávacího protokolu. "
        "V případě, že původní díl (y) nebude v uvedené lhůtě navrácen, bude předávající jejich "
        "hodnotu fakturovat přebírajícímu."
    )
    story.append(Paragraph(return_text, styles["normal"]))

    story.append(Spacer(1, 9 * mm))

    signature_table = Table(
        [
            [
                Paragraph("<b>Předal:</b>", styles["table_center"]),
                Paragraph("<b>Dne</b>", styles["table_center"]),
                Paragraph("<b>Podpis</b>", styles["table_center"]),
            ],
            [
                Paragraph(data["sender_name"], styles["table_center"]),
                Paragraph(data["date"], styles["table_center"]),
                "",
            ],
            [
                Paragraph("<b>Převzal:</b>", styles["table_center"]),
                Paragraph("<b>Dne</b>", styles["table_center"]),
                Paragraph("<b>Podpis</b>", styles["table_center"]),
            ],
            [
                Paragraph(data["receiver"], styles["table_center"]),
                Paragraph(data["date"], styles["table_center"]),
                "",
            ],
        ],
        colWidths=[55 * mm, 53 * mm, 44 * mm],
        rowHeights=[6 * mm, 12 * mm, 6 * mm, 14 * mm],
    )

    signature_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, -1), "AppFont"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
    ]))

    story.append(signature_table)
    story.append(Spacer(1, 4 * mm))

    footer = (
        "APOLLO SOFT s.r.o. | V parku 2294/2, Chodov | 148 00 Praha 4 | www.apollogames.com<br/>"
        "IČ: 28179781 | DIČ: CZ28179781 | spol. je zapsána v OR u Městského soudu Praha, C 266997"
    )
    story.append(Paragraph(footer, styles["footer"]))

    doc.jira = data.get("jira", "")

    doc.build(
        story,
        onFirstPage=draw_footer,
        onLaterPages=draw_footer,
    )

    return output_path


def _build_styles() -> dict:
    return {
        "title": ParagraphStyle(
            "title",
            fontName="AppFont-Bold",
            fontSize=12.5,
            leading=15,
            alignment=TA_LEFT,
        ),
        "normal": ParagraphStyle(
            "normal",
            fontName="AppFont",
            fontSize=8.4,
            leading=11,
            alignment=TA_LEFT,
        ),
        "item_bold": ParagraphStyle(
            "item_bold",
            fontName="AppFont-Bold",
            fontSize=8.4,
            leading=11,
            leftIndent=7 * mm,
        ),
        "item_value": ParagraphStyle(
            "item_value",
            fontName="AppFont-Bold",
            fontSize=8.4,
            leading=11,
            leftIndent=20 * mm,
        ),
        "table_center": ParagraphStyle(
            "table_center",
            fontName="AppFont",
            fontSize=8.4,
            leading=10,
            alignment=TA_CENTER,
        ),
        "footer": ParagraphStyle(
            "footer",
            fontName="AppFont",
            fontSize=7,
            leading=9,
            alignment=TA_CENTER,
        ),
    }