// =============================================================================
// 🔹 ИНИЦИАЛИЗАЦИЯ ДАННЫХ
// =============================================================================

const PLAN_ID = parseInt(document.getElementById('plan-data-container')?.dataset.planId) || 0;
let REQUIRED_HOURS = parseFloat(document.getElementById('plan-data-container')?.dataset.requiredHours || '0') || 0;
const MAX_HOURS_PER_DAY = 12;

// 🔹 Загружаем список исключённых дат
let excludedDates = [];
try {
    const rawExcluded = document.getElementById('plan-data-container')?.dataset.excludedDates || '[]';
    excludedDates = JSON.parse(rawExcluded);
} catch (e) {
    console.warn('⚠️ Ошибка парсинга excludedDates:', e);
}

window.topicsState = {};
try {
    const rawInput = document.getElementById('plan-data-container')?.dataset.topicsState || '{}';
    if (rawInput && rawInput !== '{}' && rawInput !== 'null') {
        const decoded = rawInput.replace(/\\'/g, "'").replace(/\\"/g, '"').replace(/\\\\/g, '\\');
        window.topicsState = JSON.parse(decoded);
    }
} catch (e) {
    console.warn('⚠️ Ошибка парсинга topicsState:', e);
    window.topicsState = {};
}

let currentModalDate = null;
let currentModalSubject = null;
const cellsMap = {};
const form = document.getElementById('hours-form');
const grandTotalInput = document.getElementById('grand-total');

// =============================================================================
// 🔹 ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
// =============================================================================

function formatHours(value) {
    const num = parseFloat(value);
    if (isNaN(num)) return '';
    return Math.round(num).toString();
}

function saveStateToStorage() {
    localStorage.setItem(`topicsState_${PLAN_ID}`, JSON.stringify(window.topicsState));
}

function loadStateFromStorage() {
    try {
        const stored = localStorage.getItem(`topicsState_${PLAN_ID}`);
        if (stored && stored !== 'null' && stored !== '{}') {
            Object.assign(window.topicsState, JSON.parse(stored));
        }
    } catch (e) { console.error("Ошибка загрузки состояния:", e); }
}

function buildCellsMap() {
    document.querySelectorAll('.subject-hours').forEach(el => {
        cellsMap[`${el.dataset.date}_${el.dataset.subject}`] = el;
    });
}

// 🔹 🔥 🔥 НОВАЯ ФУНКЦИЯ: Полное удаление строк исключённых дней из таблицы 🔥 🔥 🔥
function removeExcludedDateRows() {
    console.log('🗑️ Удаление исключённых дней из таблицы:', excludedDates);

    excludedDates.forEach(dateStr => {
        // Находим все ячейки этой даты и поднимаемся до строки <tr>
        const cells = document.querySelectorAll(`.subject-hours[data-date="${dateStr}"]`);
        if (cells.length > 0) {
            const row = cells[0].closest('tr');
            if (row) {
                row.remove();  // 🔥 Полностью удаляем строку из DOM
                console.log(`✅ Удалена строка дня: ${dateStr}`);
            }
        }

        // Также удаляем "Всего за день", если есть
        const dayTotal = document.querySelector(`.day-total[data-date="${dateStr}"]`);
        if (dayTotal?.closest('tr')) {
            dayTotal.closest('tr').remove();
        }
    });

    // Перестраиваем cellsMap после удаления строк
    buildCellsMap();
}

function syncDOMFromState() {
    for (const date in window.topicsState) {
        // 🔹 Пропускаем исключённые даты
        if (excludedDates.includes(date)) continue;

        const dayTopics = window.topicsState[date];
        for (const subject in dayTopics) {
            let daySum = 0;
            const topicMap = dayTopics[subject];
            for (const tid in topicMap) {
                daySum += parseFloat(topicMap[tid]) || 0;
            }
            const key = `${date}_${subject}`;
            const cell = cellsMap[key];
            if (cell) {
                cell.value = formatHours(daySum);
            }
        }
    }
    recalculateTotals();
    updateMedicineHighlight();
}

