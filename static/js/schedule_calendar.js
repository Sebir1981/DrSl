/**
 * schedule_calendar.js — Stable Base v1.6
 * ✅ Global tooltip with smart positioning
 * ✅ Tooltip never goes outside viewport
 * ✅ Better readability
 */

const CFG = {
    SLOTS: { MORNING: 'У', DAY: 'Д', EVENING: 'В' },
    CLS: {
        DAY: 'cal-day', EMPTY: 'cal-empty', SCHEDULED: 'is-scheduled', WEEKEND: 'is-weekend',
        MED: 'is-med', CONFLICT: 'is-conflict', INACTIVE: 'is-inactive', NUM: 'cal-num',
        TEACHER_SLOTS_ROW: 'teacher-slots', CURRENT_SLOTS_ROW: 'current-slots',
        MED_BADGE: 'med-badge',
        TOOLTIP: 'cal-tooltip', BOTTOM_ROW: 'bottom-row', MONTH: 'calendar-month',
        MONTH_TITLE: 'cal-month-title', GRID: 'calendar-grid', HEAD: 'cal-head',
        SLOT_BADGE: 'slot-badge', SLOT_U: 'slot-u', SLOT_D: 'slot-d', SLOT_V: 'slot-v',
        SLOT_CONFLICT: 'slot-conflict',
        TEACHER_INDICATOR: 'teacher-indicator'
    }
};

const Utils = {
    parseDate(str) {
        if (!str || typeof str !== 'string') return null;
        if (/^\d{4}-\d{2}-\d{2}$/.test(str)) {
            const [y, m, d] = str.split('-').map(Number);
            return new Date(y, m - 1, d);
        }
        return null;
    },
    formatDate(d) {
        return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    },
    isScheduledDate(date, type) {
        const day = date.getDate(), isWk = date.getDay() === 0 || date.getDay() === 6;
        if (type === 'odd') return day % 2 === 1 && !isWk;
        if (type === 'even') return day % 2 === 0 && !isWk;
        if (type === 'weekend') return isWk;
        return true;
    },
    arraysEqual(a, b) {
        if (!a && !b) return true;
        if (!a || !b || a.length !== b.length) return false;
        const sa = [...a].sort(), sb = [...b].sort();
        for (let i = 0; i < sa.length; i++) if (sa[i] !== sb[i]) return false;
        return true;
    },
    createSlotBadge(slotType) {
        const span = document.createElement('span');
        span.className = `${CFG.CLS.SLOT_BADGE} ${slotType === CFG.SLOTS.MORNING ? CFG.CLS.SLOT_U : slotType === CFG.SLOTS.DAY ? CFG.CLS.SLOT_D : CFG.CLS.SLOT_V}`;
        span.textContent = slotType;
        span.style.cssText = 'font-size:8px!important;padding:1px 3px!important;border-radius:2px!important;font-weight:600!important;background:#e2e8f0!important;color:#334155!important;white-space:nowrap!important;line-height:1.2!important;margin:0!important;';
        return span;
    }
};

class ScheduleCalendar {
    constructor() {
        this.teacherScheduleData = {};
        this.mainTeacherData = {};
        this.medTeacherData = {};
        this._state = {
            excludedDates: [],
            additionalDates: [],
            currentScheduleType: 'custom',
            dateStart: null,
            dateEnd: null,
            defaultSlotsSnapshot: []
        };
        this._elements = {};
        this._listeners = [];
        this._debounceTimer = null;
        this.currentDate = null;
        this._tooltipEl = null;
    }

    init() {
        this._cacheElements();
        this._createGlobalTooltip();
        this._bindEvents();
    }

