/**
 * static/js/master_plan/dashboard.js
 * Генеральный план — основной JS
 * Автошкола
 *
 * Зависимости:
 *   window.MASTER_PLAN_CONFIG — объект с csrfToken и url-ами (задаётся в dashboard.html)
 */

(function () {
    'use strict';

    // =======================================================================
    // 🔹 КОНФИГ И КОНСТАНТЫ
    // =======================================================================
    const CONFIG = window.MASTER_PLAN_CONFIG || {};
    const URLS = CONFIG.urls || {};
    const CSRF_TOKEN = CONFIG.csrfToken || '';
    const DEFAULT_HOURS_PER_STUDENT = 50;

    const URL_CELL_STUDENTS = URLS.cellStudents
        || '/master-plan/api/cell-students/__PG__/__M__/';
    const URL_REASSIGN_DATA = URLS.reassignData
        || '/master-plan/api/reassignment/group/__ID__/';
    const URL_SAVE_REASSIGN = URLS.saveReassignment
        || '/master-plan/save-reassignment/';

    // =======================================================================
    // 🔹 СОСТОЯНИЕ МОДУЛЯ
    // =======================================================================
    let selectedEditPlanGroupId = null;
    let deletePlanGroupId = null;

    const hoursPerStudentMap = {};
    const cellStudentsCache = {};

    let reassignGroupId = null;
    let reassignMasters = [];

    // =======================================================================
    // 🔹 ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
    // =======================================================================
    const getCsrfToken = () =>
        document.querySelector('[name=csrfmiddlewaretoken]')?.value || CSRF_TOKEN;

    const setFieldValue = (id, value) => {
        const el = document.getElementById(id);
        if (el) el.value = value;
    };

    function buildCellStudentsUrl(planGroupId, masterId) {
        return URL_CELL_STUDENTS
            .replace('__PG__', planGroupId)
            .replace('__M__', masterId);
    }

    // =======================================================================
    // 🔹 ВИЗУАЛИЗАЦИЯ
    // =======================================================================
    function updateGroupCompletionVisuals() {
        document.querySelectorAll('.matrix-header-group').forEach(header => {
            const planGroupId = header.dataset.planGroupId;
            const totalStudents = parseInt(header.dataset.totalStudents) || 0;
            const drivenStudents = parseInt(header.dataset.drivenStudents) || 0;

            let currentDistributed = 0;
            document.querySelectorAll(`.matrix-cell[data-plan-group-id="${planGroupId}"] .matrix-input-manual`)
                .forEach(inp => {
                    currentDistributed += parseInt(inp.value) || 0;
                });

            const remainingToDistribute = Math.max(0, totalStudents - currentDistributed);
            const remainingSpan = header.querySelector('.remaining-counter');

            if (remainingSpan) {
                const isArchived = drivenStudents >= totalStudents && totalStudents > 0;
                header.classList.toggle('is-archived', isArchived);

                if (isArchived) {
                    remainingSpan.textContent = '✅ В архив';
                } else {
                    remainingSpan.textContent = `Ост: ${remainingToDistribute} студ.`;
                    remainingSpan.style.color = remainingToDistribute === 0 ? '#16a34a' : '#d97706';
                }
            }
        });
    }

    function updateMastersStats() {
        document.querySelectorAll('.master-stat-item').forEach(statRow => {
            const masterId = statRow.dataset.masterId;
            if (!masterId) return;

            let totalStudents = 0;
            let totalHours = 0;
            let drivenHours = 0;

            document.querySelectorAll(`.matrix-row[data-master-id="${masterId}"] .matrix-cell`)
                .forEach(cell => {
                    const planGroupId = cell.dataset.planGroupId;
                    const hoursPerStudent = hoursPerStudentMap[planGroupId] || DEFAULT_HOURS_PER_STUDENT;

                    const input = cell.querySelector('.matrix-input-manual');
                    const studentsCount = parseInt(input?.value) || 0;

                    const autoDiv = cell.querySelector('.matrix-input-auto');
                    const completedCount = parseInt(autoDiv?.textContent) || 0;

                    totalStudents += studentsCount;
                    totalHours += studentsCount * hoursPerStudent;
                    drivenHours += completedCount * hoursPerStudent;
                });

            const remainingHours = Math.max(0, totalHours - drivenHours);

            const studentsEl = statRow.querySelector('[data-stat-field="students"]');
            const totalHoursEl = statRow.querySelector('[data-stat-field="total_hours"]');
            const drivenHoursEl = statRow.querySelector('[data-stat-field="driven_hours"]');
            const remainingHoursEl = statRow.querySelector('[data-stat-field="remaining_hours"]');

            if (studentsEl) studentsEl.textContent = totalStudents;
            if (totalHoursEl) totalHoursEl.textContent = Math.round(totalHours);
            if (drivenHoursEl) drivenHoursEl.textContent = Math.round(drivenHours);
            if (remainingHoursEl) remainingHoursEl.textContent = Math.round(remainingHours);
        });

        if (typeof window.attachTooltips === 'function') {
            window.attachTooltips();
        }
    }

    // =======================================================================
    // 🔹 СИНХРОНИЗАЦИЯ ПРОКРУТОК
    // =======================================================================
    function syncAllScroll() {
        const mastersScroll = document.querySelector('.masters-scroll-container');
        const matrixScroll = document.querySelector('.distribution-matrix-wrapper');
        const statsScroll = document.querySelector('.stats-scroll-container');
        const headerScroll = document.querySelector('.values-scroll-container');

        if (!mastersScroll || !matrixScroll || !statsScroll) return;

        let isScrolling = false;

        function syncScroll(source, targets, axis) {
            if (isScrolling) return;
            isScrolling = true;

            targets.forEach(target => {
                if (target && target !== source) {
                    if (axis === 'vertical') {
                        target.scrollTop = source.scrollTop;
                    } else if (axis === 'horizontal') {
                        target.scrollLeft = source.scrollLeft;
                    }
                }
            });

            setTimeout(() => { isScrolling = false; }, 0);
        }

        matrixScroll.addEventListener('scroll', function () {
            syncScroll(this, [mastersScroll, statsScroll], 'vertical');
        });
        mastersScroll.addEventListener('scroll', function () {
            syncScroll(this, [matrixScroll, statsScroll], 'vertical');
        });
        statsScroll.addEventListener('scroll', function () {
            syncScroll(this, [matrixScroll, mastersScroll], 'vertical');
        });

        if (headerScroll) {
            headerScroll.addEventListener('scroll', function () {
                syncScroll(this, [matrixScroll], 'horizontal');
            });
            matrixScroll.addEventListener('scroll', function () {
                syncScroll(this, [headerScroll], 'horizontal');
            });
        }
    }

    // =======================================================================
    // 🔹 ОБНОВЛЕНИЕ РАСПРЕДЕЛЕНИЯ (из матрицы)
    // =======================================================================
    function updateDistribution(input) {
        if (input.disabled) return;

        const masterId = input.dataset.masterId;
        const planGroupId = input.dataset.planGroupId;
        const newValue = parseInt(input.value) || 0;
        const oldValue = parseInt(input.dataset.oldValue || '0');

        const groupHeader = document.querySelector(`.matrix-header-group[data-plan-group-id="${planGroupId}"]`);
        const totalStudents = parseInt(groupHeader?.dataset.totalStudents) || 0;

        let distributedOthers = 0;
        document.querySelectorAll(`.matrix-cell[data-plan-group-id="${planGroupId}"] .matrix-input-manual`)
            .forEach(inp => {
                if (inp !== input) {
                    distributedOthers += parseInt(inp.value) || 0;
                }
            });

        const newTotalDistributed = distributedOthers + newValue;

        if (newTotalDistributed > totalStudents) {
            const remainingSlots = totalStudents - distributedOthers;
            const correctedValue = Math.max(0, remainingSlots);

            showToast(
                `⚠️ Превышение лимита! Распределено ${distributedOthers}, доступно ещё ${remainingSlots}. Значение изменено на ${correctedValue}`,
                'warning'
            );

            input.value = correctedValue;
            input.dataset.oldValue = correctedValue;
            updateGroupCompletionVisuals();
            updateMastersStats();
            return;
        }

        if (newValue < 0) {
            showToast('⚠️ Значение не может быть отрицательным. Установлено 0.', 'warning');
            input.value = 0;
            input.dataset.oldValue = 0;
            updateGroupCompletionVisuals();
            updateMastersStats();
            return;
        }

        const csrfToken = getCsrfToken();
        fetch(URLS.updateDistribution, {
            method: 'POST',
            headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': csrfToken },
            body: new URLSearchParams({
                csrfmiddlewaretoken: csrfToken,
                master_id: masterId,
                plan_group_id: planGroupId,
                students_count: newValue,
            }),
        })
            .then(response => {
                if (!response.ok) {
                    return response.text().then(() => {
                        throw new Error(`Сервер вернул ошибку ${response.status}`);
                    });
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    input.dataset.oldValue = input.value;

                    const cell = input.closest('.matrix-cell');
                    if (cell) {
                        if (cell.classList.contains('matrix-cell-auto')) {
                            cell.classList.remove('matrix-cell-auto');
                            const badge = cell.querySelector('.auto-badge');
                            if (badge) badge.remove();
                        }

                        const autoField = cell.querySelector('.matrix-input-auto');
                        if (autoField && data.completed_count !== undefined) {
                            autoField.textContent = data.completed_count;
                        }

                        const key = `${planGroupId}:${masterId}`;
                        delete cellStudentsCache[key];
                    }

                    if (data.fully_driven_students !== undefined && data.total_students !== undefined) {
                        if (groupHeader) {
                            groupHeader.dataset.drivenStudents = data.fully_driven_students;
                            groupHeader.dataset.totalStudents = data.total_students;
                        }
                    }

                    updateGroupCompletionVisuals();
                    updateMastersStats();

                    if (data.is_fully_distributed) {
                        blockGroupMatrixInputs(planGroupId);
                    }

                    if (data.is_archived) {
                        showToast('✅ Группа полностью выкатана и отправлена в архив!', 'success');
                        delete hoursPerStudentMap[planGroupId];

                        if (groupHeader) {
                            groupHeader.remove();
                            document.querySelectorAll(`.matrix-cell[data-plan-group-id="${planGroupId}"]`)
                                .forEach(c => c.remove());
                            document.querySelector(`.header-value-row[data-plan-group-id="${planGroupId}"]`)?.remove();
                        }
                    }
                } else {
                    input.value = oldValue;
                    showToast('❌ Ошибка: ' + (data.error || 'Неизвестная ошибка'), 'error');
                    updateGroupCompletionVisuals();
                    updateMastersStats();
                }
            })
            .catch(error => {
                console.error('Ошибка:', error);
                input.value = oldValue;
                showToast('❌ Ошибка сети: ' + error.message, 'error');
                updateGroupCompletionVisuals();
                updateMastersStats();
            });
    }

    function blockGroupMatrixInputs(planGroupId) {
        document.querySelectorAll(
            `.matrix-cell[data-plan-group-id="${planGroupId}"] .matrix-input-manual`
        ).forEach(inp => {
            inp.disabled = true;
            inp.title = 'Группа распределена. Изменения — через «Распределение учащихся».';
        });

        const header = document.querySelector(
            `.matrix-header-group[data-plan-group-id="${planGroupId}"]`
        );
        if (header) {
            header.dataset.isFullyDistributed = '1';
        }
    }

    // =======================================================================
    // 🔹 TOAST-УВЕДОМЛЕНИЯ
    // =======================================================================
    function showToast(message, type = 'info') {
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 999999;
                display: flex;
                flex-direction: column;
                gap: 10px;
                pointer-events: none;
            `;
            document.body.appendChild(container);
        }

        const toast = document.createElement('div');
        toast.className = `toast-notification toast-${type}`;
        toast.textContent = message;

        Object.assign(toast.style, {
            padding: '12px 20px',
            borderRadius: '8px',
            color: 'white',
            fontWeight: '600',
            fontSize: '14px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
            animation: 'slideIn 0.3s ease-out',
            maxWidth: '350px',
            wordWrap: 'break-word',
            pointerEvents: 'auto',
        });

        const colors = { success: '#16a34a', warning: '#d97706', error: '#dc2626', info: '#3b82f6' };
        toast.style.background = colors[type] || colors.info;

        container.appendChild(toast);

        setTimeout(() => {
            toast.style.animation = 'fadeOut 0.3s ease-out forwards';
            setTimeout(() => {
                if (toast.parentNode) toast.remove();
                if (container.children.length === 0) container.remove();
            }, 300);
        }, 4000);
    }

    // =======================================================================
    // 🔹 ГЛОБАЛЬНЫЙ TOOLTIP
    // =======================================================================
    function initGlobalTooltip() {
        const tooltip = document.createElement('div');
        tooltip.id = 'global-tooltip';
        tooltip.style.cssText = `
            position: fixed;
            background: #1e293b;
            color: white;
            padding: 6px 10px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 500;
            white-space: nowrap;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.2s;
            z-index: 999999;
            box-shadow: 0 4px 12px rgba(0,0,0,0.25);
            transform: translate(-50%, -100%);
        `;
        document.body.appendChild(tooltip);

        function showTooltip(text, el) {
            tooltip.textContent = text;
            const rect = el.getBoundingClientRect();

            let x = rect.left + (rect.width / 2);
            let y = rect.top - 8;

            const tooltipWidth = tooltip.offsetWidth || 100;
            if (x - tooltipWidth / 2 < 5) x = tooltipWidth / 2 + 5;
            if (x + tooltipWidth / 2 > window.innerWidth - 5) x = window.innerWidth - tooltipWidth / 2 - 5;

            tooltip.style.left = x + 'px';
            tooltip.style.top = y + 'px';
            tooltip.style.opacity = '1';
        }

        function hideTooltip() {
            tooltip.style.opacity = '0';
        }

        function attachTooltips() {
            const selector = '.stat-compact-value[title], .stats-column [data-tooltip]';

            document.querySelectorAll(selector).forEach(el => {
                if (el.dataset.tooltipText) return;

                const text = el.dataset.tooltip || el.getAttribute('title');
                if (!text) return;

                el.dataset.tooltipText = text;
                el.removeAttribute('title');

                el.addEventListener('mouseenter', function () {
                    showTooltip(this.dataset.tooltipText, this);
                });
                el.addEventListener('mouseleave', hideTooltip);
            });
        }

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', attachTooltips);
        } else {
            attachTooltips();
        }

        window.attachTooltips = attachTooltips;
    }

    // =======================================================================
    // 🔹 TOOLTIP: ЯЧЕЙКА МАТРИЦЫ (список ФИО)
    // =======================================================================

    let matrixTooltipTimeout = null;

    /**
     * Показывает подсказку над ячейкой матрицы со списком ФИО студентов,
     * назначенных этому мастеру в этой группе.
     */
    function showMatrixCellTooltip(cell) {
        const tooltip = document.getElementById('matrixCellTooltip');
        if (!tooltip) return;

        const planGroupId = cell.dataset.planGroupId;
        const masterId = cell.dataset.masterId;
        if (!planGroupId || !masterId) return;

        const groupHeader = document.querySelector(
            `.matrix-header-group[data-plan-group-id="${planGroupId}"]`
        );
        const groupNumber = groupHeader
            ? groupHeader.querySelector('.group-number-compact')?.textContent.trim() || '—'
            : '—';

        const totalStudents = groupHeader
            ? parseInt(groupHeader.dataset.totalStudents) || 0
            : 0;

        const input = cell.querySelector('.matrix-input-manual');
        const distributedCount = input ? parseInt(input.value) || 0 : 0;

        const isAuto = cell.classList.contains('matrix-cell-auto');

        // Собираем базовую часть подсказки
        let html = `<div class="tlt-title">Группа ${groupNumber}`;
        if (isAuto) html += ` <span class="tlt-badge auto">🔒 авто</span>`;
        html += `</div>`;

        // Если ничего не распределено — короткая подсказка
        if (distributedCount <= 0) {
            html += `<div class="tlt-row tlt-muted"><span>Не распределено</span></div>`;
            tooltip.innerHTML = html;
            positionMatrixTooltip(tooltip, cell);
            return;
        }

        // Показываем заглушку «Загрузка…», затем тянем список студентов
        html += `<div class="tlt-row"><span>Распределено:</span><b>${distributedCount} из ${totalStudents} студ.</b></div>`;
        html += `<div class="tlt-row tlt-muted" style="font-style:italic;"><span>Загрузка…</span></div>`;
        tooltip.innerHTML = html;
        positionMatrixTooltip(tooltip, cell);

        const cacheKey = `${planGroupId}:${masterId}`;

        // Если есть кэш — сразу рендерим
        if (cellStudentsCache[cacheKey]) {
            renderMatrixTooltipStudents(tooltip, cellStudentsCache[cacheKey], groupNumber, totalStudents, distributedCount, isAuto);
            positionMatrixTooltip(tooltip, cell);
            return;
        }

        // Иначе — fetch
        fetch(buildCellStudentsUrl(planGroupId, masterId))
            .then(r => r.json())
            .then(data => {
                if (!data.success) {
                    tooltip.innerHTML = `<div class="tlt-title">Группа ${groupNumber}</div>` +
                        `<div class="tlt-row tlt-muted"><span>Ошибка загрузки</span></div>`;
                    positionMatrixTooltip(tooltip, cell);
                    return;
                }
                cellStudentsCache[cacheKey] = data;
                renderMatrixTooltipStudents(tooltip, data, groupNumber, totalStudents, distributedCount, isAuto);
                positionMatrixTooltip(tooltip, cell);
            })
            .catch(err => {
                console.error('Fetch cell students error:', err);
                tooltip.innerHTML = `<div class="tlt-title">Группа ${groupNumber}</div>` +
                    `<div class="tlt-row tlt-muted"><span>Ошибка сети</span></div>`;
                positionMatrixTooltip(tooltip, cell);
            });
    }

        /**
     * Рендерит список студентов в тултип ячейки:
     *   ФИО • Всего • Выкатано • Осталось
     */
    function renderMatrixTooltipStudents(tooltip, data, groupNumber, totalStudents, distributedCount, isAuto) {
        let html = `<div class="tlt-title">Группа ${groupNumber}`;
        if (isAuto) html += ` <span class="tlt-badge auto">🔒 авто</span>`;
        html += `</div>`;

        // Строка итогов по ячейке
        html += `<div class="tlt-row"><span>Распределено:</span><b>${distributedCount} из ${totalStudents} студ.</b></div>`;

        if (!data.students || data.students.length === 0) {
            html += `<div class="tlt-row tlt-muted"><span>Нет назначенных</span></div>`;
        } else {
            const MAX_ROWS = 15;
            const shown = data.students.slice(0, MAX_ROWS);

            // Заголовок «шапки» таблицы
            html += `<div class="tlt-row tlt-header" style="border-top:1px solid #334155;padding-top:4px;margin-top:4px;font-size:10px;color:#94a3b8;">`;
            html += `<span>Учащийся</span>`;
            html += `<span style="display:flex;gap:8px;">`;
            html += `<span style="min-width:32px;text-align:right;" title="Всего часов">Вс.</span>`;
            html += `<span style="min-width:32px;text-align:right;" title="Выкатано часов">Вык.</span>`;
            html += `<span style="min-width:32px;text-align:right;" title="Осталось часов">Ост.</span>`;
            html += `</span>`;
            html += `</div>`;

            shown.forEach(s => {
                const initials = `${s.last_name} ${s.first_name.charAt(0)}.` +
                    (s.patronymic ? s.patronymic.charAt(0) + '.' : '');
                const autoBadge = s.is_auto
                    ? ' <span class="tlt-badge auto" style="font-size:8px;padding:0 4px;">🔒</span>'
                    : '';

                const total = Math.round(s.hours_required);
                const done = Math.round(s.hours_completed);
                const rest = Math.round(s.hours_remaining);

                html += `<div class="tlt-row tlt-student-row">`;
                html += `<span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${initials}${autoBadge}</span>`;
                html += `<span style="display:flex;gap:8px;font-variant-numeric:tabular-nums;flex-shrink:0;">`;
                html += `<span style="min-width:32px;text-align:right;color:#cbd5e1;">${total}</span>`;
                html += `<span style="min-width:32px;text-align:right;color:#86efac;font-weight:600;">${done}</span>`;
                html += `<span style="min-width:32px;text-align:right;color:#fcd34d;font-weight:600;">${rest}</span>`;
                html += `</span>`;
                html += `</div>`;
            });

            if (data.students.length > MAX_ROWS) {
                html += `<div class="tlt-row tlt-muted"><span>… и ещё ${data.students.length - MAX_ROWS}</span></div>`;
            }
        }

        tooltip.innerHTML = html;
    }

    /**
     * Позиционирует тултип рядом с ячейкой.
     */
    function positionMatrixTooltip(tooltip, cell) {
        tooltip.style.display = 'block';
        tooltip.style.opacity = '0';
        tooltip.style.left = '-9999px';
        tooltip.style.top = '-9999px';

        const rect = cell.getBoundingClientRect();
        const tltW = tooltip.offsetWidth;
        const tltH = tooltip.offsetHeight;
        const vw = window.innerWidth;
        const vh = window.innerHeight;
        const margin = 8;
        const offset = 8;

        // Горизонталь — по центру ячейки
        let left = rect.left + (rect.width / 2) - (tltW / 2);
        if (left < margin) left = margin;
        if (left + tltW > vw - margin) left = vw - tltW - margin;

        // Вертикаль — над ячейкой, если влезает; иначе под
        let top = rect.top - tltH - offset;
        if (top < margin) top = rect.bottom + offset;
        if (top + tltH > vh - margin) top = vh - tltH - margin;
        if (top < margin) top = margin;

        tooltip.style.left = left + 'px';
        tooltip.style.top = top + 'px';
        tooltip.style.opacity = '1';
        tooltip.classList.add('visible');
    }

    function hideMatrixCellTooltip() {
        const tooltip = document.getElementById('matrixCellTooltip');
        if (!tooltip) return;
        tooltip.classList.remove('visible');
        tooltip.style.opacity = '0';
    }

    function bindMatrixCellTooltips() {
        document.querySelectorAll('.matrix-cell').forEach(cell => {
            if (cell.dataset.tooltipBound === '1') return;
            cell.dataset.tooltipBound = '1';

            cell.addEventListener('mouseenter', function () {
                clearTimeout(matrixTooltipTimeout);
                matrixTooltipTimeout = setTimeout(() => {
                    showMatrixCellTooltip(this);
                }, 150);
            });

            cell.addEventListener('mouseleave', function () {
                clearTimeout(matrixTooltipTimeout);
                hideMatrixCellTooltip();
            });
        });
    }

    // =======================================================================
    // 🔹 TOOLTIP: СТАТИСТИКА ПО МАСТЕРАМ
    // =======================================================================

    let masterTooltipTimeout = null;

    function showMasterStatsTooltip(statRow) {
        const tooltip = document.getElementById('matrixCellTooltip');
        if (!tooltip) return;

        const masterName = statRow.dataset.masterName || '—';
        const groupsRaw = statRow.dataset.groups || '';

        const groups = groupsRaw
            .split(';')
            .filter(s => s.length > 0)
            .map(s => {
                const parts = s.split(':');
                return {
                    number: parts[0] || '—',
                    count: parseInt(parts[1]) || 0,
                };
            });

        let html = `<div class="tlt-title">${masterName}</div>`;

        if (groups.length === 0) {
            html += `<div class="tlt-row tlt-muted"><span>Нет данных</span></div>`;
        } else {
            let total = 0;
            groups.forEach(g => {
                total += g.count;
                const value = g.count > 0
                    ? `<b>${g.count} студ.</b>`
                    : `<span class="tlt-muted">—</span>`;
                html += `<div class="tlt-row"><span>Группа ${g.number}:</span>${value}</div>`;
            });
            html += `<div class="tlt-row" style="border-top:1px solid #334155;padding-top:4px;margin-top:4px;">` +
                    `<span>Всего:</span><b>${total} студ.</b></div>`;
        }

        tooltip.innerHTML = html;
        tooltip.style.display = 'block';
        tooltip.style.opacity = '0';
        tooltip.style.left = '-9999px';
        tooltip.style.top = '-9999px';

        const rect = statRow.getBoundingClientRect();
        const tltW = tooltip.offsetWidth;
        const tltH = tooltip.offsetHeight;
        const vw = window.innerWidth;
        const vh = window.innerHeight;
        const margin = 8;
        const offset = 8;

        let left = rect.left - tltW - offset;
        if (left < margin) left = rect.right + offset;
        if (left + tltW > vw - margin) left = vw - tltW - margin;

        let top = rect.top + (rect.height / 2) - (tltH / 2);
        if (top < margin) top = margin;
        if (top + tltH > vh - margin) top = vh - tltH - margin;

        tooltip.style.left = left + 'px';
        tooltip.style.top = top + 'px';
        tooltip.style.opacity = '1';
        tooltip.classList.add('visible');
    }

    function hideMasterStatsTooltip() {
        const tooltip = document.getElementById('matrixCellTooltip');
        if (!tooltip) return;
        tooltip.classList.remove('visible');
        tooltip.style.opacity = '0';
    }

    function bindMasterStatsTooltips() {
        document.querySelectorAll('.master-stat-item').forEach(statRow => {
            if (statRow.dataset.tooltipBound === '1') return;
            statRow.dataset.tooltipBound = '1';

            statRow.addEventListener('mouseenter', function () {
                clearTimeout(masterTooltipTimeout);
                masterTooltipTimeout = setTimeout(() => {
                    showMasterStatsTooltip(this);
                }, 150);
            });

            statRow.addEventListener('mouseleave', function () {
                clearTimeout(masterTooltipTimeout);
                hideMasterStatsTooltip();
            });
        });
    }

    // =======================================================================
    // 🔹 МОДАЛЬНЫЕ ОКНА
    // =======================================================================
    function openAddGroupModal() {
        document.getElementById('addGroupModal').classList.add('active');
    }

    function closeAddGroupModal() {
        document.getElementById('addGroupModal').classList.remove('active');
        document.getElementById('addGroupForm').reset();
    }

    function openEditModal() {
        document.getElementById('editGroupSelect').value = '';
        document.getElementById('proceedEditBtn').disabled = true;
        document.getElementById('selectEditModal').classList.add('active');
    }

    function closeSelectEditModal() {
        document.getElementById('selectEditModal').classList.remove('active');
        selectedEditPlanGroupId = null;
    }

    function proceedToEdit() {
        if (!selectedEditPlanGroupId) {
            showToast('⚠️ Выберите группу', 'warning');
            return;
        }
        const select = document.getElementById('editGroupSelect');
        const groupId = select.options[select.selectedIndex].getAttribute('data-group-id');

        document.getElementById('editPlanGroupId').value = selectedEditPlanGroupId;
        const editSelect2 = document.getElementById('editGroupSelect2');
        if (editSelect2 && groupId) editSelect2.value = groupId;

        closeSelectEditModal();

        fetch(URLS.getGroupData.replace('__ID__', groupId))
            .then(response => response.ok ? response.json() : Promise.reject('Ошибка загрузки'))
            .then(data => {
                if (data.error) {
                    console.error('Ошибка API:', data.error);
                    return;
                }
                setFieldValue('editHoursInput', data.hours_per_student || DEFAULT_HOURS_PER_STUDENT);
                setFieldValue('editDistributionDate', data.distribution_date || '');
                setFieldValue('editCanDriveFrom', data.can_drive_from || '');
                setFieldValue('editDriveUntil', data.drive_until || '');
                setFieldValue('editExamTheory', data.exam_internal_theory_date || '');
                setFieldValue('editExamDriving', data.exam_internal_driving_date || '');
                setFieldValue('editExamGai', data.exam_gai_date || '');
                document.getElementById('editModal').classList.add('active');
            })
            .catch(error => {
                console.error('Ошибка загрузки данных:', error);
                showToast('❌ Ошибка загрузки данных группы', 'error');
            });
    }

    function closeEditModal() {
        document.getElementById('editModal').classList.remove('active');
        document.getElementById('editForm').reset();
    }

    function openDeleteModal() {
        document.getElementById('deleteGroupSelect').value = '';
        document.getElementById('deleteWarning').style.display = 'none';
        document.getElementById('confirmDeleteBtn').disabled = true;
        document.getElementById('deleteModal').classList.add('active');
    }

    function closeDeleteModal() {
        document.getElementById('deleteModal').classList.remove('active');
        deletePlanGroupId = null;
    }

    function confirmDelete() {
        if (!deletePlanGroupId) {
            showToast('⚠️ Выберите группу для удаления', 'warning');
            return;
        }
        const csrfToken = getCsrfToken();
        const formData = new FormData();
        formData.append('csrfmiddlewaretoken', csrfToken);
        formData.append('plan_group_id', deletePlanGroupId);

        fetch(URLS.deleteGroup, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrfToken, 'X-Requested-With': 'XMLHttpRequest' },
            body: formData,
        })
            .then(response => response.ok ? response.json() : Promise.reject(`Ошибка сервера: ${response.status}`))
            .then(data => {
                if (data.success) {
                    closeDeleteModal();
                    location.reload();
                } else {
                    showToast('❌ Ошибка: ' + (data.error || 'Неизвестная ошибка'), 'error');
                }
            })
            .catch(error => {
                console.error('Ошибка сети:', error);
                showToast('❌ Ошибка сети или сервера: ' + error.message, 'error');
            });
    }

    // =======================================================================
    // 🔹 РАСПРЕДЕЛЕНИЕ УЧАЩИХСЯ (МОДАЛКА)
    // =======================================================================
    let currentPlanGroupId = null;
    let allMastersData = [];
    let masterQuotas = {};
    let alreadyAssigned = {};

    const URL_DISTRIBUTE = URLS.distribute || '/master-plan/api/distribute/__ID__/';
    const URL_SAVE_DISTRIBUTION = URLS.saveDistribution || '/master-plan/save-distribution/';

    function buildDistributeUrl(planGroupId) {
        return URL_DISTRIBUTE.replace('__ID__', planGroupId);
    }

    function autoOpenDistributionModal() {
        const groupHeaders = document.querySelectorAll('.matrix-header-group');
        let targetGroupId = null;
        let targetGroupName = null;

        for (let i = 0; i < groupHeaders.length; i++) {
            const header = groupHeaders[i];
            const total = parseInt(header.getAttribute('data-total-students')) || 0;
            const distributed = parseInt(header.getAttribute('data-distributed-students')) || 0;

            if (total > distributed) {
                targetGroupId = header.getAttribute('data-plan-group-id');
                targetGroupName = header.querySelector('.group-number-compact').textContent.trim();
                break;
            }
        }

        if (!targetGroupId) {
            if (groupHeaders.length > 0) {
                showToast('Все учащиеся распределены. Открываем перераспределение.', 'info');
                openReassignFlow();
            } else {
                showToast('Нет групп для распределения.', 'info');
            }
            return;
        }

        openDistributionModal(targetGroupId, targetGroupName);
    }

    function openDistributionModal(planGroupId, groupName) {
        currentPlanGroupId = planGroupId;
        document.getElementById('modalGroupName').textContent = groupName;
        document.getElementById('distributionModal').style.display = 'flex';

        fetch(buildDistributeUrl(planGroupId))
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    allMastersData = data.masters || [];
                    masterQuotas = data.master_quotas || {};
                    alreadyAssigned = data.already_assigned || {};
                    renderDistributionTable(data.students || []);
                } else {
                    showToast('Ошибка: ' + (data.error || 'Неизвестная ошибка'), 'error');
                }
            })
            .catch(error => {
                console.error('Fetch error:', error);
                showToast('Ошибка сети при загрузке данных', 'error');
            });
    }

    function closeDistributionModal() {
        document.getElementById('distributionModal').style.display = 'none';
        currentPlanGroupId = null;
        allMastersData = [];
        masterQuotas = {};
        alreadyAssigned = {};
    }

    function renderDistributionTable(students) {
        const tbody = document.getElementById('distributionTableBody');
        tbody.innerHTML = '';

        if (!students || students.length === 0) {
            const tr = document.createElement('tr');
            const td = document.createElement('td');
            td.colSpan = 4;
            td.style.padding = '24px';
            td.style.textAlign = 'center';
            td.style.color = '#94a3b8';
            td.textContent = 'Все учащиеся распределены';
            tr.appendChild(td);
            tbody.appendChild(tr);
            return;
        }

        for (let i = 0; i < students.length; i++) {
            const student = students[i];
            const tr = document.createElement('tr');
            tr.style.borderBottom = '1px solid #e2e8f0';

            const tdName = document.createElement('td');
            tdName.style.padding = '10px';
            tdName.style.verticalAlign = 'top';
            tdName.textContent = student.full_name;
            tr.appendChild(tdName);

            const tdServices = document.createElement('td');
            tdServices.style.padding = '10px';
            tdServices.style.verticalAlign = 'top';
            if (student.services && student.services.length > 0) {
                let html = '';
                for (let j = 0; j < student.services.length; j++) {
                    const svc = student.services[j];
                    html += '<div style="margin-bottom:4px;padding:4px 8px;background:#f0f9ff;border-radius:4px;border-left:3px solid #0ea5e9;">';
                    html += '<strong style="color:#0369a1;font-size:12px;">' + svc.name + '</strong><br>';
                    html += '<span style="color:#64748b;font-size:11px;">' + svc.values + '</span></div>';
                }
                tdServices.innerHTML = html;
            } else {
                tdServices.innerHTML = '<span style="color:#94a3b8;font-style:italic;font-size:12px;">Нет услуг</span>';
            }
            tr.appendChild(tdServices);

            const tdLimits = document.createElement('td');
            tdLimits.style.padding = '10px';
            tdLimits.style.verticalAlign = 'top';
            tdLimits.style.fontSize = '12px';
            tdLimits.style.color = '#64748b';

            let limitsHtml = '';

            if (student.car_brand) {
                limitsHtml += '🚗 Марка: <strong>' + student.car_brand + '</strong>';
            }

            if (student.brand_warning) {
                limitsHtml += (limitsHtml ? '<br>' : '') +
                    '<span style="display:inline-block;margin-top:4px;padding:4px 8px;' +
                    'background:#fef2f2;color:#dc2626;border-radius:4px;' +
                    'font-weight:600;font-size:11px;">⚠️ ' + student.brand_warning + '</span>';
            } else if (student.car_brand && student.brand_masters && student.brand_masters.length > 0) {
                limitsHtml += (limitsHtml ? '<br>' : '') +
                    '<span style="color:#16a34a;font-size:11px;">✅ Доступны мастера: ' +
                    student.brand_masters.join(', ') + '</span>';
            }

            if (student.is_locked) {
                limitsHtml += (limitsHtml ? '<br>' : '') +
                    '<span style="color:#dc2626;font-weight:600;">🔒 Мастер из услуг</span>';
            }

            if (!limitsHtml) {
                limitsHtml = '<span style="color:#94a3b8;">Нет ограничений</span>';
            }
            tdLimits.innerHTML = limitsHtml;
            tr.appendChild(tdLimits);

            const tdMaster = document.createElement('td');
            tdMaster.style.padding = '10px';
            tdMaster.style.verticalAlign = 'top';

            const select = document.createElement('select');
            select.style.width = '100%';
            select.style.padding = '6px';
            select.style.borderRadius = '4px';
            select.style.border = '1px solid #cbd5e1';
            select.dataset.studentId = student.id;

            select.addEventListener('change', function () {
                const sid = this.dataset.studentId;
                const row = this.closest('tr');
                const oldHidden = row.querySelector('input[type="hidden"][name="assignment_' + sid + '"]');
                if (oldHidden) oldHidden.remove();

                const hidden = document.createElement('input');
                hidden.type = 'hidden';
                hidden.name = 'assignment_' + sid;
                hidden.value = this.value;
                row.appendChild(hidden);

                updateMasterQuotaDisplay();
            });

            const defaultOpt = document.createElement('option');
            defaultOpt.value = '';
            defaultOpt.textContent = '— Не назначен —';
            select.appendChild(defaultOpt);

            const allowedIds = (student.allowed_master_ids || []).slice();
            if (student.preferred_master_id) {
                const prefId = String(student.preferred_master_id);
                const hasPref = allowedIds.some(id => String(id) === prefId);
                if (!hasPref) allowedIds.push(student.preferred_master_id);
            }

            let optionsAdded = 0;
            for (let k = 0; k < allMastersData.length; k++) {
                const master = allMastersData[k];
                const isAllowed = allowedIds.some(id => String(id) === String(master.id));
                if (isAllowed) {
                    const opt = document.createElement('option');
                    opt.value = master.id;
                    const quota = masterQuotas[master.id] || 0;
                    const already = alreadyAssigned[master.id] || 0;
                    const free = Math.max(0, quota - already);
                    opt.textContent = `${master.name} (свободно ${free} из ${quota})`;
                    select.appendChild(opt);
                    optionsAdded++;
                }
            }

            if (optionsAdded === 0 && student.car_brand) {
                const opt = document.createElement('option');
                opt.value = '';
                opt.disabled = true;
                opt.textContent = '— Нет мастеров с маркой ' + student.car_brand + ' —';
                select.appendChild(opt);
            }

            const currentMaster = student.assigned_master_id || student.preferred_master_id;

            if (currentMaster) {
                const currentStr = String(currentMaster);
                const optionExists = Array.from(select.options).some(o => o.value === currentStr);

                if (!optionExists) {
                    const fallbackOpt = document.createElement('option');
                    fallbackOpt.value = currentStr;
                    const m = allMastersData.find(mm => String(mm.id) === currentStr);
                    fallbackOpt.textContent = (m ? m.name : 'Мастер #' + currentStr) + ' (авто из услуг)';
                    select.appendChild(fallbackOpt);
                }

                select.value = currentStr;

                if (student.is_locked) {
                    select.disabled = true;
                    select.style.backgroundColor = '#f1f5f9';
                    select.style.color = '#64748b';
                }
            }

            const hidden = document.createElement('input');
            hidden.type = 'hidden';
            hidden.name = 'assignment_' + student.id;
            hidden.value = currentMaster ? String(currentMaster) : '';
            tdMaster.appendChild(hidden);

            tdMaster.appendChild(select);
            tr.appendChild(tdMaster);
            tbody.appendChild(tr);
        }

        setTimeout(updateMasterQuotaDisplay, 50);
    }

    function updateMasterQuotaDisplay() {
        const incoming = {};
        const selects = document.querySelectorAll('#distributionTableBody select');

        selects.forEach(sel => {
            if (sel.disabled) return;
            if (sel.value) {
                incoming[sel.value] = (incoming[sel.value] || 0) + 1;
            }
        });

        selects.forEach(sel => {
            if (sel.disabled) return;

            const mid = sel.value;
            if (mid) {
                const quota = masterQuotas[mid] || 0;
                const already = alreadyAssigned[mid] || 0;
                const newCount = incoming[mid] || 0;
                const total = already + newCount;

                if (total > quota) {
                    sel.style.borderColor = '#ef4444';
                    sel.style.backgroundColor = '#fef2f2';
                    sel.title = `⚠️ Превышение: ${already} уже + ${newCount} новых = ${total}, квота ${quota}`;
                } else {
                    sel.style.borderColor = '#cbd5e1';
                    sel.style.backgroundColor = 'white';
                    sel.title = `Назначено: ${total} из ${quota}`;
                }
            } else {
                sel.style.borderColor = '#cbd5e1';
                sel.style.backgroundColor = 'white';
                sel.title = '';
            }
        });
    }

    function submitDistribution() {
        const assignments = {};
        const incoming = {};
        const selects = document.querySelectorAll('#distributionTableBody select');

        selects.forEach(sel => {
            const sid = sel.dataset.studentId;
            let mid = sel.value;

            if (sel.disabled) {
                const row = sel.closest('tr');
                const hidden = row.querySelector('input[type="hidden"][name="assignment_' + sid + '"]');
                if (hidden) mid = hidden.value;
            }

            assignments[sid] = mid;
            if (mid) incoming[mid] = (incoming[mid] || 0) + 1;
        });

        const overflow = [];
        for (const mid in incoming) {
            const quota = masterQuotas[mid] || 0;
            const already = alreadyAssigned[mid] || 0;
            const total = already + incoming[mid];
            if (total > quota) {
                const master = allMastersData.find(m => String(m.id) === String(mid));
                overflow.push(
                    `${master ? master.name : 'Мастер ' + mid}: ` +
                    `${already} + ${incoming[mid]} = ${total}, квота ${quota}`
                );
            }
        }

        if (overflow.length > 0) {
            showToast(
                '⚠️ Превышена квота мастеров:\n' + overflow.join('\n'),
                'error'
            );
            return;
        }

        fetch(URL_SAVE_DISTRIBUTION, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({
                plan_group_id: currentPlanGroupId,
                assignments: assignments
            })
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showToast('✅ ' + data.message, 'success');
                    closeDistributionModal();
                    setTimeout(() => location.reload(), 600);
                } else {
                    showToast('❌ ' + (data.error || 'Неизвестная ошибка'), 'error');
                }
            })
            .catch(error => {
                showToast('Ошибка сети: ' + error, 'error');
            });
    }

    // =======================================================================
    // 🔹 ЯЧЕЙКА: МОДАЛЬНОЕ ОКНО СО СПИСКОМ СТУДЕНТОВ
    // =======================================================================
    function openCellStudentsModal(button) {
        const planGroupId = button.dataset.planGroupId;
        const masterId = button.dataset.masterId;
        if (!planGroupId || !masterId) return;

        document.getElementById('cellStudentsGroup').textContent = '…';
        document.getElementById('cellStudentsMaster').textContent = '…';
        document.getElementById('cellStudentsBody').innerHTML =
            '<div style="padding:32px;text-align:center;color:#94a3b8;">Загрузка…</div>';
        document.getElementById('cellStudentsModal').style.display = 'flex';

        const cacheKey = `${planGroupId}:${masterId}`;

        if (cellStudentsCache[cacheKey]) {
            renderCellStudentsModal(cellStudentsCache[cacheKey]);
            return;
        }

        fetch(buildCellStudentsUrl(planGroupId, masterId))
            .then(r => r.json())
            .then(data => {
                if (!data.success) {
                    document.getElementById('cellStudentsBody').innerHTML =
                        '<div style="padding:32px;text-align:center;color:#dc2626;">Ошибка загрузки</div>';
                    return;
                }
                cellStudentsCache[cacheKey] = data;
                renderCellStudentsModal(data);
            })
            .catch(err => {
                console.error('Fetch cell students error:', err);
                document.getElementById('cellStudentsBody').innerHTML =
                    '<div style="padding:32px;text-align:center;color:#dc2626;">Ошибка сети</div>';
            });
    }

    function renderCellStudentsModal(data) {
        document.getElementById('cellStudentsGroup').textContent = data.group_number || '—';
        document.getElementById('cellStudentsMaster').textContent = data.master_name || '—';

        const body = document.getElementById('cellStudentsBody');

        if (!data.students || data.students.length === 0) {
            body.innerHTML = '<div style="padding:32px;text-align:center;color:#94a3b8;">Нет назначенных студентов</div>';
            return;
        }

        let html = `
            <table style="width:100%;border-collapse:collapse;">
                <thead>
                    <tr style="background:#f1f5f9;position:sticky;top:0;z-index:1;">
                        <th style="padding:10px;text-align:left;font-size:12px;color:#64748b;font-weight:700;">№</th>
                        <th style="padding:10px;text-align:left;font-size:12px;color:#64748b;font-weight:700;">Учащийся</th>
                        <th style="padding:10px;text-align:right;font-size:12px;color:#64748b;font-weight:700;" title="Выкатано часов">Вык.</th>
                        <th style="padding:10px;text-align:right;font-size:12px;color:#64748b;font-weight:700;" title="Осталось часов">Ост.</th>
                        <th style="padding:10px;text-align:right;font-size:12px;color:#64748b;font-weight:700;" title="Всего часов">Всего</th>
                    </tr>
                </thead>
                <tbody>
        `;

        data.students.forEach((s, idx) => {
            const rowBg = s.is_auto ? '#eff6ff' : (idx % 2 === 0 ? '#ffffff' : '#fafbfc');
            const autoBadge = s.is_auto
                ? '<span style="margin-left:6px;font-size:11px;color:#3b82f6;" title="Автоназначение из платной услуги">🔒 авто</span>'
                : '';

            html += `
                <tr style="background:${rowBg};border-bottom:1px solid #e2e8f0;">
                    <td style="padding:10px;font-size:12px;color:#94a3b8;">${idx + 1}</td>
                    <td style="padding:10px;font-size:13px;font-weight:600;color:#1e293b;">
                        ${s.full_name}${autoBadge}
                    </td>
                    <td style="padding:10px;text-align:right;font-size:13px;font-weight:600;color:#16a34a;">
                        ${Math.round(s.hours_completed)}
                    </td>
                    <td style="padding:10px;text-align:right;font-size:13px;font-weight:700;color:#d97706;">
                        ${Math.round(s.hours_remaining)}
                    </td>
                    <td style="padding:10px;text-align:right;font-size:12px;color:#64748b;">
                        ${Math.round(s.hours_required)}
                    </td>
                </tr>
            `;
        });

        html += '</tbody></table>';
        body.innerHTML = html;
    }

    function closeCellStudentsModal() {
        document.getElementById('cellStudentsModal').style.display = 'none';
    }

    // =======================================================================
    // 🔹 ПЕРЕРАСПРЕДЕЛЕНИЕ
    // =======================================================================
    function openReassignFlow() {
        document.getElementById('reassignGroupSelect').value = '';
        document.getElementById('reassignProceedBtn').disabled = true;
        document.getElementById('reassignSelectGroupModal').style.display = 'flex';
    }

    function closeReassignSelectGroup() {
        document.getElementById('reassignSelectGroupModal').style.display = 'none';
    }

    function proceedToReassign() {
        const groupId = document.getElementById('reassignGroupSelect').value;
        if (!groupId) return;

        closeReassignSelectGroup();
        openReassignModal(groupId);
    }

    function openReassignModal(planGroupId) {
        reassignGroupId = planGroupId;
        document.getElementById('reassignGroupName').textContent = '…';
        document.getElementById('reassignTableBody').innerHTML =
            '<tr><td colspan="3" style="padding:24px;text-align:center;color:#94a3b8;">Загрузка…</td></tr>';
        document.getElementById('reassignReason').value = 'reassign';
        document.getElementById('reassignComment').value = '';
        document.getElementById('reassignModal').style.display = 'flex';

        fetch(URL_REASSIGN_DATA.replace('__ID__', planGroupId))
            .then(r => r.json())
            .then(data => {
                if (!data.success) {
                    document.getElementById('reassignTableBody').innerHTML =
                        '<tr><td colspan="3" style="padding:24px;text-align:center;color:#dc2626;">Ошибка загрузки</td></tr>';
                    return;
                }
                document.getElementById('reassignGroupName').textContent = data.group_number;
                reassignMasters = data.masters || [];
                renderReassignTable(data.students || []);
            })
            .catch(err => {
                console.error('Fetch reassign error:', err);
                document.getElementById('reassignTableBody').innerHTML =
                    '<tr><td colspan="3" style="padding:24px;text-align:center;color:#dc2626;">Ошибка сети</td></tr>';
            });
    }

    function renderReassignTable(students) {
        const tbody = document.getElementById('reassignTableBody');
        tbody.innerHTML = '';

        if (!students.length) {
            tbody.innerHTML =
                '<tr><td colspan="3" style="padding:24px;text-align:center;color:#94a3b8;">Нет студентов в группе</td></tr>';
            return;
        }

        for (const s of students) {
            const tr = document.createElement('tr');
            tr.style.borderBottom = '1px solid #e2e8f0';
            tr.dataset.studentId = s.id;

            const tdName = document.createElement('td');
            tdName.style.padding = '8px 10px';
            tdName.style.fontSize = '13px';
            tdName.style.fontWeight = '600';
            tdName.textContent = s.full_name;
            tr.appendChild(tdName);

            const tdCurrent = document.createElement('td');
            tdCurrent.style.padding = '8px 10px';
            tdCurrent.style.fontSize = '12px';
            tdCurrent.style.color = '#64748b';
            tdCurrent.textContent = s.current_master_name || '—';
            tr.appendChild(tdCurrent);

            const tdNew = document.createElement('td');
            tdNew.style.padding = '8px 10px';

            const select = document.createElement('select');
            select.style.width = '100%';
            select.style.padding = '6px';
            select.style.borderRadius = '4px';
            select.style.border = '1px solid #cbd5e1';
            select.dataset.studentId = s.id;
            select.dataset.fromMasterId = s.current_master_id || '';

            const optNone = document.createElement('option');
            optNone.value = '';
            optNone.textContent = '— Не назначен —';
            select.appendChild(optNone);

            for (const m of reassignMasters) {
                const opt = document.createElement('option');
                opt.value = m.id;
                opt.textContent = m.name;
                select.appendChild(opt);
            }

            select.value = s.current_master_id || '';

            tdNew.appendChild(select);
            tr.appendChild(tdNew);

            tbody.appendChild(tr);
        }
    }

    function closeReassignModal() {
        document.getElementById('reassignModal').style.display = 'none';
        reassignGroupId = null;
        reassignMasters = [];
    }

    function submitReassign() {
        if (!reassignGroupId) return;

        const reason = document.getElementById('reassignReason').value;
        const comment = document.getElementById('reassignComment').value.trim();

        const changes = [];
        document.querySelectorAll('#reassignTableBody tr[data-student-id]').forEach(tr => {
            const studentId = tr.dataset.studentId;
            const select = tr.querySelector('select[data-student-id]');
            if (!select) return;

            const fromMasterId = select.dataset.fromMasterId || '';
            const toMasterId = select.value || '';

            if (fromMasterId === toMasterId) return;

            changes.push({
                student_id: parseInt(studentId),
                to_master_id: toMasterId ? parseInt(toMasterId) : null,
            });
        });

        if (changes.length === 0) {
            showToast('Ничего не изменено', 'info');
            return;
        }

        fetch(URL_SAVE_REASSIGN, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
            },
            body: JSON.stringify({
                plan_group_id: reassignGroupId,
                reason: reason,
                comment: comment,
                changes: changes,
            }),
        })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    showToast('✅ ' + data.message, 'success');
                    closeReassignModal();
                    setTimeout(() => location.reload(), 600);
                } else {
                    showToast('❌ Ошибка: ' + data.error, 'error');
                }
            })
            .catch(err => {
                console.error('Save reassign error:', err);
                showToast('Ошибка сети: ' + err, 'error');
            });
    }

    // =======================================================================
    // 🔹 ИНИЦИАЛИЗАЦИЯ
    // =======================================================================
    function init() {
        document.querySelectorAll('.matrix-header-group').forEach(header => {
            const planGroupId = header.dataset.planGroupId;
            hoursPerStudentMap[planGroupId] =
                parseFloat(header.dataset.hoursPerStudent) || DEFAULT_HOURS_PER_STUDENT;

            if (header.dataset.isFullyDistributed === '1') {
                blockGroupMatrixInputs(planGroupId);
            }
        });

        updateGroupCompletionVisuals();
        updateMastersStats();
        syncAllScroll();

        document.querySelectorAll('.matrix-input-manual').forEach(inp => {
            inp.dataset.oldValue = inp.value;
        });

        bindAddGroupForm();
        bindEditGroupForm();
        bindDeleteGroupForm();
        bindModalCloseOnOverlay();

        const reassignGroupSelect = document.getElementById('reassignGroupSelect');
        if (reassignGroupSelect) {
            reassignGroupSelect.addEventListener('change', function () {
                const proceedBtn = document.getElementById('reassignProceedBtn');
                if (proceedBtn) proceedBtn.disabled = !this.value;
            });
        }

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') {
                closeCellStudentsModal();
                closeReassignSelectGroup();
                closeReassignModal();
            }
        });

        // Подсказки на ячейках матрицы (список ФИО)
        bindMatrixCellTooltips();

        // Подсказки на статистике по мастерам (разбивка по группам)
        bindMasterStatsTooltips();
    }

    function bindAddGroupForm() {
        const addForm = document.getElementById('addGroupForm');
        if (addForm && addForm.dataset.bound === '1') return;
        if (addForm) addForm.dataset.bound = '1';

        const groupSelect = document.getElementById('groupSelect');
        if (groupSelect) {
            groupSelect.addEventListener('change', function () {
                const groupId = this.value;
                if (!groupId) {
                    setFieldValue('hoursInput', String(DEFAULT_HOURS_PER_STUDENT));
                    document.querySelectorAll('#addGroupForm [data-date-input="true"]')
                        .forEach(el => el.value = '');
                    return;
                }
                fetch(URLS.getGroupData.replace('__ID__', groupId))
                    .then(response => response.ok ? response.json() : Promise.reject(`Ошибка ${response.status}`))
                    .then(data => {
                        if (data.error) {
                            console.error('Ошибка:', data.error);
                            return;
                        }
                        setFieldValue('hoursInput', data.hours_per_student || DEFAULT_HOURS_PER_STUDENT);
                        const setDateField = (name, value) => {
                            const field = document.querySelector(`#addGroupForm [name="${name}"]`);
                            if (field) field.value = value || '';
                        };
                        ['distribution_date', 'can_drive_from', 'drive_until',
                            'exam_internal_theory_date', 'exam_internal_driving_date', 'exam_gai_date']
                            .forEach(field => setDateField(field, data[field]));
                    })
                    .catch(error => console.error('Ошибка загрузки данных группы:', error));
            });
        }

        if (addForm) {
            addForm.addEventListener('submit', function (e) {
                e.preventDefault();
                if (addForm.dataset.submitting === '1') return;
                addForm.dataset.submitting = '1';

                const submitBtn = addForm.querySelector('button[type="submit"]');
                if (submitBtn) submitBtn.disabled = true;

                const formData = new FormData(addForm);
                const csrfToken = formData.get('csrfmiddlewaretoken') || getCsrfToken();

                fetch(URLS.addGroup, {
                    method: 'POST',
                    headers: { 'X-CSRFToken': csrfToken, 'X-Requested-With': 'XMLHttpRequest' },
                    body: formData,
                })
                    .then(response => {
                        if (!response.ok) {
                            return response.text().then(text => {
                                throw new Error(`Сервер вернул ошибку ${response.status}: ${text.substring(0, 150)}...`);
                            });
                        }
                        return response.json();
                    })
                    .then(data => {
                        if (data.success) {
                            closeAddGroupModal();
                            addForm.reset();
                            location.reload();
                        } else {
                            showToast('❌ Ошибка: ' + (data.error || 'Неизвестная ошибка'), 'error');
                        }
                    })
                    .catch(error => {
                        console.error('Ошибка при добавлении группы:', error);
                        showToast('❌ Ошибка сети или сервера: ' + error.message, 'error');
                    })
                    .finally(() => {
                        addForm.dataset.submitting = '0';
                        if (submitBtn) submitBtn.disabled = false;
                    });
            });
        }
    }

    function bindEditGroupForm() {
        const editGroupSelectStep1 = document.getElementById('editGroupSelect');
        if (editGroupSelectStep1) {
            editGroupSelectStep1.addEventListener('change', function () {
                const selectedId = this.value;
                const proceedBtn = document.getElementById('proceedEditBtn');
                if (selectedId) {
                    selectedEditPlanGroupId = selectedId;
                    proceedBtn.disabled = false;
                } else {
                    selectedEditPlanGroupId = null;
                    proceedBtn.disabled = true;
                }
            });
        }

        const editForm = document.getElementById('editForm');
        if (editForm) {
            editForm.addEventListener('submit', function (e) {
                e.preventDefault();
                if (editForm.dataset.submitting === '1') return;
                editForm.dataset.submitting = '1';

                const submitBtn = editForm.querySelector('button[type="submit"]');
                if (submitBtn) submitBtn.disabled = true;

                const formData = new FormData(editForm);
                if (!formData.get('plan_group_id')) {
                    showToast('❌ Ошибка: не указан ID группы в плане.', 'error');
                    editForm.dataset.submitting = '0';
                    if (submitBtn) submitBtn.disabled = false;
                    return;
                }
                fetch(URLS.updateGroup, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': formData.get('csrfmiddlewaretoken') || getCsrfToken(),
                        'X-Requested-With': 'XMLHttpRequest',
                    },
                    body: formData,
                })
                    .then(response => response.ok ? response.json() : Promise.reject(`Ошибка сервера: ${response.status}`))
                    .then(data => {
                        if (data.success) {
                            closeEditModal();
                            location.reload();
                        } else {
                            showToast('❌ Ошибка: ' + (data.error || 'Неизвестная ошибка'), 'error');
                        }
                    })
                    .catch(error => {
                        console.error('Ошибка сети:', error);
                        showToast('❌ Ошибка сети или сервера: ' + error.message, 'error');
                    })
                    .finally(() => {
                        editForm.dataset.submitting = '0';
                        if (submitBtn) submitBtn.disabled = false;
                    });
            });
        }
    }

    function bindDeleteGroupForm() {
        const deleteSelect = document.getElementById('deleteGroupSelect');
        if (deleteSelect) {
            deleteSelect.addEventListener('change', function () {
                const selectedId = this.value;
                const warning = document.getElementById('deleteWarning');
                const warningText = document.getElementById('deleteWarningText');
                const confirmBtn = document.getElementById('confirmDeleteBtn');

                if (selectedId) {
                    deletePlanGroupId = selectedId;
                    warning.style.display = 'block';
                    confirmBtn.disabled = false;

                    warning.style.background = '#fef2f2';
                    warning.style.border = '1px solid #fecaca';
                    warningText.style.color = '#dc2626';

                    const groupName = this.options[this.selectedIndex].text;
                    warningText.textContent = `⚠️ Внимание! Это действие нельзя отменить. Группа "${groupName}" будет удалена из генерального плана вместе со всеми распределениями по мастерам.`;
                } else {
                    deletePlanGroupId = null;
                    warning.style.display = 'none';
                    confirmBtn.disabled = true;
                }
            });
        }
    }

    function bindModalCloseOnOverlay() {
        ['addGroupModal', 'selectEditModal', 'editModal', 'deleteModal',
         'distributionModal', 'cellStudentsModal',
         'reassignSelectGroupModal', 'reassignModal']
            .forEach(modalId => {
                const modal = document.getElementById(modalId);
                if (modal) {
                    modal.addEventListener('click', function (e) {
                        if (e.target === this) {
                            if (modalId === 'addGroupModal') closeAddGroupModal();
                            if (modalId === 'selectEditModal') closeSelectEditModal();
                            if (modalId === 'editModal') closeEditModal();
                            if (modalId === 'deleteModal') closeDeleteModal();
                            if (modalId === 'distributionModal') closeDistributionModal();
                            if (modalId === 'cellStudentsModal') closeCellStudentsModal();
                            if (modalId === 'reassignSelectGroupModal') closeReassignSelectGroup();
                            if (modalId === 'reassignModal') closeReassignModal();
                        }
                    });
                }
            });
    }

    // =======================================================================
    // 🔹 АВТОЗАПУСК
    // =======================================================================
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            initGlobalTooltip();
            init();
        });
    } else {
        initGlobalTooltip();
        init();
    }

    // =======================================================================
    // 🔹 ЭКСПОРТ В window
    // =======================================================================
    window.updateDistribution = updateDistribution;
    window.showToast = showToast;
    window.openAddGroupModal = openAddGroupModal;
    window.closeAddGroupModal = closeAddGroupModal;
    window.openEditModal = openEditModal;
    window.closeSelectEditModal = closeSelectEditModal;
    window.proceedToEdit = proceedToEdit;
    window.closeEditModal = closeEditModal;
    window.openDeleteModal = openDeleteModal;
    window.closeDeleteModal = closeDeleteModal;
    window.confirmDelete = confirmDelete;

    window.autoOpenDistributionModal = autoOpenDistributionModal;
    window.openDistributionModal = openDistributionModal;
    window.closeDistributionModal = closeDistributionModal;
    window.submitDistribution = submitDistribution;
    window.updateMasterQuotaDisplay = updateMasterQuotaDisplay;
    window.renderDistributionTable = renderDistributionTable;

    window.openCellStudentsModal = openCellStudentsModal;
    window.closeCellStudentsModal = closeCellStudentsModal;

    window.openReassignFlow = openReassignFlow;
    window.closeReassignSelectGroup = closeReassignSelectGroup;
    window.proceedToReassign = proceedToReassign;
    window.openReassignModal = openReassignModal;
    window.closeReassignModal = closeReassignModal;
    window.submitReassign = submitReassign;

    window.showMatrixCellTooltip = showMatrixCellTooltip;
    window.hideMatrixCellTooltip = hideMatrixCellTooltip;
    window.bindMatrixCellTooltips = bindMatrixCellTooltips;

    window.showMasterStatsTooltip = showMasterStatsTooltip;
    window.hideMasterStatsTooltip = hideMasterStatsTooltip;
    window.bindMasterStatsTooltips = bindMasterStatsTooltips;

    window.__masterPlan = {
        updateGroupCompletionVisuals,
        updateMastersStats,
        hoursPerStudentMap,
        cellStudentsCache,
        blockGroupMatrixInputs,
    };
})();