function recalculateTotals() {
    let grandTotal = 0;

    // 🔹 Подсчёт и подсветка по предметам
    document.querySelectorAll('.subject-total-display').forEach(displayEl => {
        const subjectCode = displayEl.id.replace('-total-display', '');
        const hiddenInput = document.getElementById(`${subjectCode}-total`);
        if (!hiddenInput) return;

        const requiredHours = parseFloat(hiddenInput.value) || 0;
        let distributedHours = 0;

        // Считаем из ячеек таблицы (игнорируем excluded_dates)
        document.querySelectorAll(`.subject-hours[data-subject="${subjectCode}"]`).forEach(cell => {
            if (excludedDates.includes(cell.dataset.date)) return;
            const val = parseFloat(cell.value);
            if (!isNaN(val)) distributedHours += val;
        });

        // Округляем для отображения
        const distributedRounded = Math.round(distributedHours);
        displayEl.textContent = `${distributedRounded} / ${Math.round(requiredHours)}`;

        // 🔹 ПОДСВЕТКА СТРОКИ
        const row = displayEl.closest('tr');
        if (row) {
            if (requiredHours > 0) {
                if (Math.abs(distributedHours - requiredHours) < 0.01) {
                    // 🟢 Точно в цель: зелёный
                    row.style.background = '#f0fdf4';
                    row.style.borderLeft = '4px solid #22c55e';
                    displayEl.style.color = '#166534';
                    displayEl.style.fontWeight = '700';
                    row.classList.add('completed-subject');
                } else if (distributedHours > requiredHours) {
                    // 🔴 Перерасход: красный
                    row.style.background = '#fef2f2';
                    row.style.borderLeft = '4px solid #ef4444';
                    displayEl.style.color = '#991b1b';
                    displayEl.style.fontWeight = '700';
                    row.classList.remove('completed-subject');
                } else {
                    // 🟡 Недорасход: жёлтый
                    row.style.background = '#fefce8';
                    row.style.borderLeft = '4px solid #eab308';
                    displayEl.style.color = '#854d0e';
                    displayEl.style.fontWeight = '600';
                    row.classList.remove('completed-subject');
                }
            } else {
                // Нет требований: нейтральный
                row.style.background = '';
                row.style.borderLeft = '';
                displayEl.style.color = '';
                displayEl.style.fontWeight = '';
                row.classList.remove('completed-subject');
            }
        }

        grandTotal += distributedHours;
    });

    // 🔹 Подсветка общего итога
    if (grandTotalInput) {
        const distributed = Math.round(grandTotal);
        const required = Math.round(REQUIRED_HOURS);
        grandTotalInput.value = `${distributed} / ${required}`;

        if (REQUIRED_HOURS > 0) {
            if (Math.abs(grandTotal - REQUIRED_HOURS) < 0.01) {
                grandTotalInput.style.background = '#86efac';
                grandTotalInput.style.color = '#065f46';
                grandTotalInput.style.fontWeight = '700';
            } else if (grandTotal > REQUIRED_HOURS) {
                grandTotalInput.style.background = '#fecaca';
                grandTotalInput.style.color = '#991b1b';
                grandTotalInput.style.fontWeight = '700';
            } else {
                grandTotalInput.style.background = '#fef3c7';
                grandTotalInput.style.color = '#92400e';
                grandTotalInput.style.fontWeight = '600';
            }
        }
    }

    // 🔹 Подсветка "Всего за день"
    const dates = new Set(Object.keys(cellsMap).map(k => k.split('_')[0]));
    dates.forEach(date => {
        if (excludedDates.includes(date)) return;

        let daySum = 0;
        document.querySelectorAll(`.subject-hours[data-date="${date}"]`).forEach(cell => {
            const val = parseFloat(cell.value);
            if (!isNaN(val)) daySum += val;
        });

        const dayTotalCell = document.querySelector(`.day-total[data-date="${date}"]`);
        if (dayTotalCell) {
            dayTotalCell.value = formatHours(daySum);
            // Подсветка дня: зелёный если > 0, иначе нейтральный
            dayTotalCell.style.background = daySum > 0 ? '#bbf7d0' : '#f1f5f9';
            dayTotalCell.style.fontWeight = daySum > 0 ? '700' : '400';
        }
    });
}

function updateMedicineHighlight() {
    document.querySelectorAll('td[data-subject="med"]').forEach(td => {
        // 🔹 Пропускаем исключённые даты
        if (excludedDates.includes(td.dataset.date)) {
            td.classList.remove('has-hours');
            return;
        }
        const input = td.querySelector('.hours-input');
        const currentHours = parseFloat(input.value) || 0;
        const isReserved = window.topicsState[td.dataset.date] && window.topicsState[td.dataset.date]['med'];
        td.classList.toggle('has-hours', currentHours > 0 || isReserved);
    });
}

// =============================================================================
// 🔹 МОДАЛЬНОЕ ОКНО: ОТКРЫТИЕ И РЕНДЕР
// =============================================================================