    _cacheElements() {
        this._elements = {
            classDays: document.getElementById('id_class_days'),
            excluded: document.getElementById('id_excluded_dates'),
            additional: document.getElementById('id_additional_dates'),
            dateStart: document.getElementById('id_date_start'),
            dateEnd: document.getElementById('id_date_end'),
            scheduleType: document.getElementById('id_schedule_type'),
            timeMorning: document.getElementById('id_time_morning'),
            timeDay: document.getElementById('id_time_day'),
            timeEvening: document.getElementById('id_time_evening'),
            monthsContainer: document.getElementById('months-container'),
            modal: document.getElementById('day-modal'),
            del: document.getElementById('m-del'),
            mTitle: document.getElementById('m-title'),
            mDate: document.getElementById('m-date'),
            mSlotU: document.getElementById('m-slot-u'),
            mSlotD: document.getElementById('m-slot-d'),
            mSlotV: document.getElementById('m-slot-v'),
            mMed: document.getElementById('m-med-toggle'),
            mWarn: document.getElementById('m-conflict-warn')
        };
    }

    _createGlobalTooltip() {
        if (this._tooltipEl) return;
        this._tooltipEl = document.createElement('div');
        this._tooltipEl.id = 'global-cal-tooltip';
        this._tooltipEl.className = CFG.CLS.TOOLTIP;
        this._tooltipEl.style.cssText = [
            'position:fixed',
            'z-index:99999',
            'min-width:240px',
            'max-width:320px',
            'padding:12px 14px',
            'background:#ffffff',
            'border:2px solid #334155',
            'border-radius:8px',
            'box-shadow:0 8px 24px rgba(0,0,0,0.35)',
            'font-size:12px',
            'line-height:1.6',
            'color:#0f172a',
            'display:none',
            'pointer-events:none',
            'opacity:0',
            'white-space:normal',
            'text-align:left',
            'box-sizing:border-box',
            'transition:opacity 0.15s ease'
        ].join(';');
        document.body.appendChild(this._tooltipEl);
    }

    updateTeachers(rawData) {
        if (!rawData || typeof rawData !== 'object') return;
        this.teacherScheduleData = {};
        this.mainTeacherData = {};
        this.medTeacherData = {};

        for (const [date, slots] of Object.entries(rawData)) {
            if (!Array.isArray(slots)) continue;
            const main = [], med = [];
            slots.forEach(item => {
                const ind = typeof item === 'string' ? item : (item.ind || item.slot);
                const isMed = typeof item === 'object' && (item.is_med || item.isMed);
                if (!ind) return;
                const obj = { ind, isMed, group: typeof item === 'object' ? (item.group || '') : '', location: typeof item === 'object' ? (item.location || '') : '' };
                if (isMed) {
                    med.push(obj);
                    this.medTeacherData[date] = this.medTeacherData[date] || [];
                    this.medTeacherData[date].push(obj);
                } else {
                    main.push(obj);
                    this.mainTeacherData[date] = this.mainTeacherData[date] || [];
                    this.mainTeacherData[date].push(obj);
                }
                this.teacherScheduleData[date] = this.teacherScheduleData[date] || [];
                this.teacherScheduleData[date].push(obj);
            });
        }
        this._refreshVisibleDays();
        this._enforceLayoutAll();
    }

    _refreshVisibleDays() {
        if (!this._elements.monthsContainer) return;
        this._elements.monthsContainer.querySelectorAll('.cal-day:not(.cal-empty)').forEach(el => this._updateDayVisuals(el));
    }

    _enforceLayoutAll() {
        if (!this._elements.monthsContainer) return;
        this._elements.monthsContainer.querySelectorAll('.cal-day:not(.cal-empty)').forEach(el => this._enforceLayout(el));
    }

    _enforceLayout(el) {
        const bottomRow = el.querySelector('.bottom-row');
        if (bottomRow) {
            bottomRow.style.cssText = 'display:flex!important;flex-direction:row!important;justify-content:space-between!important;align-items:flex-start!important;gap:2px!important;margin-top:2px!important;width:100%!important;';
        }
        const teacherSlots = el.querySelector('.teacher-slots');
        if (teacherSlots) {
            teacherSlots.style.cssText = 'display:flex!important;flex-direction:column!important;gap:1px!important;align-items:flex-start!important;margin:0!important;flex:0 0 auto!important;';
        }
        const currentSlots = el.querySelector('.current-slots');
        if (currentSlots) {
            currentSlots.style.cssText = 'display:flex!important;flex-direction:column!important;gap:1px!important;align-items:flex-end!important;margin:0!important;flex:0 0 auto!important;margin-left:auto!important;';
        }
    }

