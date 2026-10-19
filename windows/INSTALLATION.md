# Construire et installer sous Windows 10/11 x64

Prévoir Python 3.14 x64 et .NET Framework 4.x. Le lecteur actuel a été testé avec Python 3.14.4. Placez ce dossier et ses fichiers dans un emplacement autorisé en écriture, par exemple D:\Lecteur-Gilles\lecteur. Conservez les textes de licence et fichiers de contrôle.

Dans PowerShell, depuis ce dossier, remplacez le chemin Python par celui de votre installation privée :

```powershell
$pythonBase = 'D:\Lecteur-Gilles\python-private\python.exe'
New-Item -ItemType Directory -Force temp | Out-Null
$env:TEMP = Join-Path $PWD 'temp'
$env:TMP = $env:TEMP
& $pythonBase -m venv runtime
& .\runtime\Scripts\python.exe -m pip install --no-cache-dir -r requirements.txt
& .\runtime\Scripts\python.exe prepare_voices.py
.\build.ps1
.\Ouvrir-Piper.bat
```

Le dossier `licences` est préparé par `python legal/prepare_notices.py` depuis la racine du dépôt, avant copie de `windows`. Aucun document personnel n’est nécessaire.

Le venv référence le Python de base : **ne déplacez pas simplement un environnement existant**. Recréez-le avec le Python du nouvel emplacement. Dans l’installation locale migrée, le Python de base et les dépendances sont sur D. Les lanceurs de console tiers hérités ne sont pas utilisés : utilisez toujours `runtime\Scripts\python.exe -m ...`.

Cliquez dans le texte puis sur « Lire à partir du curseur » pour commencer à cet endroit. Une sélection commence à son début, puis la lecture continue jusqu’à la fin. « Lire tout » recommence depuis le début ; « Continuer » reprend une lecture en pause. Le texte affiché n’est pas tronqué.

Validation exécutée sur la version locale : compilation C#, lecture réelle depuis curseur/sélection, exclusion du préambule dans la requête, document intact, pause/reprise, fin de texte et lecture complète ; import et lecture progressive du PDF synthétique de 300 pages. La réinstallation intégrale depuis Internet et la reconstruction de toutes les bibliothèques natives restent à vérifier séparément (voir legal/AUDIT.md).

Le surlignage jaune suit le passage audio joué ; il reste fixe en pause, avance au passage suivant et disparaît à l’arrêt ou en fin de lecture. Le texte est conservé.

## Version 1.4 : voix Gilles plafonnée

Télécharger `fr_FR-gilles-low.onnx` dans la version publiée sur GitHub (Releases) et remplacer `voix\fr_FR-gilles-low.onnx`. Ce fichier corrige le bredouillement. Il diffère du fichier de Hugging Face : ne pas relancer `prepare_voices.py` ensuite (la somme de contrôle ne correspondrait plus). Pour plafonner un modèle soi-même : `python plafonner_voix.py entree.onnx sortie.onnx` (paquet `onnx` requis).

## Version 1.5 : surlignage mot à mot et mémoire de lecture

Le paquet `Lecteur-Gilles-Windows-1.5.zip` publié sur GitHub contient `Piper-Gilles.exe`, `lecteur.py` et la voix Gilles avec alignement. Mode d'emploi : `MISE-A-JOUR-1.5.txt`. Le texte et la position sont gardés dans le sous-dossier `session`. Test sans carte son : `Piper-Gilles.exe --test-minutage [part-000001.json]` (écrit `verification-minutage.txt` ; met de côté puis restaure le dossier `session`).
