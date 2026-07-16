class ScheduleStore {
    constructor(planId, initialData = {}) {
        this.planId = planId;
        this.data = JSON.parse(JSON.stringify(initialData)); // Глубокая копия
        this.listeners = [];
    }

    // Получить данные темы
    getTopic(date, subject, topicId) {
        return this.data[date]?.[subject]?.[topicId] || 0;
    }

    // Установить часы темы (с валидацией)
    setTopic(date, subject, topicId, hours) {
        if (!this.data[date]) this.data[date] = {};
        if (!this.data[date][subject]) this.data[date][subject] = {};

        // Сохраняем
        this.data[date][subject][topicId] = hours;

        // Уведомляем UI об изменении
        this.notify({ type: 'UPDATE_TOPIC', date, subject, topicId, hours });
        this.persist();
    }

    // Удалить тему (Новая функциональность)
    deleteTopic(date, subject, topicId) {
        if (this.data[date]?.[subject]?.[topicId]) {
            delete this.data[date][subject][topicId];
            this.notify({ type: 'DELETE_TOPIC', date, subject, topicId });
            this.persist();
        }
    }

    // Сохранение в localStorage
    persist() {
        localStorage.setItem(`drsl_state_${this.planId}`, JSON.stringify(this.data));
    }

    // Подписка на изменения
    subscribe(callback) {
        this.listeners.push(callback);
    }

    notify(event) {
        this.listeners.forEach(cb => cb(event));
    }
}

// Инициализация
const store = new ScheduleStore(PLAN_ID, initialDataFromServer);