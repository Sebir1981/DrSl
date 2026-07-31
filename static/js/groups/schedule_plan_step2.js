/**
 * ============================================================================
 * 📦 schedule_plan_step2.js
 * 🏷️  Версия: 0.0.4.27b (Production-Ready: Fixed Initialization & Modal)
 * ✅ Статус: PRODUCTION-READY
 *  Последнее обновление: 2026-07-30
 *
 * 🔹 Исправлено в v0.0.4.27b:
 *    - ✅ Исправлена переменная `subject` → `c.subject` в DOMContentLoaded
 *    - ✅ Фильтрация серверных данных перенесена ПОСЛЕ определения UI
 *    - ✅ ModalController теперь работает корректно
 *
 *  Исправлено в v0.0.4.27:
 *    - ✅ Очистка localStorage при смене программы
 *    - ✅ PROGRAM_ID: приоритет URL → dataset → null
 *    - ✅ Фильтрация серверных данных по предметам программы
 *    - ✅ Логирование мёрджа данных (localStorage → сервер)
 *    - ✅ Оптимизация: batch reset вместо множественных setSubject
 *    - ✅ Валидация PROGRAM_ID (предотвращение коллизий)
 *    - ✅ DEBUG через URL-параметр (?debug=true)
 *    - ✅ Null-check для UI.getSubjectEl()
 *    - ✅ Кэширование ключа StorageManager
 * ============================================================================
 */

// =============================================================================
// 🔹 КОНСТАНТЫ И НАСТРОЙКИ
// =============================================================================

// 🔹 DEBUG управляется через URL: ?debug=true
const DEBUG = new URLSearchParams(window.location.search).get('debug') === 'true';

const CONFIG = {
    MAX_HOURS_PER_DAY: 12,
    STORAGE_PREFIX: 'topicsState_',
    STORAGE_VERSION: 1,
    MED_SUBJECT: 'med',
    SUBJECT_TOTAL: 'total',
    MANUAL_TOPIC_ID: '999',
    EMPTY_VALUE: '',
    ZERO_VALUE: '0',
    DEFAULT_TITLE: 'План-график',
};

// =============================================================================
// 🔹 УТИЛИТЫ И УВЕДОМЛЕНИЯ
// =============================================================================

const debugLog = (...args) => { if (DEBUG) console.log(...args); };

const Notifications = {
    show(message, type = 'info') {
        console.log(`[${type.toUpperCase()}] ${message}`);
        alert(message);
    },
    error(msg) { this.show(msg, 'error'); },
    warn(msg) { this.show(msg, 'warning'); },
    success(msg) { this.show(msg, 'success'); }
};

const toNumber = (value) => {
    if (value === null || value === undefined) return 0;
    if (typeof value === 'string') value = value.replace(',', '.');
    const num = Number(value);
    return isNaN(num) ? 0 : num;
};

function formatHours(value) {
    const num = toNumber(value);
    if (num === 0) return CONFIG.EMPTY_VALUE;
    if (Number.isInteger(num)) return num.toString();
    return num.toFixed(1).replace(',', '.');
}

function roundHalf(value) {
    const num = toNumber(value);
    return Math.round(num * 2) / 2;
}

// =============================================================================
// 🔹 ИНИЦИАЛИЗАЦИЯ ДАННЫХ
// =============================================================================

const PLAN_ID = toNumber(document.getElementById('plan-data-container')?.dataset.planId);

// 🔹 PROGRAM_ID: сначала URL, потом dataset, потом null
const PROGRAM_ID =
    new URLSearchParams(window.location.search).get('program_id')
    || document.getElementById('plan-data-container')?.dataset.programId
    || null;

// 🔹 Валидация PROGRAM_ID
if (!PROGRAM_ID) {
    console.warn('️ PROGRAM_ID не определён! Данные будут сохранены в общий ключ.');
}

let REQUIRED_HOURS = toNumber(document.getElementById('plan-data-container')?.dataset.requiredHours);

debugLog('🔹 PLAN_ID:', PLAN_ID);
debugLog('🔹 PROGRAM_ID:', PROGRAM_ID);
debugLog('🔹 REQUIRED_HOURS:', REQUIRED_HOURS);

// =============================================================================
// 🔹 STORAGE MANAGER
// =============================================================================

const StorageManager = {
    _keyCache: null,

    _getKey() {
        if (this._keyCache) return this._keyCache;

        // 🔹 Валидация: если PROGRAM_ID нет, предупреждаем
        if (!PROGRAM_ID) {
            console.warn('⚠️ PROGRAM_ID is null, using legacy key format');
        }

        const programPart = PROGRAM_ID ? `_program_${PROGRAM_ID}` : '';
        this._keyCache = `${CONFIG.STORAGE_PREFIX}${PLAN_ID}${programPart}_v${CONFIG.STORAGE_VERSION}`;
        return this._keyCache;
    },

    save(dataObj) {
        try { localStorage.setItem(this._getKey(), JSON.stringify(dataObj)); }
        catch (e) { console.error('❌ Storage save failed:', e); }
    },

    load() {
        try {
            const raw = localStorage.getItem(this._getKey());
            return raw && raw !== 'null' ? JSON.parse(raw) : null;
        } catch (e) { console.error('❌ Storage load failed:', e); return null; }
    },

    clear() { localStorage.removeItem(this._getKey()); },

    // 🔹 Новый метод: очистка по ключу (для смены программы)
    clearByKey(key) { localStorage.removeItem(key); }
};

