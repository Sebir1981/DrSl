// =============================================================================
// 🔹 ИНИЦИАЛИЗАЦИЯ ДАННЫХ
// =============================================================================

const PLAN_ID = parseInt(document.getElementById('plan-data-container')?.dataset.planId) || 0;
let REQUIRED_HOURS = parseFloat(document.getElementById('plan-data-container')?.dataset.requiredHours || '0') || 0;
const MAX_HOURS_PER_DAY = 12;

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

function syncDOMFromState() {
    for (const date in window.topicsState) {
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
                // 🔹 Всегда устанавливаем значение, включая "0"
                cell.value = formatHours(daySum);
            }
        }
    }
    recalculateTotals();
    updateMedicineHighlight();
}

function recalculateTotals() {
    const dates = new Set(Object.keys(cellsMap).map(k => k.split('_')[0]));
    let grandTotal = 0;

    dates.forEach(date => {
        let daySum = 0;

        // 🔹 Читаем суммы НАПРЯМУЮ из topicsState (источник истины)
        for (const subject in window.topicsState[date] || {}) {
            const topicMap = window.topicsState[date][subject];
            let subjectSum = 0;
            for (const tid in topicMap) {
                subjectSum += parseFloat(topicMap[tid]) || 0;
            }
            daySum += subjectSum;

            // Обновляем ячейку в таблице
            const key = `${date}_${subject}`;
            const cell = cellsMap[key];
            if (cell) {
                cell.value = formatHours(subjectSum); // 🔹 Всегда устанавливаем значение, включая "0"
            }
        }

        // Обновляем "Всего за день"
        const dayTotalCell = document.querySelector(`.day-total[data-date="${date}"]`);
        if (dayTotalCell) {
            dayTotalCell.value = formatHours(daySum);
            dayTotalCell.style.background = daySum > 0 ? '#bbf7d0' : '#fef3c7';
        }
        grandTotal += daySum;
    });

    // Обновляем общий итог
    if (grandTotalInput) {
        const distributed = Math.round(grandTotal);
        const required = Math.round(REQUIRED_HOURS);
        grandTotalInput.value = `${distributed} / ${required}`;
        const diff = grandTotal - REQUIRED_HOURS;
        if (Math.abs(diff) < 0.01 && REQUIRED_HOURS > 0) {
            grandTotalInput.style.background = '#86efac';
        } else if (diff > 0) {
            grandTotalInput.style.background = '#fecaca';
        } else {
            grandTotalInput.style.background = '#fef3c7';
        }
    }

    // Обновляем итоги по предметам
    document.querySelectorAll('.subject-total-display').forEach(displayEl => {
        const subjectCode = displayEl.id.replace('-total-display', '');
        const hiddenInput = document.getElementById(`${subjectCode}-total`);
        if (hiddenInput) {
            const requiredHours = parseFloat(hiddenInput.value) || 0;

            // 🔹 Считаем распределённые часы из topicsState, а не из DOM
            let distributedHours = 0;
            for (const date in window.topicsState) {
                const subjectData = window.topicsState[date][subjectCode];
                if (subjectData) {
                    for (const tid in subjectData) {
                        distributedHours += parseFloat(subjectData[tid]) || 0;
                    }
                }
            }

            displayEl.textContent = `${formatHours(distributedHours)} / ${formatHours(requiredHours)}`;

            const row = displayEl.closest('tr');
            if (row) {
                if (Math.abs(distributedHours - requiredHours) < 0.01 && requiredHours > 0) {
                    row.style.background = '#f1f5f9';
                    row.style.opacity = '0.7';
                    row.classList.add('completed-subject');
                } else {
                    row.style.background = '';
                    row.style.opacity = '1';
                    row.classList.remove('completed-subject');
                }
            }
        }
    });
}

function updateMedicineHighlight() {
    document.querySelectorAll('td[data-subject="med"]').forEach(td => {
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

    // 🔹 Навешиваем обработчики на inputs
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

        // 🔹 Обработка Enter: сохранить и отправить форму (БЕЗ alert)
        input.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                window._savingViaEnter = true; // 🔹 Флаг: не показывать alert
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
        // 🔹 Сохраняем ВСЕ значения (включая 0)
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

    // 🔹 Если есть ненулевые темы — сохраняем, иначе удаляем предмет за этот день
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
            // 🔹 Показываем alert только если это НЕ нажатие Enter
            if (!window._savingViaEnter) {
                alert('✅ Распределение сохранено!');
            }
            window._savingViaEnter = false; // 🔹 Сбрасываем флаг
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
    loadStateFromStorage();
    buildCellsMap();
    syncDOMFromState();
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