    _checkConflict(dateStr, slots, isMed) {
        const result = { hasConflict: false, conflictSlots: new Set() };
        if (!slots?.length) return result;
        const mainData = this.mainTeacherData[dateStr] || [];
        const medData = this.medTeacherData[dateStr] || [];
        const allTeacherData = [...mainData, ...medData];
        for (const slot of slots) {
            for (const item of allTeacherData) {
                if (slot === item.ind) {
                    result.hasConflict = true;
                    result.conflictSlots.add(slot);
                    break;
                }
            }
        }
        return result;
    }

    generateCalendar(dateStart, dateEnd, scheduleType, savedDays) {
        const s = Utils.parseDate(dateStart), e = Utils.parseDate(dateEnd);
        if (!s || !e) return false;
        this._state.currentScheduleType = scheduleType || 'custom';
        this._state.dateStart = dateStart;
        this._state.dateEnd = dateEnd;
        this._state.defaultSlotsSnapshot = [];
        if (this._elements.timeMorning?.checked) this._state.defaultSlotsSnapshot.push(CFG.SLOTS.MORNING);
        if (this._elements.timeDay?.checked) this._state.defaultSlotsSnapshot.push(CFG.SLOTS.DAY);
        if (this._elements.timeEvening?.checked) this._state.defaultSlotsSnapshot.push(CFG.SLOTS.EVENING);
        try { this._state.excludedDates = JSON.parse(this._elements.excluded?.value || '[]'); } catch { this._state.excludedDates = []; }

        const frag = document.createDocumentFragment();
        let cur = new Date(s.getFullYear(), s.getMonth(), 1);
        const endM = new Date(e.getFullYear(), e.getMonth(), 1);
        const mNames = ['Янв','Фев','Мар','Апр','Май','Июн','Июл','Авг','Сен','Окт','Ноя','Дек'];

        while (cur <= endM) {
            frag.appendChild(this._renderMonth(cur, mNames, savedDays));
            cur = new Date(cur.getFullYear(), cur.getMonth() + 1, 1);
        }
        if (this._elements.monthsContainer) this._elements.monthsContainer.replaceChildren(frag);
        this._enforceLayoutAll();
        this.calculateDateLogs();
        this.updateJSON();
        return true;
    }

    _renderMonth(date, mNames, savedDays) {
        const y = date.getFullYear(), m = date.getMonth();
        const div = document.createElement('div');
        div.className = CFG.CLS.MONTH;
        div.innerHTML = `<div class="${CFG.CLS.MONTH_TITLE}">${mNames[m]} ${y}</div>`;
        const grid = document.createElement('div');
        grid.className = CFG.CLS.GRID;
        ['Пн','Вт','Ср','Чт','Пт','Сб','Вс'].forEach(n => {
            const h = document.createElement('div'); h.className = CFG.CLS.HEAD; h.textContent = n; grid.appendChild(h);
        });
        const fd = new Date(y, m, 1).getDay() || 7;
        for (let i = 1; i < fd; i++) { const el = document.createElement('div'); el.className = `${CFG.CLS.DAY} ${CFG.CLS.EMPTY}`; grid.appendChild(el); }
        const dim = new Date(y, m + 1, 0).getDate();
        for (let d = 1; d <= dim; d++) grid.appendChild(this._createDayElement(y, m, d, savedDays));
        div.appendChild(grid);
        return div;
    }

