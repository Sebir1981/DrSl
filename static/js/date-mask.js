// static/js/date-mask.js
(function() {
    'use strict';

    function applyDateMask(input) {
        if (input.dataset.maskApplied) return;

        // Убираем браузерные ограничения
        input.removeAttribute('min');
        input.removeAttribute('max');
        input.removeAttribute('pattern');
        input.removeAttribute('step');
        input.type = 'text';
        input.placeholder = 'дд.мм.гггг';
        input.setAttribute('inputmode', 'numeric');
        input.setAttribute('autocomplete', 'off');
        input.dataset.maskApplied = '1';

        // Автоконвертация ГГГГ-ММ-ДД → ДД.ММ.ГГГГ
        let val = input.value.trim();
        if (val && /^\d{4}-\d{2}-\d{2}$/.test(val)) {
            const [y, m, d] = val.split('-');
            input.value = `${d}.${m}.${y}`;
        }

        // Только цифры и разделители
        input.addEventListener('keydown', function(e) {
            const allowed = ['Backspace', 'Delete', 'ArrowLeft', 'ArrowRight', 'Tab'];
            if (allowed.includes(e.key)) return;
            if (!/^\d$/.test(e.key) && e.key !== '.' && e.key !== '/') {
                e.preventDefault();
            }
        });

        // Автоформатирование: дд.мм.гггг
        input.addEventListener('input', function(e) {
            let digits = e.target.value.replace(/\D/g, '').slice(0, 8);
            let formatted = '';
            if (digits.length > 0) formatted += digits.slice(0, 2);
            if (digits.length > 2) formatted += '.' + digits.slice(2, 4);
            if (digits.length > 4) formatted += '.' + digits.slice(4, 8);
            e.target.value = formatted;
        });

        // Валидация при потере фокуса
        input.addEventListener('blur', function(e) {
            const val = e.target.value.trim();
            if (!val || val.replace(/\./g, '').length < 8) return;

            const parts = val.split('.');
            if (parts.length !== 3) { e.target.value = ''; return; }

            const day = parseInt(parts[0], 10);
            const month = parseInt(parts[1], 10);
            const year = parseInt(parts[2], 10);
            const currentYear = new Date().getFullYear();

            if (year < 1900 || year > currentYear + 10) {
                input.setCustomValidity(`Год: 1900–${currentYear + 10}`);
                input.reportValidity();
                e.target.value = '';
                return;
            }
            if (month < 1 || month > 12) {
                input.setCustomValidity('Месяц: 01–12');
                input.reportValidity();
                e.target.value = '';
                return;
            }
            const daysInMonth = new Date(year, month, 0).getDate();
            if (day < 1 || day > daysInMonth) {
                input.setCustomValidity(`В ${month}-м месяце ${year} г. максимум ${daysInMonth} дней`);
                input.reportValidity();
                e.target.value = '';
                return;
            }
            input.setCustomValidity('');
            e.target.value = `${String(day).padStart(2, '0')}.${String(month).padStart(2, '0')}.${year}`;
        });
    }

    function initAllDateInputs() {
        document.querySelectorAll('input.vDateField, input.ru-date-input').forEach(applyDateMask);
    }

    document.addEventListener('DOMContentLoaded', initAllDateInputs);
    document.addEventListener('shown.bs.tab', initAllDateInputs);
    document.addEventListener('shownTab', initAllDateInputs);
    setTimeout(initAllDateInputs, 100);

    if (window.MutationObserver) {
        const observer = new MutationObserver(initAllDateInputs);
        observer.observe(document.body, { childList: true, subtree: true });
    }
})();