// =============================================================================
// 🔹 STATE MANAGER
// =============================================================================

const StateManager = (() => {
    let _data = {};
    let _cache = null;
    let _isDirty = true;
    let _topicCache = null;

    const _clone = (obj) => {
        try { return structuredClone(obj); }
        catch (e) { return JSON.parse(JSON.stringify(obj)); }
    };

    const _getCache = () => {
        if (!_isDirty && _cache) return _cache;
        const subjectSums = {}, daySums = {}, daySubjectSums = {};
        let grandTotal = 0;
        for (const date in _data) {
            daySubjectSums[date] = {};
            for (const subject in _data[date]) {
                const topics = _data[date][subject];
                if (topics === null) { daySubjectSums[date][subject] = 0; continue; }
                let s = 0;
                for (const key in topics) {
                    if (!isNaN(parseInt(key)) || key === CONFIG.MANUAL_TOPIC_ID) {
                        s += toNumber(topics[key]);
                    }
                }
                daySubjectSums[date][subject] = s;
                if (s > 0) {
                    subjectSums[subject] = (subjectSums[subject] || 0) + s;
                    daySums[date] = (daySums[date] || 0) + s;
                    grandTotal += s;
                }
            }
        }
        _cache = { subjectSums, daySums, daySubjectSums, grandTotal };
        _isDirty = false;
        return _cache;
    };

    const _getTopicCache = () => {
        if (!_isDirty && _topicCache) return _topicCache;
        const topicSums = {};
        for (const date in _data) {
            for (const subject in _data[date]) {
                const topics = _data[date][subject];
                if (topics === null) continue;
                for (const topicId in topics) {
                    if (!isNaN(parseInt(topicId)) || topicId === CONFIG.MANUAL_TOPIC_ID) {
                        const key = `${subject}_${topicId}`;
                        topicSums[key] = (topicSums[key] || 0) + toNumber(topics[topicId]);
                    }
                }
            }
        }
        _topicCache = topicSums;
        return topicSums;
    };

    const _invalidate = () => { _isDirty = true; _cache = null; _topicCache = null; };

    const _getCleanCopy = (obj) => {
        if (!obj) return {};
        const clean = {};
        for (const key in obj) if (obj[key] !== null) clean[key] = _clone(obj[key]);
        return clean;
    };

    return {
        init(initialData = {}) { _data = _clone(initialData); _invalidate(); },
        getData() { const c = {}; for (const d in _data) c[d] = _getCleanCopy(_data[d]); return c; },
        getDay(date) { return _getCleanCopy(_data[date]); },
        getDayRaw(date) { return _clone(_data[date]); },
        setSubject(date, subject, topics) {
            if (!_data[date]) _data[date] = {};
            if (!topics || (typeof topics === 'object' && Object.keys(topics).length === 0)) {
                _data[date][subject] = null;
            } else { _data[date][subject] = _clone(topics); }
            _invalidate();
        },
        clearDay(date) {
            if (!_data[date]) return;
            for (const s in _data[date]) _data[date][s] = null;
            _invalidate();
            if (Object.values(_data[date]).every(v => v === null)) {
                delete _data[date];
            }
        },
        getDaySubjectSum(date, subject) { return _getCache().daySubjectSums[date]?.[subject] || 0; },
        getComputedTotals() { const c = _getCache(); return { subjectSums: c.subjectSums, daySums: c.daySums, grandTotal: c.grandTotal }; },
        getDaySubject(date, subject) {
            const v = _data[date]?.[subject];
            return v === null ? {} : _clone(v || {});
        },
        getTopicSumAcrossDays(subject, topicId, excludeDate = null) {
            const key = `${subject}_${topicId}`;
            const totals = _getTopicCache();
            let sum = totals[key] || 0;
            if (excludeDate && _data[excludeDate]?.[subject]?.[topicId]) {
                sum -= toNumber(_data[excludeDate][subject][topicId]);
            }
            return sum;
        },
        save() { StorageManager.save(_data); },
        load() { const p = StorageManager.load(); if (p) { _data = p; _invalidate(); } return p; },
        clearStorage() { StorageManager.clear(); },

        // 🔹 Batch reset: загружает все данные за один раз
        reset(newData = {}) {
            _data = _clone(newData);
            _invalidate();
        },

        // 🔹 Batch merge: мёржит данные без множественных вызовов setSubject
        mergeData(mergeSource) {
            for (const date in mergeSource) {
                if (!_data[date]) _data[date] = {};
                for (const subject in mergeSource[date]) {
                    _data[date][subject] = _clone(mergeSource[date][subject]);
                }
            }
            _invalidate();
        }
    };
})();

