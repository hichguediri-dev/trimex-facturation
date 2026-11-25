"""Génération du PDF de facture (reproduit le modèle Trimex)."""
from __future__ import annotations
from datetime import date
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import BaseDocTemplate, Flowable, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle
from xml.sax.saxutils import escape

from .db import SECTIONS, money

W, H = A4
MARGIN = 15 * mm
CW = W - 2 * MARGIN
BASE = ParagraphStyle("base", fontName="Helvetica", fontSize=8.5, leading=11)
BOLD = ParagraphStyle("bold", parent=BASE, fontName="Helvetica-Bold")
RIGHT = ParagraphStyle("right", parent=BASE, alignment=2)
RIGHTB = ParagraphStyle("rightb", parent=RIGHT, fontName="Helvetica-Bold")
CENTER = ParagraphStyle("center", parent=BASE, alignment=1)
SECT = ParagraphStyle("sect", parent=CENTER, fontName="Times-Bold", fontSize=7.5)


def p(text, style=BASE):
    return Paragraph(escape(str(text or "")).replace("\n", "<br/>"), style)


def amt(v):
    return f"{money(v):,.2f} USD"


def num(v):
    v = float(v)
    return f"{int(v)}" if v == int(v) else f"{v:g}"


def fmt_date(iso, fmt):
    try:
        return date.fromisoformat(iso).strftime(fmt)
    except Exception:
        return iso or ""


class SignBlock(Flowable):
    """« The Responsible » + signature et cachet superposés."""
    def __init__(self, sig, stamp):
        super().__init__()
        self.sig, self.stamp = sig, stamp
        self.width, self.height = CW, 38 * mm

    def wrap(self, aw, ah):
        return self.width, self.height

    def draw(self):
        c = self.canv
        x0 = self.width - 62 * mm
        c.setFont("Helvetica", 8)
        c.drawString(x0 + 18 * mm, self.height - 8, "The Responsible")
        c.line(x0 + 18 * mm, self.height - 10, x0 + 18 * mm + 26 * mm, self.height - 10)
        for path, w, dx, dy in ((self.stamp, 30 * mm, 28 * mm, 0), (self.sig, 38 * mm, 0, 4 * mm)):
            if path:
                iw, ih = ImageReader(str(path)).getSize()
                h = w * ih / iw
                c.drawImage(str(path), x0 + dx, dy, w, h, mask="auto")


