"""Interface PySide6 (français)."""
from __future__ import annotations
import os
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from PySide6.QtCore import QDate, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox,
                               QFileDialog, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QListWidget, QMainWindow, QMessageBox, QPlainTextEdit, QPushButton,
                               QSpinBox, QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from . import __version__
from .db import IMAGE_KEYS, SECTIONS, money
from .export import export_rows
from .pdf import build_pdf

STYLE = """
QMainWindow, QDialog { background:#f4f6f9; }
QListWidget#nav { background:#1f3a5f; color:#dfe7f2; border:0; font-size:14px; padding-top:12px; }
QListWidget#nav::item { padding:12px 18px; }
QListWidget#nav::item:selected { background:#2f5486; color:white; }
QPushButton { background:#1f3a5f; color:white; border:0; padding:7px 14px; border-radius:4px; }
QPushButton:hover { background:#2f5486; } QPushButton:disabled { background:#b9c2d0; }
QPushButton#flat { background:#e3e8f0; color:#1f3a5f; }
QTableWidget { background:white; gridline-color:#e3e8f0; alternate-background-color:#f7f9fc; }
QHeaderView::section { background:#e3e8f0; padding:5px; border:0; font-weight:bold; }
QLineEdit, QPlainTextEdit, QComboBox, QDateEdit, QSpinBox { background:white; border:1px solid #c5cedb; padding:4px; border-radius:3px; }
QGroupBox { font-weight:bold; border:1px solid #d3dae6; border-radius:5px; margin-top:10px; padding-top:8px; }
QGroupBox::title { subcontrol-origin: margin; left:10px; }
"""
STATE_COLORS = {"Brouillon": "#7a869a", "Payée": "#1e8e3e", "Partielle": "#d98e04", "En retard": "#c62828",
                "Impayée": "#b26a00", "Avoir": "#5b3ea6"}


def num(text, default=None, rate=False):
    """Lit un nombre saisi à la main : 14,030.00 / 14.030,00 / 14 030,5 / 14030.5"""
    t = str(text or "").replace("\u00a0", "").replace(" ", "")
    if not t:
        return default
    if rate:                                        # taux de change : la virgule est toujours décimale
        t = t.replace(",", ".")
        try:
            return Decimal(t)
        except InvalidOperation:
            return default
    last = max(t.rfind(","), t.rfind("."))
    if last >= 0:
        intpart = t[:last].replace(",", "").replace(".", "")
        frac = t[last + 1:]
        if frac.isdigit() and len(frac) == 3 and (t.count(",") + t.count(".")) == 1 and last > 0:
            intpart, frac = intpart + frac, ""      # « 14,030 » = quatorze mille trente
        t = intpart + ("." + frac if frac else "")
    try:
        return Decimal(t)
    except InvalidOperation:
        return default


def fmt(v):
    return f"{float(v):,.2f}"


def qdate(iso):
    d = QDate.fromString(iso or "", "yyyy-MM-dd")
    return d if d.isValid() else QDate.currentDate()


def warn(parent, msg):
    QMessageBox.warning(parent, "Attention", msg)


def open_file(path):
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def make_table(headers, widths=None):
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setSelectionMode(QAbstractItemView.SingleSelection)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setAlternatingRowColors(True)
    t.verticalHeader().setVisible(False)
    t.horizontalHeader().setStretchLastSection(True)
    for i, w in enumerate(widths or []):
        t.setColumnWidth(i, w)
    return t


def cell(text, align=None, user=None, color=None):
    it = QTableWidgetItem(str(text if text is not None else ""))
    if align == "r":
        it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    if user is not None:
        it.setData(Qt.UserRole, user)
    if color:
        from PySide6.QtGui import QBrush, QColor
        it.setForeground(QBrush(QColor(color)))
    return it