    _createDayElement(y, m, d, savedDays) {
        const dt = new Date(y, m, d);
        const dateStr = Utils.formatDate(dt);
        const isWk = dt.getDay() === 0 || dt.getDay() === 6;
        const shouldSchedule = Utils.isScheduledDate(dt, this._state.currentScheduleType);

        let dayData = { slots: [], med: false, _useDefault: true, scheduled: false, manuallyRemoved: false };
        if (savedDays && savedDays[dateStr]) dayData = { ...savedDays[dateStr] };
        else if (shouldSchedule && !this._state.excludedDates.includes(dateStr)) {
            dayData.slots = [...this._state.defaultSlotsSnapshot];
            dayData.scheduled = dayData.slots.length > 0;
        }

        const el = document.createElement('div');
        el.className = this._buildClassList(dayData, isWk, shouldSchedule, dateStr);
        el.dataset.date = dateStr;
        el.dataset.scheduled = dayData.scheduled ? 'true' : 'false';
        el.dataset.daydata = JSON.stringify(dayData);
        el.style.cursor = 'pointer';

        const teacherSlotsRow = document.createElement('div');
        teacherSlotsRow.className = CFG.CLS.TEACHER_SLOTS_ROW;
        teacherSlotsRow.style.cssText = 'display:flex!important;flex-direction:column!important;gap:1px!important;align-items:flex-start!important;margin:0!important;flex:0 0 auto!important;';
        this._renderTeacherSlots(teacherSlotsRow, dateStr, dayData);

        const currentSlotsRow = document.createElement('div');
        currentSlotsRow.className = CFG.CLS.CURRENT_SLOTS_ROW;
        currentSlotsRow.style.cssText = 'display:flex!important;flex-direction:column!important;gap:1px!important;align-items:flex-end!important;margin:0!important;flex:0 0 auto!important;margin-left:auto!important;';
        this._renderCurrentSlots(currentSlotsRow, dateStr, dayData);

        const bottomRow = document.createElement('div');
        bottomRow.className = CFG.CLS.BOTTOM_ROW;
        bottomRow.style.cssText = 'display:flex!important;flex-direction:row!important;justify-content:space-between!important;align-items:flex-start!important;gap:2px!important;margin-top:2px!important;width:100%!important;';
        bottomRow.appendChild(teacherSlotsRow);
        bottomRow.appendChild(currentSlotsRow);

        const numSpan = document.createElement('span'); numSpan.className = CFG.CLS.NUM; numSpan.textContent = d; el.appendChild(numSpan);
        if (dayData.med) { const badge = document.createElement('div'); badge.className = CFG.CLS.MED_BADGE; badge.textContent = ''; badge.style.cssText = 'color:#22c55e;font-weight:800;font-size:11px;'; el.appendChild(badge); }
        el.appendChild(bottomRow);
        return el;
    }

    _renderTeacherSlots(container, dateStr, dayData) {
        container.replaceChildren();
        const tData = this.teacherScheduleData[dateStr] || [];
        if (!tData.length) return;

        const conflictInfo = this._checkConflict(dateStr, dayData.slots || [], dayData.med);
        const conflictInds = new Set();
        tData.forEach(item => {
            if (conflictInfo.conflictSlots.has(item.ind)) conflictInds.add(item.ind);
        });

        tData.forEach(item => {
            if (!item.ind) return;
            const span = document.createElement('span');
            span.className = `${CFG.CLS.SLOT_BADGE} ${item.ind === CFG.SLOTS.MORNING ? CFG.CLS.SLOT_U : item.ind === CFG.SLOTS.DAY ? CFG.CLS.SLOT_D : CFG.CLS.SLOT_V}`;
            span.textContent = item.ind;
            const isConflicted = conflictInds.has(item.ind);
            span.style.cssText = isConflicted
                ? 'font-size:8px!important;padding:1px 3px!important;border-radius:2px!important;font-weight:700!important;background:#fecaca!important;color:#991b1b!important;white-space:nowrap!important;line-height:1.2!important;margin:0!important;border:1px solid #ef4444!important;box-shadow:0 0 0 1px #ef4444!important;'
                : 'font-size:8px!important;padding:1px 3px!important;border-radius:2px!important;font-weight:600!important;background:#e2e8f0!important;color:#334155!important;white-space:nowrap!important;line-height:1.2!important;margin:0!important;';
            if (isConflicted) span.title = '️ Конфликт с расписанием';
            container.appendChild(span);
        });
    }

