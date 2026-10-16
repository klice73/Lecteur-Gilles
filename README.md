# Lecteur Gilles pour Android

Application française de lecture vocale locale avec la voix Piper **Gilles** via Sherpa-ONNX.

## Installer

Téléchargez `Lecteur-Gilles-Android.apk` dans les [Releases](https://github.com/klice73/Lecteur-Gilles/releases).
Ouvrez-le sur un téléphone Android 8 ou ultérieur, puis autorisez l'installation depuis l'application qui ouvre le fichier si Android le demande.
Il s'agit d'une version de test signée avec une clé de développement. Les versions de test successives peuvent avoir des signatures différentes : désinstallez l'ancienne si Android refuse une mise à jour (le texte mémorisé sera perdu).

## Utiliser

- Collez un texte ou ouvrez un PDF textuel, DOCX, ODT, TXT ou HTML.
- Appuyez sur **▶ Lire**, **Ⅱ Pause**, **▶ Continuer**, **■ Arrêter**.
- La pause conserve la position du flux audio. Aucun remplacement par la voix Android.
- Réglez la vitesse avant la lecture. Les longs textes sont traités par passages.
- La lecture se met en pause en arrière-plan ou en cas de perte du focus audio.

Gilles et le moteur sont intégrés à l'APK. L'application ne demande aucune permission Internet et n'envoie pas de documents à un serveur. Le dernier texte (jusqu'à 100 000 caractères) reste enregistré localement pour la réouverture.

## Limites

- Les PDF scannés nécessitent un OCR, non inclus. L'ordre des colonnes/tableaux peut nécessiter une correction du texte.
- Import limité à 30 Mo par fichier. DOCX/ODT : texte principal, sans reproduction de la mise en page.
- La lecture reste au premier plan ; elle ne continue pas écran verrouillé.
- Les tests automatisés ne remplacent pas un essai sur votre téléphone. La qualité vocale, les interruptions d'appel et la pause/reprise doivent aussi être vérifiées sur appareil.
- La première ouverture copie le modèle dans le stockage privé de l'application. Prévoir plusieurs centaines de Mo disponibles.

## Compiler

Prérequis : JDK 17, Gradle 8.11.1, Android SDK 35, Python 3.12 ou ultérieur.

```sh
python prepare.py
gradle assembleDebug testDebugUnitTest lintDebug
```

Le script télécharge les composants officiels, vérifie leurs SHA-256 enregistrés dans `downloads.sha256.json`, puis place le modèle dans les assets. Les fichiers binaires ne sont pas stockés dans Git.
Le workflow GitHub Actions compile et publie automatiquement un APK de test après un push sur `main`.

## Licences

Le code de cette application est sous GPL-3.0-or-later. Voir `LICENSE` et `THIRD_PARTY_NOTICES.md` pour le moteur, la voix et les autres composants. Aucun document utilisateur ni clé privée ne doit être ajouté au dépôt.
