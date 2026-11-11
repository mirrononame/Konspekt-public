from app import study

ORG = [
    "Do kiedy trzeba oddać sprawozdanie?", "Kiedy jest egzamin z SK?", "Kiedy kolokwium?",
    "Następna laba UCiSW (za 2 tygodnie)", "Co będzie na następnym wykładzie?", "W jakiej sali jest wykład?",
    "Ile punktów za kolokwium?", "Коли буде іспит?", "До якого числа здати звіт?", "Когда экзамен?",
    "When is the exam?", "Czy na wykładzie jest lista obecności?", "Jaka jest ocena końcowa z przedmiotu?",
]
KNOW = [
    "Kiedy firma potrzebuje łącza symetrycznego?", "Kiedy algorytm Bresenhama wybiera piksel NE?",
    "When is a class abstract?", "Коли система здатна обробити запит?", "Kiedy stosujemy sygnał wewnętrzny zamiast inout?",
    "Jak prowadzący chce zapisać pobudzenie w test benchu?", "Pasmo VoIP mierzymy na zajęciach, zestawiając połączenie w sali.",
    "Ułóż kroki algorytmu skanowania linii", "Co oznacza 'X' w std_logic?", "Когда процесс переходит в состояние ожидания?",
]


def test_org_detected():
    for q in ORG:
        assert study.is_org({"type": "flip", "q": q, "a": "x"}), q


def test_knowledge_kept():
    for q in KNOW:
        assert not study.is_org({"type": "flip", "q": q, "a": "x"}), q


def test_kind_org():
    assert study.is_org({"type": "flip", "q": "Cokolwiek", "kind": "org"})