// =============================================================================
//  ЗАГРУЗКА ДАННЫХ (БЕЗ ФИЛЬТРАЦИИ — она будет ПОСЛЕ определения UI)
// =============================================================================

let excludedDates = [];
try { excludedDates = JSON.parse(document.getElementById('plan-data-container')?.dataset.excludedDates || '[]'); }
catch (e) { console.error('⚠️ Ошибка парсинга excludedDates:', e); excludedDates = []; }

let serverTopicsState = {};
try {
    const rawInput = document.getElementById('plan-data-container')?.dataset.topicsState;
    if (rawInput && rawInput !== '{}' && rawInput !== 'null') {
        serverTopicsState = JSON.parse(rawInput);
        // 🔹 Фильтрация отложена до после определения UI
    }
} catch (e) { console.error('⚠️ Ошибка парсинга topicsState:', e); serverTopicsState = {}; }

// 🔹 Инициализируем StateManager с сырыми серверными данными
StateManager.init(serverTopicsState);

// 🔹 Загружаем localStorage и мёржим
const storedLocal = StateManager.load();
if (storedLocal && typeof storedLocal === 'object') {
    debugLog('🔄 Merging localStorage data');
    StateManager.mergeData(storedLocal);
} else {
    debugLog('💾 localStorage empty for this program');
}

/** @type {Object.<string, HTMLInputElement>} */
let cellsMap = {};

// =============================================================================
// 🔹 ЦЕНТРАЛИЗОВАННЫЙ UI КЭШ (ОПРЕДЕЛЯЕТСЯ ЗДЕСЬ)
// =============================================================================

const UI = {
    grandTotal: document.getElementById('grand-total'),
    modalDate: document.getElementById('modal-date'),
    topicModal: document.getElementById('topic-modal'),
    modalContent: document.getElementById('modal-content'),
    modalTotalRequired: document.getElementById('modal-total-required'),
    modalRemainingTotal: document.getElementById('modal-remaining-total'),
    planDataContainer: document.getElementById('plan-data-container'),
    modalCloseBtn: document.getElementById('modal-close-btn'),
    modalCancelBtn: document.getElementById('modal-cancel-btn'),
    modalSaveBtn: document.getElementById('modal-save-btn'),
    hoursForm: document.getElementById('hours-form'),
    deleteModal: document.getElementById('deleteModal'),
    trainingProgramSelect: document.getElementById('training-program-select'),
    programTitleHeader: document.getElementById('program-title-header'),
    exportTypeSelect: document.getElementById('export-type-select'),
    exportBtn: document.getElementById('export-btn'),
    timeStart: document.getElementById('time-start'),
    timeEnd: document.getElementById('time-end'),
    csrfToken: () => document.querySelector('[name=csrfmiddlewaretoken]')?.value,
    /** @param {string} code @returns {{display: HTMLElement|null, hidden: HTMLInputElement|null}} */
    getSubjectEl: (code) => {
        const display = document.getElementById(`${code}-total-display`);
        const hidden = document.getElementById(`${code}-total`);
        return { display, hidden };
    },
    getCategoryInput: () => document.querySelector('[name="category"]'),
    getMedTeacherSelect: () => document.querySelector('select[name="med_teacher"]')
};

// =============================================================================
// 🔹 ФИЛЬТРАЦИЯ СЕРВЕРНЫХ ДАННЫХ (Теперь UI определён!)
// =============================================================================

// 🔹 Фильтруем серверные данные: оставляем только предметы текущей программы
if (PROGRAM_ID && Object.keys(serverTopicsState).length > 0) {
    debugLog('🔍 Filtering server data for program', PROGRAM_ID);
    for (const date in serverTopicsState) {
        for (const subject in serverTopicsState[date]) {
            // 🔹 Null-safe доступ к UI
            const subjectEl = UI.getSubjectEl?.(subject) || { hidden: null };
            if (!subjectEl?.hidden) {
                debugLog(`⚠️ Subject "${subject}" not in program ${PROGRAM_ID}, removing`);
                delete serverTopicsState[date][subject];
            }
        }
        if (Object.keys(serverTopicsState[date] || {}).length === 0) {
            delete serverTopicsState[date];
        }
    }
    // Перезагружаем StateManager с отфильтрованными данными
    StateManager.reset(serverTopicsState);
    debugLog('📦 Filtered server data applied');
}

// =============================================================================
// 🔹 КЭШИ DOM
// =============================================================================

const CellCache = {
    allCells: [],
    dayTotalEls: new Map(),
    build() {
        this.allCells = [];
        this.dayTotalEls.clear();
        document.querySelectorAll('.subject-hours').forEach(el => this.allCells.push({ el, date: el.dataset.date, subject: el.dataset.subject }));
        document.querySelectorAll('.day-total').forEach(el => this.dayTotalEls.set(el.dataset.date, el));
    }
};

// =============================================================================
// 🔹 MODAL CONTROLLER
// =============================================================================