# ===================================================================== clients
class ClientDialog(QDialog):
    def __init__(self, db, cid=None, parent=None):
        super().__init__(parent)
        self.db, self.cid = db, cid
        self.setWindowTitle("Client"); self.resize(480, 520)
        c = db.get_client(cid) if cid else {}
        f = QFormLayout()
        self.name = QLineEdit(c.get("name", "")); self.div = QLineEdit(c.get("division", ""))
        self.cc = QLineEdit(c.get("cost_center", ""))
        self.addr = QPlainTextEdit(c.get("address", "")); self.addr.setFixedHeight(70)
        self.refs = QPlainTextEdit(c.get("refs", "")); self.refs.setFixedHeight(70)
        self.contact = QLineEdit(c.get("contact", "")); self.email = QLineEdit(c.get("contact_email", ""))
        self.addr.setPlaceholderText("BP 527 ROUTE D EL BORMA\n30500 HASSI MESSAOUD. ALGERIA")
        self.refs.setPlaceholderText("GL 500200\nNIF: 308004000006746")
        self.contact.setPlaceholderText("BH requestor name:Adib, George")
        for lab, w in (("Nom du client *", self.name), ("Division", self.div), ("Centre de coût (cc)", self.cc),
                       ("Adresse", self.addr), ("Références (GL, NIF…)", self.refs),
                       ("Contact (ligne « Name »)", self.contact), ("E-mail du contact", self.email)):
            f.addRow(lab, w)
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.save); bb.rejected.connect(self.reject)
        lay = QVBoxLayout(self); lay.addLayout(f); lay.addWidget(bb)

    def save(self):
        try:
            self.db.save_client(dict(name=self.name.text(), division=self.div.text(), cost_center=self.cc.text(),
                                     address=self.addr.toPlainText(), refs=self.refs.toPlainText(),
                                     contact=self.contact.text(), contact_email=self.email.text()), self.cid)
        except ValueError as e:
            return warn(self, str(e))
        self.accept()


