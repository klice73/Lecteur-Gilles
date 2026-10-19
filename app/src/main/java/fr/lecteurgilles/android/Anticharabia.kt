package fr.lecteurgilles.android

import kotlin.math.max
import kotlin.math.min
import kotlin.math.pow
import kotlin.math.sqrt

/**
 * Anti-charabia, version 1.4 (19 octobre 2026). Même logique que windows/lecteur.py.
 *
 * Mesure : la voix Gilles (fr_FR-gilles-low) continue souvent à « parler » après
 * une phrase de moins de 7 mots (titre, numéro de page, « Oui. »).
 * 1. regrouper : une phrase trop courte est rattachée à la suivante (son point
 *    devient une virgule). Seul le texte envoyé au moteur change, jamais l'affichage.
 * 2. couper : si l'audio dépasse nettement la durée attendue, il est coupé au
 *    premier silence, là où le charabia commence.
 */
object Anticharabia {
    const val MOTS_MIN = 7
    private val fin = Regex("(?U)(?<=[.!?…])[\"»”)\\]]*\\s+")
    private val pointFinal = Regex("(?U)[.!?…]+([\"»”)\\]]*)$")
    private val points = Regex("(?U)(?:\\s*[.…·_]){3,}\\s*")
    private val titre = Regex("(?U)(?<=[^\\s.!?,;:…])[ \\t]*\\n[ \\t]*\\n\\s*")
    private val mot = Regex("(?U)[^\\W\\d_]+(?:['’-][^\\W\\d_]+)*|\\d+")
    private val lettre = Regex("(?U)[^\\W\\d_]")
    private val chiffre = Regex("\\d")

    fun mots(texte: String) = mot.findAll(texte).count()
    fun lettres(texte: String) = lettre.findAll(texte).count() + 3 * chiffre.findAll(texte).count()

    private fun virgule(s: String) = pointFinal.replace(s, ",$1")

    fun regrouper(texte: String): List<String> {
        val propre = titre.replace(points.replace(texte, ", "), ", ")
        val phrases = fin.split(propre).map { it.trim() }.filter { it.isNotEmpty() }
        val groupes = mutableListOf<String>()
        var courant = ""
        for (p in phrases) {
            courant = when {
                courant.isEmpty() -> p
                mots(courant) < MOTS_MIN -> virgule(courant) + " " + p
                else -> { groupes.add(courant); p }
            }
        }
        if (courant.isNotEmpty()) {
            if (groupes.isNotEmpty() && mots(courant) < MOTS_MIN) groupes[groupes.size - 1] = virgule(groupes.last()) + " " + courant
            else groupes.add(courant)
        }
        return groupes
    }

    /** lent = 1 / vitesse ; à 0,8× la voix est plus lente, le seuil suit. */
    fun couper(audio: FloatArray, sr: Int, texte: String, lent: Float = 1f): FloatArray {
        val n = audio.size
        val l = lettres(texte)
        val limite = (0.8 + 0.13 * l) * lent
        if (n <= limite * sr) return audio
        val trame = max(1, (0.02 * sr).toInt())
        val k = n / trame
        if (k == 0) return audio
        val rms = DoubleArray(k) { t ->
            var s = 0.0
            for (i in t * trame until (t + 1) * trame) s += audio[i].toDouble() * audio[i]
            sqrt(s / trame) + 1e-9
        }
        val tri = rms.sortedArray()
        val p90 = tri[min(k - 1, (0.9 * (k - 1)).toInt())]
        val seuil = p90 * 10.0.pow(-30.0 / 20)
        val muet = BooleanArray(k) { rms[it] < seuil }
        val premier = muet.indexOfFirst { !it }.let { if (it < 0) 0 else it }
        var i = premier + (max(0.6 * 0.065 * l * lent, 0.35) / 0.02).toInt()
        val besoin = (0.25 / 0.02).toInt()
        while (i < k) {
            if (muet[i]) {
                var j = i
                while (j < k && muet[j]) j++
                if (j - i >= besoin && j < k) return audio.copyOf(min(n, (i + (0.12 / 0.02).toInt()) * trame))
                i = j
            } else i++
        }
        val out = audio.copyOf(min(n, (limite * sr).toInt()))
        val f = min(out.size, (0.03 * sr).toInt())
        for (x in 0 until f) out[out.size - f + x] *= 1f - x.toFloat() / f
        return out
    }
}