const ModalController = {
    currentDate: null,
    currentSubject: null,
    topics: [],
    _abortController: null,
    _eventCleanup: null,

    open(date, subject) {
        if (excludedDates.includes(date)) { Notifications.warn('️ Этот день исключён.'); return; }
        this.currentDate = date;
        this.currentSubject = subject;

        if (UI.modalDate) UI.modalDate.textContent = date;
        this.showLoading();
        this.show();

        this.loadTopics(date, subject)
            .then(() => {
                this.updateHeaderInfo();
                this.render();
                this.bindEvents();
            })
            .catch(err => {
                if (err.name !== 'AbortError') this.showError(err);
            });
    },

    async loadTopics(date, subject) {
        if (this._abortController) this._abortController.abort();
        this._abortController = new AbortController();
        const signal = this._abortController.signal;

        const programId = UI.planDataContainer?.dataset.programId;
        let url = `/reference/api/topics/?subject=${subject}`;
        if (programId) url += `&program_id=${programId}`;

        const response = await fetch(url, { signal });
        const data = await response.json();
        if (!data.success || !Array.isArray(data.topics)) throw new Error(data.error || 'Нет тем');
        this.topics = data.topics;
    },

    showLoading() {
        if (UI.modalContent) UI.modalContent.innerHTML = '<div style="text-align: center; padding: 40px; color: #64748b;">Загрузка тем...</div>';
    },

    showError(err) {
        console.error('❌ Ошибка:', err);
        if (UI.modalContent) UI.modalContent.innerHTML = `<div style="text-align: center; padding: 40px; color: #dc2626;">❌ ${err.message || 'Ошибка сети'}</div>`;
    },

    show() { if (UI.topicModal) UI.topicModal.style.display = 'flex'; },

    hide() {
        if (this._abortController) { this._abortController.abort(); this._abortController = null; }
        if (this._eventCleanup) { this._eventCleanup.abort(); this._eventCleanup = null; }

        if (UI.topicModal) UI.topicModal.style.display = 'none';
        this.currentDate = null;
        this.currentSubject = null;
        this.topics = [];
    },

    updateHeaderInfo() {
        const totalRequired = toNumber(UI.getSubjectEl(this.currentSubject).hidden?.value);
        if (UI.modalTotalRequired) UI.modalTotalRequired.textContent = `Всего: ${formatHours(totalRequired)} ч.`;
        this.updateRemainingTotal();
    },

    updateRemainingTotal() {
        const totalRequired = toNumber(UI.getSubjectEl(this.currentSubject).hidden?.value);
        const totals = StateManager.getComputedTotals();
        let distributedOtherDays = (totals.subjectSums[this.currentSubject] || 0) - StateManager.getDaySubjectSum(this.currentDate, this.currentSubject);
        let distributedCurrentDay = 0;
        document.querySelectorAll('#modal-content .topic-input:not([disabled])').forEach(input => distributedCurrentDay += toNumber(input.value));
        const remaining = totalRequired - (distributedOtherDays + distributedCurrentDay);

        if (UI.modalRemainingTotal) {
            UI.modalRemainingTotal.textContent = `Осталось: ${formatHours(remaining)} ч.`;
            UI.modalRemainingTotal.style.color = remaining < 0 ? '#dc2626' : (remaining === 0 ? '#16a34a' : '#0369a1');
        }
    },

    render() {
        const dayData = StateManager.getDayRaw(this.currentDate);
        const currentDayTopics = dayData?.[this.currentSubject] || {};
        let html = '', visibleTopicsCount = 0;
        const sortedTopics = [...this.topics].sort((a, b) => toNumber(a.id) - toNumber(b.id));

        sortedTopics.forEach((t) => {
            const topicHours = toNumber(t.hours);
            const topicId = String(t.id);
            const savedHours = toNumber(currentDayTopics[topicId]);
            const isPZ = t.name.toLowerCase().includes('. пз') || t.name.toLowerCase().endsWith(' пз.');

            const usedOtherDays = StateManager.getTopicSumAcrossDays(this.currentSubject, topicId, this.currentDate);

            const maxAvailable = topicHours - usedOtherDays;
            if (maxAvailable <= 0 && savedHours <= 0) return;
            visibleTopicsCount++;
            if (maxAvailable <= 0) {
                html += `<div class="topic-row${isPZ ? ' pz' : ''}" style="opacity: 0.5; background: #f1f5f9;">
                    <div class="topic-name">${isPZ ? '📝 ПЗ: ' : ''}Тема №${t.number}: ${t.name}</div>
                    <div class="topic-required">Всего: ${topicHours.toFixed(1)} ч.</div>
                    <input type="number" step="1" min="0" max="0" value="${savedHours}" disabled>
                    <div style="font-size:11px;color:#94a3b8;">Заполнено</div>
                </div>`;
            } else {
                const inputValue = savedHours > 0 ? (Number.isInteger(savedHours) ? savedHours : savedHours.toFixed(1)) : CONFIG.EMPTY_VALUE;
                html += `<div class="topic-row${isPZ ? ' pz' : ''}" data-topic-id="${topicId}" data-max-available="${maxAvailable.toFixed(1)}">
                    <div class="topic-name">${isPZ ? '📝 ПЗ: ' : ''}Тема №${t.number}: ${t.name}</div>
                    <div class="topic-required">Всего: ${topicHours.toFixed(1)} ч.</div>
                    <input type="number" step="1" min="0" max="${maxAvailable}" class="topic-input" value="${inputValue}" placeholder="—">
                    <div style="font-size:11px;color:#64748b;">Макс: ${formatHours(maxAvailable)}</div>
                </div>`;
            }
        });

        if (UI.modalContent) {
            if (visibleTopicsCount === 0) UI.modalContent.innerHTML = `<div style="text-align:center;padding:40px;color:#16a34a;">✅ Все часы распределены!</div>`;
            else UI.modalContent.innerHTML = html;
        }
    },

    bindEvents() {
        this._eventCleanup = new AbortController();
        const signal = this._eventCleanup.signal;

        document.querySelectorAll('#modal-content .topic-input:not([disabled])').forEach(input => {
            input.addEventListener('input', () => {
                const val = toNumber(input.value);
                const max = toNumber(input.closest('.topic-row').dataset.maxAvailable);
                input.style.borderColor = val > max ? '#ef4444' : '#cbd5e1';
                this.updateRemainingTotal();
                refreshCellFromModal(this.currentDate, this.currentSubject);
            }, { signal });

            input.addEventListener('change', () => {
                const raw = input.value.trim();
                const max = toNumber(input.closest('.topic-row').dataset.maxAvailable);
                if (raw === CONFIG.EMPTY_VALUE) { input.value = CONFIG.EMPTY_VALUE; }
                else {
                    let num = toNumber(raw);
                    if (num > max) { num = max; }
                    input.value = formatHours(roundHalf(num));
                }
                this.updateRemainingTotal();
                refreshCellFromModal(this.currentDate, this.currentSubject);
            }, { signal });

            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    window._savingViaEnter = true;
                    handleSaveAllTopics();
                    UI.hoursForm?.requestSubmit();
                }
            }, { signal });
        });
    }
};

