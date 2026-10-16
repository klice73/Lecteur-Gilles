# Composants tiers

- **Sherpa-ONNX 1.13.8** : Apache-2.0, Copyright k2-fsa et contributeurs. Source : https://github.com/k2-fsa/sherpa-onnx/tree/v1.13.8 ; licence : https://github.com/k2-fsa/sherpa-onnx/blob/v1.13.8/LICENSE
- **ONNX Runtime** inclus dans la bibliothèque Android : MIT. Source et licence : https://github.com/microsoft/onnxruntime
- **eSpeak NG** utilisé par le moteur pour la phonétisation : GPL-3.0-or-later. Sources : https://github.com/espeak-ng/espeak-ng ; les données linguistiques sont incluses dans le modèle distribué par Sherpa-ONNX.
- **Gilles / Piper, fr_FR-gilles-low** : la fiche MODEL_CARD indique CC0 pour le jeu de données, un locuteur français, audio 16 kHz. La fiche complète et la configuration accompagnent les assets : https://huggingface.co/rhasspy/piper-voices/tree/main/fr/fr_FR/gilles/low . Distribution adaptée : https://github.com/k2-fsa/sherpa-onnx/releases/tag/tts-models
- **PDFBox-Android 2.0.27.0** et Apache PDFBox : Apache-2.0. Sources et notices : https://github.com/TomRoush/PdfBox-Android
- **Kotlin** : Apache-2.0. https://github.com/JetBrains/kotlin

Les fichiers de licences des dépendances sont conservés dans leurs distributions. Ce dépôt fournit le code de l'application et les liens vers le code source des composants utilisés, ainsi que le script reproductible de récupération des binaires. Les notices ci-dessus ne remplacent pas les licences complètes.
