// static/js/date-mask.js
(function() {
    'use strict';

    function applyDateMask(input) {
        // ✅ Убираем блокировку, чтобы маска перезапускалась при сбое
        // if (input.dataset.maskApplied) return;

        // Настройка поля
        input.removeAttribute('min');
        input.removeAttribute('max');
        input.removeAttribute('pattern');
        input.removeAttribute('step');
        input.type = 'text';
        input.placeholder = 'дд.мм.гггг';
        input.setAttribute('inputmode', 'numeric');
        input.setAttribute('autocomplete', 'off');
        input.dataset.maskApplied = '1';

        // 1. Инициализация при загрузке
        let val = input.value.trim();
        if (val && /^\d{4}-\d{2}-\d{2}$/.test(val)) {
            const [y, m, d] = val.split('-');
            input.value = `${d}.${m}.${y}`;
        } else if (val && val.length === 6 && /^\d{6}$/.test(val)) {
            // Если пришло 180826, сразу преобразуем в 18.08.26
            const d = val.slice(0, 2);
            const m = val.slice(2, 4);
            const y = val.slice(4, 6);
            input.value = `${d}.${m}.${y}`;
        }

        // 2. Блокировка ввода не-цифр
        input.addEventListener('keydown', function(e) {
            const allowed = ['Backspace', 'Delete', 'ArrowLeft', 'ArrowRight', 'Tab'];
            if (allowed.includes(e.key)) return;
            if (!/^\d$/.test(e.key) && e.key !== '.' && e.key !== '/') {
                e.preventDefault();
            }
        });

        // 3. АВТОМАТИЧЕСКАЯ МАСКА ПРИ ВВОДЕ
        input.addEventListener('input', function(e) {
            let raw = e.target.value.replace(/\D/g, ''); // Оставляем только цифры
            let formatted = '';
            raw = raw.slice(0, 8); // Максимум 8 цифр

            if (raw.length > 0) formatted += raw.slice(0, 2);
            if (raw.length > 2) formatted += '.' + raw.slice(2, 4);
            if (raw.length > 4) formatted += '.' + raw.slice(4, 8);

            // Обновляем, только если изменилось (избегаем бесконечного цикла)
            if (e.target.value !== formatted) {
                e.target.value = formatted;
            }
        });

        // 4. Превращение короткого года в полный
        function normalizeYear(year) {
            if (year >= 0 && year <= 99) {
                if (year >= 70 && year <= 99) return year + 1900;
                return year + 2000;
            }
            return year;
        }

        input.addEventListener('blur', function(e) {
            const parts = e.target.value.trim().split('.');
            if (parts.length === 3 && parts[2].length === 2) {
                let year = parseInt(parts[2], 10);
                year = normalizeYear(year);
                e.target.value = `${parts[0]}.${parts[1]}.${year}`;
            }
        });

        // 5. Безопасная отправка формы
        const form = input.closest('form');
        if (form) {
            form.addEventListener('submit', function() {
                const parts = input.value.trim().split('.');
                if (parts.length === 3) {
                    let year = parseInt(parts[2], 10);
                    if (year >= 0 && year <= 99) {
                        year = normalizeYear(year);
                        input.value = `${parts[0]}.${parts[1]}.${year}`;
                    }
                }
            });
        }
    }

    function initAllDateInputs() {
        document.querySelectorAll('input[data-date-input="true"]').forEach(applyDateMask);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAllDateInputs);
    } else {
        initAllDateInputs();
    }

    setInterval(initAllDateInputs, 500);
})();