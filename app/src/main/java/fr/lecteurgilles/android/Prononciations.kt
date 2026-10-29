package fr.lecteurgilles.android

/**
 * Lexique de prononciation (version 1.8), même règle que lecteur.py (lire_lexique, appliquer_lexique) :
 * une ligne par mot « mot = comment le dire », lignes vides et « # » ignorées, mot entier sans tenir
 * compte des majuscules, première ligne gagnante. Seule la voix change : le texte affiché reste intact.
 */
class Prononciations private constructor(private val motif:Regex?,private val table:Map<String,String>) {
    fun appliquer(texte:String):String = corrigerMoteur(motif?.replace(texte){table[it.value.replace('\u2019','\'').lowercase(java.util.Locale.ROOT)]?:it.value} ?: texte)
    val taille get()=table.size
    companion object {
        private const val LETTRES="0-9A-Za-z\\u00c0-\\u00d6\\u00d8-\\u00f6\\u00f8-\\u024f"
        // 1.11 : « qu'h... » et « d'aujourd'hui » étaient lus à l'anglaise par le moteur ; même règle que corriger_moteur (lecteur.py)
        private val QU_H=Regex("(?<![$LETTRES])((?:quoi)?qu)['’](?=h)",RegexOption.IGNORE_CASE)
        private val AUJOURDHUI=Regex("(['’])(aujourd)['’](hui)(?![$LETTRES])",RegexOption.IGNORE_CASE)
        fun corrigerMoteur(t:String):String = AUJOURDHUI.replace(QU_H.replace(t,"$1' "),"$1$2$3")
        const val ENTETE="# Lexique de prononciation de Gilles\n# Une ligne par mot :  mot = comment Gilles doit le dire\n"+
            "# Écrivez la prononciation comme un mot français (accents permis). Exemples :\n#   Bateson = Bétsonne\n#   POETICS-S = Poétixe esse\n"+
            "# Mot entier seulement, majuscules ou non. Les lignes qui commencent par # sont ignorées.\n# Le texte affiché ne change pas ; seule la voix est corrigée.\n\n"
        fun lire(contenu:String):Prononciations {
            val table=LinkedHashMap<String,String>()
            for(brute in contenu.replace("\r","").split('\n')){
                val ligne=brute.trim().trimStart('\uFEFF').trim()
                if(ligne.isEmpty() || ligne.startsWith("#") || '=' !in ligne)continue
                val mot=ligne.substringBefore('=').trim(); val dire=ligne.substringAfter('=').trim()
                if(mot.isNotEmpty() && dire.isNotEmpty())table.putIfAbsent(mot.replace('\u2019','\'').lowercase(java.util.Locale.ROOT),dire)   // ’ = '
            }
            if(table.isEmpty())return Prononciations(null,table)
            val alternatives=table.keys.sortedByDescending{it.length}.joinToString("|"){k->k.split('\'').joinToString("['\u2019]"){Regex.escape(it)}}
            return Prononciations(Regex("(?<![$LETTRES])(?:$alternatives)(?![$LETTRES])",setOf(RegexOption.IGNORE_CASE)),table)
        }
    }
}
