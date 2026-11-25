# Trimex Facturation — v0.1

Logiciel de facturation local pour Windows (aucune connexion internet nécessaire pour l'utiliser).
Le dépôt ne contient **que le code**. Logo, cachet, signature, IBAN et toutes tes données restent sur ton PC.

## 1. Obtenir le fichier .exe (une fois, puis à chaque mise à jour)
1. Sur github.com : **New repository** → nom `trimex-facturation` → **Public** → ne coche rien → **Create repository**.
2. Clique sur le lien **uploading an existing file**.
3. Décompresse ce zip sur ton PC, ouvre le dossier, sélectionne **tout son contenu** et glisse-le dans la page GitHub.
   (Vérifie que le dossier `.github` est bien dans la liste des fichiers déposés.)
4. En bas : **Commit changes**.
5. Onglet **Actions** : la compilation démarre seule (si GitHub demande d'activer les workflows, accepte).
   Sinon : **Build Windows EXE** → **Run workflow**.
6. Attends 5 à 10 minutes (pastille verte ✔). Ouvre l'exécution, descends à **Artifacts**,
   télécharge **TrimexFacturation-windows**, décompresse : tu obtiens `TrimexFacturation.exe`.
7. Mets l'.exe où tu veux (ex. `C:\Trimex\`) et crée un raccourci sur le bureau (clic droit → Envoyer vers → Bureau).
   Au premier lancement, Windows peut afficher « Windows a protégé votre PC » : **Informations complémentaires → Exécuter quand même**
   (l'application n'est pas signée numériquement).

Si l'onglet Actions ne montre aucun workflow : **Add file → Create new file**, nom `.github/workflows/build.yml`,
et colle le contenu du fichier `build.yml` de ce dossier.

## 2. Premier démarrage (une seule fois)
1. **Paramètres** → importe les 4 images (fichier `mes_images_a_importer.zip`, à ne jamais mettre sur GitHub).
2. **Paramètres** → vérifie les préfixes (`EX/ALG/`, `DZ/FF/`) et mets le **prochain numéro** (ex. 279 si ta dernière facture est 00278).
3. **Clients** → crée tes clients (un client par division/centre de coût).
4. **Factures** → Nouvelle facture → Enregistrer le brouillon → **Valider** (numéro attribué, PDF créé).

## 3. Règles
- Une facture validée ne se modifie plus : on crée un **avoir** lié, puis une nouvelle facture.
- Les paiements partiels sont gérés ; l'onglet **Impayés** donne le solde par facture.
- Une ligne en devise (EUR…) : renseigne la devise et le taux → converti en USD, le taux est conservé et imprimé.
- Sauvegarde automatique chaque jour ; **Paramètres → Sauvegarder** pour une copie sur clé USB.

## Données
`%APPDATA%\TrimexFacturation\` : `data.db`, `images\`, `pdf\`, `backups\`. Une mise à jour de l'.exe ne les touche pas.