class ClientsPage(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.table = make_table(["Client", "Division", "cc", "Adresse"], [260, 160, 110])
        bar = QHBoxLayout()
        for txt, fn in (("Nouveau client", self.add), ("Modifier", self.edit), ("Supprimer", self.delete)):
            b = QPushButton(txt); b.clicked.connect(fn); bar.addWidget(b)
        bar.addStretch()
        self.table.doubleClicked.connect(self.edit)
        lay = QVBoxLayout(self); lay.addLayout(bar); lay.addWidget(self.table)

    def refresh(self):
        rows = self.db.list_clients()
        self.table.setRowCount(len(rows))
        for i, c in enumerate(rows):
            self.table.setItem(i, 0, cell(c["name"], user=c["id"]))
            self.table.setItem(i, 1, cell(c["division"])); self.table.setItem(i, 2, cell(c["cost_center"]))
            self.table.setItem(i, 3, cell(c["address"].replace("\n", " · ")))

    def current(self):
        r = self.table.currentRow()
        return self.table.item(r, 0).data(Qt.UserRole) if r >= 0 else None

    def add(self):
        if ClientDialog(self.db, None, self).exec():
            self.refresh()

    def edit(self):
        cid = self.current()
        if cid and ClientDialog(self.db, cid, self).exec():
            self.refresh()

    def delete(self):
        cid = self.current()
        if cid and QMessageBox.question(self, "Supprimer", "Supprimer ce client ?\n(S'il a des factures, il sera "
                                        "seulement masqué.)") == QMessageBox.Yes:
            self.db.delete_client(cid); self.refresh()


# ===================================================================== facture
class InvoiceDialog(QDialog):
    COLS = ["Section", "Description", "Qté", "Prix unitaire", "Devise", "Taux → USD", "Montant USD"]

    def __init__(self, db, invoice_id=None, parent=None):
        super().__init__(parent)
        self.db, self.iid = db, invoice_id
        inv = db.get_invoice(invoice_id) if invoice_id else {}
        self.doc_type = inv.get("doc_type", "invoice"); self.credit_of = inv.get("credit_of_id")
        self.setWindowTitle("Avoir" if self.doc_type == "credit_note" else "Facture")
        self.resize(1050, 760)
        self.clients = db.list_clients()
        self.client = QComboBox()
        for c in self.clients:
            self.client.addItem(c["name"] + (" — " + c["division"] if c["division"] else ""), c["id"])
        if inv.get("client_id"):
            i = self.client.findData(inv["client_id"]); self.client.setCurrentIndex(max(i, 0))
        self.date = QDateEdit(qdate(inv.get("date"))); self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("MM/dd/yyyy")
        self.due = QDateEdit(qdate(inv.get("due_date")) if inv.get("due_date") else
                             QDate.currentDate().addDays(int(db.get("terms_days"))))
        self.due.setCalendarPopup(True); self.due.setDisplayFormat("MM/dd/yyyy")
        e = lambda k, ph="": self._edit(inv.get(k, ""), ph)
        self.file_no = e("file_no", "auto à la validation (DZ/FF/…)")
        self.code = self._edit(inv.get("code_decl") or db.get("code_decl"))
        self.customs = e("customs_decl"); self.value = e("shipment_value", "ex. 155,750.81")
        self.parcels = e("parcels"); self.weight = e("weight"); self.shipper = e("shipper")
        self.tlabel = QComboBox(); self.tlabel.addItems(["AWB", "BL", "CMR"])
        self.tlabel.setCurrentText(inv.get("transport_label") or "AWB")
        self.tno = e("transport_no"); self.supp = e("supp_invoice")
        self.contact = e("contact"); self.email = e("contact_email")
        self.notes = e("notes", "note interne (non imprimée)")

        g = QGridLayout()
        fields = [("Client", self.client), ("Date", self.date), ("Échéance", self.due), ("FILE N°", self.file_no),
                  ("Code Declaration", self.code), ("Customs Declaration N°", self.customs),
                  ("Shipment Value (USD)", self.value), ("Parcels", self.parcels), ("Weight", self.weight),
                  ("Shipper", self.shipper), ("Doc transport", self.tlabel), ("N° AWB/BL/CMR", self.tno),
                  ("Supp Invoice", self.supp), ("Contact (Name)", self.contact), ("E-mail", self.email),
                  ("Note interne", self.notes)]
        for i, (lab, w) in enumerate(fields):
            r, c = divmod(i, 3)
            g.addWidget(QLabel(lab), r * 2, c); g.addWidget(w, r * 2 + 1, c)
        head = QGroupBox("Informations"); head.setLayout(g)
        self.client.currentIndexChanged.connect(self.client_changed)

        self.table = QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        h = self.table.horizontalHeader(); h.setSectionResizeMode(1, QHeaderView.Stretch)
        for i, w in enumerate([210, 0, 60, 110, 70, 90, 110]):
            if w:
                self.table.setColumnWidth(i, w)
        self.table.itemChanged.connect(self.recalc)
        self.tpl = QComboBox(); self.reload_templates()
        bar = QHBoxLayout()
        for txt, fn, flat in (("+ Ligne", lambda: self.add_line(), False), ("− Supprimer la ligne", self.del_line, True),
                              ("Insérer ligne type", self.insert_template, True),
                              ("Enregistrer comme ligne type", self.save_template, True)):
            b = QPushButton(txt); b.setObjectName("flat" if flat else ""); b.clicked.connect(fn)
            if txt == "Insérer ligne type":
                bar.addWidget(self.tpl)
            bar.addWidget(b)
        bar.addStretch()
        self.total = QLabel(); self.total.setStyleSheet("font-size:16px;font-weight:bold;color:#1f3a5f")
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Save).setText("Enregistrer le brouillon")
        bb.accepted.connect(self.save); bb.rejected.connect(self.reject)
        lay = QVBoxLayout(self); lay.addWidget(head); lay.addLayout(bar); lay.addWidget(self.table)
        foot = QHBoxLayout(); foot.addWidget(self.total); foot.addStretch(); foot.addWidget(bb)
        lay.addLayout(foot)
        for ln in inv.get("lines", []):
            self.add_line(ln)
        if not inv.get("lines"):
            self.add_line()
        if not invoice_id and self.clients:
            self.client_changed()
        self.recalc()

    def _edit(self, text="", ph=""):
        w = QLineEdit(str(text or "")); w.setPlaceholderText(ph); return w

    def client_changed(self):
        c = self.db.get_client(self.client.currentData()) or {}
        if not self.contact.text():
            self.contact.setText(c.get("contact", ""))
        if not self.email.text():
            self.email.setText(c.get("contact_email", ""))

    def reload_templates(self):
        self.tpl.clear()
        for t in self.db.list_templates():
            self.tpl.addItem(f"{t['description']} ({t['unit_price']:,.2f})", t)

    def add_line(self, ln=None):
        ln = ln or {}
        self.table.blockSignals(True)
        r = self.table.rowCount(); self.table.insertRow(r)
        sec = QComboBox()
        for k, (title, _) in SECTIONS.items():
            sec.addItem(title, k)
        sec.setCurrentIndex(sec.findData(ln.get("section", 1)))
        self.table.setCellWidget(r, 0, sec)
        vals = [ln.get("description", ""), num_s(ln.get("qty", 1)), num_s(ln.get("unit_price", "")),
                ln.get("currency", "USD"), num_s(ln.get("rate", 1))]
        for j, v in enumerate(vals, 1):
            self.table.setItem(r, j, cell(v, "r" if j in (2, 3, 5) else None))
        amt = cell("0.00", "r"); amt.setFlags(amt.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(r, 6, amt)
        self.table.blockSignals(False)
        self.recalc()

    def del_line(self):
        r = self.table.currentRow()
        if r >= 0:
            self.table.removeRow(r); self.recalc()

    def insert_template(self):
        t = self.tpl.currentData()
        if t:
            self.add_line(dict(section=t["section"], description=t["description"], unit_price=t["unit_price"]))

    def save_template(self):
        r = self.table.currentRow()
        if r < 0:
            return warn(self, "Sélectionnez d'abord une ligne.")
        d = self.row(r)
        if not d["description"]:
            return warn(self, "La ligne n'a pas de description.")
        self.db.save_template(d["section"], d["description"], d["unit_price"]); self.reload_templates()

    def row(self, r):
        g = lambda c: (self.table.item(r, c).text() if self.table.item(r, c) else "")
        cur = (g(4) or "USD").strip().upper()
        return dict(section=self.table.cellWidget(r, 0).currentData(), description=g(1).strip(),
                    qty=num(g(2), Decimal(1)), unit_price=num(g(3), Decimal(0)), currency=cur,
                    rate=num(g(5), Decimal(1), rate=True) if cur != "USD" else Decimal(1))

    def recalc(self, *_):
        total = Decimal(0)
        self.table.blockSignals(True)
        for r in range(self.table.rowCount()):
            d = self.row(r)
            a = money(d["qty"] * d["unit_price"] * d["rate"]); total += a
            self.table.item(r, 6).setText(fmt(a))
        self.table.blockSignals(False)
        self.total.setText(f"Total : {fmt(total)} USD")

    def save(self):
        lines = [self.row(r) for r in range(self.table.rowCount())]
        lines = [dict(l, qty=float(l["qty"]), unit_price=float(l["unit_price"]), rate=float(l["rate"])) for l in lines]
        data = dict(doc_type=self.doc_type, credit_of_id=self.credit_of, client_id=self.client.currentData(),
                    date=self.date.date().toString("yyyy-MM-dd"), due_date=self.due.date().toString("yyyy-MM-dd"),
                    file_no=self.file_no.text().strip(), code_decl=self.code.text().strip(),
                    customs_decl=self.customs.text().strip(), shipment_value=self.value.text().strip(),
                    parcels=self.parcels.text().strip(), weight=self.weight.text().strip(),
                    shipper=self.shipper.text().strip(), transport_label=self.tlabel.currentText(),
                    transport_no=self.tno.text().strip(), supp_invoice=self.supp.text().strip(),
                    contact=self.contact.text().strip(), contact_email=self.email.text().strip(),
                    notes=self.notes.text().strip())
        try:
            self.iid = self.db.save_invoice(data, lines, self.iid)
        except ValueError as e:
            return warn(self, str(e))
        self.accept()


def num_s(v):
    if v in ("", None):
        return ""
    f = float(v)
    return str(int(f)) if f == int(f) else f"{f:g}"


class PaymentDialog(QDialog):
    def __init__(self, db, row, parent=None):
        super().__init__(parent)
        self.db, self.row = db, row
        self.setWindowTitle(f"Paiement — {row['number']}")
        self.date = QDateEdit(QDate.currentDate()); self.date.setCalendarPopup(True)
        self.amount = QLineEdit(f"{row['balance']:.2f}")
        self.method = QComboBox(); self.method.addItems(["Bank transfer", "Cheque", "Cash"])
        self.ref = QLineEdit()
        f = QFormLayout()
        f.addRow("Solde restant", QLabel(f"{fmt(row['balance'])} USD")); f.addRow("Date", self.date)
        f.addRow("Montant (USD)", self.amount); f.addRow("Mode", self.method); f.addRow("Référence", self.ref)
        pays = db.list_payments(row["id"])
        if pays:
            f.addRow("Déjà reçu", QLabel("\n".join(f"{p['date']}  {fmt(p['amount'])}  {p['method']}" for p in pays)))
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.save); bb.rejected.connect(self.reject)
        lay = QVBoxLayout(self); lay.addLayout(f); lay.addWidget(bb)

    def save(self):
        a = num(self.amount.text())
        if a is None:
            return warn(self, "Montant invalide.")
        try:
            self.db.add_payment(self.row["id"], self.date.date().toString("yyyy-MM-dd"), a,
                                self.method.currentText(), self.ref.text())
        except ValueError as e:
            return warn(self, str(e))
        self.accept()