// =============================================================================
// 🔹 РАСЧЁТНЫЕ ФУНКЦИИ
// =============================================================================

function calculateModalSum() {
    let sum = 0;
    document.querySelectorAll('#modal-content .topic-row .topic-input:not([disabled]):not([readonly])').forEach(inp => {
        if (inp.closest('#modal-content')) {
            const val = toNumber(inp.value);
            if (!isNaN(val)) sum += val;
        }
    });
    return sum;
}

// =============================================================================
// 🔹 ФУНКЦИИ РЕНДЕРИНГА
// =============================================================================

function renderSubjectCell(date, subject, value) {
    const cell = cellsMap[`${date}_${subject}`];
    if (cell) cell.value = formatHours(value);
}

function renderDayTotal(date, value) {
    const el = document.querySelector(`.day-total[data-date="${date}"]`);
    if (el) {
        el.value = formatHours(value);
        el.style.background = value > 0 ? '#bbf7d0' : '#f1f5f9';
        el.style.fontWeight = value > 0 ? '700' : '400';
    }
}

// =============================================================================
// 🔹 ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
// =============================================================================

function scaleTopicsFairly(currentTopics, targetSum) {
    const items = [];
    let currentSum = 0;
    for (const key in currentTopics) {
        const val = toNumber(currentTopics[key]);
        if (val > 0 && (!isNaN(parseInt(key)) || key === CONFIG.MANUAL_TOPIC_ID)) {
            currentSum += val;
            items.push({ key, val });
        }
    }
    if (currentSum === 0 || items.length === 0) return {};
    const ratio = targetSum / currentSum;
    let distributedHalfHours = 0;
    const processed = items.map(item => {
        const exactHalf = item.val * ratio * 2;
        const floorHalf = Math.floor(exactHalf);
        distributedHalfHours += floorHalf;
        return { key: item.key, floorVal: floorHalf / 2, remainder: exactHalf - floorHalf };
    });
    let needed = Math.round(targetSum * 2) - distributedHalfHours;
    processed.sort((a, b) => b.remainder - a.remainder);
    for (const item of processed) { if (needed > 0) { item.floorVal += 0.5; needed--; } }
    const res = {};
    processed.forEach(item => { if (item.floorVal > 0) res[item.key] = item.floorVal; });
    return res;
}

function checkSubjectLimit(subject, date, proposedDaySum) {
    const subjectEl = UI.getSubjectEl(subject);
    const limit = toNumber(subjectEl.hidden?.value);
    if (limit === 0) return { valid: true, limit: 0, projectedTotal: proposedDaySum };
    const totals = StateManager.getComputedTotals();
    const currentOther = (totals.subjectSums[subject] || 0) - StateManager.getDaySubjectSum(date, subject);
    const projected = currentOther + proposedDaySum;
    return projected > limit + 0.01 ? { valid: false, limit, projectedTotal: projected } : { valid: true, limit, projectedTotal: projected };
}

