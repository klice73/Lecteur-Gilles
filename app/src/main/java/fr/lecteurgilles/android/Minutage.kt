package fr.lecteurgilles.android

import kotlin.math.abs
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

    private const val VOY = "aeiouyàâäéèêëîïôöùûüœæ"
    private val groupes = listOf("eau","ou","au","ai","ei","oi","ch","ph","gn","qu","ll","ss","tt","nn","mm","rr","pp")
    private val nombre = Regex("\\p{Nd}[\\p{Nd} .,\\u00a0\\u202f]*")
    private val elision = Regex("^[\\p{L}]['’]")
    private val liaison = Regex("['’-]")
    private val finMuette = Regex("(ent|es|s|x)$")
    private val eMuet = Regex("e$")
    private val consMuette = Regex("(?<=[$VOY])[tdzp]$")
    private val nasale = Regex("(?<=[$VOY])[nm](?=[^$VOY]|$)")

    /** Nombre approximatif de sons d'un mot français écrit ; identique à sons() de lecteur.py. */
    fun sons(m:String):Double {
        var w=java.text.Normalizer.normalize(m,java.text.Normalizer.Form.NFC).lowercase(java.util.Locale.ROOT)
        if(nombre.matches(w))return 3.0*chiffre.findAll(w).count()
        w=elision.replace(w,"")
        w=liaison.replace(w,"")
        if(w.length>3)w=finMuette.replace(w,"")
        if(w.length>2)w=eMuet.replace(w,"")
        w=consMuette.replace(w,"")
        for(g in groupes)w=w.replace(g,"#")
        w=nasale.replace(w,"")
        w=w.replace("h","")
        return maxOf(1,w.length).toDouble()
    }

    fun poidsMots(p:String):List<Mot> {
        val res=ArrayList<Mot>()
        var precedent=0
        for(m in mot.findAll(p)) {
            val entre=p.substring(precedent,m.range.first)
            val pause=if(virgule.containsMatchIn(entre)) 6.0 else if(tiret.containsMatchIn(entre)) 2.0 else 0.0
            res.add(Mot(m.range.first,m.range.last+1,if(res.isEmpty()) 0.0 else pause,1.0+sons(m.value)))
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

    /**
     * Pour une phrase et son audio : début/fin de chaque mot en échantillons. Identique à minuter()
     * de lecteur.py : zone parlée répartie selon le nombre de sons, chaque pause de ponctuation
     * ancrée sur le vrai silence le plus proche (au moins 80 ms sous -30 dB).
     */
    fun minuter(p:String,audio:FloatArray,sr:Int):List<Temps> {
        val mots=poidsMots(p); if(mots.isEmpty())return emptyList()
        val (a,b)=zoneParlee(audio,sr)
        val trame=max(1,sr/100); val k=audio.size/trame
        val rms=DoubleArray(k){t->var s=0.0;for(i in t*trame until (t+1)*trame)s+=audio[i].toDouble()*audio[i];sqrt(s/trame)}
        var silences=ArrayList<Pair<Double,Double>>()   // (centre, fin) en échantillons
        if(k>0){
            val seuil=rms.max()*10.0.pow(-30.0/20)
            var i=a/trame; val fin=b/trame
            while(i<fin){
                if(rms[i]<seuil){
                    var j=i
                    while(j<fin && rms[j]<seuil)j++
                    if(j-i>=8 && j<fin)silences.add((i+j)/2.0*trame to (j*trame).toDouble())
                    i=j
                } else i++
            }
        }
        val debutPoids=DoubleArray(mots.size); var cumul=0.0
        for((n,m) in mots.withIndex()){cumul+=m.pause;debutPoids[n]=cumul;cumul+=m.poids}
        val total=cumul
        val est=DoubleArray(mots.size){a+(b-a)*debutPoids[it]/total}
        data class Ancre(val k:Int,val t:Double,val s:Double)
        val ancres=arrayListOf(Ancre(0,a.toDouble(),0.0))
        for(n in 1 until mots.size){
            if(mots[n].pause>0 && silences.isNotEmpty()){
                var j=0
                for(q in silences.indices)if(abs(silences[q].first-est[n])<abs(silences[j].first-est[n]))j=q
                if(abs(silences[j].first-est[n])<0.25*(b-a)){
                    ancres.add(Ancre(n,silences[j].second,debutPoids[n]))
                    val centre=silences[j].first
                    silences=ArrayList(silences.filter{it.first>centre})
                }
            }
        }
        ancres.add(Ancre(mots.size,b.toDouble(),total))
        for(x in 0 until ancres.size-1){
            val (k0,t0,s0)=ancres[x]; val (k1,t1,_)=ancres[x+1]
            if(k1<=k0)continue
            val finPoids=debutPoids[k1-1]+mots[k1-1].poids
            if(t1<=t0 || finPoids<=s0)continue
            for(n in k0 until k1)est[n]=t0+(t1-t0)*(debutPoids[n]-s0)/(finPoids-s0)
        }
        for(n in 1 until est.size)est[n]=maxOf(est[n],est[n-1])
        return mots.mapIndexed{n,m->Temps(if(n==0) 0 else est[n].toInt(),if(n==mots.size-1) audio.size else est[n+1].toInt(),m.debut,m.fin)}
    }
}