def build_pdf(db, invoice_id, out_path) -> Path:
    inv = db.get_invoice(invoice_id)
    cl, fmt = inv["client"], db.get("date_format")
    is_cn = inv["doc_type"] == "credit_note"
    hdr, ftr = db.image_path("header"), db.image_path("footer")
    sig, stamp = db.image_path("signature"), db.image_path("stamp")

    def img_h(path, width):
        if not path:
            return 0
        iw, ih = ImageReader(str(path)).getSize()
        return width * ih / iw
    hh, fh = img_h(hdr, CW), img_h(ftr, CW)
    top = 10 * mm + hh + 6 * mm
    bottom = 10 * mm + fh + 5 * mm
    draft = inv["status"] == "draft"

    def on_page(c, doc):
        if hdr:
            c.drawImage(str(hdr), MARGIN, H - 10 * mm - hh, CW, hh, mask="auto")
        if ftr:
            c.drawImage(str(ftr), MARGIN, 10 * mm, CW, fh, mask="auto")
        if draft:
            c.saveState(); c.setFont("Helvetica-Bold", 90); c.setFillColor(colors.Color(.85, .85, .85, alpha=.5))
            c.translate(W / 2, H / 2); c.rotate(45); c.drawCentredString(0, 0, "DRAFT"); c.restoreState()

    out_path = Path(out_path)
    doc = BaseDocTemplate(str(out_path), pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN,
                          topMargin=top, bottomMargin=bottom,
                          title=inv["number"] or "Draft", author="TRIMEX LOGISTICS")
    doc.addPageTemplates([PageTemplate(id="p", frames=[Frame(MARGIN, bottom, CW, H - top - bottom,
                                                              leftPadding=0, rightPadding=0, topPadding=0,
                                                              bottomPadding=0)], onPage=on_page)])
    story = []

    # --- bloc d'informations + « Bill to » ---------------------------
    rows, spans = [], []

    def add(label, value, label2=None, value2=None):
        r = len(rows)
        if label2 is None:
            rows.append([p(label, BOLD), p(value), "", ""]); spans.append(("SPAN", (1, r), (3, r)))
        else:
            rows.append([p(label, BOLD), p(value), p(label2, BOLD), p(value2)])
    add("Credit Note N°:" if is_cn else "Invoice N°:", inv["number"] or "(draft)",
        "Date:", fmt_date(inv["date"], fmt))
    if inv["file_no"] and inv["code_decl"]:
        add("FILE N°:", inv["file_no"], "Code Declaration:", inv["code_decl"])
    elif inv["file_no"] or inv["code_decl"]:
        add("FILE N°:" if inv["file_no"] else "Code Declaration:", inv["file_no"] or inv["code_decl"])
    if is_cn and inv["credit_of_id"]:
        ref = db.get_invoice(inv["credit_of_id"])
        add("Credit of invoice:", ref["number"] if ref else "")
    if inv["customs_decl"]:
        add("Customs Declaration N°:", inv["customs_decl"])
    if inv["shipment_value"]:
        add("Shipment Value :", f"{inv['shipment_value']} USD")
    if inv["parcels"] or inv["weight"]:
        add("Parcel Nbr :", inv["parcels"], "Weight :", inv["weight"])
    if inv["shipper"]:
        add("Shipper :", inv["shipper"])
    if inv["transport_no"]:
        add(f"{inv['transport_label'] or 'AWB'} N°", inv["transport_no"])
    if inv["supp_invoice"]:
        add("Supp Invoice :", inv["supp_invoice"])
    left = Table(rows, colWidths=[40 * mm, 24 * mm, 28 * mm, 18 * mm])
    left.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                              ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)] + spans))
    left_cells = [left]
    if inv["contact"]:
        left_cells.append(Paragraph(f"<b>Name : {escape(inv['contact'])}</b>", BASE))
    if inv["contact_email"]:
        left_cells.append(Paragraph(f"<b>Email: {escape(inv['contact_email'])}</b>", BASE))

    big = ParagraphStyle("big", parent=BOLD, fontSize=11, leading=14)
    cc = ParagraphStyle("cc", parent=BOLD, fontSize=13, leading=16)
    bill = [Paragraph("<u>Bill to :</u>", ParagraphStyle("s", parent=BASE, fontSize=6.5)), p(cl.get("name"), big)]
    if cl.get("division"):
        bill.append(p(cl["division"], ParagraphStyle("d", parent=BOLD, fontSize=10, leading=13)))
    if cl.get("cost_center"):
        bill.append(p("cc:" + cl["cost_center"], cc))
    for blk in (cl.get("address"), cl.get("refs")):
        if blk:
            bill.append(Spacer(1, 3)); bill.append(p(blk, ParagraphStyle("a", parent=BASE, fontSize=7.5, leading=10.5)))
    billbox = Table([[bill]], colWidths=[68 * mm])
    billbox.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, colors.black), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    head = Table([[left_cells, billbox]], colWidths=[CW - 70 * mm, 70 * mm])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                              ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    story += [head, Spacer(1, 6 * mm)]

    # --- tableau des lignes -----------------------------------------
    it = ParagraphStyle("it", parent=CENTER, fontName="Helvetica-BoldOblique")
    data = [[p("Description", it), p("Qty", it), p("Unit Price", it), p("Amount", it)]]
    st = [("BOX", (0, 0), (-1, 0), 1, colors.black), ("INNERGRID", (0, 0), (-1, 0), 0.5, colors.black),
          ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 1.5),
          ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5)]
    fx = {}
    for sec in (1, 2, 3):
        ls = [x for x in inv["lines"] if x["section"] == sec]
        if not ls:
            continue
        r = len(data)
        data.append([p(SECTIONS[sec][0], SECT), "", "", ""])
        st += [("SPAN", (0, r), (3, r)), ("BOX", (0, r), (-1, r), 0.5, colors.black)]
        sub = money(0)
        for x in ls:
            usd_price = money(x["unit_price"] * x["rate"])
            data.append([p(x["description"]), p(num(x["qty"]), RIGHT), p(amt(usd_price), RIGHT), p(amt(x["amount"]), RIGHT)])
            sub += money(x["amount"])
            if x["currency"] != "USD":
                fx[x["currency"]] = x["rate"]
        r = len(data)
        data.append([p(SECTIONS[sec][1], RIGHTB), "", "", p(amt(sub), RIGHTB)])
        st += [("SPAN", (0, r), (2, r)), ("BOX", (3, r), (3, r), 1, colors.black), ("TOPPADDING", (0, r), (-1, r), 4)]
    total = money(inv["total"])
    r = len(data)
    data.append([p("TOTAL", ParagraphStyle("t", parent=BOLD, alignment=1)), "", "", p(amt(total), RIGHTB)])
    st += [("SPAN", (0, r), (2, r)), ("BOX", (0, r), (-1, r), 1, colors.black), ("LINEABOVE", (0, r), (-1, r), 1, colors.black)]
    for label, val in ([("Total HT", amt(total))] +
                       ([("VAT (0%)", "EXEMPT")] if db.get("show_vat") == "1" else []) +
                       [("Total Amount", amt(total))]):
        r = len(data)
        data.append(["", "", p(label, BOLD), p(val, RIGHTB)])
        st += [("BOX", (2, r), (3, r), 1, colors.black), ("TOPPADDING", (0, r), (-1, r), 3)]
    tbl = Table(data, colWidths=[CW - 90 * mm, 14 * mm, 36 * mm, 40 * mm], repeatRows=1)
    tbl.setStyle(TableStyle(st))
    story.append(tbl)
    if fx:
        story += [Spacer(1, 3 * mm), p("   ".join(f"Currency 1.00 {c} = {r:g} USD" for c, r in fx.items()),
                                      ParagraphStyle("fx", parent=BASE, fontSize=7.5))]
    story += [Spacer(1, 8 * mm), SignBlock(sig, stamp)]
    doc.build(story)
    return out_path
