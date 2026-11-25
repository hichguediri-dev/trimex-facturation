"""Base de données locale (SQLite) et règles de gestion."""
from __future__ import annotations
import os, shutil, sqlite3, tempfile, zipfile
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

APP_NAME = "TrimexFacturation"
IMAGE_KEYS = {
    "header": "Bandeau d'en-tête (logo + adresse)",
    "footer": "Pied de page (RN, TRN, coordonnées bancaires)",
    "signature": "Signature",
    "stamp": "Cachet",
}
SECTIONS = {
    1: ("Customs Clearance & International Freight", "Total Customs Clearance"),
    2: ("Warehousing", "Total Warehousing"),
    3: ("Delivery, Land Transportation & Other Charges", "Total Transport"),
}
DEFAULTS = {
    "inv_prefix": "EX/ALG/", "file_prefix": "DZ/FF/", "cn_prefix": "CN/ALG/",
    "terms_days": "30", "code_decl": "P.EX", "show_vat": "0",
    "date_format": "%m/%d/%Y", "currency": "USD",
}
INVOICE_FIELDS = [
    "doc_type", "credit_of_id", "client_id", "date", "due_date", "file_no", "code_decl",
    "customs_decl", "shipment_value", "parcels", "weight", "shipper", "transport_label",
    "transport_no", "supp_invoice", "contact", "contact_email", "notes",
]
SCHEMA = """
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS counters(name TEXT PRIMARY KEY, next INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS clients(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, division TEXT DEFAULT '', cost_center TEXT DEFAULT '',
  address TEXT DEFAULT '', refs TEXT DEFAULT '', contact TEXT DEFAULT '', contact_email TEXT DEFAULT '',
  active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS invoices(
  id INTEGER PRIMARY KEY, number TEXT UNIQUE, doc_type TEXT NOT NULL DEFAULT 'invoice',
  status TEXT NOT NULL DEFAULT 'draft', credit_of_id INTEGER REFERENCES invoices(id),
  client_id INTEGER REFERENCES clients(id), date TEXT, due_date TEXT, file_no TEXT DEFAULT '',
  code_decl TEXT DEFAULT '', customs_decl TEXT DEFAULT '', shipment_value TEXT DEFAULT '',
  parcels TEXT DEFAULT '', weight TEXT DEFAULT '', shipper TEXT DEFAULT '',
  transport_label TEXT DEFAULT '', transport_no TEXT DEFAULT '', supp_invoice TEXT DEFAULT '',
  contact TEXT DEFAULT '', contact_email TEXT DEFAULT '', notes TEXT DEFAULT '',
  total REAL NOT NULL DEFAULT 0, created_at TEXT, validated_at TEXT);
CREATE TABLE IF NOT EXISTS lines(
  id INTEGER PRIMARY KEY, invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
  section INTEGER NOT NULL DEFAULT 1, pos INTEGER NOT NULL DEFAULT 0, description TEXT DEFAULT '',
  qty REAL NOT NULL DEFAULT 1, unit_price REAL NOT NULL DEFAULT 0, currency TEXT NOT NULL DEFAULT 'USD',
  rate REAL NOT NULL DEFAULT 1, amount REAL NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS payments(
  id INTEGER PRIMARY KEY, invoice_id INTEGER NOT NULL REFERENCES invoices(id),
  date TEXT NOT NULL, amount REAL NOT NULL, method TEXT DEFAULT '', reference TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS line_templates(
  id INTEGER PRIMARY KEY, section INTEGER NOT NULL DEFAULT 1, description TEXT NOT NULL,
  unit_price REAL NOT NULL DEFAULT 0);
"""


def money(x) -> Decimal:
    return Decimal(str(x)).quantize(Decimal("0.01"), ROUND_HALF_UP)


def data_dir() -> Path:
    base = os.environ.get("TRIMEX_DATA") or os.path.join(
        os.environ.get("APPDATA") or str(Path.home()), APP_NAME)
    p = Path(base)
    for sub in ("images", "pdf", "backups"):
        (p / sub).mkdir(parents=True, exist_ok=True)
    return p