    _renderCurrentSlots(container, dateStr, dayData) {
        container.replaceChildren();
        if (dayData.manuallyRemoved) return;

        const conflictInfo = this._checkConflict(dateStr, dayData.slots || [], dayData.med);

        (dayData.slots || []).forEach(s => {
            const span = document.createElement('span');
            span.className = `${CFG.CLS.SLOT_BADGE} ${s === CFG.SLOTS.MORNING ? CFG.CLS.SLOT_U : s === CFG.SLOTS.DAY ? CFG.CLS.SLOT_D : CFG.CLS.SLOT_V}`;
            span.textContent = s;
            const isConflicted = conflictInfo.conflictSlots.has(s);
            span.style.cssText = isConflicted
                ? 'font-size:8px!important;padding:1px 3px!important;border-radius:2px!important;font-weight:700!important;background:#fecaca!important;color:#991b1b!important;white-space:nowrap!important;line-height:1.2!important;margin:0!important;border:1px solid #ef4444!important;box-shadow:0 0 0 1px #ef4444!important;'
                : 'font-size:8px!important;padding:1px 3px!important;border-radius:2px!important;font-weight:600!important;background:#dbeafe!important;color:#1e40af!important;white-space:nowrap!important;line-height:1.2!important;margin:0!important;';
            if (isConflicted) span.title = `⚠️ Конфликт: ${dayData.med ? 'мед.' : 'осн.'} преподаватель занят в это время`;
            container.appendChild(span);
        });
    }

    _buildClassList(dayData, isWk, shouldSchedule, dateStr) {
        const classes = [CFG.CLS.DAY];
        const isManuallyRemoved = dayData.manuallyRemoved;
        if (isManuallyRemoved) {
            classes.push(CFG.CLS.INACTIVE);
        } else if (dayData.scheduled) {
            classes.push(CFG.CLS.SCHEDULED);
        } else if (!shouldSchedule) {
            classes.push(CFG.CLS.INACTIVE);
        }
        if (isWk) classes.push(CFG.CLS.WEEKEND);
        if (dayData.med) classes.push(CFG.CLS.MED);
        if (this._hasConflict(dateStr, dayData.slots, dayData.med)) classes.push(CFG.CLS.CONFLICT);
        return classes.filter(Boolean).join(' ');
    }

    _hasConflict(dateStr, slots, isMed) {
        return this._checkConflict(dateStr, slots, isMed).hasConflict;
    }

    _showTooltip(targetEl, dateStr) {
        if (!this._tooltipEl) this._createGlobalTooltip();
        const tData = this.teacherScheduleData[dateStr];
        if (!tData?.length) {
            this._hideTooltip();
            return;
        }

        const listHtml = tData.map((item) => {
            if (!item.ind) return '';
            const timeClass = item.ind === 'У' ? 'morning' : item.ind === 'Д' ? 'day' : 'evening';
            const loc = item.location || '— адрес не указан —';
            return `<div class="tooltip-item">
                <span class="time-badge ${timeClass}">${item.ind}</span>
                <span class="tooltip-location">${loc}</span>
                ${item.isMed ? '<span class="med-icon" title="Медицина">✚</span>' : ''}
            </div>`;
        }).join('');

        const groups = [...new Set(tData.map(i => i.group).filter(Boolean))];
        const groupHtml = groups.length > 0
            ? `<div class="tooltip-group">${groups.length === 1 ? 'Группа: ' + groups[0] : 'Группы: ' + groups.join(', ')}</div>`
            : '';

        this._tooltipEl.innerHTML = `
            <div class="tooltip-header">📅 Занятое расписание</div>
            <div>${listHtml}</div>
            ${groupHtml}
        `;

        // ✅ Показываем тултип СНАЧАЛА (чтобы получить размеры)
        this._tooltipEl.classList.add('show');
        this._tooltipEl.style.display = 'block';
        this._tooltipEl.style.opacity = '1';

        // Получаем размеры
        const tipRect = this._tooltipEl.getBoundingClientRect();
        const targetRect = targetEl.getBoundingClientRect();
        const margin = 10;
        const vw = window.innerWidth;
        const vh = window.innerHeight;

        // ✅ Умное позиционирование: пробуем сверху, если не влезает — снизу
        let top = targetRect.top - tipRect.height - margin;
        let left = targetRect.left + targetRect.width / 2 - tipRect.width / 2;

        // Проверяем, влезает ли сверху
        const fitsTop = top >= margin;
        const fitsBottom = (targetRect.bottom + tipRect.height + margin) <= (vh - margin);

        if (!fitsTop && fitsBottom) {
            // Показываем снизу
            top = targetRect.bottom + margin;
        }

        // ✅ Clamp по горизонтали
        if (left < margin) {
            left = margin;
        } else if (left + tipRect.width > vw - margin) {
            left = vw - tipRect.width - margin;
        }

        // ✅ Clamp по вертикали
        if (top < margin) top = margin;
        if (top + tipRect.height > vh - margin) {
            top = vh - tipRect.height - margin;
        }

        // Применяем позицию
        this._tooltipEl.style.left = `${Math.round(left)}px`;
        this._tooltipEl.style.top = `${Math.round(top)}px`;
    }

