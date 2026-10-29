# Voix Gilles medium (réentraînée)

- `fr_FR-gilles-medium.onnx` : voix Gilles réentraînée sur Kaggle les 28 et 29 octobre 2026 (carnet `entrainement/Reentrainer-Gilles-Kaggle.ipynb`,
  piper1-gpl 619f513), séance 1 : 10 h 23 sur GPU T4. Départ à chaud depuis le point Siwis medium de rhasspy/piper-checkpoints.
  Corpus : CSS10 French (French Single Speaker Speech Dataset, Kaggle bryanpark), marqué CC0.
- `fr_FR-gilles-medium.onnx.json` : configuration produite par l'entraînement ; seul changement : `noise_w` 0,8 → 0,4
  (durées des sons plus régulières, mesuré sur 40 synthèses).
- `prepare.py` en tire la version Android (métadonnées Sherpa et `tokens.txt`, script `preparer_voix_sherpa.py`) ;
  la CI en tire la version Windows avec la durée de chaque son (`aligner_voix.py`).
