# Протокол «Конспект» — розділ G

Читай цей файл лише тоді, коли в `queue.json` є відповідний список. Загальні правила — у `../CLAUDE.md`.

## G. Умови заліку — `queue.json → zaliczenie` і `subjects/<id>/zaliczenie.json` (2.3)
Джерела: `memory.md → Terminy i zaliczenie`, `materials.json`, слайди «Charakterystyka/Karta przedmiotu» у `files/`. Нічого не вигадуй:
чого немає в джерелах — не пиши (порожній `min`, без етапу). Запиши атомарно:
```
{"updated_at":"<ISO>","formula":"0,3·L + 0,3·P + 0,4·E (кожна > 2,0)",
 "components":[{"id":"L","name":"Laboratorium","weight":0.3,"min":3.0,"note":"лаби 1–7"}],
 "milestones":[{"date":"2026-11-03","title":"Filozofowie — oddanie","component":"P"}],
 "notes":"1–2 речення, якщо щось неоднозначне"}
```
`weight` — частка (0–1), `min` — найнижча прохідна оцінка частини (у Польщі «> 2» = 3,0), `id` — коротко (L, P, E, T, K).
Оцінки вписує студент сам у застосунку (`grades.json`) — їх не чіпай.
