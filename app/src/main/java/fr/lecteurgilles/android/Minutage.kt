package fr.lecteurgilles.android

import kotlin.math.max
import kotlin.math.min
import kotlin.math.pow
import kotlin.math.sqrt

/**
 * Minutage mot à mot, version 1.5. Même règle que windows/lecteur.py (phrases, poids_mots,
 * zone_parlee, minuter) : chaque phrase est synthétisée seule, donc son début et sa fin sont
 * exacts ; dans la phrase, la zone parlée (sans les silences de bord) est répartie entre
 * les mots selon leur longueur, une virgule comptant comme une petite pause.
 * Pas de drapeau (?U) : Android (ICU) le refuse.
 */
object Minutage {
    data class Mot(val debut:Int,val fin:Int,val pause:Double,val poids:Double)
    data class Temps(val t0:Int,val t1:Int,val debut:Int,val fin:Int)

    private const val L = "[\\p{L}\\p{M}]"
    private val phrase = Regex("[^\\S\\n]*(?:[.!?…]+[\"»”)\\]]*\\s+|\\n[^\\S\\n]*\\n\\s*)")
    private val mot = Regex("$L+(?:['’-]$L+)*|\\p{Nd}+(?:[.,\\u00a0\\u202f ]\\p{Nd}+)*")
    private val virgule = Regex("[,;:]")
    private val tiret = Regex("[–—()«»\"]")
    private val lettre = Regex(L)
    private val chiffre = Regex("\\p{Nd}")

    /** (début, fin) des phrases qui contiennent au moins un mot. */
    fun phrases(texte:String):List<IntRange> {
        val res=ArrayList<IntRange>()
        var debut=0
        for(m in phrase.findAll(texte)) {
            val fin=m.range.last+1
            if(fin>debut){res.add(debut until fin);debut=fin}
        }
        if(debut<texte.length)res.add(debut until texte.length)
        return res.filter{ mot.find(texte.substring(it.first,it.last+1))!=null }
    }

    fun poidsMots(p:String):List<Mot> {
        val res=ArrayList<Mot>()
        var precedent=0
        for(m in mot.findAll(p)) {
            val entre=p.substring(precedent,m.range.first)
            val pause=if(virgule.containsMatchIn(entre)) 4.0 else if(tiret.containsMatchIn(entre)) 2.0 else 0.0
            val l=lettre.findAll(m.value).count(); val c=chiffre.findAll(m.value).count()
            res.add(Mot(m.range.first,m.range.last+1,if(res.isEmpty()) 0.0 else pause,1.0+l+3.0*c))
            precedent=m.range.last+1
        }
        return res
    }

    /** (premier, fin) échantillon parlé, d'après l'énergie par tranches de 10 ms. */
    fun zoneParlee(audio:FloatArray,sr:Int):Pair<Int,Int> {
        val trame=max(1,sr/100); val k=audio.size/trame
        if(k==0)return 0 to audio.size
        val rms=DoubleArray(k){t->var s=0.0;for(i in t*trame until (t+1)*trame)s+=audio[i].toDouble()*audio[i];sqrt(s/trame)}
        val seuil=max(rms.max()*10.0.pow(-35.0/20),1e-12)
        val premier=rms.indexOfFirst{it>=seuil}; val dernier=rms.indexOfLast{it>=seuil}
        if(premier<0)return 0 to audio.size
        return premier*trame to min(audio.size,(dernier+1)*trame)
    }

    /** Pour une phrase et son audio : début/fin de chaque mot en échantillons. */
    fun minuter(p:String,audio:FloatArray,sr:Int):List<Temps> {
        val mots=poidsMots(p); if(mots.isEmpty())return emptyList()
        val (a,b)=zoneParlee(audio,sr)
        val total=mots.sumOf{it.pause+it.poids}
        var cumul=0.0
        val res=ArrayList<Temps>()
        for((i,m) in mots.withIndex()) {
            cumul+=m.pause; val t0=a+(b-a)*cumul/total
            cumul+=m.poids; val t1=a+(b-a)*cumul/total
            res.add(Temps(if(i==0) 0 else t0.toInt(),t1.toInt(),m.debut,m.fin))
        }
        res[res.size-1]=res.last().copy(t1=audio.size)
        return res
    }
}