function setCellDirectValue(date, subject, totalValue) {
    debugLog(`📝 setCellDirectValue: ${date} ${subject} = ${totalValue}`);
    if (totalValue === 0) { StateManager.setSubject(date, subject, null); return; }
    const currentTopics = StateManager.getDaySubject(date, subject);
    let currentSum = 0;
    for (const key in currentTopics) {
        if (!isNaN(parseInt(key)) || key === CONFIG.MANUAL_TOPIC_ID) currentSum += toNumber(currentTopics[key]);
    }
    if (currentSum === 0 || Object.keys(currentTopics).length === 0) {
        StateManager.setSubject(date, subject, { [CONFIG.MANUAL_TOPIC_ID]: totalValue });
        return;
    }
    StateManager.setSubject(date, subject, scaleTopicsFairly(currentTopics, totalValue));
}

// =============================================================================
// 🔹 ГЛОБАЛЬНАЯ РЕКАЛЬКУЛЯЦИЯ
// =============================================================================

let _recalcRAF = null;

function recalculateTotals() {
    if (_recalcRAF) cancelAnimationFrame(_recalcRAF);
    _recalcRAF = requestAnimationFrame(() => {
        const totals = StateManager.getComputedTotals();
        debugLog('📊 recalculateTotals');

        CellCache.dayTotalEls.forEach((el, date) => renderDayTotal(date, totals.daySums[date] || 0));

        document.querySelectorAll('.subject-total-display').forEach(el => {
            const subjectCode = el.id.replace('-total-display', '');
            const subjectEl = UI.getSubjectEl(subjectCode);
            const req = toNumber(subjectEl.hidden?.value);
            el.textContent = `0 / ${formatHours(req)}`;
            const row = el.closest('tr');
            if (row) { row.style.background = ''; row.style.borderLeft = ''; el.style.color = ''; el.style.fontWeight = ''; row.classList.remove('completed-subject'); }
        });

        for (const subj in totals.subjectSums) {
            const els = UI.getSubjectEl(subj);
            if (!els.display || !els.hidden) continue;
            const req = toNumber(els.hidden.value);
            const dist = totals.subjectSums[subj];
            els.display.textContent = `${formatHours(dist) || 0} / ${formatHours(req)}`;
            const row = els.display.closest('tr');
            if (row && req > 0) {
                if (Math.abs(dist - req) < 0.01) {
                    row.style.background = '#f0fdf4'; row.style.borderLeft = '4px solid #22c55e';
                    els.display.style.color = '#166534'; els.display.style.fontWeight = '700'; row.classList.add('completed-subject');
                } else if (dist > req) {
                    row.style.background = '#fef2f2'; row.style.borderLeft = '4px solid #ef4444';
                    els.display.style.color = '#991b1b'; els.display.style.fontWeight = '700';
                } else {
                    row.style.background = '#fefce8'; row.style.borderLeft = '4px solid #eab308';
                    els.display.style.color = '#854d0e'; els.display.style.fontWeight = '600';
                }
            }
        }

        if (UI.grandTotal) {
            const total = totals.grandTotal;
            UI.grandTotal.value = `${formatHours(total) || 0} / ${formatHours(REQUIRED_HOURS)}`;
            if (REQUIRED_HOURS > 0) {
                if (Math.abs(total - REQUIRED_HOURS) < 0.01) {
                    UI.grandTotal.style.background = '#86efac'; UI.grandTotal.style.color = '#065f46'; UI.grandTotal.style.fontWeight = '700';
                } else if (total > REQUIRED_HOURS) {
                    UI.grandTotal.style.background = '#fecaca'; UI.grandTotal.style.color = '#991b1b'; UI.grandTotal.style.fontWeight = '700';
                } else {
                    UI.grandTotal.style.background = '#fef3c7'; UI.grandTotal.style.color = '#92400e'; UI.grandTotal.style.fontWeight = '600';
                }
            }
        }
        updateMedicineHighlight();
        _recalcRAF = null;
    });
}

function updateMedicineHighlight() {
    document.querySelectorAll(`td[data-subject="${CONFIG.MED_SUBJECT}"]`).forEach(td => {
        if (excludedDates.includes(td.dataset.date)) { td.classList.remove('has-hours'); return; }
        const input = td.querySelector('.hours-input');
        const isReserved = StateManager.getDaySubjectSum(td.dataset.date, CONFIG.MED_SUBJECT) > 0;
        td.classList.toggle('has-hours', toNumber(input.value) > 0 || isReserved);
    });
}

function syncDOMFromState() {
    CellCache.allCells.forEach(c => c.el.value = formatHours(StateManager.getDaySubjectSum(c.date, c.subject)));
    recalculateTotals();
}

function refreshCellFromModal(date, subject) {
    renderSubjectCell(date, subject, calculateModalSum());
    recalculateTotals();
}

// =============================================================================
// 🔹 ОЧИСТКА ИСКЛЮЧЁННЫХ ДНЕЙ
// =============================================================================

function cleanExcludedDaysFromState() {
    let cleanedCount = 0;
    excludedDates.forEach(dateStr => {
        StateManager.clearDay(dateStr);
        cleanedCount++;
        document.querySelectorAll(`.subject-hours[data-date="${dateStr}"]`).forEach(cell => { cell.value = CONFIG.EMPTY_VALUE; });
        const dayTotal = document.querySelector(`.day-total[data-date="${dateStr}"]`);
        if (dayTotal) dayTotal.value = CONFIG.EMPTY_VALUE;
    });
    if (cleanedCount > 0) {
        StateManager.save();
        recalculateTotals();
        debugLog(`✅ Очищено дней: ${cleanedCount}. Часы возвращены в пул предметов.`);
    }
}

