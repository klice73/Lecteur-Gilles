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
        private val NOMBRES_MOTS=listOf("UN","DEUX","TROIS","QUATRE","CINQ","SIX","SEPT","HUIT","NEUF","DIX","ONZE","DOUZE",
            "TREIZE","QUATORZE","QUINZE","SEIZE","DIX-SEPT","DIX-HUIT","DIX-NEUF","VINGT")
        private val nombreSeul=Regex("(?d)^(?:[–—-]$E*)?([0-9]{1,3})(?:$E*[–—-])?$")
        private val suiteLong=Regex("(?d)^(?:$|$E*[:.–—-](?:$|$E)|$E+(?:[0-9]{1,4}|[IVXLC]{1,7}|[A-Z])(?=$|$E|[.:)–—,-])|$E+(?iu:premi[eè]re?|premier|derni[eè]re?|un|une|deux|trois|quatre|cinq|six|sept|huit|neuf|dix|onze|douze|treize|quatorze|quinze|seize|vingt)$E*(?:$|[.:–—-]))")
        private data class Trouve(val titre:String,val niveau:Int,val debut:Int,val ligne:Int)
        /** Titres reconnus dans un texte sans table (« Chapitre 3 », « Première partie », « III » ou « 3 » seuls…).
         *  pages : débuts des pages quand on les connaît (numéros de page écartés). */
        fun chapitresDevines(texte:String,pages:List<Int>?=null):List<Titre> {
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
            val rang=IntArray(nets.size); var nonVides=0   // rang parmi les lignes non vides
            for((k,s) in nets.withIndex()){rang[k]=nonVides;if(s.isNotEmpty())nonVides++}
            val seuls=linkedMapOf("nombre" to ArrayList<Int>(),"seul" to ArrayList<Int>(),"mot" to ArrayList<Int>())   // vérifiés après coup
            var res=ArrayList<Trouve>()
            val majeur=hashMapOf("arabe" to 0,"romain" to 0,"seul" to 0,"nombre" to 0,"mot" to 0)
            var pos=0
            for((k,ligne) in lignes.withIndex()){
                val debut=pos; pos+=ligne.length+1
                val s=nets[k]
                if(longueur(s) !in 2..90 && romainSeul.find(s)==null && nombreSeul.find(s)==null)continue
                if(s.isEmpty() || s.last() in ",;" || pointilles.containsMatchIn(s))continue
                val av=voisin(k,-1); val ap=voisin(k,1)
                val suiteTable=finNb[k] && ((av!=null && finNb[av]) || (ap!=null && finNb[ap]))
                val ici=debut+(ligne.length-ligne.trimStart{it in ESP || it=='\r'}.length)
                val nm=mots(s)
                val m=motTitre.find(s)?:ordinal.find(s)
                val mot=m?.groupValues?.get(1)?.lowercase(java.util.Locale.ROOT)?:""
                if(titreNu.find(s)!=null){
                    res.add(Trouve(s,if(mot in NIVEAU_UN) 1 else 2,ici,k))
                }else if(m!=null){
                    if(suiteTable)continue
                    if(mot in LONGS){
                        // « Partie depuis trois jours. », « Livre-moi ça. » : pas des titres
                        if(suiteLong.find(s.substring(m.groups[1]!!.range.last+1))==null || (s.endsWith(".") && nm>6))continue
                    }
                    else if(longueur(s)>60 || (s.last() in ".!?" && nm>2))continue
                    res.add(Trouve(s,if(mot in NIVEAU_UN) 1 else 2,ici,k))
                }else{
                    val r=romainSeul.find(s); val c=nombreSeul.find(s)
                    if(r!=null || c!=null || s in NOMBRES_MOTS){
                        val (sorte,v)=if(r!=null) "seul" to romain(r.groupValues[1]) else if(c!=null) "nombre" to c.groupValues[1].toInt() else "mot" to NOMBRES_MOTS.indexOf(s)+1
                        if(v==majeur.getValue(sorte)+1 || v==1){majeur[sorte]=v;res.add(Trouve(s,2,ici,k));seuls.getValue(sorte).add(k)}   // suite, ou numérotation qui repart
                        continue
                    }
                    val n=num[k]
                    if(n==null || nm>12 || s.last() in ".:" || suiteTable)continue
                    if(dansListe(k,av,ap))continue
                    val nb=n.groupValues[1]
                    if('.' in nb){
                        if(majeur.getValue("arabe")>0 && nb.substringBefore('.').toInt()==majeur.getValue("arabe"))res.add(Trouve(s,3,ici,k))
                        continue
                    }
                    val sorte=if(nb[0].isDigit()) "arabe" else "romain"
                    val v=if(sorte=="arabe") nb.toInt() else romain(nb)
                    if(v==majeur.getValue(sorte)+1 || v==1){majeur[sorte]=v;res.add(Trouve(s,2,ici,k))}
                }
            }
            // Numéros seuls (« 3 », « III », « TROIS ») écartés en bloc s'ils ressemblent à autre chose qu'à des chapitres :
            // un seul ; moins de 3 lignes entre deux (recette, liste) ; un sur deux pages ou plus ; écarts très réguliers.
            val ecartes=HashSet<Int>()
            for((sorte,ks) in seuls){
                if(ks.isEmpty())continue
                val ecarts=ks.zipWithNext{a,b->rang[b]-rang[a]}.sorted()
                // chiffres et nombres en lettres : moins de 3 lignes entre deux = étapes d'une liste (pas les chiffres romains seuls)
                var mauvais=ks.size<2 || (sorte!="seul" && ecarts[ecarts.size/2]<3)
                if(pages!=null && pages.isNotEmpty() && ks.size>=5 && 2*ks.size>=pages.size)mauvais=true
                if(ecarts.size>=7){
                    val moy=ecarts.sum().toDouble()/ecarts.size
                    if(Math.sqrt(ecarts.sumOf{(it-moy)*(it-moy)}/ecarts.size)<0.25*moy)mauvais=true
                }
                if(mauvais)ecartes.addAll(ks)
            }
            res=ArrayList(res.filter{it.ligne !in ecartes})
            // Doublons. 1) même titre répété sans autre titre entre (en-tête courant) : garder le premier.
            // 2) table imprimée (au moins 3 titres sur des lignes qui se suivent, ou suite d'un « Sommaire ») :
            //    retirer ses entrées qui réapparaissent plus loin dans le livre.
            fun cle(titre:String)=titre.lowercase(java.util.Locale.ROOT).split(espaces).filter{it.isNotEmpty()}.joinToString(" ")
            fun cleTable(titre:String):String{val c=cle(titre);return if(c.count{it==' '}>=2) finNombre.replace(c,"") else c}
            val garde=ArrayList<Trouve>()
            for(x in res){ if(garde.isNotEmpty() && cle(garde.last().titre)==cle(x.titre))continue; garde.add(x) }
            val blocs=ArrayList<List<Trouve>>(); var bloc=ArrayList<Trouve>()
            for(x in garde){
                if(bloc.isNotEmpty() && voisin(bloc.last().ligne,1)==x.ligne)bloc.add(x)
                else{ if(bloc.isNotEmpty())blocs.add(bloc); bloc=arrayListOf(x) }
            }
            if(bloc.isNotEmpty())blocs.add(bloc)
            val retires=HashSet<Int>()
            for(b in blocs){
                val mm=motTitre.find(b[0].titre)?:ordinal.find(b[0].titre)
                val sommaire=mm!=null && mm.groupValues[1].lowercase(java.util.Locale.ROOT) in setOf("sommaire","table des matières")
                if(b.size<3 && !(sommaire && b.size>=2))continue
                for(x in if(sommaire) b.drop(1) else b)
                    if(garde.any{y->cleTable(y.titre)==cleTable(x.titre) && y.ligne>x.ligne})retires.add(x.ligne)
            }
            var r=garde.filter{it.ligne !in retires}.take(2000).map{Titre(it.titre,it.niveau,it.debut)}
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
