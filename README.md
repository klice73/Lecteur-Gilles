# Lecteur Gilles — Android et Windows

Application franÃ§aise de lecture vocale locale avec la voix Piper **Gilles** via Sherpa-ONNX.

## Installer

TÃ©lÃ©chargez `Lecteur-Gilles-Android.apk` dans les [Releases](https://github.com/klice73/Lecteur-Gilles/releases).
Ouvrez-le sur un tÃ©lÃ©phone Android 8 ou ultÃ©rieur, puis autorisez l'installation depuis l'application qui ouvre le fichier si Android le demande.
Il s'agit d'une version de test signÃ©e avec une clÃ© de dÃ©veloppement. Les versions de test successives peuvent avoir des signatures diffÃ©rentes : dÃ©sinstallez l'ancienne si Android refuse une mise Ã  jour (le texte mÃ©morisÃ© sera perdu).

## Utiliser

- Collez un texte ou ouvrez un PDF textuel, DOCX, ODT, TXT ou HTML.
- Appuyez sur **â–¶ Lire**, **â…¡ Pause**, **â–¶ Continuer**, **â–  ArrÃªter**.
- Pour sauter la table des matières, placez le curseur puis choisissez **▶ Lire à partir du curseur**. Une sélection commence à son début et la lecture continue jusqu’à la fin. Le texte reste intact. Arrêtez la lecture en cours avant de changer de départ.
- La pause conserve la position du flux audio. Aucun remplacement par la voix Android.
- RÃ©glez la vitesse avant la lecture. Les longs textes sont traitÃ©s par passages.
- La lecture se met en pause en arriÃ¨re-plan ou en cas de perte du focus audio.

Gilles et le moteur sont intÃ©grÃ©s Ã  l'APK. L'application ne demande aucune permission Internet et n'envoie pas de documents Ã  un serveur. Le dernier texte (jusqu'Ã  100 000 caractÃ¨res) reste enregistrÃ© localement pour la rÃ©ouverture.

## Limites

- Les PDF scannÃ©s nÃ©cessitent un OCR, non inclus. L'ordre des colonnes/tableaux peut nÃ©cessiter une correction du texte.
- Import limitÃ© Ã  30 Mo par fichier. DOCX/ODT : texte principal, sans reproduction de la mise en page.
- La lecture reste au premier plan ; elle ne continue pas Ã©cran verrouillÃ©.
- Les tests automatisÃ©s ne remplacent pas un essai sur votre tÃ©lÃ©phone. La qualitÃ© vocale, les interruptions d'appel et la pause/reprise doivent aussi Ãªtre vÃ©rifiÃ©es sur appareil.
- La premiÃ¨re ouverture copie le modÃ¨le dans le stockage privÃ© de l'application. PrÃ©voir plusieurs centaines de Mo disponibles.

## Compiler

PrÃ©requis : JDK 17, Gradle 8.11.1, Android SDK 35, Python 3.12 ou ultÃ©rieur.

```sh
python prepare.py
gradle assembleDebug testDebugUnitTest lintDebug
```

Le script tÃ©lÃ©charge les composants officiels, vÃ©rifie leurs SHA-256 enregistrÃ©s dans `downloads.sha256.json`, puis place le modÃ¨le dans les assets. Les fichiers binaires ne sont pas stockÃ©s dans Git.
Le workflow GitHub Actions compile et publie automatiquement un APK de test aprÃ¨s un push sur `main`.

## Licences

Le code de cette application est sous GPL-3.0-or-later. Voir `LICENSE` et `THIRD_PARTY_NOTICES.md` pour le moteur, la voix et les autres composants. Aucun document utilisateur ni clÃ© privÃ©e ne doit Ãªtre ajoutÃ© au dÃ©pÃ´t.

## Windows

Sources et recette : [windows/INSTALLATION.md](windows/INSTALLATION.md). Les fichiers audio temporaires sont créés dans le dossier du lecteur et supprimés à sa fermeture normale.

## Préparation commerciale

Voir [legal/AUDIT.md](legal/AUDIT.md) pour les constats et les points ouverts. Les licences et archives ne constituent pas une certification de conformité.