function openTopicModal(date, subject) {
    // 🔹 Не открываем модальное окно для исключённых дат
    if (excludedDates.includes(date)) {
        alert('⚠️ Этот день исключён из расписания и не может быть редактирован.');
        return;
    }

    currentModalDate = date;
    currentModalSubject = subject;
    document.getElementById('modal-date').textContent = date;
    document.getElementById('topic-modal').style.display = 'flex';
    document.getElementById('modal-content').innerHTML = '<div style="text-align: center; padding: 40px; color: #64748b;">Загрузка тем...</div>';

    const totalRequired = parseFloat(document.getElementById(`${subject}-total`)?.value) || 0;
    document.getElementById('modal-total-required').textContent = formatHours(totalRequired);
    updateModalRemainingTotal(subject);

    const programId = document.getElementById('plan-data-container')?.dataset.programId;
    let url = `/reference/api/topics/?subject=${subject}`;
    if (programId) {
        url += `&program_id=${programId}`;
    }

    fetch(url)
        .then(r => r.json())
        .then(data => {
            if (data.success && Array.isArray(data.topics)) {
                renderTopicsList(data.topics, subject, date);
            } else {
                document.getElementById('modal-content').innerHTML = `
                    <div style="text-align: center; padding: 40px; color: #dc2626;">
                        ❌ ${data.error || 'Нет тем для этого предмета'}
                    </div>`;
            }
        })
        .catch(error => {
            console.error('❌ Ошибка:', error);
            document.getElementById('modal-content').innerHTML = `
                <div style="text-align: center; padding: 40px; color: #dc2626;">
                    ❌ Ошибка сети: ${error.message}
                </div>`;
        });
}

function renderTopicsList(topics, subject, date) {
    const currentDayTopics = window.topicsState?.[date]?.[subject] || {};
    let html = '';
    let visibleTopicsCount = 0;

    const sortedTopics = [...topics].sort((a, b) => {
        const idA = parseInt(a.id) || 0;
        const idB = parseInt(b.id) || 0;
        return idA - idB;
    });

    sortedTopics.forEach((t, index) => {
        const topicHours = parseFloat(t.hours) || 0;
        const topicId = String(t.id);
        const savedHours = currentDayTopics[topicId] || 0;
        const isPZ = t.name.toLowerCase().includes('. пз') || t.name.toLowerCase().endsWith(' пз.');

        let usedOtherDays = 0;
        for (const d in window.topicsState) {
            if (d !== date && window.topicsState[d][subject]?.[topicId]) {
                usedOtherDays += parseFloat(window.topicsState[d][subject][topicId]) || 0;
            }
        }

        const maxAvailable = topicHours - usedOtherDays;
        if (maxAvailable <= 0 && savedHours <= 0) {
            return;
        }
        visibleTopicsCount++;

        if (maxAvailable <= 0) {
            html += `
                <div class="topic-row${isPZ ? ' pz' : ''}" style="opacity: 0.5; background: #f1f5f9;">
                    <div class="topic-name">${isPZ ? '📝 ПЗ: ' : ''}Тема №${t.number}: ${t.name}</div>
                    <div class="topic-required">Всего: ${topicHours.toFixed(1)} ч.</div>
                    <input type="number" step="1" min="0" max="0" value="${savedHours}" disabled>
                    <div style="font-size:11px;color:#94a3b8;">Заполнено</div>
                </div>`;
        } else {
            const inputValue = savedHours > 0 ? Math.floor(savedHours) : '';
            html += `
                <div class="topic-row${isPZ ? ' pz' : ''}" data-topic-id="${topicId}" data-max-available="${maxAvailable.toFixed(1)}">
                    <div class="topic-name">${isPZ ? ' ПЗ: ' : ''}Тема №${t.number}: ${t.name}</div>
                    <div class="topic-required">Всего: ${topicHours.toFixed(1)} ч.</div>
                    <input type="number" step="1" min="0" max="${Math.floor(maxAvailable)}"
                        class="topic-input" value="${inputValue}" placeholder="—">
                    <div style="font-size:11px;color:#64748b;">Макс: ${Math.floor(maxAvailable)}</div>
                </div>`;
        }
    });

    if (visibleTopicsCount === 0) {
        document.getElementById('modal-content').innerHTML = `
            <div style="text-align:center;padding:40px;color:#16a34a;">
                ✅ Все часы по этому предмету уже распределены!
            </div>`;
    } else {
        document.getElementById('modal-content').innerHTML = html;
    }

    document.querySelectorAll('#modal-content .topic-input:not([disabled])').forEach(input => {
        input.addEventListener('input', function() {
            const val = parseFloat(this.value) || 0;
            const max = parseFloat(this.closest('.topic-row').dataset.maxAvailable);
            this.style.borderColor = val > max ? '#ef4444' : '#cbd5e1';
            updateModalRemainingTotal(subject);
        });

        input.addEventListener('change', function() {
            const val = this.value.trim();
            this.value = (val === '0.5' || val === '.5') ? '0.5' : Math.round(parseFloat(val) || 0);
            updateModalRemainingTotal(subject);
        });

        input.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                window._savingViaEnter = true;
                handleSaveAllTopics();
                const form = document.getElementById('hours-form');
                if (form) form.requestSubmit();
            }
        });
    });
}

