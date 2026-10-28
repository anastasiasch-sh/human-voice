#!/usr/bin/env python3
"""Линтер живого текста: ищет механические признаки нейросетевого стиля.

Запуск:
    python3 lint.py --file draft.txt
    echo "текст" | python3 lint.py
    python3 lint.py --file draft.txt --json

Код выхода 1, если есть ошибки (error). Предупреждения (warn) код не меняют,
пока не передан --strict. Только стандартная библиотека Python 3.8+.
"""
import argparse
import json
import re
import statistics
import sys

# --- словари -----------------------------------------------------------------

STOP_RU = [
    # ИИ-вводные и связки
    r"стоит отметить", r"важно (?:отметить|подчеркнуть|понимать|помнить)",
    r"следует отметить", r"необходимо отметить", r"нельзя не (?:упомянуть|отметить)",
    r"давайте (?:разберёмся|разберемся|разберём|разберем|посмотрим|поговорим)",
    r"представьте себе", r"представьте ситуацию", r"в современном мире",
    r"в наше время", r"в эпоху", r"в мире,? где", r"ни для кого не секрет",
    r"как известно", r"по сути(?: дела)?", r"правда в том,? что", r"и вот почему",
    r"вот в чём (?:дело|фишка|секрет)", r"вот в чем (?:дело|фишка|секрет)", r"спойлер",
    r"и это ещё не всё", r"и это еще не все", r"без лишних слов", r"что ещё важнее",
    r"более того", r"кроме того", r"помимо этого", r"таким образом", r"в заключение",
    r"подводя итог\w*", r"резюмируя", r"одним словом",
    # пустые концовки
    r"будущее уже здесь", r"выбор за тобой", r"выбор за вами", r"попробуй и убедись",
    r"попробуйте и убедитесь", r"всё в твоих руках", r"все в твоих руках",
    r"мир ждёт тебя", r"мир ждет тебя",
    # подхалимаж
    r"отличный вопрос", r"прекрасный выбор", r"ваше мнение очень важно",
    r"не стесняйтесь обращаться", r"надеемся,? это поможет",
]

HYPE_RU = [
    r"ключев\w+", r"уникальн\w+", r"неповторим\w+", r"инновационн\w+",
    r"революционн\w+", r"знаков\w+", r"непреходящ\w+", r"поистине", r"по-настоящему",
    r"настоящий прорыв", r"новый уровень", r"на новый уровень", r"меняет правила игры",
    r"гейм-?чейнджер\w*", r"открывает новые возможности", r"раскрыва\w+ потенциал",
    r"погружени\w+ в мир", r"окун\w+ в мир", r"незабываем\w+ впечатлени\w+",
    r"бесшовн\w+", r"безупречн\w+", r"идеальное решение", r"мир возможностей",
    r"неотъемлем\w+ част\w+", r"краеугольн\w+",
    # канцелярит
    r"являет\w*", r"являют\w*", r"представляет собой", r"осуществ\w+",
    r"производить оплату", r"в рамках", r"данн(?:ый|ая|ое|ые|ого|ому|ом|ой|ых|ую) (?!вам)",
    r"вышеуказанн\w+", r"посредством", r"на сегодняшний день", r"на текущий момент",
    r"в случае,? если", r"в связи с тем,? что", r"имеет место",
    r"обладает возможностью", r"позволяет осуществить",
]

STOP_EN = [
    r"here'?s the (?:thing|kicker|truth|deal)", r"here'?s why", r"let'?s dive",
    r"dive (?:into|deep)", r"delv\w*", r"let'?s break (?:it|this) down",
    r"let'?s talk about", r"let'?s be honest", r"in today'?s (?:world|fast-paced|digital)",
    r"in a world where", r"ever-evolving", r"imagine this", r"picture this",
    r"the truth is", r"spoiler alert", r"buckle up", r"without further ado",
    r"it'?s worth noting", r"it is (?:important|worth) (?:to note|noting)",
    r"needless to say", r"at the end of the day", r"moreover", r"furthermore",
    r"additionally", r"in conclusion", r"to sum up", r"look no further",
    r"the future is here", r"the choice is yours", r"see for yourself",
    r"what are you waiting for", r"great question",
]

HYPE_EN = [
    r"game[- ]?chang\w+", r"revolutionar\w+", r"cutting[- ]edge", r"seamless\w*",
    r"effortless\w*", r"unlock\w*", r"unleash\w*", r"elevat\w+", r"empower\w*",
    r"supercharg\w+", r"next[- ]level", r"transform the way", r"robust", r"leverag\w+",
    r"harness\w*", r"landscape", r"realm", r"tapestry", r"testament", r"pivotal",
    r"crucial", r"unparalleled", r"world of possibilities",
]

NEG_RU = {"без", "никаких", "никакой", "никакого", "никакие", "ни", "не", "нет", "ноль"}
NEG_EN = {"no", "not", "zero", "without", "never"}

