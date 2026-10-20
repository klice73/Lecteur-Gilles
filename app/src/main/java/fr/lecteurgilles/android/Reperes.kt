package fr.lecteurgilles.android

/**
 * Repères du document, version 1.6 : pages (étiquette imprimée et position) et table des matières.
 * Positions en unités UTF-16 dans le texte affiché. chapitresDevines() est identique à
 * chapitres_devines() de windows/documents.py (même règles, mêmes résultats).
 */
data class Titre(val titre:String,val niveau:Int,val debut:Int)
data class Reperes(val pages:List<Pair<String,Int>>,val table:List<Titre>,val source:String) {
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
        private val MOTS=listOf("chapitre","chap.","partie","livre","tome","section","annexe","appendice",
            "prologue","épilogue","epilogue","introduction","conclusion","préface","preface",
            "avant-propos","postface","remerciements","bibliographie","références","glossaire",
            "sommaire","table des matières","résumé","lexique","notes")
        private val NIVEAU_UN=setOf("partie","livre","tome")
        private val LONGS=setOf("chapitre","chap.","partie","livre","tome","section","annexe","appendice")
        private val motTitre=Regex("^("+MOTS.sortedByDescending{it.length}.joinToString("|"){Regex.escape(it)}+")(?=$|[\\s.:,–—-])",RegexOption.IGNORE_CASE)
        private val ordinal=Regex("^(?:premi[eè]re?|deuxi[eè]me|seconde?|troisi[eè]me|quatri[eè]me|cinqui[eè]me|sixi[eè]me|septi[eè]me|huiti[eè]me|neuvi[eè]me|dixi[eè]me|derni[eè]re?)\\s+(partie|chapitre|livre|tome|section)(?=$|[\\s.:,–—-])",RegexOption.IGNORE_CASE)
        private val numero=Regex("^([0-9]{1,2}(?:\\.[0-9]{1,2}){0,2}|[IVXLC]{1,7})[.)]?\\s+(?=[A-Z\\u00c0-\\u00dd])")
        private val finPage=Regex("(?:\\.{2,}|…|\\s)\\s*[0-9]{1,4}$")
        private val espaces=Regex("\\s+")
        private fun mots(s:String)=s.split(espaces).count{it.isNotEmpty()}
        private fun romain(s:String):Int {
            val v=mapOf('I' to 1,'V' to 5,'X' to 10,'L' to 50,'C' to 100)
            var total=0; var prec=0
            for(c in s.reversed()){val x=v.getValue(c);total+=if(x<prec) -x else x;prec=maxOf(prec,x)}
            return total
        }
        /** Titres reconnus dans un texte sans table (« Chapitre 3 », « Introduction », « II. La méthode »…). */
        fun chapitresDevines(texte:String):List<Titre> {
            val lignes=texte.split('\n')
            val num=lignes.map{numero.find(it.trim())!=null}
            val liste=num.indices.map{k->num[k] && ((k>0 && num[k-1]) || (k+1<num.size && num[k+1]))}
            val res=ArrayList<Titre>()
            val majeur=hashMapOf("arabe" to 0,"romain" to 0)
            var pos=0
            for((k,ligne) in lignes.withIndex()){
                val debut=pos; pos+=ligne.length+1
                val s=ligne.trim()
                if(s.length !in 2..90 || s.last() in ",;" || finPage.containsMatchIn(s))continue
                val ici=debut+(ligne.length-ligne.trimStart().length)
                val m=motTitre.find(s)?:ordinal.find(s)   // « Chapitre 3 », « Première partie »
                if(m!=null){
                    val mot=m.groupValues[1].lowercase()
                    if(mot !in LONGS && s.length>60)continue
                    if(s.endsWith(".") && mots(s)>6)continue
                    res.add(Titre(s,if(mot in NIVEAU_UN) 1 else 2,ici))
                    continue
                }
                val n=if(liste[k]) null else numero.find(s)
                if(n!=null && mots(s)<=12 && s.last() !in ".:"){
                    val nb=n.groupValues[1]
                    val sorte=if(nb[0].isDigit()) "arabe" else "romain"
                    if('.' in nb){
                        if(majeur.getValue("arabe")>0 && nb.substringBefore('.').toInt()==majeur.getValue("arabe"))res.add(Titre(s,3,ici))
                        continue
                    }
                    val v=if(sorte=="arabe") nb.toInt() else romain(nb)
                    if(v==majeur.getValue(sorte)+1){majeur[sorte]=v;res.add(Titre(s,2,ici))}
                }
            }
            // même titre deux fois (table imprimée puis corps du livre) : garder le dernier
            val vus=HashMap<String,Int>(); val fin=ArrayList<Titre?>()
            for(t in res){
                val cle=t.titre.lowercase().split(espaces).filter{it.isNotEmpty()}.joinToString(" ")
                vus[cle]?.let{fin[it]=null}
                vus[cle]=fin.size; fin.add(t)
            }
            var r=fin.filterNotNull().take(500)
            if(r.isNotEmpty()){val d=r.minOf{it.niveau}-1; if(d>0)r=r.map{it.copy(niveau=it.niveau-d)}}
            return r
        }
        /** Position exacte du titre dans texte[debut,fin) (espaces et casse ignorés), sinon debut. */
        fun chercher(texte:String,titre:String,debut:Int,fin:Int):Int {
            val m=titre.split(espaces).filter{it.isNotEmpty()}.map{Regex.escape(it)}
            if(m.isEmpty() || debut>=texte.length)return debut
            val r=Regex(m.joinToString("\\s+"),RegexOption.IGNORE_CASE).find(texte.substring(debut,minOf(maxOf(debut,fin),texte.length)))
            return if(r!=null) debut+r.range.first else debut
        }
    }
}
