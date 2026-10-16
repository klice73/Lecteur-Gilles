package fr.lecteurgilles.android

object TextChunks {
    fun split(text: String, limit: Int = 600): List<String> {
        require(limit > 1)
        val parts = mutableListOf<String>()
        var rest = text.trim()
        while (rest.length > limit) {
            val prefix = rest.substring(0, limit)
            var cut = maxOf(prefix.lastIndexOf(". "), prefix.lastIndexOf("? "), prefix.lastIndexOf("! "), prefix.lastIndexOf('\n'))
            if (cut < limit / 3) cut = prefix.lastIndexOf(' ')
            if (cut < 1) cut = limit - 1
            cut += 1
            if (cut < rest.length && Character.isHighSurrogate(rest[cut - 1])) cut--
            parts.add(rest.substring(0, cut).trim())
            rest = rest.substring(cut).trim()
        }
        if (rest.isNotEmpty()) parts.add(rest)
        return parts
    }
}