NOT_JUST_RU = [
    r"\bне просто\b",
    r"\bне только\b[^.!?\n]{0,80}\bно и\b",
    r"\bдело не в\b",
    r"\bречь (?:идёт|идет) не о\b",
    r"\bэто не\b[^.!?\n]{1,60}[,.]\s*(?:это|а)\b",
    r"\bскорее\b[^.!?\n]{1,40}\bчем\b",
]
NOT_JUST_EN = [
    r"\b(?:not|isn'?t|aren'?t|is not|are not) just\b", r"\bnot only\b[^.!?\n]{0,80}\bbut\b", r"\bit'?s not about\b",
    r"\bmore than just\b",
    r"\b(?:this|it) (?:isn'?t|is not)\b[^.!?\n]{1,50}[,.;]\s*(?:it'?s|it is)\b",
]

# --- вспомогательное ---------------------------------------------------------

WORD = re.compile(r"[\w'’-]+", re.UNICODE)
SENT_END = re.compile(r"[^.!?…\n]+[.!?…]*", re.UNICODE)


def detect_lang(text):
    cyr = len(re.findall(r"[а-яёА-ЯЁ]", text))
    lat = len(re.findall(r"[a-zA-Z]", text))
    return "ru" if cyr >= lat else "en"


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


def snippet(text, start, end, pad=30):
    a = max(0, start - pad)
    b = min(len(text), end + pad)
    s = text[a:b].replace("\n", " ⏎ ")
    return ("…" if a > 0 else "") + s + ("…" if b < len(text) else "")


def sentences(text):
    """Предложения с позициями. Строка без точки тоже считается предложением."""
    out = []
    for m in SENT_END.finditer(text):
        s = m.group(0).strip()
        if WORD.search(s):
            out.append((m.start() + (len(m.group(0)) - len(m.group(0).lstrip())), s))
    return out


# --- проверки ----------------------------------------------------------------