// =============================================================================
// 🔹 ОБЕРТКИ ДЛЯ ОБРАТНОЙ СОВМЕСТИМОСТИ
// =============================================================================

function openTopicModal(date, subject) { ModalController.open(date, subject); }
function closeTopicModal() { ModalController.hide(); }

function handleSaveAllTopics() {
    if (!ModalController.currentDate || !ModalController.currentSubject) return;

    const newDayTopics = {};
    let newDaySum = 0;

    document.querySelectorAll('#modal-content .topic-row').forEach(row => {
        const input = row.querySelector('.topic-input');
        if (!input || input.disabled || !input.closest('#modal-content')) return;

        let val = toNumber(input.value);
        const maxAvailable = toNumber(row.dataset.maxAvailable);
        if (val > maxAvailable) { val = maxAvailable; input.value = formatHours(val); }
        newDayTopics[row.dataset.topicId] = val;
        if (val > 0) newDaySum += val;
    });

    if (newDaySum > CONFIG.MAX_HOURS_PER_DAY) { Notifications.warn(`⚠️ Нельзя больше ${CONFIG.MAX_HOURS_PER_DAY} часов в день!`); return; }
    const limitCheck = checkSubjectLimit(ModalController.currentSubject, ModalController.currentDate, newDaySum);
    if (!limitCheck.valid) {
        Notifications.warn(`⚠️ Превышение лимита по предмету "${ModalController.currentSubject}".\nДоступно: ${limitCheck.limit} ч.\nПопытка распределить: ${limitCheck.projectedTotal.toFixed(1)} ч.`);
        return;
    }
    const nonZeroTopics = {};
    for (const tid in newDayTopics) { if (newDayTopics[tid] > 0) nonZeroTopics[tid] = newDayTopics[tid]; }
    if (Object.keys(nonZeroTopics).length === 0) StateManager.setSubject(ModalController.currentDate, ModalController.currentSubject, null);
    else StateManager.setSubject(ModalController.currentDate, ModalController.currentSubject, nonZeroTopics);

    StateManager.save();
    syncDOMFromState();
    closeTopicModal();
}

// =============================================================================
// 🔹 LISTENERS & INIT
// =============================================================================

function setupListeners() {
    const tableBody = document.querySelector('.distribution-table tbody');
    if (!tableBody) return;
    tableBody.addEventListener('click', function(e) {
        const td = e.target.closest('td[data-date][data-subject]');
        if (!td) return;
        const date = td.dataset.date; const subject = td.dataset.subject;
        if (subject === CONFIG.SUBJECT_TOTAL) return;
        if (excludedDates.includes(date)) { e.preventDefault(); Notifications.warn('️ Этот день исключён.'); return; }
        e.preventDefault(); openTopicModal(date, subject);
    });
    document.querySelectorAll('.subject-hours').forEach(input => {
        input.addEventListener('input', function() {
            if (this.dataset.subject === CONFIG.MED_SUBJECT) updateMedicineHighlight();
        });
        input.addEventListener('change', function() {
            let val = toNumber(this.value);
            const roundedVal = roundHalf(val);
            const date = this.dataset.date; const subject = this.dataset.subject;
            const limitCheck = checkSubjectLimit(subject, date, roundedVal);
            if (!limitCheck.valid) {
                Notifications.warn(`️ Превышение лимита по предмету "${subject}".\nДоступно: ${limitCheck.limit} ч.\nПопытка распределить: ${limitCheck.projectedTotal.toFixed(1)} ч.`);
                this.value = formatHours(StateManager.getDaySubjectSum(date, subject));
                recalculateTotals();
                return;
            }
            setCellDirectValue(date, subject, roundedVal);
            this.value = formatHours(StateManager.getDaySubjectSum(date, subject));
            if (subject === CONFIG.MED_SUBJECT) updateMedicineHighlight();
            recalculateTotals();
            StateManager.save();
        });
        input.addEventListener('blur', function() {
            const trimmedValue = this.value.trim();
            debugLog(`🔍 Blur: value="${trimmedValue}"`);
            if (trimmedValue === CONFIG.EMPTY_VALUE || trimmedValue === CONFIG.ZERO_VALUE) {
                const date = this.dataset.date; const subject = this.dataset.subject;
                this.value = CONFIG.ZERO_VALUE;
                setCellDirectValue(date, subject, 0);
                this.value = formatHours(StateManager.getDaySubjectSum(date, subject));
                recalculateTotals();
                StateManager.save();
            }
        });
    });
    if (UI.modalCloseBtn) UI.modalCloseBtn.addEventListener('click', closeTopicModal);
    if (UI.modalCancelBtn) UI.modalCancelBtn.addEventListener('click', closeTopicModal);
    if (UI.modalSaveBtn) UI.modalSaveBtn.addEventListener('click', handleSaveAllTopics);
    document.addEventListener('click', function(event) {
        if (event.target === UI.topicModal) closeTopicModal();
    });
    UI.hoursForm?.addEventListener('submit', handleSubmitForm);
}

