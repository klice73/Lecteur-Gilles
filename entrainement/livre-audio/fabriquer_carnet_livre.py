"""Fabrique « Hubert-Livre-Audio-Kaggle.ipynb » : livre audio avec la voix Hubert sur la carte graphique de Kaggle."""
import json, sys, os
ICI = os.path.dirname(os.path.abspath(__file__))
REV = '5916bf7'   # revision de qwentts.cpp utilisee par le lecteur Windows (qwen-tts.exe du 2 nov. 2026)
C = []
def md(t): C.append({"cell_type": "markdown", "metadata": {}, "source": t.strip("\n").splitlines(True)})
def code(t): C.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": t.strip("\n").splitlines(True)})
md("""
# Livre audio avec la voix d'Hubert (carte graphique Kaggle)

Fabrique **un fichier MP3 par chapitre**, à copier sur le téléphone. Tout se fait avec **Save Version** : vous pouvez
fermer l'onglet. Une séance s'arrête d'elle-même après environ 10 heures ; la suivante reprend où elle s'était arrêtée.

**Entrées à ajouter (panneau de droite, Add Input → Your Work → Datasets) :**
1. votre jeu de données **privé** « hubert-voix » : le contenu du dossier `hubert-local` (au minimum `codec-Q8.gguf`,
   `Hubert-candidat-Q8.gguf` ou `Hubert-adapte-Q8.gguf`, `reference.spk`, `reference.rvq`, `reference.txt`, `config.json`) ;
2. votre jeu de données **privé** « livre » : le livre (`.docx`, `.epub`, `.pdf` ou `.txt`) et, si vous voulez,
   votre `prononciations.txt`.

**Réglages (une fois) :** Accelerator **GPU T4 x2**, Internet **On**.

**Séance suivante :** ajoutez aussi en entrée la **dernière version de ce carnet** (Your Work → Notebooks) : les chapitres
déjà faits sont repris tels quels.

**Résultat :** onglet **Output** : dossier `livre-audio` (un MP3 par chapitre) et `livre-audio.zip` à télécharger.
""")
md("## 1. Carte graphique")
code("""
import subprocess, torch
print(subprocess.run(['nvidia-smi','-L'],capture_output=True,text=True).stdout)
assert torch.cuda.is_available() and torch.cuda.get_device_capability()>=(7,0), "Choisir Accelerator = GPU T4 x2"
""")
md("## 2. Moteur de la voix (environ 10 minutes)")
code(f"""
%%bash
set -e
apt-get -qq update && apt-get -qq install -y ffmpeg cmake > /dev/null
mkdir -p /kaggle/tmp && cd /kaggle/tmp
[ -d qwentts ] || git clone -q --recurse-submodules https://github.com/ServeurpersoCom/qwentts.cpp qwentts
cd qwentts && git checkout -q {REV} && git submodule update -q --init --recursive
mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=75 > /tmp/cmake.log 2>&1 || (tail -30 /tmp/cmake.log; exit 1)
cmake --build . -j 4 > /tmp/build.log 2>&1 || (tail -40 /tmp/build.log; exit 1)
ls -la qwen-tts
curl -sL -o /kaggle/tmp/documents.py https://raw.githubusercontent.com/klice73/Lecteur-Gilles/main/windows/documents.py
""")
md("## 3. Moteur du livre audio")
code("%%writefile /kaggle/tmp/moteur_livre.py\n" + open(os.path.join(ICI, 'moteur_livre.py'), encoding='utf-8').read())
md("""
## 4. Fabriquer le livre

* `HEURES` : temps de calcul de la séance (10 h laisse le temps de finir avant la limite de 12 h de Kaggle).
* `MODELE` : laisser vide pour la voix indiquée dans `config.json` ; sinon `Hubert-candidat-Q8.gguf` ou `Hubert-adapte-Q8.gguf`.
""")
code("""
import glob, os, subprocess, sys, shutil
HEURES = 10
MODELE = ''
cfgs = [p for p in glob.glob('/kaggle/input/**/reference.spk', recursive=True)]
assert cfgs, "Voix introuvable : ajoutez en entrée votre jeu de données privé avec le contenu de hubert-local"
VOIX = os.path.dirname(cfgs[0])
livres = [p for p in glob.glob('/kaggle/input/**/*', recursive=True)
          if p.lower().endswith(('.docx','.epub','.pdf','.txt','.odt','.md')) and not os.path.basename(p).lower() in ('reference.txt','prononciations.txt')
          and VOIX not in p and '/livre-audio/' not in p]
assert livres, "Livre introuvable : ajoutez en entrée votre jeu de données avec le livre"
assert len(livres) == 1, "Plusieurs livres trouvés, n'en garder qu'un : %s" % livres
lex = (glob.glob('/kaggle/input/**/prononciations.txt', recursive=True) or [''])[0]
print('Voix :', VOIX); print('Livre :', livres[0]); print('Lexique :', lex or 'aucun')
cmd = [sys.executable, '/kaggle/tmp/moteur_livre.py', '--qwen', '/kaggle/tmp/qwentts/build/qwen-tts', '--dossier-voix', VOIX,
       '--livre', livres[0], '--sortie', '/kaggle/working/livre-audio', '--documents', '/kaggle/tmp/documents.py',
       '--reprise', '/kaggle/input', '--heures', str(HEURES), '--device', 'CUDA0']
if lex: cmd += ['--lexique', lex]
if MODELE: cmd += ['--modele', MODELE]
p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
for ligne in p.stdout: print(ligne.rstrip(), flush=True)
print('code', p.wait())
""")
md("## 5. Archive à télécharger")
code("""
import shutil, os
if os.path.isdir('/kaggle/working/livre-audio'):
    shutil.make_archive('/kaggle/working/livre-audio', 'zip', '/kaggle/working/livre-audio')
    print(sorted(os.listdir('/kaggle/working/livre-audio')))
""")
nb = {"cells": C, "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"}, "language_info": {"name": "python"}},
      "nbformat": 4, "nbformat_minor": 5}
json.dump(nb, open(sys.argv[1], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('ecrit', sys.argv[1])
