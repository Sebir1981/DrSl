// static/js/schedule_calendar.js
if (window.scheduleCalendarInstance) {
    console.log('ℹ️ ScheduleCalendar уже инициализирован');
} else {
    class ScheduleCalendar {
        constructor() {
            this.currentDayEl = null;
            this.teacherScheduleData = {};
            this.mainTeacherData = {};
            this.medTeacherData = {};
            this._calendarGenerated = false;
            this.init();
        }

        parseDate(dateStr) {
            if (!dateStr) return null;
            if (dateStr.includes('-')) {
                const [y, m, d] = dateStr.split('-');
                return new Date(y, m - 1, d);
            }
            if (dateStr.includes('.')) {
                const [d, m, y] = dateStr.split('.');
                return new Date(y, m - 1, d);
            }
            return new Date(dateStr);
        }

        init() {
            console.log('🔹 ScheduleCalendar инициализирован');
            this.bindEvents();
            this.checkAutoFill();
            this.bindModalEnter();
        }

        loadAndGenerate() {
            if (this._calendarGenerated) {
                console.log('⏭️ Календарь уже сгенерирован, пропускаем автозапуск');
                return;
            }

            const dateStartEl = document.getElementById('id_date_start');
            const dateEndEl = document.getElementById('id_date_end');
            const scheduleTypeEl = document.getElementById('id_schedule_type');
            const hiddenInput = document.getElementById('id_class_days');

            const dateStart = dateStartEl?.value;
            const dateEnd = dateEndEl?.value;
            const scheduleType = scheduleTypeEl?.value || 'custom';

            if (dateStart && dateEnd) {
                console.log('📅 Автозапуск генерации:', dateStart, dateEnd, scheduleType);
                let savedDays = {};
                if (hiddenInput?.value && hiddenInput.value !== '{}') {
                    try { savedDays = JSON.parse(hiddenInput.value); } catch(e) {}
                }
                this.generateCalendar(dateStart, dateEnd, scheduleType, savedDays);
            }
        }

        bindModalEnter() {
            const handleEnter = (e, isEndField = false) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    if (isEndField) this.saveModal();
                }
            };
            document.getElementById('m-slot-v')?.addEventListener('keydown', (e) => handleEnter(e, true));
        }

        bindEvents() {
            const modal = document.getElementById('day-modal');
            const delBtn = document.getElementById('m-del');
            if (delBtn) delBtn.addEventListener('click', () => this.deleteDay());
            if (modal) modal.addEventListener('click', (e) => { if (e.target === modal) this.closeModal(); });

            const groupSelect = document.getElementById('id_group');
            if (groupSelect) {
                groupSelect.addEventListener('change', (e) => {
                    const groupId = e.target.value;
                    if (groupId) this.fillFormFromGroup(groupId);
                });
            }
            this.bindPeriodChange();
        }

        bindPeriodChange() {
            const dateStart = document.getElementById('id_date_start');
            const dateEnd = document.getElementById('id_date_end');
            const scheduleType = document.getElementById('id_schedule_type');

            const updateCalendar = () => {
                const start = dateStart?.value;
                const end = dateEnd?.value;
                const type = scheduleType?.value;
                if (start && end) {
                    console.log(' Пересоздание календаря:', start, end, type);
                    const classDaysInput = document.getElementById('id_class_days');
                    if (classDaysInput && type && type !== 'custom') {
                        classDaysInput.value = '{}';
                    }
                    this.generateCalendar(start, end, type || 'custom', {});
                }
            };
            if (dateStart) dateStart.addEventListener('change', updateCalendar);
            if (dateEnd) dateEnd.addEventListener('change', updateCalendar);
            if (scheduleType) scheduleType.addEventListener('change', updateCalendar);
        }

        openDayModal(el) {
            this.currentDayEl = el;
            const date = el.dataset.date;
            const isScheduled = el.dataset.scheduled === 'true';
            const dayData = el.dataset.daydata ? JSON.parse(el.dataset.daydata) : {};

            document.getElementById('m-title').textContent = ` ${date}`;
            document.getElementById('m-date').value = date;
            document.getElementById('m-del').style.display = isScheduled ? 'inline-block' : 'none';

            let selectedSlots = dayData.slots || [];
            const useDefault = selectedSlots.length === 0 || dayData._useDefault === true;

            if (useDefault) {
                selectedSlots = [];
                if (document.getElementById('id_time_morning')?.checked) selectedSlots.push('У');
                if (document.getElementById('id_time_day')?.checked) selectedSlots.push('Д');
                if (document.getElementById('id_time_evening')?.checked) selectedSlots.push('В');
            }

            document.getElementById('m-slot-u').checked = selectedSlots.includes('У');
            document.getElementById('m-slot-d').checked = selectedSlots.includes('Д');
            document.getElementById('m-slot-v').checked = selectedSlots.includes('В');
            document.getElementById('m-med-toggle').checked = dayData.med || false;

            const teacherSlots = dayData.med ? this.medTeacherData : this.mainTeacherData;
            const relevantData = (teacherSlots[date] || []).map(item => typeof item === 'object' ? item.ind : item);
            const hasConflict = selectedSlots.some(s => relevantData.includes(s));
            document.getElementById('m-conflict-warn').style.display = hasConflict ? 'block' : 'none';

            document.getElementById('day-modal').style.display = 'flex';
        }

        closeModal() {
            document.getElementById('day-modal').style.display = 'none';
            this.currentDayEl = null;
        }

        saveModal() {
            if (!this.currentDayEl) return;

            const slots = [];
            if (document.getElementById('m-slot-u').checked) slots.push('У');
            if (document.getElementById('m-slot-d').checked) slots.push('Д');
            if (document.getElementById('m-slot-v').checked) slots.push('В');

            const isMed = document.getElementById('m-med-toggle').checked;

            const dayData = {
                slots: [...slots],
                med: isMed,
                scheduled: slots.length > 0,
                _useDefault: false
            };

            this.currentDayEl.dataset.scheduled = slots.length > 0 ? 'true' : 'false';
            if (slots.length > 0) this.currentDayEl.classList.add('is-scheduled');
            else this.currentDayEl.classList.remove('is-scheduled');

            this.currentDayEl.dataset.daydata = JSON.stringify(dayData);
            this.updateCellVisuals(this.currentDayEl, dayData);
            this.updateJSON();
            this.closeModal();
        }

        deleteDay() {
            if (!this.currentDayEl) return;

            const dateStr = this.currentDayEl.dataset.date;
            console.log('🗑️ Удаление дня:', dateStr);

            const excludedInput = document.getElementById('id_excluded_dates');
            if (excludedInput) {
                let excluded = [];
                try {
                    let rawValue = excludedInput.value.replace(/'/g, '"');
                    excluded = JSON.parse(rawValue) || [];
                } catch(e) {
                    console.warn('⚠️ Ошибка парсинга excluded_dates:', e);
                    excluded = [];
                }

                if (!excluded.includes(dateStr)) {
                    excluded.push(dateStr);
                    excluded.sort();
                    excludedInput.value = JSON.stringify(excluded);
                    console.log('✅ Обновлено excluded_dates:', excluded);
                }
            }

            const additionalInput = document.getElementById('id_additional_dates');
            if (additionalInput) {
                let additional = [];
                try {
                    let rawValue = additionalInput.value.replace(/'/g, '"');
                    additional = JSON.parse(rawValue) || [];
                } catch(e) {}
                const idx = additional.indexOf(dateStr);
                if (idx > -1) {
                    additional.splice(idx, 1);
                    additionalInput.value = JSON.stringify(additional);
                }
            }

            // 🔹 Очищаем часы из class_days для этого дня
            const classDaysInput = document.getElementById('id_class_days');
            if (classDaysInput) {
                try {
                    let classDays = JSON.parse(classDaysInput.value) || {};
                    if (classDays[dateStr]) {
                        delete classDays[dateStr];
                        classDaysInput.value = JSON.stringify(classDays);
                        console.log('🗑️ Часы дня удалены из class_days:', dateStr);
                    }
                } catch(e) {
                    console.warn('⚠️ Ошибка очистки class_days:', e);
                }
            }

            this.currentDayEl.classList.remove('is-scheduled', 'is-med', 'is-conflict');
            this.currentDayEl.dataset.scheduled = 'false';
            this.currentDayEl.dataset.daydata = JSON.stringify({
                slots: [],
                med: false,
                scheduled: false,
                _useDefault: false
            });

            this.updateCellVisuals(this.currentDayEl, {slots: [], med: false});
            this.updateJSON();
            this.closeModal();
        }

        updateCellVisuals(el, dayData) {
            const slots = dayData.slots || [];
            const dateStr = el.dataset.date;

            let slotsHtml = '';
            if (slots.length > 0) {
                slotsHtml = `<div style="display:flex;gap:2px;margin-top:2px;justify-content:flex-start;flex-wrap:wrap;">
                    ${slots.map(ind => {
                        const styles = { 'У': { bg: '#fef3c7', cl: '#b45309' }, 'Д': { bg: '#dbeafe', cl: '#1d4ed8' }, 'В': { bg: '#ede9fe', cl: '#7c3aed' } };
                        const s = styles[ind] || styles['Д'];
                        return `<span style="font-size:10px;font-weight:700;color:${s.cl};background:${s.bg};padding:2px 6px;border-radius:4px;line-height:1.2;">${ind}</span>`;
                    }).join('')}
                </div>`;
            }

            let teacherIndicatorsHtml = '';
            if (this.teacherScheduleData[dateStr]) {
                 teacherIndicatorsHtml = `<div style="display:flex;gap:2px;margin-top:2px;justify-content:flex-end;flex-wrap:wrap;">
                    ${this.teacherScheduleData[dateStr].map(item => {
                        const ind = typeof item === 'object' ? item.ind : item;
                        const isMed = typeof item === 'object' ? (item.is_med || false) : false;
                        const styles = { 'У': { bg: '#fef3c7', cl: '#b45309' }, 'Д': { bg: '#dbeafe', cl: '#1d4ed8' }, 'В': { bg: '#ede9fe', cl: '#7c3aed' } };
                        const s = styles[ind] || styles['Д'];
                        const medBadge = isMed ? ' <span style="color:#22c55e;font-weight:800;"></span>' : '';
                        return `<span style="font-size:9px;font-weight:600;color:${s.cl};background:${s.bg};padding:1px 4px;border-radius:4px;line-height:1.2;opacity:0.8;">${ind}${medBadge}</span>`;
                    }).join('')}
                </div>`;
            }

            let medHtml = '';
            if (dayData.med) {
                el.classList.add('is-med');
                medHtml = `<div class="med-indicator">✚</div>`;
            } else {
                el.classList.remove('is-med');
                const existingMed = el.querySelector('.med-indicator');
                if (existingMed) existingMed.remove();
            }

            let hasConflict = false;
            if (dayData.med) {
                const medSlots = (this.medTeacherData[dateStr] || []).map(item => typeof item === 'object' ? item.ind : item);
                hasConflict = slots.some(s => medSlots.includes(s));
            } else {
                const mainSlots = (this.mainTeacherData[dateStr] || []).map(item => typeof item === 'object' ? item.ind : item);
                hasConflict = slots.some(s => mainSlots.includes(s));
            }

            if (hasConflict) el.classList.add('is-conflict');
            else el.classList.remove('is-conflict');

            el.innerHTML = `
                <span class="cal-num">${el.dataset.date.split('-')[2]}</span>
                ${medHtml}
                <div style="display:flex;justify-content:space-between;align-items:center;margin-top:2px;">
                    ${slotsHtml}
                    ${teacherIndicatorsHtml}
                </div>
            `;
        }

        updateJSON() {
            const days = {};
            document.querySelectorAll('.cal-day.is-scheduled').forEach(el => {
                const data = JSON.parse(el.dataset.daydata || '{}');
                data.scheduled = true;
                days[el.dataset.date] = data;
            });
            const hiddenInput = document.getElementById('id_class_days');
            if (hiddenInput) hiddenInput.value = JSON.stringify(days);
        }

        calculateDateLogs() {
            const startDate = document.getElementById('id_date_start')?.value;
            const endDate = document.getElementById('id_date_end')?.value;
            const scheduleType = document.getElementById('id_schedule_type')?.value || 'custom';

            if (!startDate || !endDate) return;

            const startObj = this.parseDate(startDate);
            const endObj = this.parseDate(endDate);

            const idealDates = new Set();
            let current = new Date(startObj);

            while (current <= endObj) {
                const dateStr = current.toISOString().split('T')[0];
                const day = current.getDate();
                const dayOfWeek = current.getDay();
                const isWeekend = (dayOfWeek === 0 || dayOfWeek === 6);

                let shouldBeScheduled = false;
                if (scheduleType === 'odd') {
                    if (day % 2 === 1 && !isWeekend) shouldBeScheduled = true;
                } else if (scheduleType === 'even') {
                    if (day % 2 === 0 && !isWeekend) shouldBeScheduled = true;
                } else if (scheduleType === 'weekend') {
                    if (isWeekend) shouldBeScheduled = true;
                }

                if (shouldBeScheduled) idealDates.add(dateStr);
                current.setDate(current.getDate() + 1);
            }

            const actualDates = new Set();
            document.querySelectorAll('.cal-day.is-scheduled').forEach(el => {
                actualDates.add(el.dataset.date);
            });

            const excluded = [];
            const additional = [];

            idealDates.forEach(date => { if (!actualDates.has(date)) excluded.push(date); });
            actualDates.forEach(date => { if (!idealDates.has(date)) additional.push(date); });

            excluded.sort();
            additional.sort();

            const exclInput = document.getElementById('id_excluded_dates');
            const addInput = document.getElementById('id_additional_dates');
            if (exclInput) exclInput.value = JSON.stringify(excluded);
            if (addInput) addInput.value = JSON.stringify(additional);

            console.log('📝 Лог дат обновлен:', { excluded, additional });
        }

        async fillFormFromGroup(groupId) {
            console.log('🔄 Загрузка данных для группы:', groupId);
            try {
                const response = await fetch(`/groups/api/groups/${groupId}/data/`, { headers: { 'X-Requested-With': 'XMLHttpRequest' }});
                if (!response.ok) throw new Error('Network response was not ok');
                const data = await response.json();

                this.setField('id_teacher', data.teacher_id);
                this.setField('id_date_start', data.contract_start);
                this.setField('id_date_end', data.contract_end);
                this.setField('id_schedule_type', data.schedule_type);
                this.setField('id_duration_display', data.duration);
                this.setField('id_category_display', data.category);

                if (data.location) {
                    const classroomSelect = document.getElementById('id_classroom');
                    const locationHidden = document.getElementById('id_location');
                    if (classroomSelect) classroomSelect.value = data.location;
                    if (locationHidden) locationHidden.value = data.location;
                }
            } catch (error) {
                console.error('❌ Ошибка загрузки данных группы:', error);
            }
        }

        setField(fieldId, value) {
            const field = document.getElementById(fieldId);
            if (field && value !== undefined && value !== null) { field.value = value; }
        }

        generateCalendar(dateStart, dateEnd, scheduleType, savedDays = null) {
            const excludedInput = document.getElementById('id_excluded_dates');
            console.log('🔍 ОТЛАДКА excluded_dates:', {
                'element': excludedInput,
                'value': excludedInput ? excludedInput.value : 'NOT FOUND',
                'type': typeof excludedInput?.value
            });

            if (this._calendarGenerated) {
                console.log('⏭️ Календарь уже сгенерирован, пропускаем');
                return false;
            }
            this._calendarGenerated = true;

            console.log('🔹 Генерация календаря:', dateStart, dateEnd, scheduleType);
            const startObj = this.parseDate(dateStart);
            const endObj = this.parseDate(dateEnd);

            if (!startObj || !endObj || isNaN(startObj.getTime()) || isNaN(endObj.getTime())) {
                console.error('❌ Некорректные даты:', dateStart, dateEnd);
                return false;
            }

            const container = document.getElementById('months-container');
            if (!container) return false;
            container.innerHTML = '';

            const monthNames = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'];
            const dayNames = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

            if (!savedDays) {
                const hiddenInput = document.getElementById('id_class_days');
                if (hiddenInput?.value) { try { savedDays = JSON.parse(hiddenInput.value); } catch(e) { savedDays = {}; } }
            }
            if (!savedDays) savedDays = {};

            const startStr = dateStart.includes('-') ? dateStart : dateStart.split('.').reverse().join('-');
            const endStr = dateEnd.includes('-') ? dateEnd : dateEnd.split('.').reverse().join('-');

            let currentMonth = new Date(startObj.getFullYear(), startObj.getMonth(), 1);
            const endMonth = new Date(endObj.getFullYear(), endObj.getMonth(), 1);

            while (currentMonth <= endMonth) {
                const year = currentMonth.getFullYear();
                const month = currentMonth.getMonth();

                const monthDiv = document.createElement('div');
                monthDiv.className = 'calendar-month';
                const titleDiv = document.createElement('div');
                titleDiv.className = 'cal-month-title';
                titleDiv.textContent = `${monthNames[month]} ${year}`;
                monthDiv.appendChild(titleDiv);

                const gridDiv = document.createElement('div');
                gridDiv.className = 'calendar-grid';
                dayNames.forEach(name => {
                    const header = document.createElement('div');
                    header.className = 'cal-head';
                    header.textContent = name;
                    gridDiv.appendChild(header);
                });

                const firstDayDate = new Date(year, month, 1);
                let startDayOfWeek = firstDayDate.getDay() || 7;
                for (let i = 1; i < startDayOfWeek; i++) {
                    const emptyEl = document.createElement('div');
                    emptyEl.className = 'cal-day cal-empty';
                    gridDiv.appendChild(emptyEl);
                }

                const daysInMonth = new Date(year, month + 1, 0).getDate();
                for (let day = 1; day <= daysInMonth; day++) {
                    const thisDate = new Date(year, month, day);
                    const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;

                    const dayOfWeek = thisDate.getDay();
                    const isWeekend = (dayOfWeek === 0 || dayOfWeek === 6);
                    const isInPeriod = dateStr >= startStr && dateStr <= endStr;

                    const isSaved = savedDays[dateStr];
                    const dayData = isSaved ? {...isSaved} : {};

                    if (!dayData.slots || dayData.slots.length === 0) {
                        dayData._useDefault = true;
                    }

                    let isScheduled = false;
                    const slots = dayData.slots || [];
                    if (slots.length > 0) {
                        isScheduled = true;
                    } else if (isInPeriod) {
                        if (scheduleType === 'odd') { if (day % 2 === 1 && !isWeekend) isScheduled = true; }
                        else if (scheduleType === 'even') { if (day % 2 === 0 && !isWeekend) isScheduled = true; }
                        else if (scheduleType === 'weekend') { if (isWeekend) isScheduled = true; }
                    }

                    const exclInput = document.getElementById('id_excluded_dates');
                    let excludedDates = [];
                    if (exclInput && exclInput.value && exclInput.value !== '[]') {
                        try {
                            let rawValue = exclInput.value.replace(/'/g, '"');
                            excludedDates = JSON.parse(rawValue) || [];
                        } catch(e) {
                            console.warn('️ Ошибка парсинга excluded_dates:', e);
                            excludedDates = [];
                        }
                    }
                    if (excludedDates.includes(dateStr)) {
                        isScheduled = false;
                        console.log('⏭️ Исключённый день пропущен:', dateStr);
                    }

                    const allSlots = this.teacherScheduleData[dateStr] || [];
                    const mainSlots = allSlots.filter(slot => {
                        const isMed = typeof slot === 'object' ? (slot.is_med || false) : false;
                        return !isMed;
                    }).map(item => typeof item === 'object' ? item.ind : item);

                    const medSlots = allSlots.filter(slot => {
                        const isMed = typeof slot === 'object' ? (slot.is_med || false) : false;
                        return isMed;
                    }).map(item => typeof item === 'object' ? item.ind : item);

                    let hasConflict = false;
                    const isMedDay = dayData.med || false;
                    if (isMedDay) {
                         hasConflict = slots.some(s => medSlots.includes(s));
                    } else {
                         hasConflict = slots.some(s => mainSlots.includes(s));
                    }

                    const dayEl = document.createElement('div');
                    let classes = 'cal-day';
                    if (!isInPeriod) classes += ' is-inactive';
                    else if (isScheduled) classes += ' is-scheduled';
                    else if (isWeekend) classes += ' is-weekend';
                    if (dayData.med) classes += ' is-med';
                    if (hasConflict) classes += ' is-conflict';

                    dayEl.className = classes;
                    dayEl.dataset.date = dateStr;
                    dayEl.dataset.scheduled = (isScheduled && isInPeriod) ? 'true' : 'false';
                    dayEl.dataset.daydata = JSON.stringify(dayData);

                    if (isInPeriod) {
                        dayEl.onclick = () => window.scheduleCalendarInstance.openDayModal(dayEl);
                    }

                    let slotsHtml = '';
                    if (slots.length > 0) {
                        slotsHtml = `<div style="display:flex;gap:2px;margin-top:2px;justify-content:flex-start;flex-wrap:wrap;">
                            ${slots.map(ind => {
                                const styles = { 'У': { bg: '#fef3c7', cl: '#b45309' }, 'Д': { bg: '#dbeafe', cl: '#1d4ed8' }, 'В': { bg: '#ede9fe', cl: '#7c3aed' } };
                                const s = styles[ind] || styles['Д'];
                                return `<span style="font-size:10px;font-weight:700;color:${s.cl};background:${s.bg};padding:2px 6px;border-radius:4px;line-height:1.2;">${ind}</span>`;
                            }).join('')}
                        </div>`;
                    }

                    let teacherIndicatorsHtml = '';
                    if (allSlots.length > 0) {
                        teacherIndicatorsHtml = `<div style="display:flex;gap:2px;margin-top:2px;justify-content:flex-end;flex-wrap:wrap;">
                            ${allSlots.map(item => {
                                const ind = typeof item === 'object' ? item.ind : item;
                                const isMed = typeof item === 'object' ? (item.is_med || false) : false;
                                const styles = { 'У': { bg: '#fef3c7', cl: '#b45309' }, 'Д': { bg: '#dbeafe', cl: '#1d4ed8' }, 'В': { bg: '#ede9fe', cl: '#7c3aed' } };
                                const s = styles[ind] || styles['Д'];
                                const medBadge = isMed ? ' <span style="color:#22c55e;font-weight:800;">✚</span>' : '';
                                return `<span style="font-size:9px;font-weight:600;color:${s.cl};background:${s.bg};padding:1px 4px;border-radius:4px;line-height:1.2;opacity:0.8;">${ind}${medBadge}</span>`;
                            }).join('')}
                        </div>`;
                    }

                    let tooltipContent = '';
                    if (allSlots.length > 0) {
                        tooltipContent = allSlots.map(item => {
                            const ind = typeof item === 'object' ? item.ind : item;
                            const group = typeof item === 'object' ? item.group : 'Не указано';
                            const location = typeof item === 'object' ? item.location : 'Не указано';
                            const isMed = typeof item === 'object' ? (item.is_med || false) : false;
                            const medBadge = isMed ? ' <span style="color:#22c55e;font-weight:800;">✚</span>' : '';
                            return `<div style="margin-bottom:4px; border-bottom:1px solid #eee; padding-bottom:4px;">
                                <strong>⏰ ${ind}${medBadge}</strong><br>
                                 ${group}<br>
                                📍 ${location}
                            </div>`;
                        }).join('');
                    }

                    let tooltipHtml = '';
                    if (tooltipContent) {
                        tooltipHtml = `<div class="cal-day-tooltip" style="display:none; position:absolute; bottom:100%; left:50%; transform:translateX(-50%); background:white; border:1px solid #cbd5e1; border-radius:8px; padding:8px; box-shadow:0 4px 12px rgba(0,0,0,0.15); z-index:100; width:200px; font-size:12px; text-align:left; pointer-events:none; margin-bottom:5px;">
                            ${tooltipContent}
                        </div>`;
                    }

                    let medHtml = dayData.med ? `<div class="med-indicator">✚</div>` : '';

                    dayEl.innerHTML = `
                        ${tooltipHtml}
                        <span class="cal-num">${day}</span>
                        ${medHtml}
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-top:2px;">
                            ${slotsHtml}
                            ${teacherIndicatorsHtml}
                        </div>
                    `;

                    if (tooltipContent) {
                        dayEl.addEventListener('mouseenter', function() {
                            const tip = this.querySelector('.cal-day-tooltip');
                            if (tip) tip.style.display = 'block';
                        });
                        dayEl.addEventListener('mouseleave', function() {
                            const tip = this.querySelector('.cal-day-tooltip');
                            if (tip) tip.style.display = 'none';
                        });
                    }

                    gridDiv.appendChild(dayEl);
                }

                monthDiv.appendChild(gridDiv);
                container.appendChild(monthDiv);
                currentMonth = new Date(year, month + 1, 1);
            }

            const warningEl = document.querySelector('.calendar-warning');
            if (warningEl) warningEl.style.display = 'none';

            this.updateJSON();
            this.showSuccessMessage();
            console.log('✅ Календарь сгенерирован');
            return true;
        }

        showSuccessMessage() {
            const successDiv = document.createElement('div');
            successDiv.className = 'auto-fill-message';
            successDiv.style.cssText = 'background:#dcfce7; border:1px solid #16a34a; border-radius:8px; padding:12px; margin:15px 0; color:#166534; text-align:center;';
            successDiv.innerHTML = '✅ Календарь сгенерирован!';
            const oldSuccess = document.querySelector('.auto-fill-message');
            if (oldSuccess) oldSuccess.remove();
            const warningEl = document.querySelector('.calendar-warning');
            const calendarSection = document.querySelector('.calendar-section');
            if (warningEl && warningEl.parentNode) warningEl.parentNode.insertBefore(successDiv, warningEl);
            else if (calendarSection) calendarSection.insertBefore(successDiv, calendarSection.firstChild);
        }

        checkAutoFill() {
            const urlParams = new URLSearchParams(window.location.search);
            const groupId = urlParams.get('group');
            if (groupId) {
                setTimeout(() => {
                    const groupSelect = document.getElementById('id_group');
                    if (groupSelect) { groupSelect.value = groupId; this.fillFormFromGroup(groupId); }
                }, 300);
            }
        }
    }

    document.addEventListener('DOMContentLoaded', () => { window.scheduleCalendarInstance = new ScheduleCalendar(); });
    window.openDayModal = (el) => { if (window.scheduleCalendarInstance) window.scheduleCalendarInstance.openDayModal(el); };
    window.closeModal = () => { if (window.scheduleCalendarInstance) window.scheduleCalendarInstance.closeModal(); };
    window.saveModal = () => { if (window.scheduleCalendarInstance) window.scheduleCalendarInstance.saveModal(); };
}