function updateModalRemainingTotal(subject) {
    const totalRequired = parseFloat(document.getElementById(`${subject}-total`)?.value) || 0;
    let distributed = 0;
    document.querySelectorAll('#modal-content .topic-input:not([disabled])').forEach(input => {
        distributed += parseFloat(input.value) || 0;
    });
    for (const d in window.topicsState) {
        if (d === currentModalDate) continue;
        const subMap = window.topicsState[d]?.[subject];
        if (subMap) Object.values(subMap).forEach(v => distributed += parseFloat(v) || 0);
    }
    const remaining = totalRequired - distributed;
    const el = document.getElementById('modal-remaining-total');
    if (el) {
        el.textContent = formatHours(remaining);
        el.style.color = remaining < 0 ? '#dc2626' : (remaining === 0 ? '#16a34a' : '#0369a1');
    }
}

function closeTopicModal() {
    document.getElementById('topic-modal').style.display = 'none';
    currentModalDate = null;
    currentModalSubject = null;
}

function handleSaveAllTopics() {
    if (!currentModalDate || !currentModalSubject) return;

    const newDayTopics = {};
    let newDaySum = 0;

    document.querySelectorAll('#modal-content .topic-row').forEach(row => {
        const input = row.querySelector('.topic-input');
        if (!input || input.disabled) return;

        let val = parseFloat(input.value) || 0;
        newDayTopics[row.dataset.topicId] = val;
        if (val > 0) {
            newDaySum += val;
        }
    });

    if (newDaySum > MAX_HOURS_PER_DAY) {
        alert(`⚠️ Нельзя распределить больше ${MAX_HOURS_PER_DAY} часов в один день!`);
        return;
    }

    let subjectUsedOutSideDay = 0;
    for (const d in window.topicsState) {
        if (d === currentModalDate) continue;
        const subMap = window.topicsState[d]?.[currentModalSubject];
        if (subMap) Object.values(subMap).forEach(v => subjectUsedOutSideDay += parseFloat(v) || 0);
    }

    const limit = parseFloat(document.getElementById(`${currentModalSubject}-total`)?.value) || 0;
    if ((newDaySum + subjectUsedOutSideDay) > limit) {
        alert(`⚠️ Превышение лимита для предмета ${currentModalSubject.toUpperCase()}.`);
        return;
    }

    if (!window.topicsState[currentModalDate]) window.topicsState[currentModalDate] = {};

    const nonZeroTopics = {};
    for (const tid in newDayTopics) {
        if (newDayTopics[tid] > 0) {
            nonZeroTopics[tid] = newDayTopics[tid];
        }
    }

    if (Object.keys(nonZeroTopics).length > 0) {
        window.topicsState[currentModalDate][currentModalSubject] = nonZeroTopics;
    } else {
        delete window.topicsState[currentModalDate][currentModalSubject];
        if (Object.keys(window.topicsState[currentModalDate]).length === 0) {
            delete window.topicsState[currentModalDate];
        }
    }

    saveStateToStorage();
    syncDOMFromState();
    closeTopicModal();
}

// =============================================================================
// 🔹 СЛУШАТЕЛИ СОБЫТИЙ
// =============================================================================

