package fr.lecteurgilles.android

/** Positions Android/Windows utilisent les unités UTF-16, comme substring. */
object ReadingStart {
    fun fromCursor(text:String,selectionStart:Int,selectionEnd:Int):String {
        val start=minOf(selectionStart.coerceIn(0,text.length),selectionEnd.coerceIn(0,text.length))
        return text.substring(start)
    }
}