    _hideTooltip() {
        if (this._tooltipEl) {
            this._tooltipEl.classList.remove('show');
            this._tooltipEl.style.opacity = '0';
            setTimeout(() => {
                if (this._tooltipEl && !this._tooltipEl.classList.contains('show')) {
                    this._tooltipEl.style.display = 'none';
                    this._tooltipEl.innerHTML = '';
                }
            }, 150);
        }
    }

    _updateDayVisuals(el) {
        const date = el.dataset.date; if (!date) return;
        let dayData = {}; try { dayData = JSON.parse(el.dataset.daydata || '{}'); } catch (e) {}
        const dt = Utils.parseDate(date); if (!dt) return;
        const isWk = dt.getDay() === 0 || dt.getDay() === 6;
        const shouldSchedule = Utils.isScheduledDate(dt, this._state.currentScheduleType);

        el.className = this._buildClassList(dayData, isWk, shouldSchedule, date);
        el.dataset.scheduled = (dayData.scheduled && !dayData.manuallyRemoved) ? 'true' : 'false';

        const teacherSlotsRow = el.querySelector('.teacher-slots');
        if (teacherSlotsRow) this._renderTeacherSlots(teacherSlotsRow, date, dayData);

        const currentSlotsRow = el.querySelector('.current-slots');
        if (currentSlotsRow) this._renderCurrentSlots(currentSlotsRow, date, dayData);

        let mi = el.querySelector('.med-badge');
        if (dayData.med && !mi) {
            const badge = document.createElement('div');
            badge.className = CFG.CLS.MED_BADGE;
            badge.textContent = '';
            badge.style.cssText = 'color:#22c55e;font-weight:800;font-size:11px;';
            const br = el.querySelector('.bottom-row');
            if (br) el.insertBefore(badge, br);
        } else if (!dayData.med && mi) {
            mi.remove();
        }

        this._enforceLayout(el);
    }

    openDayModal(el) {
        if (!el?.dataset?.date) return;
        this.currentDate = el.dataset.date;
        if (this._elements.mTitle) this._elements.mTitle.textContent = this.currentDate;
        if (this._elements.mDate) this._elements.mDate.value = this.currentDate;
        let dayData = {}; try { dayData = JSON.parse(el.dataset.daydata || '{}'); } catch (e) {}
        if (this._elements.del) this._elements.del.style.display = (dayData.scheduled || dayData.manuallyRemoved) ? 'inline-block' : 'none';
        const slots = dayData.slots || [];
        if (this._elements.mSlotU) this._elements.mSlotU.checked = slots.includes('У');
        if (this._elements.mSlotD) this._elements.mSlotD.checked = slots.includes('Д');
        if (this._elements.mSlotV) this._elements.mSlotV.checked = slots.includes('В');
        if (this._elements.mMed) this._elements.mMed.checked = dayData.med || false;
        if (this._elements.modal) this._elements.modal.style.display = 'flex';
    }

