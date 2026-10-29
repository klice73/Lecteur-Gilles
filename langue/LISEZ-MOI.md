# Dictionnaire français corrigé du moteur de prononciation (version 1.11)

Le moteur de prononciation (eSpeak NG) passe parfois en anglais au milieu d'un texte français : « dos » devenait
« doss » à l'anglaise, « traversons », « méthane », « mammouth », « Berthe », « assieds-toi »… La cause : des règles
de `fr_rules` qui envoient certaines suites de lettres vers l'anglais.

`fr_dict` est le dictionnaire français d'eSpeak NG **révision 724808c** (celle de Piper 1.8.0), recompilé avec, en plus,
les 74 mots de `fr_lecteur_gilles.txt` (prononciation française forcée). Rien d'autre ne change : les vrais anglicismes
(week-end, football, e-mail…) gardent leur prononciation. Contrôle : sur 139 856 mots français courants, seuls ces
mots (et « dos-d'âne ») changent de prononciation.

Liste trouvée en faisant lire 139 856 mots par le moteur et en gardant ceux qui passaient en anglais alors qu'ils sont
français (accents, terminaisons françaises, fréquence en français bien plus forte qu'en anglais), vérifiés un par un.

Reconstruire : copier `dictsource/fr_*` d'eSpeak NG 724808c, ajouter `fr_lecteur_gilles.txt` à la fin de `fr_list`,
puis `espeak-ng --path=<dossier contenant espeak-ng-data> --compile=fr` depuis ce dossier `dictsource`.
Licence : GPL-3.0-or-later (eSpeak NG).

Deux autres erreurs du moteur sont corrigées dans le texte avant la lecture (lecteur.py `corriger_moteur`,
Prononciations.kt `corrigerMoteur`) : « qu'h… » (qu'hier, qu'histoire) et « d'aujourd'hui ».