/** @param {Event} e */
function handleSubmitForm(e) {
    e.preventDefault();
    const data = {
        plan_id: PLAN_ID,
        topics: StateManager.getData(),
        hours: {},
        category: UI.getCategoryInput()?.value || CONFIG.EMPTY_VALUE,
        time_start: UI.timeStart?.value,
        time_end: UI.timeEnd?.value,
        med_teacher: UI.getMedTeacherSelect()?.value,
        training_program: UI.trainingProgramSelect?.value
    };
    fetch(window.location.href, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': UI.csrfToken() },
        body: JSON.stringify(data)
    }).then(r => r.json()).then(res => {
        if (res.success) {
            if (!window._savingViaEnter) Notifications.success('✅ Распределение сохранено!');
            window._savingViaEnter = false;
        }
        else Notifications.error('❌ ' + (res.error || 'Ошибка'));
    }).catch(err => { console.error('❌ Ошибка сети:', err); Notifications.error('❌ Ошибка сети'); });
}

function confirmDeleteSchedule() {
    if (UI.deleteModal) UI.deleteModal.style.display = 'flex';
    else { if (confirm('Вы уверены, что хотите очистить план-график?')) deleteSchedule(); }
}

function closeDeleteModal() { if (UI.deleteModal) UI.deleteModal.style.display = 'none'; }

function deleteSchedule() {
    if (PLAN_ID === 0) { Notifications.error('❌ Ошибка: не найден ID план-графика'); closeDeleteModal(); return; }
    fetch(`/groups/schedules/${PLAN_ID}/delete-plan/`, {
        method: 'DELETE',
        headers: { 'X-CSRFToken': UI.csrfToken(), 'Content-Type': 'application/json' }
    }).then(async response => {
        if (!response.ok) {
            if (response.status === 404) throw new Error('План-график не найден');
            const text = await response.text();
            throw new Error(`HTTP ${response.status}: ${text.slice(0, 200)}`);
        }
        return response.json();
    }).then(result => {
        if (result.success) {
            StateManager.clearStorage();
            Notifications.success('✅ Таблица распределения часов очищена!');
            closeDeleteModal();
            const url = new URL(window.location.href);
            url.searchParams.set('_clear_cache', Date.now().toString());
            window.location.href = url.toString();
        } else { Notifications.error('❌ Ошибка: ' + (result.error || 'Неизвестная ошибка')); closeDeleteModal(); }
    }).catch(err => { console.error('Ошибка:', err); Notifications.error('Ошибка при удалении: ' + err.message); closeDeleteModal(); });
}

function updatePageHeader() {
    if (!UI.trainingProgramSelect || !UI.programTitleHeader) return;
    UI.programTitleHeader.textContent = UI.trainingProgramSelect.options[UI.trainingProgramSelect.selectedIndex].getAttribute('data-graphic-title') || CONFIG.DEFAULT_TITLE;
}

window.triggerExport = function() {
    const exportType = UI.exportTypeSelect?.value || 'schedule';
    if (!UI.exportBtn) return;
    const programId = new URLSearchParams(window.location.search).get('program_id') || UI.trainingProgramSelect?.value;
    let finalUrl = exportType === 'schedule' ? UI.exportBtn.dataset.scheduleUrl : UI.exportBtn.dataset.planUrl;
    if (exportType === 'plan_graphic' && programId) finalUrl += (finalUrl.includes('?') ? '&' : '?') + `program_id=${programId}`;
    window.location.href = finalUrl;
};

// =============================================================================
// 🔹 ЗАПУСК
// =============================================================================
document.addEventListener('DOMContentLoaded', function() {
    debugLog('✅ Step2 загружен (v0.0.4.27b Production-Ready)');

    CellCache.build();

    // ✅ Исправлено: c.subject вместо неопределённой subject
    CellCache.allCells.forEach(c => cellsMap[`${c.date}_${c.subject}`] = c.el);

    cleanExcludedDaysFromState();
    syncDOMFromState();
    setupListeners();

    setTimeout(() => {
        recalculateTotals();
        const totals = StateManager.getComputedTotals();
        debugLog('📊 Итоги:', totals.grandTotal);
    }, 200);

    if (UI.trainingProgramSelect) {
        // 🔹 Очистка localStorage при смене программы
        UI.trainingProgramSelect.addEventListener('change', function() {
            const newProgramId = this.value;
            if (!newProgramId) return;

            const oldKey = StorageManager._getKey();
            StorageManager.clearByKey(oldKey);
            debugLog(`🗑️ Очищен ключ для программы ${PROGRAM_ID}: ${oldKey}`);

            const url = new URL(window.location.href);
            url.searchParams.set('program_id', newProgramId);
            url.searchParams.set('_clear_cache', Date.now().toString());
            window.location.href = url.toString();
        });
    }
    updatePageHeader();
    if (UI.trainingProgramSelect) UI.trainingProgramSelect.addEventListener('change', updatePageHeader);
});