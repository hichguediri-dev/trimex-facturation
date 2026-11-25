import os, sys, tempfile
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from PySide6.QtWidgets import QApplication
from app.db import DB
from app.ui import MainWindow, InvoiceDialog, PaymentDialog, ClientDialog
app = QApplication([])
db = DB(tempfile.mkdtemp())
w = MainWindow(db); w.show()
cid = db.save_client(dict(name="ACME", division="D1", cost_center="1"))
for i in range(4): w.go(i)
d = InvoiceDialog(db)
d.table.item(0, 1).setText("SEA FREIGHT"); d.table.item(0, 3).setText("14,030.00")
d.add_line(dict(section=3, description="Truck", qty=2, unit_price=100, currency="EUR", rate=1.1))
assert d.total.text() == "Total : 14,250.00 USD", d.total.text()
d.save(); assert d.iid, "pas sauvegardé"
inv = db.get_invoice(d.iid); assert inv["total"] == 14250 and len(inv["lines"]) == 2
p = w.pages[0]; p.refresh(); p.table.selectRow(0); p.update_buttons()
assert p.btn["validate"].isEnabled() and not p.btn["pay"].isEnabled()
db.validate_invoice(d.iid); p.refresh(); p.table.selectRow(0); p.update_buttons()
assert p.btn["pay"].isEnabled() and not p.btn["edit"].isEnabled()
pd = PaymentDialog(db, p.cur()); pd.amount.setText("1000"); pd.save()
p.refresh(); assert p.rows[0]["state"] in ("Partielle", "En retard"); w.go(2); w.go(3)
print("UI OK")
