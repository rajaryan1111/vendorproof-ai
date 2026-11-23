import re
import unicodedata
from datetime import date,datetime


def spaces(value):
    return " ".join(unicodedata.normalize("NFC",value).casefold().split())


def company(value,suffixes):
    # Word boundaries matter: A-B never becomes AB. Preserve ampersands and digits.
    text=spaces(re.sub(r"[.,]", " ",value))
    for alias,canonical in sorted(suffixes.items(),key=lambda item:-len(item[0])):
        alias=spaces(alias)
        if text.endswith(" "+alias):
            return text[:-len(alias)]+spaces(canonical)
    return text


def address(value):
    text=spaces(value.replace(","," "))
    return re.sub(r"\b(rd|st|ave)\.?(?= |$)",lambda m:{"rd":"road","st":"street","ave":"avenue"}[m[1]],text)


def identifier(value,scheme):
    if scheme=="uk_company":
        compact=re.sub(r"\s+","",value).upper()
        return compact if re.fullmatch(r"(?:[A-Z]{2}[0-9]{6}|[0-9]{8})",compact) else None
    return value.strip() or None


def calendar_date(value):
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}",value):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    for fmt in ("%d %B %Y","%d %b %Y"):
        try:
            return datetime.strptime(value,fmt).date()
        except ValueError:
            pass
    m=re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})",value)
    if m:
        a,b,y=map(int,m.groups())
        if min(a,b)<=12<max(a,b):
            try:
                return date(y,min(a,b),max(a,b))
            except ValueError:
                pass
    return None
