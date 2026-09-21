// static/js/date-mask.js
(function () {
    'use strict';

    if (window.__dateMaskInitialized) return;
    window.__dateMaskInitialized = true;

    // Есть ли в этом браузере beforeinput (Safari < 14, IE11, старые WebView — нет)
    const BEFOREINPUT_SUPPORTED = (function () {
        try { return 'onbeforeinput' in document.createElement('input'); }
        catch (e) { return false; }
    })();

    // =========================================================================
    // 🔹 Инъекция CSS
    // =========================================================================
    function injectDateMaskStyles() {
        if (window.__dateMaskStylesInjected) return;
        window.__dateMaskStylesInjected = true;

        const style = document.createElement('style');
        style.textContent = `
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
            @keyframes dateShake {
                0%, 100% { transform: translateX(0); }
                25% { transform: translateX(-4px); }
                75% { transform: translateX(4px); }
            }
            .date-invalid-wrapper {
                position: relative;
                display: inline-block;
                width: 100%;
            }
            /* Тултип рисуем только если реально есть data-date-error, иначе
               при фокусе на валидном поле всплывал бы пустой красный блок */
            .date-invalid-wrapper[data-date-error]::after {
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
            .date-invalid-wrapper[data-date-error]:hover::after,
            .date-invalid-wrapper[data-date-error]:focus-within::after { opacity: 1; }
            .date-invalid-wrapper[data-date-error]::before {
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
            .date-invalid-wrapper[data-date-error]:hover::before,
            .date-invalid-wrapper[data-date-error]:focus-within::before { opacity: 1; }
        `;
        document.head.appendChild(style);
    }

    // =========================================================================
    // 🔹 Утилиты
    // =========================================================================
    const onlyDigits = (str) => (str || '').replace(/\D/g, '');

    function normalizeYear(year) {
        if (year < 100) {
            return year >= 70 ? year + 1900 : year + 2000;
        }
        return year;
    }

    function isValidDate(day, month, year) {
        if (isNaN(day) || isNaN(month) || isNaN(year)) return false;
        if (day < 1 || day > 31) return false;
        if (month < 1 || month > 12) return false;

        const fullYear = normalizeYear(year);
        if (fullYear < 1970 || fullYear > 2099) return false;

        const daysInMonth = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
        if ((fullYear % 4 === 0 && fullYear % 100 !== 0) || fullYear % 400 === 0) {
            daysInMonth[1] = 29;
        }
        return day <= daysInMonth[month - 1];
    }

    // Идемпотентно: не трогает DOM, если состояние ошибки не поменялось —
    // при быстром наборе это заметно снижает число layout/paint операций.
    function showError(input, message) {
        const wrap = input.parentElement;
        const already = input.classList.contains('date-invalid') &&
            wrap && wrap.getAttribute('data-date-error') === message;
        if (already) return;

        input.classList.add('date-invalid');
        input.setAttribute('aria-invalid', 'true');
        if (wrap && wrap.classList.contains('date-invalid-wrapper')) {
            wrap.setAttribute('data-date-error', message);
        }
    }

    function clearError(input) {
        const alreadyClear = !input.classList.contains('date-invalid') &&
            input.getAttribute('aria-invalid') === 'false';
        if (alreadyClear) return;

        input.classList.remove('date-invalid');
        input.setAttribute('aria-invalid', 'false');
        const wrap = input.parentElement;
        if (wrap && wrap.classList.contains('date-invalid-wrapper')) {
            wrap.removeAttribute('data-date-error');
        }
    }

    // Чистая проверка по строке цифр длиной 6 (ддммгг) или 8 (ддммгггг)
    function checkDateDigits(digits) {
        const day = parseInt(digits.slice(0, 2), 10);
        const month = parseInt(digits.slice(2, 4), 10);

        let year;
        if (digits.length >= 8) {
            year = parseInt(digits.slice(4, 8), 10);
        } else {
            year = normalizeYear(parseInt(digits.slice(4, 6), 10));
        }

        if (!isValidDate(day, month, year)) {
            let msg;
            if (month < 1 || month > 12) msg = '⚠ Месяц должен быть 01–12';
            else if (day < 1 || day > 31) msg = '⚠ День должен быть 01–31';
            else if (year < 1970 || year > 2099) msg = '⚠ Год должен быть 1970–2099';
            else msg = `⚠ В ${String(month).padStart(2, '0')}.${year} нет ${String(day).padStart(2, '0')} числа`;
            return { valid: false, message: msg, day, month, year };
        }
        return { valid: true, message: '', day, month, year };
    }

    // =========================================================================
    // 🔹 Модель сегментов: дд(0-1) . мм(3-4) . гггг(6-9) — фиксированная сетка
    //    из 10 символов. Каждый сегмент — массив цифр или null.
    // =========================================================================
    const stateMap = new WeakMap();

    function emptyState() {
        return { day: [null, null], month: [null, null], year: [null, null, null, null] };
    }

    function fillStateFromDigits(state, digits) {
        digits = onlyDigits(digits).slice(0, 8);
        const c = digits.split('');
        state.day = [c[0] ?? null, c[1] ?? null];
        state.month = [c[2] ?? null, c[3] ?? null];
        state.year = [c[4] ?? null, c[5] ?? null, c[6] ?? null, c[7] ?? null];
    }

    // Пытается распознать распространённые форматы (д.м.гггг, дд/мм/гг, ISO)
    // прежде чем грубо резать в одну кучу цифр — иначе "1.2.3" превратится
    // в бессмысленное "12.3_.___" вместо "01.02.0003"/понятной ошибки.
    function parseInitialValue(initVal) {
        if (/^\d{4}-\d{2}-\d{2}$/.test(initVal)) {
            const [y, m, d] = initVal.split('-');
            return d + m + y;
        }
        const m = initVal.match(/^(\d{1,2})[.\/\-](\d{1,2})[.\/\-](\d{2,4})$/);
        if (m) {
            return m[1].padStart(2, '0') + m[2].padStart(2, '0') + m[3];
        }
        return onlyDigits(initVal);
    }

    function renderValue(state) {
        const isEmpty = state.day.every(c => c == null) &&
            state.month.every(c => c == null) &&
            state.year.every(c => c == null);
        if (isEmpty) return '';
        const d = state.day.map(c => c ?? '_').join('');
        const m = state.month.map(c => c ?? '_').join('');
        const y = state.year.map(c => c ?? '_').join('');
        return `${d}.${m}.${y}`;
    }

    function segStartOf(key) { return key === 'day' ? 0 : key === 'month' ? 3 : 6; }
    function segLenOf(key) { return key === 'year' ? 4 : 2; }

    // Позиция курсора (0..10, "щель" между символами) -> куда попадёт
    // следующий набранный символ. Клик ровно на точке — переход к следующему сегменту.
    function getSegmentAtForTyping(pos) {
        if (pos <= 1) return { key: 'day', offset: pos };
        if (pos === 2) return { key: 'month', offset: 0 };
        if (pos <= 4) return { key: 'month', offset: pos - 3 };
        if (pos === 5) return { key: 'year', offset: 0 };
        if (pos <= 9) return { key: 'year', offset: pos - 6 };
        return { key: 'year', offset: 3 };
    }

    // Индекс символа (0..9) в отрендеренной строке -> сегмент+смещение.
    // Для индексов точек (2 и 5) возвращает null.
    function charIndexToSegment(idx) {
        const map = { 0: ['day', 0], 1: ['day', 1], 3: ['month', 0], 4: ['month', 1], 6: ['year', 0], 7: ['year', 1], 8: ['year', 2], 9: ['year', 3] };
        return map[idx] ? { key: map[idx][0], offset: map[idx][1] } : null;
    }

    // Очищает все цифровые слоты, чьи символьные позиции попадают в [start, end)
    // — используется вместо полного сброса state при вводе/удалении с выделением.
    function clearRange(state, start, end) {
        for (let i = start; i < end; i++) {
            const seg = charIndexToSegment(i);
            if (seg) state[seg.key][seg.offset] = null;
        }
    }

    function clampSegment(state, key, min, max) {
        const arr = state[key];
        if (arr.every(c => c != null)) {
            let val = parseInt(arr.join(''), 10);
            if (val > max) val = max;
            if (val < min) val = min;
            const s = String(val).padStart(2, '0');
            arr[0] = s[0]; arr[1] = s[1];
        }
    }

    // Ввод одной цифры в позицию caret. Возвращает новую позицию курсора.
    function applyDigit(state, caret, digit) {
        if (!/^[0-9]$/.test(digit)) return caret; // защита на случай вызова не из обработчиков ввода

        const seg = getSegmentAtForTyping(caret);
        state[seg.key][seg.offset] = digit;

        const segLen = segLenOf(seg.key);
        if (seg.offset + 1 < segLen) {
            return segStartOf(seg.key) + seg.offset + 1;
        }
        if (seg.key === 'day') { clampSegment(state, 'day', 1, 31); return 3; }
        if (seg.key === 'month') { clampSegment(state, 'month', 1, 12); return 6; }
        return 10; // год заполнен — курсор в конец
    }

    // Backspace: чистит цифру слева от caret (перепрыгивая точку при необходимости)
    function applyBackspace(state, caret) {
        if (caret <= 0) return 0;
        let idx = caret - 1;
        let seg = charIndexToSegment(idx);
        if (!seg) {
            idx -= 1;
            if (idx < 0) return 0;
            seg = charIndexToSegment(idx);
            if (!seg) return caret;
        }
        state[seg.key][seg.offset] = null;
        return idx;
    }

    // Delete: чистит цифру справа от caret (перепрыгивая точку при необходимости)
    function applyDeleteForward(state, caret) {
        if (caret >= 10) return caret;
        let idx = caret;
        let seg = charIndexToSegment(idx);
        let newCaret = caret;
        if (!seg) {
            idx += 1;
            if (idx >= 10) return caret;
            seg = charIndexToSegment(idx);
            if (!seg) return caret;
            newCaret = idx;
        }
        state[seg.key][seg.offset] = null;
        return newCaret;
    }

    function applyStateToInput(input, state, caretPos) {
        input.value = renderValue(state);
        input.setSelectionRange(caretPos, caretPos);
        livePreview(input, state);
    }

    // Живая подсказка об ошибке во время набора. Показываем красную подсветку
    // только когда дата ПОЛНОСТЬЮ введена (день+месяц+4-значный год) — иначе
    // при ещё недописанном годе (например "20" из будущих "2004") пользователь
    // видел бы преждевременную и пугающую ошибку.
    function livePreview(input, state) {
        const dayFull = state.day.every(c => c != null);
        const monthFull = state.month.every(c => c != null);
        const yearFull = state.year.every(c => c != null);

        if (!dayFull || !monthFull || !yearFull) {
            clearError(input);
            return;
        }
        const digits = state.day.join('') + state.month.join('') + state.year.join('');
        const r = checkDateDigits(digits);
        r.valid ? clearError(input) : showError(input, r.message);
    }

    // Финальная проверка: на blur/submit дополняет короткий год (гг -> гггг).
    // Возвращает true/false — валидна ли дата.
    function finalizeValidate(input) {
        const state = stateMap.get(input);
        if (!state) return true;

        const dayFull = state.day.every(c => c != null);
        const monthFull = state.month.every(c => c != null);
        const yearFilled = state.year.filter(c => c != null).length;
        const isEmpty = !dayFull && !monthFull && yearFilled === 0;

        if (isEmpty) { clearError(input); input.value = ''; return true; }

        if (!dayFull || !monthFull || (yearFilled !== 2 && yearFilled !== 4)) {
            showError(input, '⚠ Введите дату полностью: дд.мм.гг или дд.мм.гггг');
            return false;
        }

        const digits = yearFilled === 2
            ? state.day.join('') + state.month.join('') + state.year[0] + state.year[1]
            : state.day.join('') + state.month.join('') + state.year.join('');

        const r = checkDateDigits(digits);
        if (!r.valid) { showError(input, r.message); return false; }

        const dayStr = String(r.day).padStart(2, '0');
        const monthStr = String(r.month).padStart(2, '0');
        const yearStr = String(r.year);
        state.day = [dayStr[0], dayStr[1]];
        state.month = [monthStr[0], monthStr[1]];
        state.year = [yearStr[0], yearStr[1], yearStr[2], yearStr[3]];
        input.value = renderValue(state);
        clearError(input);
        return true;
    }

    // =========================================================================
    // 🔹 Общая логика операций ввода — используется и beforeinput-обработчиком,
    //    и keydown-фолбэком для старых браузеров, чтобы не дублировать код.
    // =========================================================================
    function performInsertDigits(input, state, rawText) {
        const digits = (rawText || '').replace(/[^0-9]/g, '');
        if (!digits) return;

        const start = input.selectionStart;
        const end = input.selectionEnd;
        if (end > start) clearRange(state, start, end); // выделен только кусок — чистим только его

        let caret = start;
        for (const ch of digits) caret = applyDigit(state, caret, ch);
        applyStateToInput(input, state, caret);
    }

    function performBackspace(input, state) {
        const start = input.selectionStart;
        const end = input.selectionEnd;
        if (end > start) {
            clearRange(state, start, end);
            applyStateToInput(input, state, start);
            return;
        }
        applyStateToInput(input, state, applyBackspace(state, start));
    }

    function performDeleteForward(input, state) {
        const start = input.selectionStart;
        const end = input.selectionEnd;
        if (end > start) {
            clearRange(state, start, end);
            applyStateToInput(input, state, start);
            return;
        }
        applyStateToInput(input, state, applyDeleteForward(state, start));
    }

    // =========================================================================
    // 🔹 Современный путь: beforeinput
    // =========================================================================
    function handleBeforeInput(e) {
        const input = e.target;
        const st = stateMap.get(input);
        if (!st) return;
        const type = e.inputType;

        // Undo/redo/cut не блокируем — браузер применит их сам, а рассинхронизацию
        // state с итоговым value поправит fallback-слушатель 'input' ниже.
        if (type === 'historyUndo' || type === 'historyRedo' || type === 'deleteByCut') {
            return;
        }
        if (type === 'insertText' || type === 'insertCompositionText') {
            e.preventDefault();
            performInsertDigits(input, st, e.data);
            return;
        }
        if (type === 'deleteContentBackward') {
            e.preventDefault();
            performBackspace(input, st);
            return;
        }
        if (type === 'deleteContentForward') {
            e.preventDefault();
            performDeleteForward(input, st);
            return;
        }
        // insertFromDrop и всё непредвиденное — блокируем, чтобы не поломать state
        e.preventDefault();
    }

    // =========================================================================
    // 🔹 Фолбэк для браузеров без beforeinput (Safari < 14, IE11, старые WebView)
    // =========================================================================
    const NAV_KEYS = ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End', 'Tab', 'Shift', 'Alt', 'CapsLock'];

    function handleKeydownFallback(e) {
        const input = e.target;
        const st = stateMap.get(input);
        if (!st) return;
        const key = e.key;

        // Копирование/вставка/undo через Ctrl/Cmd — отдаём браузеру,
        // 'input'-фолбэк ниже пересоберёт state из итогового значения.
        if (e.ctrlKey || e.metaKey) return;
        if (NAV_KEYS.includes(key)) return;

        if (/^[0-9]$/.test(key)) {
            e.preventDefault();
            performInsertDigits(input, st, key);
            return;
        }
        if (key === 'Backspace') {
            e.preventDefault();
            performBackspace(input, st);
            return;
        }
        if (key === 'Delete') {
            e.preventDefault();
            performDeleteForward(input, st);
            return;
        }
        if (key.length === 1) {
            e.preventDefault(); // блокируем остальные печатаемые символы
        }
    }

    // =========================================================================
    // 🔹 Применение маски к полю
    // =========================================================================
    function applyDateMask(input) {
        if (input.dataset.maskApplied === '1') return;
        input.dataset.maskApplied = '1';

        input.removeAttribute('min');
        input.removeAttribute('max');
        input.removeAttribute('pattern');
        input.removeAttribute('step');
        input.setAttribute('type', 'text');
        input.setAttribute('inputmode', 'numeric');
        input.setAttribute('autocomplete', 'off');
        input.placeholder = 'дд.мм.гггг';

        if (!input.parentElement.classList.contains('date-invalid-wrapper')) {
            const wrapper = document.createElement('div');
            wrapper.className = 'date-invalid-wrapper';
            input.parentNode.insertBefore(wrapper, input);
            wrapper.appendChild(input);
        }

        const state = emptyState();
        const initVal = input.value.trim();
        if (initVal) {
            fillStateFromDigits(state, parseInitialValue(initVal));
        }
        stateMap.set(input, state);
        input.value = renderValue(state);
        finalizeValidate(input);

        if (BEFOREINPUT_SUPPORTED) {
            input.addEventListener('beforeinput', handleBeforeInput);
        } else {
            input.addEventListener('keydown', handleKeydownFallback);
        }

        // Вставка из буфера — заменяет собой всю дату целиком, как и раньше
        input.addEventListener('paste', function (e) {
            const st = stateMap.get(input);
            if (!st) return;
            e.preventDefault();
            const text = (e.clipboardData || window.clipboardData).getData('text');
            const digits = onlyDigits(text).slice(0, 8);
            if (!digits) return;
            fillStateFromDigits(st, digits);
            applyStateToInput(input, st, renderValue(st).length);
            if (digits.length >= 6) finalizeValidate(input);
        });

        // Подстраховка: если значение поменялось в обход наших обработчиков
        // (автозаполнение браузера, undo/redo, cut, IME в фолбэк-режиме) —
        // пересобираем состояние из итоговой строки, а не оставляем его битым.
        input.addEventListener('input', function () {
            const st = stateMap.get(input);
            if (!st) return;
            if (input.value === renderValue(st)) return; // это наша же программная запись
            fillStateFromDigits(st, onlyDigits(input.value));
            applyStateToInput(input, st, renderValue(st).length);
        });

        input.addEventListener('blur', function (e) {
            if (e.target.value.trim() !== '') finalizeValidate(e.target);
        });

        const form = input.closest('form');
        if (form && !form.dataset.dateMaskBound) {
            form.dataset.dateMaskBound = '1';
            form.addEventListener('submit', function (e) {
                const dateInputs = form.querySelectorAll('input[data-date-input="true"]');
                let hasInvalid = false;
                dateInputs.forEach(function (inp) {
                    if (inp.value.trim() === '') { clearError(inp); return; }
                    if (!finalizeValidate(inp)) hasInvalid = true;
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
    // 🔹 Инициализация + MutationObserver (сканирует только добавленные узлы,
    //    а не весь document на каждую мутацию — важно на страницах с сотнями полей)
    // =========================================================================
    function initAllDateInputs(root) {
        (root || document).querySelectorAll('input[data-date-input="true"]').forEach(applyDateMask);
    }

    function startObserver() {
        const observer = new MutationObserver(function (mutations) {
            for (const m of mutations) {
                if (m.type !== 'childList' || m.addedNodes.length === 0) continue;
                m.addedNodes.forEach(function (node) {
                    if (node.nodeType !== 1) return;
                    if (node.matches && node.matches('input[data-date-input="true"]')) {
                        applyDateMask(node);
                    }
                    initAllDateInputs(node);
                });
            }
        });
        observer.observe(document.body, { childList: true, subtree: true });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            injectDateMaskStyles();
            initAllDateInputs();
            startObserver();
        });
    } else {
        injectDateMaskStyles();
        initAllDateInputs();
        startObserver();
    }
})();