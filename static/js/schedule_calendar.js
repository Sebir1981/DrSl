// static/js/schedule_calendar.js

if (window.scheduleCalendarInstance) {
    console.log('ℹ️ ScheduleCalendar уже инициализирован');
} else {
    class ScheduleCalendar {
        constructor() {
            this.currentDayEl = null;
            this.init();
        }

                init() {
            console.log('🔹 ScheduleCalendar инициализирован');
            this.bindEvents();
            this.checkAutoFill();

            // 🔹 НОВОЕ: Перехват Enter в модальном окне
            this.bindModalEnter();
        }

        // 🔹 НОВЫЙ МЕТОД: Обновление времени во всём календаре (вызывается при Enter)
        updateTimeInCalendar() {
            const newStart = document.getElementById('id_time_start')?.value || '09:00';
            const newEnd = document.getElementById('id_time_end')?.value || '12:00';
            const timeHTML = `
                <span class="t-start">${newStart}</span>
                <span class="t-sep">–</span>
                <span class="t-end">${newEnd}</span>
            `;

            // Обновляем только запланированные дни
            document.querySelectorAll('.cal-day.is-scheduled').forEach(el => {
                const timeContainer = el.querySelector('.cal-time');
                if (timeContainer) {
                    timeContainer.innerHTML = timeHTML;
                }
                el.dataset.start = newStart;
                el.dataset.end = newEnd;
            });

            this.updateHoursSummary();
            this.updateJSON();
            console.log(`⏰ Время обновлено: ${newStart}–${newEnd}`);
        }

        // 🔹 НОВЫЙ МЕТОД: Перехват Enter в модальном окне
        bindModalEnter() {
            const modalStart = document.getElementById('m-start');
            const modalEnd = document.getElementById('m-end');

            const handleEnter = (e, isEndField = false) => {
                if (e.key === 'Enter') {
                    e.preventDefault(); // ❌ Блокируем отправку формы

                    if (isEndField) {
                        // Если нажали Enter в поле "окончание" — сохраняем и закрываем
                        this.saveModal();
                    } else {
                        // Если в поле "начало" — переходим к полю "окончание"
                        const endField = document.getElementById('m-end');
                        if (endField) endField.focus();
                    }
                }
            };

            if (modalStart) modalStart.addEventListener('keydown', (e) => handleEnter(e, false));
            if (modalEnd) modalEnd.addEventListener('keydown', (e) => handleEnter(e, true));
        }

        bindEvents() {
            // 1. Модальное окно
            const modal = document.getElementById('day-modal');
            const delBtn = document.getElementById('m-del');
            if (delBtn) delBtn.addEventListener('click', () => this.deleteDay());
            if (modal) {
                modal.addEventListener('click', (e) => {
                    if (e.target === modal) this.closeModal();
                });
            }

            // 2. Автозаполнение при выборе группы
            const groupSelect = document.getElementById('id_group');
            if (groupSelect) {
                groupSelect.addEventListener('change', (e) => {
                    const groupId = e.target.value;
                    if (groupId) this.fillFormFromGroup(groupId);
                });
            }

            // 3. Перестройка календаря при изменении дат/типа
            this.bindPeriodChange();

            // 4. 🔹 НОВОЕ: Обновление времени во всём календаре
            this.bindTimeChange();
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
                    console.log('🔄 Обновление календаря по датам:', start, end);
                    this.generateCalendar(start, end, type || 'custom');
                }
            };

            if (dateStart) dateStart.addEventListener('change', updateCalendar);
            if (dateEnd) dateEnd.addEventListener('change', updateCalendar);
            if (scheduleType) scheduleType.addEventListener('change', updateCalendar);
        }

        // 🔹 НОВАЯ ФУНКЦИЯ: Обновление времени во всех ячейках календаря
        bindTimeChange() {
            const timeStart = document.getElementById('id_time_start');
            const timeEnd = document.getElementById('id_time_end');

            const updateTimeInCalendar = () => {
                const newStart = timeStart?.value || '09:00';
                const newEnd = timeEnd?.value || '12:00';
                const timeHTML = `
                    <span class="t-start">${newStart}</span>
                    <span class="t-sep">–</span>
                    <span class="t-end">${newEnd}</span>
                `;

                // Обновляем только запланированные дни
                document.querySelectorAll('.cal-day.is-scheduled').forEach(el => {
                    const timeContainer = el.querySelector('.cal-time');
                    if (timeContainer) {
                        timeContainer.innerHTML = timeHTML;
                    }
                    // Обновляем data-атрибуты для отправки на сервер
                    el.dataset.start = newStart;
                    el.dataset.end = newEnd;
                });

                // Пересчитываем часы
                this.updateHoursSummary();
                // Обновляем скрытое поле JSON
                this.updateJSON();

                console.log(`⏰ Время обновлено: ${newStart}–${newEnd}`);
            };

            if (timeStart) timeStart.addEventListener('change', updateTimeInCalendar);
            if (timeEnd) timeEnd.addEventListener('change', updateTimeInCalendar);
        }

        openDayModal(el) {
            this.currentDayEl = el;
            const date = el.dataset.date;
            const isScheduled = el.dataset.scheduled === 'true';

            document.getElementById('m-title').textContent = `📅 ${date}`;
            document.getElementById('m-date').value = date;
            document.getElementById('m-start').value = isScheduled ? el.dataset.start : '09:00';
            document.getElementById('m-end').value = isScheduled ? el.dataset.end : '12:00';
            document.getElementById('m-del').style.display = isScheduled ? 'inline-block' : 'none';

            document.getElementById('day-modal').style.display = 'flex';
        }

        closeModal() {
            document.getElementById('day-modal').style.display = 'none';
            this.currentDayEl = null;
        }

        saveModal() {
            if (!this.currentDayEl) return;
            const start = document.getElementById('m-start').value;
            const end = document.getElementById('m-end').value;

            if (!start || !end) { alert('⚠️ Укажите время'); return; }
            if (start >= end) { alert('⚠️ Время окончания должно быть позже начала'); return; }

            this.currentDayEl.classList.add('is-scheduled');
            this.currentDayEl.dataset.scheduled = 'true';
            this.currentDayEl.dataset.start = start;
            this.currentDayEl.dataset.end = end;

            const timeContainer = this.currentDayEl.querySelector('.cal-time');
            if (timeContainer) {
                timeContainer.innerHTML = `
                    <span class="t-start">${start}</span>
                    <span class="t-sep">–</span>
                    <span class="t-end">${end}</span>
                `;
            }

            this.updateJSON();
            this.updateHoursSummary();
            this.closeModal();
        }

        deleteDay() {
            if (!this.currentDayEl) return;
            this.currentDayEl.classList.remove('is-scheduled');
            this.currentDayEl.dataset.scheduled = 'false';
            this.currentDayEl.dataset.start = '';
            this.currentDayEl.dataset.end = '';

            const timeContainer = this.currentDayEl.querySelector('.cal-time');
            if (timeContainer) timeContainer.innerHTML = '';

            this.updateJSON();
            this.updateHoursSummary();
            this.closeModal();
        }

        updateJSON() {
    const days = {};
    document.querySelectorAll('.cal-day.is-scheduled').forEach(el => {
        days[el.dataset.date] = {
            start: el.dataset.start,
            end: el.dataset.end
        };
    });
    const hiddenInput = document.getElementById('id_class_days');
    if (hiddenInput) {
        hiddenInput.value = JSON.stringify(days);
        console.log('💾 Сохранено в class_days:', days);
    }
}
        updateHoursSummary() {
            let totalMinutes = 0;
            document.querySelectorAll('.cal-day.is-scheduled').forEach(el => {
                const start = el.dataset.start;
                const end = el.dataset.end;
                if (start && end) {
                    const [startH, startM] = start.split(':').map(Number);
                    const [endH, endM] = end.split(':').map(Number);
                    totalMinutes += (endH * 60 + endM) - (startH * 60 + startM);
                }
            });
            const totalHours = (totalMinutes / 60).toFixed(1);
            const hoursEl = document.getElementById('total-hours');
            if (hoursEl) hoursEl.textContent = totalHours;
        }

            async fillFormFromGroup(groupId) {
    console.log('🔹 Загрузка данных для группы:', groupId);
    try {
        const response = await fetch(`/groups/api/groups/${groupId}/data/`, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        if (!response.ok) throw new Error('Network response was not ok');
        const data = await response.json();

        this.setField('id_teacher', data.teacher_id);
        this.setField('id_date_start', data.contract_start);
        this.setField('id_date_end', data.contract_end);

        // 🔹 НОВОЕ: Подстановка времени из standard_time_range
        if (data.time_start) {
            const timeStart = document.getElementById('id_time_start');
            if (timeStart) {
                timeStart.value = data.time_start;
                console.log('⏰ Время начала:', data.time_start);
            }
        }
        if (data.time_end) {
            const timeEnd = document.getElementById('id_time_end');
            if (timeEnd) {
                timeEnd.value = data.time_end;
                console.log('⏰ Время окончания:', data.time_end);
            }
        }

        this.setField('id_schedule_type', data.schedule_type);
        this.setField('id_duration_display', data.duration);

        // 🔹 Автовыбор адреса
        if (data.location) {
            const classroomSelect = document.getElementById('id_classroom');
            const locationHidden = document.getElementById('id_location');
            if (classroomSelect) classroomSelect.value = data.location;
            if (locationHidden) locationHidden.value = data.location;
        }

        // 🔹 Генерация календаря после подстановки времени
        if (data.contract_start && data.contract_end) {
            setTimeout(() => {
                // 🔹 Сначала обновим время в календаре, если есть запланированные дни
                if (window.scheduleCalendarInstance) {
                    window.scheduleCalendarInstance.updateTimeInCalendar();
                }
                this.generateCalendar(data.contract_start, data.contract_end, data.schedule_type || 'custom');
            }, 200);
        }

    } catch (error) {
        console.error('❌ Ошибка загрузки данных группы:', error);
    }
}

        setField(fieldId, value) {
            const field = document.getElementById(fieldId);
            if (field && value !== undefined && value !== null) {
                field.value = value;
            }
        }

        generateCalendar(dateStart, dateEnd, scheduleType) {
            console.log('🔹 Генерация календаря:', dateStart, dateEnd, scheduleType);

            if (!dateStart || !dateEnd) return false;

            const start = new Date(dateStart);
            const end = new Date(dateEnd);
            const container = document.getElementById('months-container');

            if (!container) return false;
            container.innerHTML = '';

            const monthNames = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
                               'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'];
            const dayNames = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

            // 🔹 Берём время из полей формы (без секунд)
            const defaultStart = (document.getElementById('id_time_start')?.value || '09:00').substring(0, 5);
            const defaultEnd = (document.getElementById('id_time_end')?.value || '12:00').substring(0, 5);

            let currentMonth = new Date(start.getFullYear(), start.getMonth(), 1);
            const endMonth = new Date(end.getFullYear(), end.getMonth(), 1);

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
                    const dateStr = thisDate.toISOString().split('T')[0];
                    const dayOfWeek = thisDate.getDay();
                    const isWeekend = (dayOfWeek === 0 || dayOfWeek === 6);
                    const isInPeriod = thisDate >= start && thisDate <= end;

                    let isScheduled = false;
                    let timeHTML = '';

                    // Чётные/Нечётные ИСКЛЮЧАЯ выходные
                    if (isInPeriod && !isWeekend) {
                        if (scheduleType === 'odd' && day % 2 === 1) isScheduled = true;
                        else if (scheduleType === 'even' && day % 2 === 0) isScheduled = true;
                    } else if (isInPeriod && isWeekend && scheduleType === 'weekend') {
                        isScheduled = true;
                    }

                    if (isScheduled) {
                        timeHTML = `
                            <span class="t-start">${defaultStart}</span>
                            <span class="t-sep">–</span>
                            <span class="t-end">${defaultEnd}</span>
                        `;
                    }

                    const dayEl = document.createElement('div');
                    let classes = 'cal-day';
                    if (!isInPeriod) classes += ' is-inactive';
                    else if (isScheduled) classes += ' is-scheduled';
                    else if (isWeekend) classes += ' is-weekend';

                    dayEl.className = classes;
                    dayEl.dataset.date = dateStr;
                    dayEl.dataset.scheduled = isScheduled ? 'true' : 'false';
                    dayEl.dataset.start = isScheduled ? defaultStart : '';
                    dayEl.dataset.end = isScheduled ? defaultEnd : '';

                    if (isInPeriod) {
                        dayEl.onclick = () => window.scheduleCalendarInstance.openDayModal(dayEl);
                    }

                    dayEl.innerHTML = `
                        <span class="cal-num">${day}</span>
                        <div class="cal-time">${timeHTML}</div>
                    `;

                    gridDiv.appendChild(dayEl);
                }

                monthDiv.appendChild(gridDiv);
                container.appendChild(monthDiv);
                currentMonth = new Date(year, month + 1, 1);
            }

            const warningEl = document.querySelector('.calendar-warning');
            if (warningEl) warningEl.style.display = 'none';

            const hoursSummary = document.getElementById('hours-summary');
            if (hoursSummary) hoursSummary.style.display = 'block';

            this.updateHoursSummary();
            this.showSuccessMessage();
            console.log('✅ Календарь сгенерирован');
            return true;
        }

        showSuccessMessage() {
            const successDiv = document.createElement('div');
            successDiv.className = 'auto-fill-message';
            successDiv.style.cssText = 'background:#dcfce7; border:1px solid #16a34a; border-radius:8px; padding:12px; margin:15px 0; color:#166534; text-align:center;';
            successDiv.innerHTML = '✅ Календарь сгенерирован! Выберите дни и установите время.';

            const oldSuccess = document.querySelector('.auto-fill-message');
            if (oldSuccess) oldSuccess.remove();

            const warningEl = document.querySelector('.calendar-warning');
            const calendarSection = document.querySelector('.calendar-section');
            if (warningEl && warningEl.parentNode) {
                warningEl.parentNode.insertBefore(successDiv, warningEl);
            } else if (calendarSection) {
                calendarSection.insertBefore(successDiv, calendarSection.firstChild);
            }
        }

        checkAutoFill() {
            const urlParams = new URLSearchParams(window.location.search);
            const groupId = urlParams.get('group');
            if (groupId) {
                setTimeout(() => {
                    const groupSelect = document.getElementById('id_group');
                    if (groupSelect) {
                        groupSelect.value = groupId;
                        this.fillFormFromGroup(groupId);
                    }
                }, 300);
            }
        }
    }

    // 🔹 Глобальная инициализация
    document.addEventListener('DOMContentLoaded', () => {
        window.scheduleCalendarInstance = new ScheduleCalendar();
    });
    // 🔹 ПРОВЕРКА ЧАСОВ ПРИ НАЖАТИИ "ДАЛЕЕ"
