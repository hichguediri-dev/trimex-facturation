import sys
from PySide6.QtWidgets import QApplication, QMessageBox
from app.db import DB
from app.ui import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    try:
        db = DB()
        db.auto_backup()
    except Exception as e:  # noqa: BLE001
        QMessageBox.critical(None, "Erreur", f"Impossible d'ouvrir la base de données :\n{e}")
        return 1
    w = MainWindow(db)
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
