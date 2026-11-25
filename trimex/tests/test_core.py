import os, sys, tempfile, shutil
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from app.db import DB
from app.pdf import build_pdf

tmp = tempfile.mkdtemp()
db = DB(tmp)
for k, f in (("header", "image1.PNG"), ("signature", "image2.png"), ("stamp", "image3.png"), ("footer", "image4.png")):
    src = os.path.join(os.environ.get("IMG", "/tmp/x/xl/media"), f)
    if os.path.exists(src):
        db.set_image(k, src)
cid = db.save_client(dict(name="BAKER HUGHES EHO FZE (4210)", division="Division DS", cost_center="120180761",
    address="BP 527 ROUTE D EL BORMA\n30500 HASSI MESSAOUD. ALGERIA", refs="GL 500200\nNIF: 308004000006746",
    contact="BH requestor name:Adib, George", contact_email="ofslogisticsap@bakerhughes.com"))
db.set_counter("inv-26", 278)
i1 = db.save_invoice(dict(client_id=cid, date="2026-11-22", customs_decl="1016 & 1018 /2026", shipment_value="155,750.81",
    parcels="1", weight="2,470.00", shipper="BAKER HUGHES EHO FZE", transport_label="BL", transport_no="SKK0109498",
    supp_invoice="4637223", contact="BH requestor name:Adib, George", contact_email="ofslogisticsap@bakerhughes.com", code_decl="P.EX"),
    [dict(section=1, description="SEA FREIGHT SKIDA PORT TO HAMAD PORT QATAR", qty=1, unit_price=14030),
     dict(section=1, description="THC (Terminal Handling Charges)", qty=1, unit_price=270)])
assert db.get_invoice(i1)["total"] == 14300
n = db.validate_invoice(i1); print(n, db.get_invoice(i1)["file_no"])
assert n == "EX/ALG/00278-26" and db.get_invoice(i1)["file_no"] == "DZ/FF/0278"
try:
    db.save_invoice({"client_id": cid}, [], i1); raise SystemExit("modif autorisée !")
except ValueError as e:
    print("OK verrou:", e)
i2 = db.save_invoice(dict(client_id=cid, date="2026-10-22", transport_label="AWB", transport_no="501-19667222"),
    [dict(section=1, description="AIR FREIGHT ALG (AHB) TO ATYRAU (GUW) 2,650.00 EURO", qty=1, unit_price=2650, currency="EUR", rate=1.12),
     dict(section=3, description="Local delivery", qty=2, unit_price=150.5)])
assert db.get_invoice(i2)["total"] == 2968 + 301
print(db.validate_invoice(i2))
db.add_payment(i1, "2026-11-30", 5000, "Bank transfer", "REF1")
r = {d["id"]: d for d in db.list_invoices()}
assert abs(r[i1]["balance"] - 9300) < 1e-6 and r[i1]["state"] in ("Partielle", "En retard"), r[i1]
try:
    db.add_payment(i1, "2026-12-01", 99999); raise SystemExit("surpaiement accepté")
except ValueError as e:
    print("OK surpaiement:", e)
cn = db.create_credit_note(i2); db.validate_invoice(cn)
r = {d["id"]: d for d in db.list_invoices()}
assert r[i2]["balance"] == 0 and r[i2]["state"] == "Payée"
print(db.get_invoice(cn)["number"], [d["number"] for d in db.unpaid()])
out = os.environ.get("OUT", "/tmp/out"); os.makedirs(out, exist_ok=True)
build_pdf(db, i1, out + "/inv278.pdf"); build_pdf(db, i2, out + "/inv2.pdf"); build_pdf(db, cn, out + "/cn.pdf")
db.backup(out + "/b.zip"); db.set("x", "1"); db.restore(out + "/b.zip"); assert db.get("x") == "" or db.get("x") != "1"
assert db.image_path("header") and len(db.list_invoices()) == 3
print("TOUT OK")
shutil.rmtree(tmp)
