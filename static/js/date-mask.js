// static/js/date-mask.js
(function() {
    'use strict';

    // =========================================================================
    // 🔹 Инъекция CSS-стилей (выполняется один раз)
    // =========================================================================
    function injectDateMaskStyles() {
        if (window.__dateMaskStylesInjected) return;
        window.__dateMaskStylesInjected = true;

        const style = document.createElement('style');
        style.textContent = `
            /* 🔹 Подсветка некорректной даты */
            .date-invalid {
                border-color: #dc2626 !important;
                background-color: #fef2f2 !important;
                animation: dateShake 0.3s ease-in-out;
            }
            .date-invalid:focus {
                outline: none;
                border-color: #dc2626 !important;
                box-shadow: 0 0 0 3px rgba(220, 38, 38, 0.15) !important;
            }

            /* 🔹 Лёгкая тряска при ошибке */
            @keyframes dateShake {
                0%, 100% { transform: translateX(0); }
                25% { transform: translateX(-4px); }
                75% { transform: translateX(4px); }
            }

            /* 🔹 Подсказка-тултип через псевдоэлемент */
            .date-invalid-wrapper {
                position: relative;
            }
            .date-invalid-wrapper::after {
                content: attr(data-date-error);
                position: absolute;
                top: calc(100% + 4px);
                left: 0;
                background: #dc2626;
                color: white;
                padding: 4px 10px;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 500;
                white-space: nowrap;
                z-index: 1000;
                box-shadow: 0 4px 12px rgba(220, 38, 38, 0.2);
                opacity: 0;
                pointer-events: none;
                transition: opacity 0.2s;
            }
            .date-invalid-wrapper:hover::after {
                opacity: 1;
            }
            .date-invalid-wrapper::before {
                content: '';
                position: absolute;
                top: calc(100% + 0px);
                left: 12px;
                border: 4px solid transparent;
                border-bottom-color: #dc2626;
                opacity: 0;
                pointer-events: none;
                transition: opacity 0.2s;
                z-index: 1000;
            }
            .date-invalid-wrapper:hover::before {
                opacity: 1;
            }
        `;
        document.head.appendChild(style);
    }

    // =========================================================================
    // 🔹 Применение маски к полю
    // =========================================================================
    function applyDateMask(input) {
        // Защита от повторного применения к одному полю
        if (input.dataset.maskApplied === '1') return;

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

        // Оборачиваем поле для красивого tooltip (если ещё не обёрнуто)
        if (!input.parentElement.classList.contains('date-invalid-wrapper')) {
            const wrapper = document.createElement('div');
            wrapper.className = 'date-invalid-wrapper';
            wrapper.style.position = 'relative';
            wrapper.style.display = 'inline-block';
            wrapper.style.width = '100%';
            input.parentNode.insertBefore(wrapper, input);
            wrapper.appendChild(input);
        }

        // 1. Инициализация при загрузке
        let val = input.value.trim();
        if (val && /^\d{4}-\d{2}-\d{2}$/.test(val)) {
            const [y, m, d] = val.split('-');
            input.value = `${d}.${m}.${y}`;
        } else if (val && val.length === 6 && /^\d{6}$/.test(val)) {
            const d = val.slice(0, 2);
            const m = val.slice(2, 4);
            const y = val.slice(4, 6);
            input.value = `${d}.${m}.${y}`;
        }

        // 2. Блокировка ввода не-цифр
        input.addEventListener('keydown', function(e) {
            const allowed = ['Backspace', 'Delete', 'ArrowLeft', 'ArrowRight', 'Tab', 'Home', 'End'];
            if (allowed.includes(e.key)) return;
            if (!/^\d$/.test(e.key) && e.key !== '.' && e.key !== '/') {
                e.preventDefault();
            }
        });

        // 3. Автоматическая маска при вводе
        input.addEventListener('input', function(e) {
            let raw = e.target.value.replace(/\D/g, '');
            let formatted = '';
            raw = raw.slice(0, 8);

            if (raw.length > 0) formatted += raw.slice(0, 2);
            if (raw.length > 2) formatted += '.' + raw.slice(2, 4);
            if (raw.length > 4) formatted += '.' + raw.slice(4, 8);

            if (e.target.value !== formatted) {
                e.target.value = formatted;
            }

            // Снимаем класс ошибки при вводе
            clearError(input);
        });

        // 4. Проверка корректности даты
        function isValidDate(day, month, year) {
            if (isNaN(day) || isNaN(month) || isNaN(year)) return false;
            if (day < 1 || day > 31) return false;
            if (month < 1 || month > 12) return false;
            if (year < 1900 || year > 2100) return false;

            const daysInMonth = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];

            // Високосный год
            if ((year % 4 === 0 && year % 100 !== 0) || (year % 400 === 0)) {
                daysInMonth[1] = 29;
            }

            return day <= daysInMonth[month - 1];
        }

        function normalizeYear(year) {
            if (year >= 0 && year <= 99) {
                return (year >= 70 && year <= 99) ? year + 1900 : year + 2000;
            }
            return year;
        }

        function showError(input, message) {
            input.classList.add('date-invalid');
            if (input.parentElement && input.parentElement.classList.contains('date-invalid-wrapper')) {
                input.parentElement.setAttribute('data-date-error', message);
            }
        }

        function clearError(input) {
            input.classList.remove('date-invalid');
            if (input.parentElement && input.parentElement.classList.contains('date-invalid-wrapper')) {
                input.parentElement.removeAttribute('data-date-error');
            }
        }

        function validateAndFormat(input) {
            const value = input.value.trim();
            if (!value) {
                clearError(input);
                return true; // Пустое поле — валидно
            }

            const parts = value.split('.');
            if (parts.length !== 3) {
                showError(input, '⚠ Формат: дд.мм.гггг');
                return false;
            }

            let day = parseInt(parts[0], 10);
            let month = parseInt(parts[1], 10);
            let year = parseInt(parts[2], 10);

            // Нормализация короткого года
            year = normalizeYear(year);

            if (!isValidDate(day, month, year)) {
                let errorMsg = '⚠ Некорректная дата';
                if (month < 1 || month > 12) errorMsg = '⚠ Месяц: 01–12';
                else if (day < 1 || day > 31) errorMsg = '⚠ День: 01–31';
                else errorMsg = `⚠ В ${String(month).padStart(2,'0')}.${year} нет ${String(day).padStart(2,'0')} числа`;

                showError(input, errorMsg);
                return false;
            }

            // Форматируем с полным годом и ведущими нулями
            input.value = `${String(day).padStart(2, '0')}.${String(month).padStart(2, '0')}.${year}`;
            clearError(input);
            return true;
        }

        // 5. Проверка при потере фокуса
        input.addEventListener('blur', function(e) {
            if (e.target.value.trim() !== '') {
                validateAndFormat(e.target);
            }
        });

        // 6. Защита отправки формы
        const form = input.closest('form');
        if (form && !form.dataset.dateMaskBound) {
            form.dataset.dateMaskBound = '1';
            form.addEventListener('submit', function(e) {
                const dateInputs = form.querySelectorAll('input[data-date-input="true"]');
                let hasInvalid = false;

                dateInputs.forEach(function(inp) {
                    if (inp.value.trim() !== '' && !validateAndFormat(inp)) {
                        hasInvalid = true;
                    }
                });

                if (hasInvalid) {
                    e.preventDefault();
                    const firstInvalid = form.querySelector('.date-invalid');
                    if (firstInvalid) {
                        firstInvalid.focus();
                        firstInvalid.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }
                }
            });
        }
    }

    // =========================================================================
    // 🔹 Инициализация всех полей с датами
    // =========================================================================
    function initAllDateInputs() {
        document.querySelectorAll('input[data-date-input="true"]').forEach(applyDateMask);
    }

    // Инжектим стили и запускаем инициализацию
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            injectDateMaskStyles();
            initAllDateInputs();
        });
    } else {
        injectDateMaskStyles();
        initAllDateInputs();
    }

    // Периодическая проверка для динамически добавленных полей
    setInterval(initAllDateInputs, 500);
})();