    saveModal() {
        if (!this.currentDate) return;
        const el = this._elements.monthsContainer?.querySelector(`.cal-day[data-date="${this.currentDate}"]`); if (!el) return;
        const slots = [];
        if (this._elements.mSlotU?.checked) slots.push('У');
        if (this._elements.mSlotD?.checked) slots.push('Д');
        if (this._elements.mSlotV?.checked) slots.push('В');
        let dayData = {}; try { dayData = JSON.parse(el.dataset.daydata || '{}'); } catch (e) {}
        dayData._useDefault = false;
        dayData.manuallyRemoved = false;
        dayData.slots = slots;
        dayData.med = this._elements.mMed?.checked || false;
        dayData.scheduled = slots.length > 0;
        if (slots.length > 0) {
            const idx = this._state.excludedDates.indexOf(this.currentDate);
            if (idx > -1) {
                this._state.excludedDates.splice(idx, 1);
                if (this._elements.excluded) this._elements.excluded.value = JSON.stringify(this._state.excludedDates);
            }
        }
        el.dataset.daydata = JSON.stringify(dayData);
        this._updateDayVisuals(el);
        this.closeModal();
        this.updateJSON();
    }

    deleteDay() {
        if (!this.currentDate) return;
        const el = this._elements.monthsContainer?.querySelector(`.cal-day[data-date="${this.currentDate}"]`); if (!el) return;
        let dayData = {}; try { dayData = JSON.parse(el.dataset.daydata || '{}'); } catch (e) {}
        dayData.scheduled = false;
        dayData.manuallyRemoved = true;
        dayData.slots = [];
        dayData.med = false;
        dayData._useDefault = false;
        el.dataset.daydata = JSON.stringify(dayData);
        if (!this._state.excludedDates.includes(this.currentDate)) {
            this._state.excludedDates.push(this.currentDate);
            this._state.excludedDates.sort();
            if (this._elements.excluded) {
                this._elements.excluded.value = JSON.stringify(this._state.excludedDates);
            }
        }
        this._updateDayVisuals(el);
        this.closeModal();
        this.updateJSON();
    }

    closeModal() {
        if (this._elements.modal) this._elements.modal.style.display = 'none';
        this.currentDate = null;
    }

    updateJSON() {
        const days = {};
        this._elements.monthsContainer?.querySelectorAll('.cal-day').forEach(el => {
            try {
                const dayData = JSON.parse(el.dataset.daydata || '{}');
                if ((dayData.scheduled && !dayData.manuallyRemoved) || dayData.manuallyRemoved) {
                    days[el.dataset.date] = dayData;
                }
            } catch (e) {}
        });
        if (this._elements.classDays) this._elements.classDays.value = JSON.stringify(days);
    }

    calculateDateLogs() {
        const s = Utils.parseDate(this._state.dateStart), e = Utils.parseDate(this._state.dateEnd);
        if (!s || !e) return;
        const ideal = new Set(), actual = new Set();
        let cur = new Date(s);
        while (cur <= e) {
            const dStr = Utils.formatDate(cur);
            if (Utils.isScheduledDate(cur, this._state.currentScheduleType)) ideal.add(dStr);
            const el = this._elements.monthsContainer?.querySelector(`.cal-day[data-date="${dStr}"]`);
            if (el) {
                let dayData = {}; try { dayData = JSON.parse(el.dataset.daydata || '{}'); } catch (e) {}
                if (dayData.scheduled && !dayData.manuallyRemoved) actual.add(dStr);
            }
            cur.setDate(cur.getDate() + 1);
        }
        const newExcl = [], newAdd = [];
        ideal.forEach(d => { if (!actual.has(d)) newExcl.push(d); });
        actual.forEach(d => { if (!ideal.has(d)) newAdd.push(d); });
        if (!Utils.arraysEqual(newExcl, this._state.excludedDates)) {
            this._state.excludedDates = newExcl.sort();
            if (this._elements.excluded) this._elements.excluded.value = JSON.stringify(this._state.excludedDates);
        }
        if (!Utils.arraysEqual(newAdd, this._state.additionalDates)) {
            this._state.additionalDates = newAdd.sort();
            if (this._elements.additional) this._elements.additional.value = JSON.stringify(this._state.additionalDates);
        }
    }

