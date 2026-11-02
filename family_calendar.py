# לוח האירועים המשפחתי: התאריך העברי של היום, וימי ההולדת וימי הנישואים ב-7 הימים הקרובים.
# החישוב נעשה כאן בקוד, ולא על ידי המודל: חיפוש וקטורי לא יודע לשלוף "כל מי שחוגג השבוע",
# ומודלי שפה טועים בחישובים של תאריכים עבריים.
# התאריכים נקראים ישירות מקבצי האנשים בתיקייה data, כך שאין כפילות: מעדכנים תאריך רק בקובץ של האדם.

import os
import re
import datetime
from pyluach import dates, hebrewcal

# שמות החודשים כפי שהם כתובים בקבצים, ומספר החודש ב-pyluach (ניסן = 1 ... אדר / אדר א' = 12, אדר ב' = 13)
MONTHS = {
    "תשרי": 7, "חשוון": 8, "חשון": 8, "מרחשוון": 8, "כסלו": 9, "טבת": 10, "שבט": 11,
    "אדר א'": 14, "אדר ב'": 13, "אדר": 12,  # 14 = אדר א' שנכתב במפורש (בקוד בלבד)
    "ניסן": 1, "אייר": 2, "סיון": 3, "סיוון": 3, "תמוז": 4, "אב": 5, "אלול": 6,
}
# החודשים הארוכים ראשונים, כדי ש"אדר ב'" לא ייקרא כ"אדר"
MONTH_PATTERN = "|".join(sorted((re.escape(m) for m in MONTHS), key=len, reverse=True))
# יום בחודש באותיות (ח', י"ג, כ"ה, ל') ואחריו שם החודש
DATE_PATTERN = r"([א-ת](?:[\"״][א-ת]|['׳])?)\s+(" + MONTH_PATTERN + r")(?![א-ת])"

LETTER_VALUES = {"א": 1, "ב": 2, "ג": 3, "ד": 4, "ה": 5, "ו": 6, "ז": 7, "ח": 8, "ט": 9,
                 "י": 10, "כ": 20, "ל": 30}
WEEKDAYS = ["", "יום ראשון", "יום שני", "יום שלישי", "יום רביעי", "יום חמישי", "יום שישי", "שבת"]
DAYS_AHEAD = 7  # "השבוע" = היום ו-6 הימים הבאים


def parse_date(text):
    """מחזיר (חודש, יום) מתוך טקסט כמו 'כ"ה תמוז', או None אם אין בו תאריך."""
    match = re.search(DATE_PATTERN, text.replace("׳", "'").replace("״", '"'))
    if not match:
        return None
    day = sum(LETTER_VALUES.get(letter, 0) for letter in match.group(1))
    return MONTHS[match.group(2)], day


def clean_name(name):
    """מוריד סוגריים (כינויים, 'תאומים') ותווים מיותרים מהשם."""
    return re.sub(r"\s*\(.*?\)", "", name).strip(" -")


def load_events(data_dir="./data"):
    """קורא את קבצי האנשים ומחזיר רשימת אירועים: (סוג, שמות, חודש, יום)."""
    events = []
    couples = set()  # כדי שיום הנישואים של ההורים לא ייספר פעמיים (מופיע אצל שניהם)
    for file_name in sorted(os.listdir(data_dir)):
        if not file_name.endswith(".txt"):
            continue
        with open(os.path.join(data_dir, file_name), encoding="utf-8") as f:
            lines = [line.strip() for line in f]
        text = "\n".join(lines)
        if "תאריך פטירה:" in text:  # אנשים שנפטרו: לא מחשבים להם ימי הולדת
            continue
        name_match = re.search(r"^שם: (.+)$", text, re.M)
        if not name_match:
            continue
        name = clean_name(name_match.group(1))
        spouse_match = re.search(r"^נשו(?:י|אה) ל: (.+)$", text, re.M)

        for line in lines:
            # תאריך הלידה של האדם עצמו
            if line.startswith("תאריך לידה:"):
                date = parse_date(line)
                if date:
                    events.append(("birthday", name, *date))
            # תאריך הלידה של בן או בת הזוג: "תאריך לידה של X (בעלה): ..."
            elif line.startswith("תאריך לידה של "):
                date = parse_date(line.split(":", 1)[1])
                if date:
                    spouse = clean_name(line[len("תאריך לידה של "):].split(":", 1)[0])
                    events.append(("birthday", spouse, *date))
            # יום הנישואים
            elif line.startswith("יום נישואים:") and spouse_match:
                date = parse_date(line)
                spouse = clean_name(spouse_match.group(1))
                key = frozenset([name, spouse])
                if date and key not in couples:
                    couples.add(key)
                    events.append(("anniversary", f"{name} ו{spouse}", *date))
            # ימי ההולדת של הילדים (נכדים): "- שם: תאריך, בן 5"
            elif line.startswith("- ") and ":" in line:
                child, rest = line[2:].split(":", 1)
                date = parse_date(rest)
                if date:
                    events.append(("birthday", clean_name(child), *date))
    # אדם שמופיע גם בקובץ שלו וגם בקובץ של בן הזוג נספר פעם אחת
    return list(dict.fromkeys(events))


