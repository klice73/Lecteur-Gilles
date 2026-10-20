package fr.lecteurgilles.android

/**
 * Repères du document, version 1.6 : pages (étiquette imprimée et position) et table des matières.
 * Positions en unités UTF-16 dans le texte affiché. chapitresDevines() est identique à
 * chapitres_devines() de windows/documents.py (même règles, mêmes résultats).
 */
data class Titre(val titre:String,val niveau:Int,val debut:Int)
class Reperes(pages:List<Pair<String,Int>>,table:List<Titre>,val source:String) {
    val pages=pages.sortedBy{it.second}
    val table=table.sortedBy{it.debut}   // ordre du texte : la recherche du chapitre en cours en dépend
    /** Indice du dernier élément dont le début est <= position, ou -1. */
    private fun dernier(debuts:List<Int>,position:Int):Int {
        var bas=0; var haut=debuts.size-1; var res=-1
        while(bas<=haut){val m=(bas+haut)/2;if(debuts[m]<=position){res=m;bas=m+1}else haut=m-1}
        return res
    }
    fun page(position:Int)=dernier(pages.map{it.second},position)
    fun titre(position:Int)=dernier(table.map{it.debut},position)
    /** « page 12 (14 sur 300) · Chapitre 2 », ou « 45 % du texte · Chapitre 2 » sans pages. */
    fun ouSuisJe(position:Int,longueur:Int):String {
        val p=page(position)
        var s=if(p>=0) "page ${pages[p].first} (${p+1} sur ${pages.size})" else if(longueur>0) "${(100L*position/longueur).toInt()} % du texte" else ""
        val c=titre(position)
        if(c>=0)s+=" · "+table[c].titre
        return s
    }
    /** Début d'une page : étiquette imprimée (« iv », « 12 ») d'abord, sinon rang. -1 si inconnue. */
    fun debutPage(demande:String):Int {
        val d=demande.trim()
        pages.firstOrNull{it.first.equals(d,ignoreCase=true)}?.let{return it.second}
        val n=d.toIntOrNull()?:return -1
        return if(n in 1..pages.size) pages[n-1].second else -1
    }
    companion object {
        // Mêmes règles que windows/documents.py (chapitres_devines, _chercher) ; espaces en liste explicite
        // (\s diffère entre Python et Java), longueurs comptées en caractères réels (emoji = 1),
        // (?d) : seul \n termine une ligne pour ^ et $, comme en Python.
        private const val ESP=" \t\u00a0\u202f\u2007\u2009\u000b\u000c\u0085"
        private const val E="[$ESP]"
        private val MOTS=listOf("chapitre","chap.","partie","livre","tome","section","annexe","appendice",
            "prologue","épilogue","epilogue","introduction","conclusion","préface","preface",
            "avant-propos","postface","remerciements","bibliographie","références","glossaire",
            "sommaire","table des matières","résumé","lexique","notes")
        private val NIVEAU_UN=setOf("partie","livre","tome")
        private val LONGS=setOf("chapitre","chap.","partie","livre","tome","section","annexe","appendice")
        private val MOTS_RE=MOTS.sortedByDescending{it.length}.joinToString("|"){Regex.escape(it)}
        private const val ORDINAUX="premi[eè]re?|deuxi[eè]me|seconde?|troisi[eè]me|quatri[eè]me|cinqui[eè]me|sixi[eè]me|septi[eè]me|huiti[eè]me|neuvi[eè]me|dixi[eè]me|derni[eè]re?"
        private const val APRES="(?=$|$E|[.:,–—-])"
        private val motTitre=Regex("(?d)^($MOTS_RE)$APRES",RegexOption.IGNORE_CASE)
        private val ordinal=Regex("(?d)^(?:$ORDINAUX)$E+(partie|chapitre|livre|tome|section)$APRES",RegexOption.IGNORE_CASE)
        private val titreNu=Regex("(?d)^(?:(?:$ORDINAUX)$E+)?(?:$MOTS_RE)$E+([0-9]{1,3}|[ivxlc]{1,7}|[a-z])[.:]?$",RegexOption.IGNORE_CASE)
        private val numero=Regex("(?d)^([0-9]{1,2}(?:\\.[0-9]{1,2}){0,2}|[IVXLC]{1,7})(?:[.)]$E+|$E+(?=[A-Z\\u00c0-\\u00dd][^$ESP.,]))(?=[A-Z\\u00c0-\\u00dd])")
        private val romainSeul=Regex("(?d)^([IVXLC]{1,7})\\.?$")
        private val pointilles=Regex("(?d)(?:\\.{2,}|…|\\t)$E*[0-9]{1,4}$")
        private val finNombre=Regex("(?d)$E[0-9]{1,4}$")
        private val espaces=Regex("$E+")
        private fun nettoyer(l:String)=l.trim{it in ESP || it=='\r'}
        private fun mots(s:String)=s.split(espaces).count{it.isNotEmpty()}
        private fun longueur(s:String)=s.codePointCount(0,s.length)
        private fun romain(s:String):Int {
            val v=mapOf('I' to 1,'V' to 5,'X' to 10,'L' to 50,'C' to 100)
            var total=0; var prec=0
            for(c in s.reversed()){val x=v.getValue(c);total+=if(x<prec) -x else x;prec=maxOf(prec,x)}
            return total
        }
        private fun valeur(num:String):Int{val d=num.substringAfterLast('.');return d.toIntOrNull()?:romain(d)}
        /** Titres reconnus dans un texte sans table (« Chapitre 3 », « Première partie », « III » seul…). */
        fun chapitresDevines(texte:String):List<Titre> {
            val lignes=texte.split('\n')
            val nets=lignes.map{nettoyer(it)}
            val num=nets.map{numero.find(it)}
            val prof=num.map{m->m?.groupValues?.get(1)?.count{it=='.'}?:-1}
            fun voisin(k:Int,pas:Int):Int?{var j=k+pas;while(j in nets.indices && nets[j].isEmpty())j+=pas;return if(j in nets.indices) j else null}
            val finNb=nets.map{finNombre.containsMatchIn(it)}
            fun dansListe(k:Int,av:Int?,ap:Int?):Boolean{
                val n=num[k]!!.groupValues[1]; val v=valeur(n)
                for((j,pas) in listOf(av to -1,ap to 1)){
                    val m=if(j!=null && j==k+pas) num[j] else null
                    if(m!=null && prof[j!!]==prof[k] && m.groupValues[1][0].isDigit()==n[0].isDigit() && valeur(m.groupValues[1])==v+pas)return true
                }
                return false
            }
            val res=ArrayList<Titre>()
            val majeur=hashMapOf("arabe" to 0,"romain" to 0,"seul" to 0)
            var pos=0
            for((k,ligne) in lignes.withIndex()){
                val debut=pos; pos+=ligne.length+1
                val s=nets[k]
                if(longueur(s) !in 2..90 && romainSeul.find(s)==null)continue
                if(s.isEmpty() || s.last() in ",;" || pointilles.containsMatchIn(s))continue
                val av=voisin(k,-1); val ap=voisin(k,1)
                val suiteTable=finNb[k] && ((av!=null && finNb[av]) || (ap!=null && finNb[ap]))
                val ici=debut+(ligne.length-ligne.trimStart{it in ESP || it=='\r'}.length)
                val nm=mots(s)
                if(titreNu.find(s)!=null){
                    val m=motTitre.find(s)?:ordinal.find(s)
                    val mot=m?.groupValues?.get(1)?.lowercase(java.util.Locale.ROOT)?:""
                    res.add(Titre(s,if(mot in NIVEAU_UN) 1 else 2,ici));continue
                }
                val m=motTitre.find(s)?:ordinal.find(s)
                if(m!=null){
                    val mot=m.groupValues[1].lowercase(java.util.Locale.ROOT)
                    if(suiteTable)continue
                    if(mot in LONGS){ if(s.endsWith(".") && nm>6)continue }
                    else if(longueur(s)>60 || (s.last() in ".!?" && nm>2))continue
                    res.add(Titre(s,if(mot in NIVEAU_UN) 1 else 2,ici));continue
                }
                val r=romainSeul.find(s)
                if(r!=null){
                    val v=romain(r.groupValues[1])
                    if(v==majeur.getValue("seul")+1){majeur["seul"]=v;res.add(Titre(s,2,ici))}
                    continue
                }
                val n=num[k]
                if(n==null || nm>12 || s.last() in ".:" || suiteTable)continue
                if(dansListe(k,av,ap))continue
                val nb=n.groupValues[1]
                if('.' in nb){
                    if(majeur.getValue("arabe")>0 && nb.substringBefore('.').toInt()==majeur.getValue("arabe"))res.add(Titre(s,3,ici))
                    continue
                }
                val sorte=if(nb[0].isDigit()) "arabe" else "romain"
                val v=if(sorte=="arabe") nb.toInt() else romain(nb)
                if(v==majeur.getValue(sorte)+1){majeur[sorte]=v;res.add(Titre(s,2,ici))}
            }
            // même titre deux fois (table imprimée puis corps du livre) : garder le dernier
            val vus=HashMap<String,Int>(); val fin=ArrayList<Titre?>()
            for(t in res){
                val cle=t.titre.lowercase(java.util.Locale.ROOT).split(espaces).filter{it.isNotEmpty()}.joinToString(" ")
                vus[cle]?.let{fin[it]=null}
                vus[cle]=fin.size; fin.add(t)
            }
            var r=fin.filterNotNull().take(2000)
            if(r.isNotEmpty()){val d=r.minOf{it.niveau}-1; if(d>0)r=r.map{it.copy(niveau=it.niveau-d)}}
            return r
        }
        /** Position du titre dans texte[debut,fin) : ligne qui est le titre, puis ligne qui commence par lui
         *  (casse exacte puis sans casse), sinon n'importe où ; à défaut, debut. */
        fun chercher(texte:String,titre:String,debut:Int,fin:Int):Int {
            val m=titre.split(espaces).filter{it.isNotEmpty()}.map{Regex.escape(it)}
            if(m.isEmpty() || debut>=texte.length)return debut
            // comme re.search(texte, debut, fin) : ^ ne vaut au début de la zone que s'il suit un \n
            val zone=texte.substring(0,minOf(maxOf(debut,fin),texte.length))
            val corps=m.joinToString("$E+")
            val ligne="(?dm)^$E*($corps)"
            for((motif,casse) in listOf("$ligne$E*$" to false,"$ligne$E*$" to true,ligne to false,ligne to true,"($corps)" to true)){
                val r=(if(casse) Regex(motif,RegexOption.IGNORE_CASE) else Regex(motif)).find(zone,debut)
                if(r!=null)return r.groups[1]!!.range.first
            }
            return debut
        }
    }
}
