Contribuer à LabelImg
=====================

Ce guide décrit un workflow de développement local simple et reproductible, les prérequis, comment lancer l’application, exécuter les tests, et soumettre une contribution.

Prérequis
---------
- Python 3.8+
- Qt/PyQt5
- lxml

Installation rapide (Windows/macOS/Linux)
-----------------------------------------
1. Cloner le dépôt et se placer à la racine du projet::

    git clone <URL_DU_DEPOT>
    cd labelImg

2. Créer un environnement virtuel et installer les dépendances::

    python -m venv .venv
    .venv\Scripts\activate  # Windows
    # source .venv/bin/activate  # macOS/Linux
    pip install -U pip
    pip install -r requirements/requirements-linux-python3.txt || true
    pip install pyqt5 lxml

3. Générer les ressources Qt (icônes et chaînes)::

    pyrcc5 -o libs/resources.py resources.qrc

Lancer l’application en dev
---------------------------
- Lancer l’app directement::

    python labelImg.py [IMAGE_PATH] [PRE-DEFINED CLASS FILE]

Organisation du code
--------------------
- ``labelImg.py``: point d’entrée, fenêtre principale Qt.
- ``libs/``: widgets, canvas, I/O (VOC/YOLO/CreateML), utilitaires, settings, i18n.
- ``tests/``: tests unitaires (IO, Qt smoke test, settings, utils, string bundle).

Exécuter la suite de tests
--------------------------
Depuis la racine du projet::

    python -m unittest discover -v

Ajout de tests
--------------
- Placer les nouveaux tests dans ``tests/`` avec un nom ``test_*.py``.
- Utiliser des fichiers d’exemple déjà présents dans ``tests/`` lorsque possible (ex: ``test.512.512.bmp``).

Style de code
-------------
- Python 3, typage progressif (annotations PEP484 bienvenues).
- Préférer des noms explicites et du code lisible.
- Éviter les try/except trop larges; lever des erreurs explicites côté I/O.

Workflow Git recommandé
-----------------------
1. Créer une branche thématique courte: ``feat/...``, ``fix/...``, ``chore/...``.
2. Commits atomiques et messages clairs.
3. Lancer la suite de tests et vérifier le lancement local avant PR.
4. Ouvrir une PR en décrivant le contexte, les changements et l’impact.

Build/Packaging (optionnel)
---------------------------
- PyPI: voir ``build-tools/build-for-pypi.sh``.
- Binaire Windows/macOS/Linux: scripts dans ``build-tools/``. Pour macOS, py2app est supporté via ``setup.py``.

Générer et lancer le .exe (Windows)
-----------------------------------
1. Activer le venv et installer les dépendances::

    python -m venv .venv
    .venv\Scripts\activate
    python -m pip install --upgrade pip setuptools wheel
    python -m pip install -r requirements/requirements-windows.txt
    python -m pip install pyinstaller

2. Générer les ressources Qt (si non générées)::

    if (Test-Path .\.venv\Scripts\pyrcc5.exe) { .\.venv\Scripts\pyrcc5.exe -o libs/resources.py resources.qrc } 
    else { python -m PyQt5.pyrcc_main -o libs/resources.py resources.qrc }

3. Construire l'exécutable avec PyInstaller (une seule archive)::

    pyinstaller --hidden-import=PyQt5 --hidden-import=lxml -F -n "AKOUMA-Annotator" -c labelImg.py -p ./libs -p ./

4. Lancer l'application générée::

    .\dist\AKOUMA-Annotator.exe [CHEMIN_IMAGES] [FICHIER_CLASSES]

Notes:
- Si ``pyinstaller`` n'est pas trouvé, relancez après activation du venv.
- En cas d'absence de ``pyrcc5``, utilisez la commande de secours avec ``python -m PyQt5.pyrcc_main`` ci-dessus.

Ressources utiles
-----------------
- Icônes et chaînes sont packagées via ``resources.qrc`` et chargées par ``libs/resources.py``.
- Formats supportés: Pascal VOC (XML), YOLO (TXT + classes.txt), CreateML (JSON).

Contact & Crédit
----------------
- Projet d’origine: TzuTa Lin et contributeurs. Voir ``LICENSE``.
