// static/js/group-time-autofill.js v7
(function() {
    'use strict';
    console.log('🚀 group-time-autofill.js v7 загружен');

    const TIME_MAP = {
        'weekday:morning': '08:40–13:30',
        'weekday:evening': '17:30–21:15',
        'weekend:any': '13:30–18:20'
    };

    window.fillStandardTime = function(start, end) {
        const s = document.getElementById('id_time_start');
        const e = document.getElementById('id_time_end');
        if (s && e) {
            s.value = start; e.value = end;
            console.log('✅ Время подставлено:', start, '-', end);
        }
    };

    function getVal(id) {
        const el = document.getElementById(id);
        return el ? el.value.trim() : '';
    }

    function update() {
        const sched = getVal('id_schedule_type');
        const sess = getVal('id_time_session');

        // Проверяем, изменились ли значения реально
        const currentKey = `${sched}|${sess}`;
        if (window._lastCalc === currentKey) return; // Без изменений — не перерисовываем
        window._lastCalc = currentKey;

        console.log('🔄 Пересчёт по:', { schedule_type: sched, time_session: sess });

        let key = null;
        if (sched === 'weekend') key = 'weekend:any';
        else if (sess === 'morning' || sess === 'evening') key = `weekday:${sess}`;

        const timeStr = TIME_MAP[key] || null;
        const box = document.querySelector('.field-standard_time_display .readonly') ||
                    document.querySelector('.field-standard_time_display > div');

        if (!box) return;

        if (!timeStr) {
            box.innerHTML = '<span style="color:#94a3b8;">Выберите Смену или Тип расписания</span>';
        } else {
            const [s, e] = timeStr.split('–');
            box.innerHTML = `
                <strong>${timeStr}</strong>
                <button type="button" onclick="window.fillStandardTime('${s}', '${e}')"
                        style="margin-left:10px;padding:4px 10px;background:#4facfe;color:white;border:none;border-radius:4px;cursor:pointer;font-size:12px;">
                    ▶ Заполнить
                </button>
            `;
            console.log('✅ Обновлено:', timeStr);
        }
    }

    // 🔹 Прямая привязка событий
    function bindEvents() {
        const fields = ['id_schedule_type', 'id_time_session', 'id_duration'];
        fields.forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.onchange = update;
                el.oninput = update; // Для некоторых браузеров/мобильных
                console.log(`🔗 Слушаю изменения: ${id}`);
            }
        });
    }

    // 🔹 Запуск после полной отрисовки
    document.addEventListener('DOMContentLoaded', () => {
        setTimeout(bindEvents, 300);
        setTimeout(bindEvents, 1000);
        setTimeout(update, 500);
    });

    // 🔹 Фолбэк: лёгкий polling (проверяет значения каждые 500мс, обновляет ТОЛЬКО при изменении)
    setInterval(update, 500);
})();