def date_in_year(month, day, year):
    """התאריך שבו חוגגים את האירוע בשנה העברית הנתונה."""
    leap = hebrewcal.Year(year).leap
    if month == 14:                # נולד באדר א': בשנה מעוברת באדר א', בשנה פשוטה באדר
        month = 12
    elif month == 13 and not leap:  # נולד באדר ב': בשנה פשוטה חוגגים באדר
        month = 12
    elif month == 12 and leap:     # נולד באדר (בשנה פשוטה): בשנה מעוברת חוגגים באדר ב'
        month = 13
    try:
        return dates.HebrewDate(year, month, day)
    except ValueError:
        # יום ל' בחודש שיש בו השנה רק 29 ימים: חוגגים בא' בחודש הבא
        return dates.HebrewDate(year, month, 29) + 1


def today_in_israel():
    try:
        from zoneinfo import ZoneInfo
        return datetime.datetime.now(ZoneInfo("Asia/Jerusalem")).date()
    except Exception:
        return datetime.date.today()


def upcoming(events, today=None):
    """האירועים שחלים היום ובשישה הימים הבאים, לפי הסדר."""
    start = dates.HebrewDate.from_pydate(today or today_in_israel())
    window = [start + i for i in range(DAYS_AHEAD)]
    result = []
    for kind, names, month, day in events:
        for i, hebrew_day in enumerate(window):
            target = date_in_year(month, day, hebrew_day.year)
            if target == hebrew_day:
                result.append((i, kind, names, hebrew_day))
                break
    return sorted(result, key=lambda item: item[0])


def when(days_from_today):
    if days_from_today == 0:
        return "היום"
    if days_from_today == 1:
        return "מחר"
    return f"בעוד {days_from_today} ימים"


def calendar_text(events, today=None):
    """הטקסט שמצורף להקשר בכל שאלה."""
    today = today or today_in_israel()
    hebrew_today = dates.HebrewDate.from_pydate(today)
    lines = [
        "לוח אירועים מחושב (מדויק, לא לחשב תאריכים בעצמך):",
        f"היום: {WEEKDAYS[hebrew_today.weekday()]}, {hebrew_today.hebrew_date_string()} ({today.day}.{today.month}.{today.year}).",
    ]
    found = upcoming(events, today)
    for kind, title in (("birthday", "ימי הולדת"), ("anniversary", "ימי נישואים")):
        items = [f"{names}: {d.hebrew_day()} {d.month_name(True)}, {WEEKDAYS[d.weekday()]} ({when(i)})"
                 for i, k, names, d in found if k == kind]
        if items:
            lines.append(f"{title} ב-7 הימים הקרובים: " + "; ".join(items) + ".")
        else:
            lines.append(f"אין {title} ב-7 הימים הקרובים.")
    return "\n".join(lines)


# --- החיבור ל-LlamaIndex ---
# מוסיף את לוח האירועים כמקטע נוסף לכל תוצאת חיפוש, כך שהמודל מקבל אותו יחד עם המידע מהמאגר.
# כך הוא מופיע גם ברשימת המקורות שמודפסת בטרמינל.
from llama_index.core.postprocessor.types import BaseNodePostprocessor
from llama_index.core.schema import NodeWithScore, TextNode

_events = None


class CalendarPostprocessor(BaseNodePostprocessor):
    def _postprocess_nodes(self, nodes, query_bundle=None):
        global _events
        if _events is None:  # הקבצים נקראים פעם אחת, בשאלה הראשונה
            _events = load_events()
        calendar_node = TextNode(text=calendar_text(_events), metadata={"file_name": "לוח_אירועים_מחושב"})
        return list(nodes) + [NodeWithScore(node=calendar_node, score=1.0)]


if __name__ == "__main__":
    # בדיקה מהירה: python family_calendar.py
    all_events = load_events()
    print("נמצאו", len(all_events), "אירועים בקבצים")
    print(calendar_text(all_events))
