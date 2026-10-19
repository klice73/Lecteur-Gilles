# Audit de distribution — 19 octobre 2026

Préparation documentaire et inventaire réalisés. **Distribution commerciale non validée à ce stade.** Aucun paiement ni boutique configuré.

## Vérifié et préparé
- Inventaire Windows, licences originales, fiches de modèles et preuves upstream conservés.
- 28 archives sources téléchargées. SHA-256 dans source-manifest.json ; hachages PyPI vérifiés et dépendances Sherpa comparées aux CMake conservés. Un hachage simplement enregistré ne constitue pas une signature d’authenticité.
- Sources et scripts upstream de Piper, eSpeak, Sherpa, ONNX, PDFBox, Bouncy Castle, Kotlin, Python et paquets Python réunis. Les archives peuvent encore référencer des dépendances à récupérer.
- Accès aux textes de licence dans les deux interfaces. Attribution Siwis complétée ; mention CC0 limitée au corpus Gilles.
- Sources publiques séparées des documents, environnements locaux, clés et authentification GitHub.

## Points encore ouverts avant commercialisation
1. Confirmer la chaîne complète des droits des modèles et voix, y compris les modèles de base Ryan et Lessac et les droits éventuellement applicables aux personnes enregistrées. Les fiches et le README ne certifient pas tous ces droits.
2. Reconstruire les composants natifs correspondant aux binaires distribués et vérifier toutes leurs dépendances transitives et options de construction. **La reconstruction complète des AAR/DLL n’a pas été exécutée.** Les archives fournies ne garantissent donc pas des sources correspondantes exhaustives au sens GPL.
3. Vérifier l’inventaire Android résolu par Gradle et les conditions des DLL système d’une éventuelle distribution Windows autonome. Les outils de développement copiés localement ne font pas partie du paquet public.
4. Préparer une clé Android stable et sa sauvegarde privée. Les APK de test ne sont pas des versions commerciales définitives.
5. Accompagner chaque binaire distribué des notices et sources correspondantes réellement utilisables, selon la méthode GPL retenue. Faire valider les points juridiques ouverts avant une offre commerciale.

## Références
- GPL v3, articles 1 et 4–6 : licenses/GPL-3.0.txt et https://www.gnu.org/licenses/gpl-3.0.html .
- Vente sous GPL : https://www.gnu.org/licenses/gpl-faq.html#DoesTheGPLAllowMoney . La vente est permise sous réserve des obligations de redistribution.
- CC BY 4.0 : https://creativecommons.org/licenses/by/4.0/ et texte joint.
- Versions et preuves : evidence/, evidence-manifest.json, source-manifest.json et download-report.json.

Ce rapport distingue les constats des vérifications restantes ; il ne certifie pas la commercialisation.