def check(text, lang):
    found = []

    def add(level, code, msg, start, end):
        found.append({
            "level": level, "code": code, "message": msg,
            "line": line_of(text, start), "text": snippet(text, start, end),
        })

    # 1. Длинные тире и дефис вместо тире
    for m in re.finditer(r"[—–]|(?<=\S )-(?= )", text):
        add("error", "dash", "Тире. Перестрой фразу без него", m.start(), m.end())

    # 2. Двоеточия (кроме времени, ссылок и смайлов)
    for m in re.finditer(r":", text):
        before, after = text[max(0, m.start() - 6):m.start()], text[m.end():m.end() + 2]
        if re.search(r"\d$", before) and re.match(r"\d", after):
            continue
        if re.search(r"https?$|www$", before) or after.startswith("//"):
            continue
        if re.match(r"[)(DP]", after):
            continue
        add("error", "colon", "Предложение на двоеточии. Скажи то же без него",
            m.start(), m.end())

    # 3. Списки и разметка
    list_lines = list(re.finditer(
        r"(?m)^[ \t]*(?:[-*•▪►→✅✔☑️🔹🔸👉]|\d{1,2}[.)])[ \t]+\S", text))
    if len(list_lines) >= 2:
        for m in list_lines:
            add("warn", "list", "Пункт списка. Нужен ли тут список, или хватит обычных фраз?",
                m.start(), m.end())
    for m in re.finditer(r"(?m)^#{1,6}\s+\S|\*\*[^*\n]+\*\*|__[^_\n]+__", text):
        add("warn", "markup", "Заголовок или жирный текст. В посте обычно не нужен",
            m.start(), m.end())
    for m in re.finditer(r"(?i)(?m)^\s*(?:во-первых|во-вторых|в-третьих|firstly|secondly)\b",
                         text):
        add("error", "academic", "Академическая структура", m.start(), m.end())

    # 4. «No X. No Y.» и «Без X, без Y»
    neg = NEG_RU if lang == "ru" else NEG_EN
    neg_all = NEG_RU | NEG_EN
    chunks = [(m.start(), m.group(0)) for m in re.finditer(r"[^.!?,;\n]+", text)
              if WORD.search(m.group(0))]
    i = 0
    while i < len(chunks) - 1:
        w1 = WORD.findall(chunks[i][1])
        w2 = WORD.findall(chunks[i + 1][1])
        a = w1[0].lower() if w1 else ""
        b = w2[0].lower() if w2 else ""
        if a in neg_all and a == b and a not in {"не", "not"} or (
                a in {"не", "not"} and a == b and len(w1) <= 4 and len(w2) <= 4):
            start = chunks[i][0]
            j = i + 1
            while j + 1 < len(chunks):
                w = WORD.findall(chunks[j + 1][1])
                if w and w[0].lower() == a:
                    j += 1
                else:
                    break
            end = chunks[j][0] + len(chunks[j][1])
            add("error", "no-no", "Конструкция «No X. No Y.» / «Без X. Без Y.»", start, end)
            i = j + 1
            continue
        i += 1

    # 5. «не просто X, а Y»
    for pat in (NOT_JUST_RU if lang == "ru" else NOT_JUST_EN):
        for m in re.finditer(pat, text, re.IGNORECASE):
            add("error", "not-just", "Конструкция «не просто X, а Y»", m.start(), m.end())

    # 6. Тройки «X, Y и Z»
    conj = r"(?:и|или|а также)" if lang == "ru" else r"(?:and|or)"
    triple = re.compile(
        r"\b([\w-]+),\s+([\w-]+),?\s+" + conj + r"\s+([\w-]+)\b", re.IGNORECASE)
    for m in triple.finditer(text):
        add("warn", "triple", "Похоже на тройку. Оставь одно самое точное слово или два",
            m.start(), m.end())

    sents = sentences(text)
    # три предложения подряд с одинакового слова
    for k in range(len(sents) - 2):
        firsts = [WORD.findall(s)[0].lower() if WORD.findall(s) else "" for _, s in
                  sents[k:k + 3]]
        if firsts[0] and firsts[0] == firsts[1] == firsts[2] and firsts[0] not in neg_all:
            add("warn", "anaphora", "Три предложения подряд начинаются одинаково",
                sents[k][0], sents[k + 2][0] + len(sents[k + 2][1]))

    # 7. Стоп-фразы и промо-слова
    stop, hype = (STOP_RU, HYPE_RU) if lang == "ru" else (STOP_EN, HYPE_EN)
    for pat in stop:
        for m in re.finditer(r"(?<![\w])" + pat + r"(?![\w])", text, re.IGNORECASE):
            add("error", "stop-phrase", "ИИ-вводная или шаблонная фраза", m.start(), m.end())
    for pat in hype:
        for m in re.finditer(r"(?<![\w])" + pat + r"(?![\w])", text, re.IGNORECASE):
            add("warn", "hype", "Промо-слово или канцелярит. Замени простым словом",
                m.start(), m.end())

    # 8. «Результат? Минус 40%.»
    for k in range(len(sents) - 1):
        pos, s = sents[k]
        if s.endswith("?") and 1 <= len(WORD.findall(s)) <= 3:
            add("warn", "q-a", "Короткий вопрос и сразу ответ. Скажи мысль прямо",
                pos, sents[k + 1][0] + len(sents[k + 1][1]))

    # 9. Ритм: все предложения одной длины
    lens = [len(WORD.findall(s)) for _, s in sents if len(WORD.findall(s)) > 0]
    if len(lens) >= 5:
        mean = statistics.mean(lens)
        cv = statistics.pstdev(lens) / mean if mean else 0
        if cv < 0.3:
            add("warn", "rhythm",
                "Предложения почти одной длины (в среднем %.0f слов). Чередуй короткие и длинные"
                % mean, 0, 0)

    seen, uniq = set(), []
    for f in found:
        key = (f["code"], f["line"]) if f["code"] == "not-just" else (f["code"], f["line"], f["text"])
        if key not in seen:
            seen.add(key)
            uniq.append(f)
    uniq.sort(key=lambda f: (f["line"], f["level"] != "error"))
    return uniq


def main():
    ap = argparse.ArgumentParser(description="Линтер живого текста")
    ap.add_argument("--file", help="файл с текстом (по умолчанию stdin)")
    ap.add_argument("--lang", choices=["ru", "en", "auto"], default="auto")
    ap.add_argument("--json", action="store_true", help="вывод в JSON")
    ap.add_argument("--strict", action="store_true", help="предупреждения тоже дают код 1")
    args = ap.parse_args()

    if args.file:
        with open(args.file, encoding="utf-8") as f:
            text = f.read()
    else:
        text = sys.stdin.read()

    lang = detect_lang(text) if args.lang == "auto" else args.lang
    found = check(text, lang)
    errors = sum(1 for f in found if f["level"] == "error")
    warns = len(found) - errors

    if args.json:
        print(json.dumps({"lang": lang, "errors": errors, "warnings": warns,
                          "findings": found}, ensure_ascii=False, indent=2))
    else:
        if not found:
            print("Чисто: механических признаков ИИ не найдено. Теперь проверь смысл и голос.")
        for f in found:
            mark = "ОШИБКА" if f["level"] == "error" else "внимание"
            print("[%s] строка %d, %s. %s\n    %s" % (mark, f["line"], f["code"],
                                                    f["message"], f["text"]))
        if found:
            print("\nИтого: %d ошибок, %d предупреждений (язык: %s)" % (errors, warns, lang))

    sys.exit(1 if errors or (args.strict and warns) else 0)


if __name__ == "__main__":
    main()
