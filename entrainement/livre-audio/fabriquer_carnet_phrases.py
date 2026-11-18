"""Fabrique « Hubert-Phrases-Kaggle.ipynb » : la voix Hubert lit des milliers de phrases (etape 1 du « Hubert leger »).
Reutilise la cellule de compilation du carnet du livre audio (a fabriquer d'abord)."""
import json, sys, os
ICI = os.path.dirname(os.path.abspath(__file__))
livre = json.load(open(os.path.join(ICI, 'Hubert-Livre-Audio-Kaggle.ipynb'), encoding='utf-8'))
compil = next(c for c in livre['cells'] if c['cell_type'] == 'code' and 'qwentts' in ''.join(c['source']) and '%%bash' in ''.join(c['source']))
gpu = next(c for c in livre['cells'] if c['cell_type'] == 'code' and 'nvidia-smi' in ''.join(c['source']))
C = []
def md(t): C.append({"cell_type": "markdown", "metadata": {}, "source": t.strip("\n").splitlines(True)})
def code(t): C.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": t.strip("\n").splitlines(True)})
md("""
# Hubert léger, étape 1 : Hubert lit des phrases d'entraînement

La voix Hubert (votre clone) lit environ **4 000 phrases**. Ces enregistrements serviront à l'étape 2 pour entraîner
une voix **légère** qui lit en direct sur le PC et le téléphone, comme Gilles.

**Entrées à ajouter (panneau de droite, Add Input) :**
1. votre jeu de données **privé** « hubert-voix » (Your Work → Datasets) ;
2. le jeu public **« french single speaker speech dataset »** (de bryanpark) : seulement pour la **liste des phrases**
   (`transcript.txt`), les voix de ce jeu ne sont pas utilisées ici.

**Réglages (une fois) :** Accelerator **GPU T4 x2**, Internet **On**, puis **Save Version** (Save & Run All).

**Séance suivante (si tout n'est pas fini) :** ajoutez aussi en entrée la **dernière version de ce carnet**
(Your Work → Notebooks) : les phrases déjà lues sont reprises.

**Résultat :** onglet **Output** : dossier `hubert-phrases` (les enregistrements) et `ecoute-1.wav` à `ecoute-5.wav`
pour écouter quelques phrases.
""")
md("## 1. Carte graphique")
C.append(gpu)
md("## 2. Moteur de la voix (environ 10 minutes)")
C.append(compil)
md("## 3. Programmes")
code("%%writefile /kaggle/tmp/moteur_livre.py\n" + open(os.path.join(ICI, 'moteur_livre.py'), encoding='utf-8').read())
code("%%writefile /kaggle/tmp/moteur_phrases.py\n" + open(os.path.join(ICI, 'moteur_phrases.py'), encoding='utf-8').read())
md("""
## 4. Lire les phrases

* `NOMBRE` : nombre de phrases (4 000 donnent environ 5 à 6 heures d'enregistrement).
* `HEURES` : durée totale de la séance, compilation comprise (11 h, sous la limite de 12 h de Kaggle).
""")
code("""
import glob, os, subprocess, sys, time, threading, torch
NOMBRE = 4000
HEURES = 11
MODELE = ''
debut = float(open('/tmp/debut_seance.txt').read())
tous = sorted({os.path.realpath(p) for p in glob.glob('/kaggle/input/**/*', recursive=True) if os.path.isfile(p)})
voix = [p for p in tous if p.endswith('reference.spk')]
assert voix, "Voix introuvable : ajoutez en entree votre jeu de donnees prive hubert-voix"
VOIX = os.path.dirname(voix[0])
trans = [p for p in tous if os.path.basename(p) == 'transcript.txt']
assert trans, "Liste des phrases introuvable : Add Input, chercher « french single speaker speech dataset » (bryanpark)"
SORTIE = '/kaggle/working/hubert-phrases'
base = [sys.executable, '/kaggle/tmp/moteur_phrases.py', '--qwen', '/kaggle/tmp/qwentts/build/qwen-tts', '--dossier-voix', VOIX,
        '--transcript', trans[0], '--sortie', SORTIE, '--nombre', str(NOMBRE)] + (['--modele', MODELE] if MODELE else [])
subprocess.run(base + ['--reprise', '/kaggle/input', '--reprise-seule'], check=True)
ngpu = max(1, torch.cuda.device_count())
reste = HEURES - (time.time() - debut) / 3600
print('Voix :', VOIX); print('Phrases :', trans[0]); print('Cartes graphiques : %d ; temps restant : %.1f h' % (ngpu, reste))
procs = [subprocess.Popen(base + ['--heures', '%.2f' % reste, '--device', 'CUDA%d' % k, '--tranche', '%d/%d' % (k, ngpu)],
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) for k in range(ngpu)]
def suivre(k, p):
    for ligne in p.stdout: print('[carte %d] %s' % (k, ligne.rstrip()), flush=True)
fils = [threading.Thread(target=suivre, args=(k, p)) for k, p in enumerate(procs)]
for f in fils: f.start()
for f in fils: f.join()
print('codes', [p.wait() for p in procs])
""")
md("## 5. Bilan et quelques phrases à écouter")
code("""
import glob, os, shutil, subprocess
S = '/kaggle/working/hubert-phrases'
gardees = {}
for f in glob.glob(S + '/*metadata-*.csv'):
    for l in open(f, encoding='utf-8'):
        if '|' in l and os.path.isfile(os.path.join(S, l.split('|', 1)[0])): gardees[l.split('|', 1)[0]] = l.split('|', 1)[1].strip()
rejets = sum(1 for f in glob.glob(S + '/*rejets-*.txt') for l in open(f, encoding='utf-8') if l.strip())
duree = sum(os.path.getsize(os.path.join(S, n)) - 44 for n in gardees) / 2 / 22050 / 3600
print('%d phrases gardées (%.1f h d enregistrement), %d rejetées' % (len(gardees), duree, rejets))
for k, n in enumerate(sorted(gardees)[:5], 1):
    shutil.copy(os.path.join(S, n), '/kaggle/working/ecoute-%d.wav' % k); print('ecoute-%d.wav :' % k, gardees[n])
""")
nb = {"cells": C, "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"}, "language_info": {"name": "python"}},
      "nbformat": 4, "nbformat_minor": 5}
json.dump(nb, open(sys.argv[1], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('ecrit', sys.argv[1])