class DB:
    def __init__(self, folder: str | Path | None = None):
        self.dir = Path(folder) if folder else data_dir()
        for sub in ("images", "pdf", "backups"):
            (self.dir / sub).mkdir(parents=True, exist_ok=True)
        self._connect()

    def _connect(self):
        self.conn = sqlite3.connect(self.dir / "data.db")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # ---- paramètres -------------------------------------------------
    def get(self, key, default=None):
        r = self.conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        if r is not None:
            return r["value"]
        return DEFAULTS.get(key, default if default is not None else "")

    def set(self, key, value):
        with self.conn:
            self.conn.execute("INSERT INTO settings(key,value) VALUES(?,?) "
                              "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))

    def counter(self, name) -> int:
        r = self.conn.execute("SELECT next FROM counters WHERE name=?", (name,)).fetchone()
        return r["next"] if r else 1

    def set_counter(self, name, n: int):
        with self.conn:
            self.conn.execute("INSERT INTO counters(name,next) VALUES(?,?) "
                              "ON CONFLICT(name) DO UPDATE SET next=excluded.next", (name, int(n)))

    # ---- images (en-tête, pied de page, signature, cachet) ----------
    def image_path(self, key) -> Path | None:
        for f in (self.dir / "images").glob(key + ".*"):
            return f
        return None

    def set_image(self, key, src):
        if key not in IMAGE_KEYS:
            raise ValueError(key)
        self.remove_image(key)
        src = Path(src)
        shutil.copy(src, self.dir / "images" / (key + src.suffix.lower()))

    def remove_image(self, key):
        for f in (self.dir / "images").glob(key + ".*"):
            f.unlink()

    # ---- clients ----------------------------------------------------
    def list_clients(self, active_only=True):
        q = "SELECT * FROM clients" + (" WHERE active=1" if active_only else "") + " ORDER BY name, division"
        return [dict(r) for r in self.conn.execute(q)]

    def get_client(self, cid):
        r = self.conn.execute("SELECT * FROM clients WHERE id=?", (cid,)).fetchone()
        return dict(r) if r else None

    def save_client(self, d: dict, cid=None) -> int:
        if not d.get("name", "").strip():
            raise ValueError("Le nom du client est obligatoire.")
        cols = ["name", "division", "cost_center", "address", "refs", "contact", "contact_email"]
        vals = [d.get(c, "").strip() for c in cols]
        with self.conn:
            if cid:
                self.conn.execute("UPDATE clients SET " + ",".join(c + "=?" for c in cols) + " WHERE id=?",
                                  vals + [cid])
                return cid
            cur = self.conn.execute("INSERT INTO clients(" + ",".join(cols) + ") VALUES(" +
                                    ",".join("?" * len(cols)) + ")", vals)
            return cur.lastrowid

    def delete_client(self, cid):
        n = self.conn.execute("SELECT COUNT(*) FROM invoices WHERE client_id=?", (cid,)).fetchone()[0]
        with self.conn:
            if n:   # historique conservé : on désactive seulement
                self.conn.execute("UPDATE clients SET active=0 WHERE id=?", (cid,))
            else:
                self.conn.execute("DELETE FROM clients WHERE id=?", (cid,))

    # ---- factures ---------------------------------------------------
    def save_invoice(self, data: dict, lines: list[dict], invoice_id=None) -> int:
        d = {k: data.get(k, "") for k in INVOICE_FIELDS}
        d["doc_type"] = d["doc_type"] or "invoice"
        d["credit_of_id"] = d["credit_of_id"] or None
        d["client_id"] = d["client_id"] or None
        if not d["client_id"]:
            raise ValueError("Choisissez un client.")
        if not d["date"]:
            d["date"] = date.today().isoformat()
        if not d["due_date"]:
            d["due_date"] = (date.fromisoformat(d["date"]) + timedelta(days=int(self.get("terms_days")))).isoformat()
        clean, total = [], Decimal("0")
        for i, ln in enumerate(lines):
            desc = (ln.get("description") or "").strip()
            qty = Decimal(str(ln.get("qty", 1) or 1))
            price = Decimal(str(ln.get("unit_price", 0) or 0))
            rate = Decimal(str(ln.get("rate", 1) or 1))
            if not desc and price == 0:
                continue
            amount = money(qty * price * rate)
            total += amount
            clean.append((int(ln.get("section", 1)), i, desc, float(qty), float(price),
                          (ln.get("currency") or "USD").upper(), float(rate), float(amount)))
        with self.conn:
            if invoice_id:
                st = self.conn.execute("SELECT status FROM invoices WHERE id=?", (invoice_id,)).fetchone()
                if not st or st["status"] != "draft":
                    raise ValueError("Une facture validée ne peut plus être modifiée. Créez un avoir.")
                self.conn.execute("UPDATE invoices SET " + ",".join(k + "=?" for k in INVOICE_FIELDS) +
                                  ",total=? WHERE id=?", [d[k] for k in INVOICE_FIELDS] + [float(total), invoice_id])
                self.conn.execute("DELETE FROM lines WHERE invoice_id=?", (invoice_id,))
            else:
                cur = self.conn.execute(
                    "INSERT INTO invoices(" + ",".join(INVOICE_FIELDS) + ",total,created_at) VALUES(" +
                    ",".join("?" * (len(INVOICE_FIELDS) + 2)) + ")",
                    [d[k] for k in INVOICE_FIELDS] + [float(total), datetime.now().isoformat(timespec="seconds")])
                invoice_id = cur.lastrowid
            self.conn.executemany(
                "INSERT INTO lines(invoice_id,section,pos,description,qty,unit_price,currency,rate,amount) "
                "VALUES(?,?,?,?,?,?,?,?,?)", [(invoice_id,) + c for c in clean])
        return invoice_id

    def get_invoice(self, iid) -> dict | None:
        r = self.conn.execute("SELECT * FROM invoices WHERE id=?", (iid,)).fetchone()
        if not r:
            return None
        inv = dict(r)
        inv["lines"] = [dict(x) for x in self.conn.execute(
            "SELECT * FROM lines WHERE invoice_id=? ORDER BY section,pos", (iid,))]
        inv["client"] = self.get_client(inv["client_id"]) or {}
        return inv

    def delete_draft(self, iid):
        with self.conn:
            st = self.conn.execute("SELECT status FROM invoices WHERE id=?", (iid,)).fetchone()
            if not st or st["status"] != "draft":
                raise ValueError("Seuls les brouillons peuvent être supprimés.")
            self.conn.execute("DELETE FROM invoices WHERE id=?", (iid,))

    def validate_invoice(self, iid) -> str:
        inv = self.get_invoice(iid)
        if not inv or inv["status"] != "draft":
            raise ValueError("Cette facture est déjà validée.")
        if not inv["lines"]:
            raise ValueError("Ajoutez au moins une ligne avant de valider.")
        yy = date.fromisoformat(inv["date"]).year % 100
        is_cn = inv["doc_type"] == "credit_note"
        cname = ("cn-%02d" if is_cn else "inv-%02d") % yy
        n = self.counter(cname)
        prefix = self.get("cn_prefix" if is_cn else "inv_prefix")
        number = f"{prefix}{n:05d}-{yy:02d}"
        while self.conn.execute("SELECT 1 FROM invoices WHERE number=?", (number,)).fetchone():
            n += 1
            number = f"{prefix}{n:05d}-{yy:02d}"
        file_no = inv["file_no"] or ("" if is_cn else f"{self.get('file_prefix')}{n:04d}")
        with self.conn:
            self.conn.execute("UPDATE invoices SET number=?, file_no=?, status='validated', validated_at=? WHERE id=?",
                              (number, file_no, datetime.now().isoformat(timespec="seconds"), iid))
        self.set_counter(cname, n + 1)
        return number

    def create_credit_note(self, iid) -> int:
        inv = self.get_invoice(iid)
        if not inv or inv["status"] != "validated" or inv["doc_type"] != "invoice":
            raise ValueError("Un avoir se crée à partir d'une facture validée.")
        data = {k: inv[k] for k in INVOICE_FIELDS}
        data.update(doc_type="credit_note", credit_of_id=iid, date=date.today().isoformat(), due_date="")
        return self.save_invoice(data, inv["lines"])

    def duplicate_invoice(self, iid) -> int:
        inv = self.get_invoice(iid)
        data = {k: inv[k] for k in INVOICE_FIELDS}
        data.update(doc_type="invoice", credit_of_id=None, date=date.today().isoformat(),
                    due_date="", file_no="")
        return self.save_invoice(data, inv["lines"])

    def list_invoices(self, search="", client_id=None):
        rows = self.conn.execute("""
          SELECT i.*, c.name AS client_name, c.division AS client_division,
            COALESCE((SELECT SUM(amount) FROM payments p WHERE p.invoice_id=i.id),0) AS paid,
            COALESCE((SELECT SUM(total) FROM invoices cn WHERE cn.credit_of_id=i.id AND cn.status='validated'),0) AS credited
          FROM invoices i LEFT JOIN clients c ON c.id=i.client_id
          ORDER BY i.date DESC, i.id DESC""").fetchall()
        out, s = [], search.strip().lower()
        for r in rows:
            d = dict(r)
            if client_id and d["client_id"] != client_id:
                continue
            hay = " ".join(str(d.get(k) or "") for k in
                           ("number", "file_no", "client_name", "client_division", "customs_decl",
                            "transport_no", "supp_invoice")).lower()
            if s and s not in hay:
                continue
            d["balance"] = float(money(d["total"]) - money(d["paid"]) - money(d["credited"])) \
                if d["doc_type"] == "invoice" else 0.0
            d["state"] = self.state_of(d)
            out.append(d)
        return out

    @staticmethod
    def state_of(d) -> str:
        if d["status"] == "draft":
            return "Brouillon"
        if d["doc_type"] == "credit_note":
            return "Avoir"
        if d["balance"] <= 0.005:
            return "Payée"
        if d["due_date"] and d["due_date"] < date.today().isoformat():
            return "En retard"
        return "Partielle" if d["paid"] > 0 else "Impayée"

    def unpaid(self):
        return [d for d in self.list_invoices()
                if d["status"] == "validated" and d["doc_type"] == "invoice" and d["balance"] > 0.005]

    # ---- paiements --------------------------------------------------
    def add_payment(self, iid, pdate, amount, method="", reference=""):
        row = next((d for d in self.list_invoices() if d["id"] == iid), None)
        if not row or row["status"] != "validated" or row["doc_type"] != "invoice":
            raise ValueError("Les paiements s'enregistrent sur une facture validée.")
        amount = money(amount)
        if amount <= 0:
            raise ValueError("Le montant doit être positif.")
        if amount > money(row["balance"]):
            raise ValueError(f"Le montant dépasse le solde restant ({row['balance']:,.2f}).")
        with self.conn:
            self.conn.execute("INSERT INTO payments(invoice_id,date,amount,method,reference) VALUES(?,?,?,?,?)",
                              (iid, pdate, float(amount), method, reference))

    def list_payments(self, iid):
        return [dict(r) for r in self.conn.execute("SELECT * FROM payments WHERE invoice_id=? ORDER BY date,id", (iid,))]

    # ---- lignes types -----------------------------------------------
    def list_templates(self):
        return [dict(r) for r in self.conn.execute("SELECT * FROM line_templates ORDER BY section, description")]

    def save_template(self, section, description, unit_price):
        with self.conn:
            self.conn.execute("INSERT INTO line_templates(section,description,unit_price) VALUES(?,?,?)",
                              (section, description.strip(), float(unit_price or 0)))

    def delete_template(self, tid):
        with self.conn:
            self.conn.execute("DELETE FROM line_templates WHERE id=?", (tid,))

    # ---- sauvegarde / restauration ----------------------------------
    def backup(self, dest):
        tmp = Path(tempfile.mkdtemp())
        try:
            copy = sqlite3.connect(tmp / "data.db")
            self.conn.backup(copy)
            copy.close()
            with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
                z.write(tmp / "data.db", "data.db")
                for f in (self.dir / "images").glob("*"):
                    z.write(f, "images/" + f.name)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def auto_backup(self, keep=15):
        dest = self.dir / "backups" / f"auto-{date.today().isoformat()}.zip"
        if not dest.exists():
            self.backup(dest)
        files = sorted((self.dir / "backups").glob("auto-*.zip"))
        for old in files[:-keep]:
            old.unlink()

    def restore(self, src):
        with zipfile.ZipFile(src) as z:
            if "data.db" not in z.namelist():
                raise ValueError("Ce fichier n'est pas une sauvegarde valide.")
            self.backup(self.dir / "backups" / f"avant-restauration-{datetime.now():%Y%m%d-%H%M%S}.zip")
            self.conn.close()
            (self.dir / "data.db").write_bytes(z.read("data.db"))
            for f in (self.dir / "images").glob("*"):
                f.unlink()
            for n in z.namelist():
                if n.startswith("images/") and Path(n).name:
                    (self.dir / "images" / Path(n).name).write_bytes(z.read(n))
        self._connect()
