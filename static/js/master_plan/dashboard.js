/**
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

    // =======================================================================
    // 🔹 СОСТОЯНИЕ МОДУЛЯ
    // =======================================================================
    let selectedEditPlanGroupId = null;
    let deletePlanGroupId = null;

    // Кэш: часы на студента для каждой группы (чтобы не искать в DOM при каждом изменении)
    const hoursPerStudentMap = {};

    // =======================================================================
    // 🔹 ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
    // =======================================================================
    const getCsrfToken = () =>
        document.querySelector('[name=csrfmiddlewaretoken]')?.value || CSRF_TOKEN;

    const setFieldValue = (id, value) => {
        const el = document.getElementById(id);
        if (el) el.value = value;
    };

    // =======================================================================
    // 🔹 ФУНКЦИЯ ВИЗУАЛИЗАЦИИ: Пересчёт распределённых и выкатанных студентов
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

    // =======================================================================
    // 🔹 ФУНКЦИЯ: Живое обновление статистики по мастерам
    // =======================================================================
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

        // Переподключаем тултипы после динамического обновления DOM
        if (typeof window.attachTooltips === 'function') {
            window.attachTooltips();
        }
    }

    // =======================================================================
    // 🔹 ЕДИНАЯ СИНХРОНИЗАЦИЯ ВСЕХ ПРОКРУТОК
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
    // 🔹 ОБНОВЛЕНИЕ РАСПРЕДЕЛЕНИЯ СТУДЕНТОВ
    // =======================================================================
    function updateDistribution(input) {
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

        // Превышение лимита
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

        // Отрицательное значение
        if (newValue < 0) {
            showToast('⚠️ Значение не может быть отрицательным. Установлено 0.', 'warning');
            input.value = 0;
            input.dataset.oldValue = 0;
            updateGroupCompletionVisuals();
            updateMastersStats();
            return;
        }

        // Отправка на сервер
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
                    return response.text().then(text => {
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
                        const autoField = cell.querySelector('.matrix-input-auto');
                        if (autoField && data.completed_count !== undefined) {
                            autoField.textContent = data.completed_count;
                        }
                    }

                    if (data.fully_driven_students !== undefined && data.total_students !== undefined) {
                        if (groupHeader) {
                            groupHeader.dataset.drivenStudents = data.fully_driven_students;
                            groupHeader.dataset.totalStudents = data.total_students;
                        }
                    }

                    updateGroupCompletionVisuals();
                    updateMastersStats();

                    if (data.is_archived) {
                        showToast('✅ Группа полностью выкатана и отправлена в архив!', 'success');
                        delete hoursPerStudentMap[planGroupId];

                        if (groupHeader) {
                            groupHeader.remove();
                            document.querySelectorAll(`.matrix-cell[data-plan-group-id="${planGroupId}"]`)
                                .forEach(cell => cell.remove());
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
    // 🔹 МОДАЛЬНЫЕ ОКНА: УПРАВЛЕНИЕ
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
    // 🔹 ИНИЦИАЛИЗАЦИЯ
    // =======================================================================
    function init() {
        // 0. Заполняем кэш часов для всех групп
        document.querySelectorAll('.matrix-header-group').forEach(header => {
            const planGroupId = header.dataset.planGroupId;
            hoursPerStudentMap[planGroupId] =
                parseFloat(header.dataset.hoursPerStudent) || DEFAULT_HOURS_PER_STUDENT;
        });

        // 1. Визуализация и статистика
        updateGroupCompletionVisuals();
        updateMastersStats();

        // 2. Синхронизация прокруток
        syncAllScroll();

        // 3. Запоминаем изначальные значения полей
        document.querySelectorAll('.matrix-input-manual').forEach(inp => {
            inp.dataset.oldValue = inp.value;
        });

        // 4. Добавление группы
        bindAddGroupForm();

        // 5. Редактирование
        bindEditGroupForm();

        // 6. Удаление
        bindDeleteGroupForm();

        // 7. Закрытие модалок по клику вне
        bindModalCloseOnOverlay();
    }

    function bindAddGroupForm() {
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

        const addForm = document.getElementById('addGroupForm');
        if (addForm) {
            addForm.addEventListener('submit', function (e) {
                e.preventDefault();
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
                const formData = new FormData(editForm);
                if (!formData.get('plan_group_id')) {
                    showToast('❌ Ошибка: не указан ID группы в плане.', 'error');
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
        ['addGroupModal', 'selectEditModal', 'editModal', 'deleteModal'].forEach(modalId => {
            const modal = document.getElementById(modalId);
            if (modal) {
                modal.addEventListener('click', function (e) {
                    if (e.target === this) {
                        if (modalId === 'addGroupModal') closeAddGroupModal();
                        if (modalId === 'selectEditModal') closeSelectEditModal();
                        if (modalId === 'editModal') closeEditModal();
                        if (modalId === 'deleteModal') closeDeleteModal();
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
    // 🔹 ЭКСПОРТ В window (для onclick в HTML)
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

    // Вспомогательные (не обязательно, но полезно для отладки)
    window.__masterPlan = {
        updateGroupCompletionVisuals,
        updateMastersStats,
        hoursPerStudentMap,
    };
})();