function setupListeners() {
    const tableBody = document.querySelector('.distribution-table tbody');
    if (!tableBody) return;
    tableBody.addEventListener('click', function(e) {
        const td = e.target.closest('td[data-date][data-subject]');
        if (td && td.dataset.date && td.dataset.subject && td.dataset.subject !== 'total') {
            // 🔹 Не открываем модальное окно для исключённых дат
            if (excludedDates.includes(td.dataset.date)) {
                alert('⚠️ Этот день исключён из расписания.');
                return;
            }
            openTopicModal(td.dataset.date, td.dataset.subject);
        }
    });
    document.querySelectorAll('.subject-hours').forEach(input => {
        input.addEventListener('input', function() {
            if (this.dataset.subject === 'med') updateMedicineHighlight();
            recalculateTotals();
        });
        input.addEventListener('change', function() {
            if (this.dataset.subject === 'med') updateMedicineHighlight();
            recalculateTotals();
        });
    });
    document.getElementById('modal-close-btn')?.addEventListener('click', closeTopicModal);
    document.getElementById('modal-cancel-btn')?.addEventListener('click', closeTopicModal);
    document.getElementById('modal-save-btn')?.addEventListener('click', handleSaveAllTopics);
    document.addEventListener('click', function(event) {
        const modal = document.getElementById('topic-modal');
        if (event.target === modal) closeTopicModal();
    });
    form?.addEventListener('submit', handleSubmitForm);
}

function handleSubmitForm(e) {
    e.preventDefault();
    const data = {
        plan_id: PLAN_ID,
        topics: window.topicsState,
        hours: {},
        category: document.querySelector('[name="category"]')?.value || '',
        time_start: document.getElementById('time-start')?.value,
        time_end: document.getElementById('time-end')?.value,
        med_teacher: document.querySelector('select[name="med_teacher"]')?.value,
        training_program: document.getElementById('training-program-select')?.value
    };
    fetch(window.location.href, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value
        },
        body: JSON.stringify(data)
    })
    .then(r => r.json())
    .then(res => {
        if (res.success) {
            if (!window._savingViaEnter) {
                alert('✅ Распределение сохранено!');
            }
            window._savingViaEnter = false;
        } else {
            alert('❌ ' + (res.error || 'Ошибка сохранения'));
        }
    })
    .catch(err => {
        console.error('❌ Ошибка сети:', err);
        alert('❌ Ошибка сети');
    });
}

// =============================================================================
// 🔹 ФУНКЦИИ УДАЛЕНИЯ ПЛАН-ГРАФИКА
// =============================================================================

function confirmDeleteSchedule() {
    document.getElementById('deleteModal').style.display = 'flex';
}
function closeDeleteModal() {
    document.getElementById('deleteModal').style.display = 'none';
}
function deleteSchedule() {
    if (PLAN_ID === 0) {
        alert('❌ Ошибка: не найден ID план-графика');
        closeDeleteModal();
        return;
    }
    fetch(`/groups/schedules/${PLAN_ID}/delete-plan/`, {
        method: 'DELETE',
        headers: {
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
            'Content-Type': 'application/json'
        }
    })
    .then(async response => {
        if (!response.ok) {
            if (response.status === 404) {
                throw new Error('План-график не найден (ID=' + PLAN_ID + ')');
            }
            const text = await response.text();
            throw new Error(`HTTP ${response.status}: ${text.slice(0, 200)}`);
        }
        return response.json();
    })
    .then(result => {
        if (result.success) {
            localStorage.removeItem(`topicsState_${PLAN_ID}`);
            alert('✅ Таблица распределения часов очищена!');
            closeDeleteModal();
            const url = new URL(window.location.href);
            url.searchParams.set('_clear_cache', Date.now().toString());
            window.location.href = url.toString();
        } else {
            alert('❌ Ошибка: ' + (result.error || 'Неизвестная ошибка'));
            closeDeleteModal();
        }
    })
    .catch(err => {
        console.error('Ошибка:', err);
        alert(' Ошибка при удалении: ' + err.message);
        closeDeleteModal();
    });
}
document.getElementById('deleteModal')?.addEventListener('click', function(e) {
    if (e.target === this) closeDeleteModal();
});
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') closeDeleteModal();
});

// =============================================================================
// 🔹 ЗАПУСК ПРИ ЗАГРУЗКЕ СТРАНИЦЫ
// =============================================================================
document.addEventListener('DOMContentLoaded', function() {
    console.log('✅ Страница загружена, инициализация...');
    console.log('🔹 Исключённые даты:', excludedDates);

    loadStateFromStorage();
    buildCellsMap();
    syncDOMFromState();

    // 🔹 🔥 🔥 УДАЛЯЕМ строки исключённых дней из таблицы 🔥 🔥 🔥
    removeExcludedDateRows();

    setupListeners();
    setTimeout(() => {
        recalculateTotals();
        console.log('📊 Итоги пересчитаны');
    }, 200);
    document.getElementById('training-program-select')?.addEventListener('change', function() {
        const programId = this.value;
        if (programId) {
            const url = new URL(window.location.href);
            url.searchParams.set('program_id', programId);
            window.location.href = url.toString();
        }
    });
});