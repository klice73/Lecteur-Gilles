"""Fabrique « Hubert-Livre-Audio-Kaggle.ipynb » : livre audio avec la voix Hubert sur la carte graphique de Kaggle."""
import json, sys, os
ICI = os.path.dirname(os.path.abspath(__file__))
SRC = 'a67f5f3767b72d867f95e9920a6f1b30957fe906'  # documents.py et ebooks.py figes (main, version 1.12)
REV = '5916bf7'   # revision de qwentts.cpp utilisee par le lecteur Windows (qwen-tts.exe du 2 nov. 2026)
C = []
def md(t): C.append({"cell_type": "markdown", "metadata": {}, "source": t.strip("\n").splitlines(True)})
def code(t): C.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": t.strip("\n").splitlines(True)})
md("""
# Livre audio avec la voix d'Hubert (carte graphique Kaggle)

Fabrique **un fichier MP3 par chapitre**, à copier sur le téléphone. Tout se fait avec **Save Version** : vous pouvez
fermer l'onglet. Une séance s'arrête d'elle-même après environ 11 heures ; la suivante reprend où elle s'était arrêtée.

**Entrées à ajouter (panneau de droite, Add Input → Your Work → Datasets) :**
1. votre jeu de données **privé** « hubert-voix » : `codec-Q8.gguf`, **une seule** voix Hubert (la plus récente),
   `reference.spk`, `reference.rvq`, `reference.txt`, `config.json` (tous tirés du dossier `hubert-local`) ;
2. votre jeu de données **privé** « livre » : le livre (`.docx`, `.epub`, `.pdf` ou `.txt`) et, si vous voulez,
   votre `prononciations.txt`.

**Réglages (une fois) :** Accelerator **GPU T4 x2**, Internet **On**.

**Séance suivante :** ajoutez aussi en entrée la **dernière version de ce carnet** (Your Work → Notebooks) : les chapitres
déjà faits sont repris tels quels.

**Résultat :** onglet **Output** : dossier `livre-audio` (un MP3 par chapitre) et `livre-audio-mp3.zip` (seulement les MP3) à télécharger.
""")
md("## 1. Carte graphique")
code("""
import subprocess, torch, time
open('/tmp/debut_seance.txt', 'w').write(str(time.time()))
print(subprocess.run(['nvidia-smi','-L'],capture_output=True,text=True).stdout)
assert torch.cuda.is_available() and torch.cuda.get_device_capability()>=(7,0), "Choisir Accelerator = GPU T4 x2"
""")
md("## 2. Moteur de la voix (environ 10 minutes)")
code(f"""
%%bash
set -e
apt-get -qq update || true
apt-get -qq install -y ffmpeg cmake > /dev/null
pip install -q pypdf
export PATH=/usr/local/cuda/bin:$PATH
mkdir -p /kaggle/tmp && cd /kaggle/tmp
[ -d qwentts ] || git clone -q --recurse-submodules https://github.com/ServeurpersoCom/qwentts.cpp qwentts
cd qwentts && git checkout -q {REV} && git submodule update -q --init --recursive
mkdir -p build && cd build
LF=""
if ! ldconfig -p | grep -q 'libcuda.so.1'; then
  S=/usr/local/cuda/lib64/stubs; ln -sf $S/libcuda.so $S/libcuda.so.1; export LIBRARY_PATH=$S:$LIBRARY_PATH
  LF="-DCMAKE_EXE_LINKER_FLAGS=-Wl,-rpath-link,$S -DCMAKE_SHARED_LINKER_FLAGS=-L$S"
fi
cmake .. -DCMAKE_BUILD_TYPE=Release -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=75 $LF > /tmp/cmake.log 2>&1 || (tail -30 /tmp/cmake.log; exit 1)
cmake --build . -j 4 > /tmp/build.log 2>&1 || (tail -40 /tmp/build.log; exit 1)
ls -la qwen-tts
for f in documents.py ebooks.py; do curl -fsSL -o /kaggle/tmp/$f https://raw.githubusercontent.com/klice73/Lecteur-Gilles/{SRC}/windows/$f; done
cd /kaggle/tmp && python -c "import documents, ebooks; print('lecture des livres : OK')"
""")
md("## 3. Moteur du livre audio")
code("%%writefile /kaggle/tmp/moteur_livre.py\n" + open(os.path.join(ICI, 'moteur_livre.py'), encoding='utf-8').read())
md("""
## 4. Fabriquer le livre
""")
code("""
import glob, os, subprocess, sys, time, threading, torch
HEURES = 11          # temps total de la seance, compilation comprise (Kaggle coupe a 12 h)
MODELE = ''
debut = float(open('/tmp/debut_seance.txt').read())
tous = sorted({os.path.realpath(p) for p in glob.glob('/kaggle/input/**/*', recursive=True) if os.path.isfile(p)})
sorties_prec = {os.path.dirname(p) for p in tous if os.path.basename(p) == 'etat.json' or os.path.basename(p).startswith('journal-moteur')}
def dans_sortie(p): return any(p.startswith(d + os.sep) or os.path.dirname(p) == d for d in sorties_prec)
voix = [p for p in tous if p.endswith('reference.spk')]
assert voix, "Voix introuvable : ajoutez en entree votre jeu de donnees prive hubert-voix"
VOIX = os.path.dirname(voix[0])
livres = [p for p in tous if p.lower().endswith(('.docx','.epub','.pdf','.txt','.odt','.md','.fb2'))
          and os.path.basename(p).lower() not in ('reference.txt','prononciations.txt')
          and not p.startswith(VOIX + os.sep) and not dans_sortie(p)]
assert livres, "Livre introuvable : ajoutez en entree votre jeu de donnees avec le livre"
assert len(livres) == 1, "Plusieurs livres trouves, n'en garder qu'un : %s" % livres
lexs = [p for p in tous if os.path.basename(p) == 'prononciations.txt']
lexs.sort(key=lambda p: os.path.dirname(p) != os.path.dirname(livres[0]))
lex = lexs[0] if lexs else ''
ngpu = max(1, torch.cuda.device_count())
reste = HEURES - (time.time() - debut) / 3600
print('Voix :', VOIX); print('Livre :', livres[0]); print('Lexique :', lex or 'aucun')
print('Cartes graphiques : %d ; temps de calcul restant : %.1f h' % (ngpu, reste))
procs = []
for k in range(ngpu):
    cmd = [sys.executable, '/kaggle/tmp/moteur_livre.py', '--qwen', '/kaggle/tmp/qwentts/build/qwen-tts', '--dossier-voix', VOIX,
           '--livre', livres[0], '--sortie', '/kaggle/working/livre-audio', '--documents', '/kaggle/tmp/documents.py',
           '--reprise', '/kaggle/input', '--heures', '%.2f' % reste, '--device', 'CUDA%d' % k, '--tranche', '%d/%d' % (k, ngpu)]
    if lex: cmd += ['--lexique', lex]
    if MODELE: cmd += ['--modele', MODELE]
    procs.append(subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True))
    time.sleep(2)
def suivre(k, p):
    for ligne in p.stdout: print('[carte %d] %s' % (k, ligne.rstrip()), flush=True)
fils = [threading.Thread(target=suivre, args=(k, p)) for k, p in enumerate(procs)]
for f in fils: f.start()
for f in fils: f.join()
codes = [p.wait() for p in procs]
print('TERMINE' if not any(codes) else '!!! AU MOINS UN CHAPITRE A ECHOUE : voir les lignes ECHEC ci-dessus', codes)
""")
md("## 5. Archive à télécharger")
code("""
import shutil, os
if os.path.isdir('/kaggle/working/livre-audio'):
    mp3s = sorted(f for f in os.listdir('/kaggle/working/livre-audio') if f.endswith('.mp3'))
    import zipfile
    with zipfile.ZipFile('/kaggle/working/livre-audio-mp3.zip', 'w') as z:
        for f in mp3s: z.write('/kaggle/working/livre-audio/' + f, f)
    print(len(mp3s), 'chapitres en MP3 :'); print('\\n'.join(mp3s))
""")
nb = {"cells": C, "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"}, "language_info": {"name": "python"}},
      "nbformat": 4, "nbformat_minor": 5}
json.dump(nb, open(sys.argv[1], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('ecrit', sys.argv[1])
