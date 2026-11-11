# Протокол «Конспект» — розділ B

Читай цей файл лише тоді, коли в `queue.json` є відповідний список. Загальні правила — у `../CLAUDE.md`.

## B. План тем предмета `subjects/<id>/`
Прочитай `files/` (скріншоти ePortalu, силабус) і `materials.json.links`, врахуй `parse_instructions`.
Запиши `plan.json` (атомарно):
`{"updated_at":"<ISO зараз>","source":"claude","items":[{"date":"YYYY-MM-DD","title":"Тема","topics":["…"],"links":[{"title":"…","url":"…"}]}]}`
Якщо дат немає — постав дати занять за `schedule.json` по черзі або залиш `""`.
`updated_at` має бути пізніше за `parse_requested_at`. **Не редагувати `materials.json`.**