class InvoicesPage(QWidget):
    HEAD = ["N°", "Date", "Client", "Dossier", "Total USD", "Payé", "Solde", "Échéance", "État"]

    def __init__(self, db):
        super().__init__()
        self.db = db
        self.search = QLineEdit(); self.search.setPlaceholderText("Rechercher : n°, client, dossier, AWB…")
        self.filter = QComboBox(); self.filter.addItems(["Toutes", "Brouillon", "Impayée", "Partielle", "En retard",
                                                          "Payée", "Avoir"])
        self.search.textChanged.connect(self.refresh); self.filter.currentIndexChanged.connect(self.refresh)
        self.table = make_table(self.HEAD, [150, 85, 230, 100, 100, 90, 90, 85])
        self.table.itemSelectionChanged.connect(self.update_buttons)
        self.table.doubleClicked.connect(self.open_current)
        self.btn = {}
        bar = QHBoxLayout()
        for key, txt, fn in (("new", "Nouvelle facture", self.new), ("edit", "Modifier", self.edit),
                             ("validate", "Valider", self.validate), ("pdf", "PDF", self.pdf),
                             ("pay", "Paiement", self.pay), ("cn", "Créer un avoir", self.credit),
                             ("dup", "Dupliquer", self.duplicate), ("del", "Supprimer", self.delete),
                             ("xls", "Export Excel", self.export)):
            b = QPushButton(txt); b.clicked.connect(fn); self.btn[key] = b; bar.addWidget(b)
            if key not in ("new", "xls"):
                b.setObjectName("flat")
        bar.addStretch()
        top = QHBoxLayout(); top.addWidget(self.search, 1); top.addWidget(self.filter)
        self.summary = QLabel()
        lay = QVBoxLayout(self); lay.addLayout(top); lay.addLayout(bar); lay.addWidget(self.table)
        lay.addWidget(self.summary)
        self.rows = []

    def refresh(self):
        flt = self.filter.currentText()
        self.rows = [r for r in self.db.list_invoices(self.search.text()) if flt == "Toutes" or r["state"] == flt]
        t = self.table; t.setRowCount(len(self.rows))
        fmtd = self.db.get("date_format")
        for i, r in enumerate(self.rows):
            sign = -1 if r["doc_type"] == "credit_note" else 1
            vals = [r["number"] or "(brouillon)", date.fromisoformat(r["date"]).strftime(fmtd),
                    r["client_name"] + (" — " + r["client_division"] if r["client_division"] else ""), r["file_no"],
                    fmt(sign * r["total"]), fmt(r["paid"]) if r["doc_type"] == "invoice" else "",
                    fmt(r["balance"]) if r["status"] == "validated" and r["doc_type"] == "invoice" else "",
                    date.fromisoformat(r["due_date"]).strftime(fmtd) if r["due_date"] and r["doc_type"] == "invoice" else "",
                    r["state"]]
            for j, v in enumerate(vals):
                t.setItem(i, j, cell(v, "r" if j in (4, 5, 6) else None, user=r["id"] if j == 0 else None,
                                     color=STATE_COLORS.get(r["state"]) if j == 8 else None))
        out = sum(r["balance"] for r in self.rows if r["status"] == "validated" and r["doc_type"] == "invoice")
        self.summary.setText(f"{len(self.rows)} document(s) — solde à encaisser (liste affichée) : {fmt(out)} USD")
        self.update_buttons()

    def cur(self):
        r = self.table.currentRow()
        return self.rows[r] if 0 <= r < len(self.rows) else None

    def update_buttons(self):
        c = self.cur()
        draft = bool(c) and c["status"] == "draft"
        inv_ok = bool(c) and c["status"] == "validated" and c["doc_type"] == "invoice"
        for k, on in (("edit", draft), ("validate", draft), ("del", draft), ("pdf", bool(c)), ("dup", bool(c)),
                      ("pay", inv_ok and c["balance"] > 0.005), ("cn", inv_ok)):
            self.btn[k].setEnabled(on)

    def new(self):
        if not self.db.list_clients():
            return warn(self, "Créez d'abord un client (menu Clients).")
        InvoiceDialog(self.db, None, self).exec(); self.refresh()

    def edit(self):
        c = self.cur()
        if c and c["status"] == "draft":
            InvoiceDialog(self.db, c["id"], self).exec(); self.refresh()

    def open_current(self):
        c = self.cur()
        if c:
            self.edit() if c["status"] == "draft" else self.pdf()

    def validate(self):
        c = self.cur()
        if not c:
            return
        if QMessageBox.question(self, "Valider", "Une fois validé, le document reçoit son numéro définitif et ne "
                                "peut plus être modifié (correction par avoir).\n\nValider ?") != QMessageBox.Yes:
            return
        try:
            self.db.validate_invoice(c["id"])
        except ValueError as e:
            return warn(self, str(e))
        self.refresh(); self.make_pdf(c["id"])

    def make_pdf(self, iid):
        inv = self.db.get_invoice(iid)
        name = (inv["number"] or f"draft-{iid}").replace("/", "-")
        path = self.db.dir / "pdf" / f"{name}.pdf"
        try:
            build_pdf(self.db, iid, path)
        except Exception as e:  # noqa: BLE001
            return warn(self, f"Impossible de créer le PDF :\n{e}")
        open_file(path)

    def pdf(self):
        c = self.cur()
        if c:
            self.make_pdf(c["id"])

    def pay(self):
        c = self.cur()
        if c and PaymentDialog(self.db, c, self).exec():
            self.refresh()

    def credit(self):
        c = self.cur()
        if c and QMessageBox.question(self, "Avoir", "Créer un avoir (brouillon) lié à cette facture ?") == QMessageBox.Yes:
            try:
                iid = self.db.create_credit_note(c["id"])
            except ValueError as e:
                return warn(self, str(e))
            InvoiceDialog(self.db, iid, self).exec(); self.refresh()

    def duplicate(self):
        c = self.cur()
        if c:
            iid = self.db.duplicate_invoice(c["id"]); self.refresh()
            InvoiceDialog(self.db, iid, self).exec(); self.refresh()

    def delete(self):
        c = self.cur()
        if c and QMessageBox.question(self, "Supprimer", "Supprimer ce brouillon ?") == QMessageBox.Yes:
            self.db.delete_draft(c["id"]); self.refresh()

    def export(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Excel", "factures.xlsx", "Excel (*.xlsx)")
        if path:
            export_rows(path, "Factures", ["N°", "Date", "Client", "Division", "Dossier", "Type", "Total USD",
                                           "Payé", "Solde", "Échéance", "État"],
                        [[r["number"], r["date"], r["client_name"], r["client_division"], r["file_no"], r["doc_type"],
                          r["total"], r["paid"], r["balance"], r["due_date"], r["state"]] for r in self.rows])
            open_file(path)


# ===================================================================== impayés
class UnpaidPage(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.table = make_table(["N°", "Client", "Dossier", "Date", "Échéance", "Total", "Solde", "Retard (j)"],
                                [150, 250, 100, 90, 90, 100, 100])
        b = QPushButton("Export Excel"); b.clicked.connect(self.export)
        self.sum = QLabel(); self.sum.setStyleSheet("font-size:15px;font-weight:bold;color:#1f3a5f")
        lay = QVBoxLayout(self); top = QHBoxLayout(); top.addWidget(self.sum); top.addStretch(); top.addWidget(b)
        lay.addLayout(top); lay.addWidget(self.table)
        self.rows = []

    def refresh(self):
        self.rows = sorted(self.db.unpaid(), key=lambda r: r["due_date"] or "")
        self.table.setRowCount(len(self.rows)); today = date.today()
        for i, r in enumerate(self.rows):
            late = (today - date.fromisoformat(r["due_date"])).days if r["due_date"] else 0
            vals = [r["number"], r["client_name"] + (" — " + r["client_division"] if r["client_division"] else ""),
                    r["file_no"], r["date"], r["due_date"], fmt(r["total"]), fmt(r["balance"]), max(late, 0)]
            for j, v in enumerate(vals):
                self.table.setItem(i, j, cell(v, "r" if j >= 5 else None, color="#c62828" if late > 0 and j == 7 else None))
        self.sum.setText(f"Total à encaisser : {fmt(sum(r['balance'] for r in self.rows))} USD "
                         f"({len(self.rows)} facture(s))")

    def export(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Excel", "impayes.xlsx", "Excel (*.xlsx)")
        if path:
            export_rows(path, "Impayés", ["N°", "Client", "Division", "Dossier", "Date", "Échéance", "Total", "Solde"],
                        [[r["number"], r["client_name"], r["client_division"], r["file_no"], r["date"], r["due_date"],
                          r["total"], r["balance"]] for r in self.rows])
            open_file(path)


# ===================================================================== paramètres
class SettingsPage(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.inv_prefix = QLineEdit(); self.file_prefix = QLineEdit(); self.cn_prefix = QLineEdit()
        self.next_inv = QSpinBox(); self.next_inv.setRange(1, 99999)
        self.terms = QSpinBox(); self.terms.setRange(0, 365)
        self.code = QLineEdit(); self.vat = QCheckBox("Afficher la ligne « VAT (0%) EXEMPT » sur les factures")
        num_box = QGroupBox("Numérotation et conditions"); f = QFormLayout(num_box)
        f.addRow("Préfixe facture", self.inv_prefix); f.addRow("Préfixe dossier (FILE N°)", self.file_prefix)
        f.addRow("Préfixe avoir", self.cn_prefix)
        f.addRow(f"Prochain numéro (année {date.today().year % 100:02d})", self.next_inv)
        f.addRow("Délai de paiement (jours)", self.terms); f.addRow("Code Declaration par défaut", self.code)
        f.addRow("", self.vat)
        sv = QPushButton("Enregistrer"); sv.clicked.connect(self.save); f.addRow("", sv)

        img_box = QGroupBox("Images du document (importées une seule fois, stockées sur ce PC)")
        g = QGridLayout(img_box); self.previews = {}
        for r, (k, label) in enumerate(IMAGE_KEYS.items()):
            pv = QLabel(); pv.setFixedSize(210, 50); pv.setStyleSheet("border:1px solid #c5cedb;background:white")
            pv.setAlignment(Qt.AlignCenter); self.previews[k] = pv
            b = QPushButton("Importer…"); b.setObjectName("flat"); b.clicked.connect(lambda _=0, k=k: self.pick(k))
            x = QPushButton("Retirer"); x.setObjectName("flat"); x.clicked.connect(lambda _=0, k=k: self.drop(k))
            g.addWidget(QLabel(label), r, 0); g.addWidget(pv, r, 1); g.addWidget(b, r, 2); g.addWidget(x, r, 3)

        bk = QGroupBox("Sauvegarde")
        h = QHBoxLayout(bk)
        for txt, fn in (("Sauvegarder maintenant…", self.backup), ("Restaurer une sauvegarde…", self.restore),
                        ("Ouvrir le dossier des données", lambda: open_file(self.db.dir))):
            b = QPushButton(txt); b.setObjectName("flat"); b.clicked.connect(fn); h.addWidget(b)
        info = QLabel(f"Version {__version__} — données : {db.dir}\nUne sauvegarde automatique est faite chaque jour "
                      "(15 dernières conservées). Copiez de temps en temps un fichier de sauvegarde sur une clé USB.")
        info.setWordWrap(True)
        lay = QVBoxLayout(self)
        for w in (num_box, img_box, bk, info):
            lay.addWidget(w)
        lay.addStretch()

    def refresh(self):
        d = self.db
        self.inv_prefix.setText(d.get("inv_prefix")); self.file_prefix.setText(d.get("file_prefix"))
        self.cn_prefix.setText(d.get("cn_prefix")); self.terms.setValue(int(d.get("terms_days")))
        self.code.setText(d.get("code_decl")); self.vat.setChecked(d.get("show_vat") == "1")
        self.next_inv.setValue(d.counter("inv-%02d" % (date.today().year % 100)))
        for k, pv in self.previews.items():
            p = d.image_path(k); pix = QPixmap(str(p)) if p else QPixmap()
            if pix.isNull():
                pv.clear(); pv.setText("— aucune —")
            else:
                pv.setPixmap(pix.scaled(pv.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def save(self):
        d = self.db
        for k, w in (("inv_prefix", self.inv_prefix), ("file_prefix", self.file_prefix), ("cn_prefix", self.cn_prefix),
                     ("code_decl", self.code)):
            d.set(k, w.text().strip())
        d.set("terms_days", self.terms.value()); d.set("show_vat", "1" if self.vat.isChecked() else "0")
        d.set_counter("inv-%02d" % (date.today().year % 100), self.next_inv.value())
        QMessageBox.information(self, "Enregistré", "Paramètres enregistrés.")

    def pick(self, key):
        path, _ = QFileDialog.getOpenFileName(self, IMAGE_KEYS[key], "", "Images (*.png *.jpg *.jpeg)")
        if path:
            self.db.set_image(key, path); self.refresh()

    def drop(self, key):
        self.db.remove_image(key); self.refresh()

    def backup(self):
        path, _ = QFileDialog.getSaveFileName(self, "Sauvegarde", f"trimex-sauvegarde-{date.today()}.zip", "Zip (*.zip)")
        if path:
            self.db.backup(path); QMessageBox.information(self, "Sauvegarde", "Sauvegarde créée.")

    def restore(self):
        path, _ = QFileDialog.getOpenFileName(self, "Restaurer", "", "Zip (*.zip)")
        if path and QMessageBox.question(self, "Restaurer", "Remplacer toutes les données actuelles par cette "
                                         "sauvegarde ?\n(Une copie de l'état actuel est gardée.)") == QMessageBox.Yes:
            try:
                self.db.restore(path)
            except Exception as e:  # noqa: BLE001
                return warn(self, str(e))
            self.refresh(); QMessageBox.information(self, "Restauration", "Sauvegarde restaurée.")


# ===================================================================== fenêtre principale
class MainWindow(QMainWindow):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.setWindowTitle(f"Trimex Facturation {__version__}"); self.resize(1280, 780)
        self.setStyleSheet(STYLE)
        self.nav = QListWidget(); self.nav.setObjectName("nav"); self.nav.setFixedWidth(190)
        self.pages = [InvoicesPage(db), ClientsPage(db), UnpaidPage(db), SettingsPage(db)]
        self.stack = QStackedWidget()
        for name, page in zip(["Factures", "Clients", "Impayés", "Paramètres"], self.pages):
            self.nav.addItem(name); self.stack.addWidget(page)
        self.nav.currentRowChanged.connect(self.go)
        root = QWidget(); lay = QHBoxLayout(root); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)
        lay.addWidget(self.nav)
        right = QVBoxLayout(); right.setContentsMargins(14, 14, 14, 14); right.addWidget(self.stack)
        lay.addLayout(right); self.setCentralWidget(root)
        self.nav.setCurrentRow(0)
        if not db.image_path("header") or not db.list_clients():
            self.nav.setCurrentRow(3 if not db.image_path("header") else 1)

    def go(self, i):
        self.stack.setCurrentIndex(i); self.pages[i].refresh()