    _bindEvents() {
        const c = this._elements.monthsContainer;
        if (!c) return;

        const clickHandler = (e) => {
            const el = e.target.closest('.cal-day[data-date]');
            if (el) { e.preventDefault(); this._hideTooltip(); this.openDayModal(el); }
        };
        c.addEventListener('click', clickHandler);
        this._listeners.push({ el: c, evt: 'click', fn: clickHandler });

        const onMouseOver = (e) => {
            const el = e.target.closest('.cal-day:not(.cal-empty)');
            if (!el) return;
            const date = el.dataset.date;
            if (!date) return;
            this._showTooltip(el, date);
        };

        const onMouseOut = (e) => {
            const el = e.target.closest('.cal-day');
            if (!el) return;
            const to = e.relatedTarget;
            if (to && el.contains(to)) return;
            this._hideTooltip();
        };

        c.addEventListener('mouseover', onMouseOver);
        c.addEventListener('mouseout', onMouseOut);
        this._listeners.push({ el: c, evt: 'mouseover', fn: onMouseOver });
        this._listeners.push({ el: c, evt: 'mouseout', fn: onMouseOut });

        const onScroll = () => this._hideTooltip();
        window.addEventListener('scroll', onScroll, true);
        window.addEventListener('resize', onScroll);
        this._listeners.push({ el: window, evt: 'scroll', fn: onScroll, cap: true });
        this._listeners.push({ el: window, evt: 'resize', fn: onScroll });

        if (this._elements.modal) this._elements.modal.addEventListener('click', (e) => { if (e.target === this._elements.modal) this.closeModal(); });
        if (this._elements.del) this._elements.del.addEventListener('click', () => this.deleteDay());

        const updateTimeSlots = () => {
            if (!this._elements.monthsContainer) return;
            const newSlots = [];
            if (this._elements.timeMorning?.checked) newSlots.push('У');
            if (this._elements.timeDay?.checked) newSlots.push('Д');
            if (this._elements.timeEvening?.checked) newSlots.push('В');

            this._elements.monthsContainer.querySelectorAll('.cal-day[data-date]').forEach(el => {
                let dayData = {}; try { dayData = JSON.parse(el.dataset.daydata || '{}'); } catch (e) {}
                if (dayData._useDefault === true && !dayData.manuallyRemoved) {
                    dayData.slots = [...newSlots];
                    dayData.scheduled = newSlots.length > 0;
                    el.dataset.daydata = JSON.stringify(dayData);
                    this._updateDayVisuals(el);
                }
            });
            this.updateJSON();
        };

        [this._elements.timeMorning, this._elements.timeDay, this._elements.timeEvening].forEach(el => {
            if (el) el.addEventListener('change', updateTimeSlots);
        });

        const { dateStart, dateEnd, scheduleType } = this._elements;
        const update = () => {
            clearTimeout(this._debounceTimer);
            this._debounceTimer = setTimeout(() => {
                if (dateStart.value && dateEnd.value && this.generateCalendar)
                    this.generateCalendar(dateStart.value, dateEnd.value, scheduleType.value);
            }, 150);
        };
        [dateStart, dateEnd, scheduleType].forEach(el => {
            if (el) el.addEventListener('change', update);
        });
    }

    destroy() {
        this._listeners.forEach(({ el, evt, fn, cap }) => el.removeEventListener(evt, fn, cap));
        this._listeners = [];
        this.teacherScheduleData = {};
        this.mainTeacherData = {};
        this.medTeacherData = {};
        this.currentDate = null;
        if (this._tooltipEl && this._tooltipEl.parentNode) {
            this._tooltipEl.parentNode.removeChild(this._tooltipEl);
        }
        this._tooltipEl = null;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.scheduleCalendarInstance = new ScheduleCalendar();
    window.scheduleCalendarInstance.init();
});
window.openDayModal = (el) => window.scheduleCalendarInstance?.openDayModal(el);
window.closeModal = () => window.scheduleCalendarInstance?.closeModal();
window.saveModal = () => window.scheduleCalendarInstance?.saveModal();