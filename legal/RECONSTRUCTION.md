# Sources et reconstruction

`source-manifest.json` fixe les URL et SHA-256 des archives. `download-report.json` distingue les hachages comparés aux publications upstream des empreintes enregistrées lors du téléchargement. `python legal/package_sources.py` récupère les archives et produit un paquet de préparation des sources. Il faut une connexion réseau.

Application Android : JDK 17, Gradle 8.11.1, SDK 35 ; `python prepare.py`, `python legal/prepare_notices.py`, puis `gradle assembleDebug testDebugUnitTest lintDebug`. Le workflow joint ajoute les tests sur émulateur Android API 29. Les sources Windows et leur recette sont dans windows/.

Piper Windows : archive piper-tts-1.8.0 / windows-piper-tts-1.8.0, pyproject.toml et CMakeLists.txt inclus. La construction du module Python requiert un compilateur C/C++, CMake et les outils indiqués par son pyproject. CMake épingle eSpeak 724808c (archive complète fournie). Conserver les options CMake d’origine ; le moteur lie statiquement eSpeak. ONNX Runtime provient du wheel Windows identifié, dont les sources sont fournies séparément.

Sherpa Android : source sherpa-onnx-1.13.8, scripts android/ et workflow upstream conservé dans evidence/Sherpa-android-workflow.txt. Les configurations CMake et archives des dépendances principales, dont eSpeak et piper-phonemize, sont jointes. Le workflow upstream fournit les options NDK/ABI et les étapes de création des bibliothèques et AAR ; ne pas remplacer ces révisions par les dernières versions.

**Limite** : ces recettes upstream et archives ont été rassemblées, mais toutes les bibliothèques natives n’ont pas été reconstruites dans cet audit. Les archives de certains projets référencent encore des sous-modules et dépendances transitives. Le paquet est une préparation de sources, pas une certification de sources correspondantes exhaustives. Avant une distribution commerciale, vérifier une reconstruction propre et compléter le paquet avec toute dépendance requise et les informations d’installation nécessaires au sens de la licence.