document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('schedule-form');
    const modal = document.getElementById('hours-warning-modal');
    const diffText = document.getElementById('hours-diff-text');

    if (form) {
        form.addEventListener('submit', function(e) {
            e.preventDefault(); // Останавливаем стандартную отправку

            const totalHours = parseFloat(document.getElementById('total-hours').textContent) || 0;
            const requiredHours = parseFloat(document.getElementById('id_required_hours').value) || 0;
            const diff = totalHours - requiredHours;

            // Допустимая погрешность: 0.1 часа (~6 минут)
            if (Math.abs(diff) <= 0.1) {
                form.submit(); // Всё сходится → отправляем форму
            } else {
                const absDiff = Math.abs(diff).toFixed(1);
                const direction = diff > 0 ? 'больше' : 'меньше';

                diffText.innerHTML = `
                    📊 Итого в календаре: <strong>${totalHours} ч.</strong><br>
                     Требуется: <strong>${requiredHours} ч.</strong><br>
                    ⚖️ Разница: на <strong>${absDiff} ч. ${direction}</strong>
                `;
                modal.style.display = 'flex'; // Показываем предупреждение
            }
        });
    }
});

    // 🔹 Глобальные функции для onclick в HTML
    window.openDayModal = (el) => {
        if (window.scheduleCalendarInstance) window.scheduleCalendarInstance.openDayModal(el);
    };
    window.closeModal = () => {
        if (window.scheduleCalendarInstance) window.scheduleCalendarInstance.closeModal();
    };
    window.saveModal = () => {
        if (window.scheduleCalendarInstance) window.scheduleCalendarInstance.saveModal();
    };
}