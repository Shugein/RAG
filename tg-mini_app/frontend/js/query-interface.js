
class QueryInterface {
    constructor() {
        this.selectedTypes = new Set();
        this.selectedSectors = new Set();
        this.isProcessing = false;
        
        this.initializeComponents();
        this.bindEvents();
              // Обновляем описание
        const queryDescription = document.getElementById('queryDescription');
        if (queryDescription) {
          // Отображаем результаты
        resultsContent.innerHTML = contentHTML;yText = result.query || result.query?.text || this.queryInput.value || 'ваш запрос';
            queryDescription.textContent = `По запросу: "${queryText}"`;
        }

        // Рендерим результаты
        this.renderResults(result);

        // Настраиваем кнопки Telegram
        if (this.isInTelegram) {
            this.tg.MainButton.hide();
            this.tg.BackButton.show();
        }
        
        this.hapticFeedback('success');Telegram();
    }

    initializeComponents() {
        // Основные элементы
        this.queryForm = document.getElementById('queryForm');
        this.queryInput = document.getElementById('queryInput');
        this.submitBtn = document.getElementById('submitBtn');
        this.charCount = document.getElementById('charCount');
        this.loadingOverlay = document.getElementById('loadingOverlay');
        this.resultsSection = document.getElementById('resultsSection');
        this.backBtn = document.getElementById('backBtn');
        
        // Кнопки выбора
        this.queryTypeButtons = document.querySelectorAll('.query-type-btn');
        this.sectorButtons = document.querySelectorAll('.sector-btn');
        this.quickActionButtons = document.querySelectorAll('.quick-action-btn');
        
        console.log('🎯 Query Interface инициализирован');
    }

    bindEvents() {
        // Обработка формы
        if (this.queryForm) {
            this.queryForm.addEventListener('submit', (e) => this.handleSubmit(e));
        }

        // Счетчик символов
        if (this.queryInput) {
            this.queryInput.addEventListener('input', () => this.updateCharCount());
        }

        // Кнопки типов запросов
        this.queryTypeButtons.forEach(btn => {
            btn.addEventListener('click', () => this.toggleQueryType(btn));
        });

        // Кнопки секторов
        this.sectorButtons.forEach(btn => {
            btn.addEventListener('click', () => this.toggleSector(btn));
        });

        // Быстрые действия
        this.quickActionButtons.forEach(btn => {
            btn.addEventListener('click', () => this.handleQuickAction(btn));
        });

        // Кнопка "Назад"
        if (this.backBtn) {
            this.backBtn.addEventListener('click', () => this.showQueryInterface());
        }

        // Горячие клавиши
        document.addEventListener('keydown', (e) => this.handleKeyDown(e));
    }

    initializeTelegram() {
        // Проверяем запуск в Telegram
        if (window.Telegram && window.Telegram.WebApp) {
            this.tg = window.Telegram.WebApp;
            this.isInTelegram = true;
            
            // Настройка Telegram WebApp
            this.tg.ready();
            this.tg.expand();
            this.tg.setHeaderColor('#1e40af');
            this.tg.setBackgroundColor('#ffffff');
            
            // Обновляем информацию о пользователе
            this.updateUserInfo();
            
            // Настраиваем кнопки Telegram
            this.setupTelegramButtons();
            
            console.log('🤖 Telegram WebApp инициализирован');
            console.log('👤 Пользователь:', this.tg.initDataUnsafe?.user);
        } else {
            this.isInTelegram = false;
            console.log('🌐 Запуск в обычном браузере');
        }
    }

    updateUserInfo() {
        if (this.isInTelegram && this.tg.initDataUnsafe?.user) {
            const user = this.tg.initDataUnsafe.user;
            const userInitial = document.getElementById('userInitial');
            const userName = document.getElementById('userName');
            
            if (userInitial) {
                userInitial.textContent = user.first_name?.charAt(0) || 'U';
            }
            
            if (userName) {
                userName.textContent = user.first_name || 'Пользователь';
            }
        }
    }

    setupTelegramButtons() {
        if (!this.isInTelegram) return;

        // Главная кнопка - отправка запроса
        this.tg.MainButton.text = '🚀 Получить данные RADAR';
        this.tg.MainButton.color = '#1e40af';
        this.tg.MainButton.textColor = '#ffffff';
        
        // Обработчик главной кнопки
        this.tg.MainButton.onClick(() => {
            if (this.submitBtn && !this.isProcessing) {
                this.submitBtn.click();
            }
        });

        // Кнопка назад
        this.tg.BackButton.onClick(() => {
            this.showQueryInterface();
        });
    }

    updateCharCount() {
        if (this.queryInput && this.charCount) {
            const length = this.queryInput.value.length;
            this.charCount.textContent = `${length}/500`;
            
            // Обновляем кнопку отправки
            this.updateSubmitButton();
        }
    }

    updateSubmitButton() {
        const hasQuery = this.queryInput && this.queryInput.value.trim().length > 0;
        const isValid = hasQuery && !this.isProcessing;
        
        if (this.submitBtn) {
            this.submitBtn.disabled = !isValid;
            this.submitBtn.classList.toggle('opacity-50', !isValid);
        }

        // Обновляем главную кнопку Telegram
        if (this.isInTelegram) {
            if (isValid) {
                this.tg.MainButton.show();
            } else {
                this.tg.MainButton.hide();
            }
        }
    }

    toggleQueryType(button) {
        const type = button.dataset.type;
        
        if (this.selectedTypes.has(type)) {
            this.selectedTypes.delete(type);
            button.classList.remove('active');
        } else {
            this.selectedTypes.add(type);
            button.classList.add('active');
        }

        this.hapticFeedback('light');
        console.log('📋 Выбранные типы:', Array.from(this.selectedTypes));
    }

    toggleSector(button) {
        const sector = button.dataset.sector;
        
        // Если выбран "Все сектора", очищаем остальные
        if (sector === 'all') {
            this.selectedSectors.clear();
            this.sectorButtons.forEach(btn => btn.classList.remove('active'));
            this.selectedSectors.add('all');
            button.classList.add('active');
        } else {
            // Убираем "Все сектора" если выбираем конкретный
            if (this.selectedSectors.has('all')) {
                this.selectedSectors.delete('all');
                this.sectorButtons.forEach(btn => {
                    if (btn.dataset.sector === 'all') {
                        btn.classList.remove('active');
                    }
                });
            }
            
            if (this.selectedSectors.has(sector)) {
                this.selectedSectors.delete(sector);
                button.classList.remove('active');
            } else {
                this.selectedSectors.add(sector);
                button.classList.add('active');
            }
        }

        this.hapticFeedback('light');
        console.log('🏭 Выбранные сектора:', Array.from(this.selectedSectors));
    }

    handleQuickAction(button) {
        const query = button.dataset.query;
        
        if (this.queryInput) {
            this.queryInput.value = query;
            this.updateCharCount();
        }

        // Автоматически заполняем соответствующие фильтры
        this.autoFillFilters(query);
        
        this.hapticFeedback('medium');
        this.showTelegramAlert('Запрос заполнен! Нажмите "Получить данные" для отправки.');
    }

    autoFillFilters(query) {
        // Очищаем текущие выборы
        this.selectedTypes.clear();
        this.selectedSectors.clear();
        this.queryTypeButtons.forEach(btn => btn.classList.remove('active'));
        this.sectorButtons.forEach(btn => btn.classList.remove('active'));

        const queryLower = query.toLowerCase();

        // Определяем тип запроса
        if (queryLower.includes('горячие') || queryLower.includes('актуальные')) {
            this.selectedTypes.add('hot');
            document.querySelector('[data-type="hot"]')?.classList.add('active');
        }
        if (queryLower.includes('аналитик') || queryLower.includes('обзор')) {
            this.selectedTypes.add('analytics');
            document.querySelector('[data-type="analytics"]')?.classList.add('active');
        }
        if (queryLower.includes('черновик') || queryLower.includes('draft')) {
            this.selectedTypes.add('draft');
            document.querySelector('[data-type="draft"]')?.classList.add('active');
        }

        // Определяем сектор
        if (queryLower.includes('банк')) {
            this.selectedSectors.add('banking');
            document.querySelector('[data-sector="banking"]')?.classList.add('active');
        } else if (queryLower.includes('энергет')) {
            this.selectedSectors.add('energy');
            document.querySelector('[data-sector="energy"]')?.classList.add('active');
        } else {
            this.selectedSectors.add('all');
            document.querySelector('[data-sector="all"]')?.classList.add('active');
        }
    }

    async handleSubmit(e) {
        e.preventDefault();
        
        if (this.isProcessing) return;
        
        const query = this.queryInput?.value?.trim();
        if (!query) {
            this.showTelegramAlert('Пожалуйста, введите ваш запрос');
            return;
        }

        this.isProcessing = true;
        this.showLoading();

        try {
            // Определяем тип запроса и сектор
            const queryType = this.getSelectedQueryType();
            const sector = this.getSelectedSector();
            
            console.log(`� Отправка запроса в RADAR: "${query}" (${queryType}, ${sector})`);

            // ВЫЗОВ RADAR ФУНКЦИИ через API
            const result = await this.callRADARFunction(query, queryType, sector);
            
            // Показываем результаты
            this.displayResults(result);

        } catch (error) {
            console.error('❌ Ошибка обработки запроса:', error);
            this.showTelegramAlert(`Ошибка обработки запроса: ${error.message}`);
        } finally {
            this.isProcessing = false;
            this.hideLoading();
            this.updateSubmitButton();
        }
    }

    async callRADARFunction(queryText, queryType, sector) {
        /**
         * ВЫЗОВ RADAR ФУНКЦИИ через API заглушку
         * Пока используем mock данные, потом заменим на вашу локальную функцию
         */
        
        const response = await fetch('/api/process_query', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify({
                query: queryText,
                type: queryType,
                sector: sector
            })
        });
        
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`HTTP ${response.status}: ${errorText}`);
        }
        
        const result = await response.json();
        console.log('📊 Получен результат от RADAR:', result);
        
        return result;
    }

    getSelectedQueryType() {
        const activeTypeBtn = document.querySelector('.query-type-btn.active');
        return activeTypeBtn ? activeTypeBtn.dataset.type : 'general';
    }

    getSelectedSector() {
        const activeSectorBtn = document.querySelector('.sector-btn.active');
        return activeSectorBtn ? activeSectorBtn.dataset.sector : 'all';
    }

    displayResults(result) {
        console.log('🎯 Отображение результатов:', result);
        
        // Скрываем интерфейс запроса (используем более надёжный селектор)
        const heroSection = document.querySelector('.relative.overflow-hidden');
        if (heroSection) {
            heroSection.classList.add('hidden');
        }
        
        // Показываем результаты
        if (this.resultsSection) {
            this.resultsSection.classList.remove('hidden');
        }
        
        // Обновляем описание
        const queryDescription = document.getElementById('queryDescription');
        if (queryDescription) {
            const queryText = result.query?.text || result.query || 'ваш запрос';
            queryDescription.textContent = `По запросу: "${queryText}"`;
        }

        // Заполняем результаты
        this.renderResults(result);

        // Настраиваем кнопки Telegram
        if (this.isInTelegram) {
            this.tg.MainButton.hide();
            this.tg.BackButton.show();
        }
        
        this.hapticFeedback('success');
    }

    generateMockResults(queryData) {
        const mockNews = [
            {
                id: 1,
                title: "🏦 Сбербанк объявил о рекордной прибыли за квартал",
                summary: "Крупнейший банк России превысил ожидания аналитиков, показав рост прибыли на 15% в годовом выражении.",
                source: "RBC",
                date: "04.10.2025",
                hotness: 0.95,
                sector: "banking"
            },
            {
                id: 2,
                title: "⚡ Газпром расширяет поставки в Азию",
                summary: "Энергетический гигант подписал долгосрочные контракты на поставку газа общей стоимостью $50 млрд.",
                source: "Ведомости",
                date: "04.10.2025",
                hotness: 0.87,
                sector: "energy"
            },
            {
                id: 3,
                title: "💰 ЦБ РФ повысил ключевую ставку до 21%",
                summary: "Центробанк принял решение о повышении ставки на 200 б.п. в ответ на инфляционные риски.",
                source: "Коммерсант",
                date: "04.10.2025",
                hotness: 0.83,
                sector: "banking"
            }
        ];

        // Фильтруем по секторам
        let filteredNews = mockNews;
        if (queryData.sectors.length > 0 && !queryData.sectors.includes('all')) {
            filteredNews = mockNews.filter(news => 
                queryData.sectors.includes(news.sector)
            );
        }

        return {
            query: queryData.query,
            totalFound: filteredNews.length,
            news: filteredNews,
            analytics: {
                sectors: queryData.sectors,
                types: queryData.types,
                timeframe: "последние 24 часа"
            }
        };
    }

    showResults(queryData, results) {
        // Скрываем интерфейс запроса
        document.querySelector('#app > div:first-child').classList.add('hidden');
        
        // Показываем результаты
        this.resultsSection.classList.remove('hidden');
        
        // Обновляем описание
        const queryDescription = document.getElementById('queryDescription');
        if (queryDescription) {
            queryDescription.textContent = `По запросу: "${queryData.query}"`;
        }

        // Заполняем результаты
        this.renderResults(results);

        // Настраиваем кнопки Telegram
        if (this.isInTelegram) {
            this.tg.MainButton.hide();
            this.tg.BackButton.show();
        }
    }

    renderResults(result) {
        console.log('🎨 Рендер результатов:', result);
        
        const resultsContent = document.getElementById('resultsContent');
        if (!resultsContent) {
            console.error('❌ Элемент resultsContent не найден');
            return;
        }

        // Обрабатываем разные форматы ответов
        let contentHTML = '';
        
        // Если это ответ от реального RADAR API (как в вашем примере)
        if (result.documents && result.answer) {
            contentHTML = this.generateRealRadarHTML(result);
        }
        // Если это mock данные от нашего бэкенда
        else if (result.query && result.statistics && result.results) {
            const { query, statistics, results } = result;
            
            // Генерируем HTML в зависимости от типа запроса
            if (query.type === 'draft') {
                contentHTML = this.generateDraftHTML(results);
            } else if (query.type === 'hot') {
                contentHTML = this.generateHotNewsHTML(results);
            } else if (query.type === 'analytics') {
                contentHTML = this.generateAnalyticsHTML(results);
            } else {
                contentHTML = this.generateSearchHTML(results);
            }
        }
        // Fallback для любого другого формата
        else {
            contentHTML = this.generateGenericHTML(result);
        }

        // Отображаем результаты
        resultsContent.innerHTML = contentHTML;
                    </div>
                </div>
            </div>

            ${contentHTML}

            <!-- Действия -->
            <div class="mt-8 flex flex-col sm:flex-row gap-4">
                <button class="flex-1 bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white font-semibold py-4 px-6 rounded-2xl transition-all duration-300 transform hover:scale-105">
                    � Экспорт результатов
                </button>
                <button class="flex-1 bg-gradient-to-r from-green-600 to-green-700 hover:from-green-700 hover:to-green-800 text-white font-semibold py-4 px-6 rounded-2xl transition-all duration-300 transform hover:scale-105">
                    🔄 Обновить данные
                </button>
            </div>
        `;

        resultsContent.innerHTML = html;
    }

    generateDraftHTML(draft) {
        return `
            <div class="bg-white rounded-2xl shadow-lg p-6 mb-6">
                <h3 class="text-2xl font-bold text-gray-900 mb-4">${draft.title}</h3>
                <p class="text-gray-600 mb-6">${draft.summary}</p>
                
                <div class="mb-6">
                    <h4 class="text-lg font-semibold text-gray-800 mb-3">🔑 Ключевые моменты:</h4>
                    <ul class="space-y-2">
                        ${draft.key_points.map(point => `
                            <li class="flex items-start">
                                <span class="text-blue-500 mr-2">•</span>
                                <span class="text-gray-700">${point}</span>
                            </li>
                        `).join('')}
                    </ul>
                </div>
                
                <div class="mb-6">
                    <h4 class="text-lg font-semibold text-gray-800 mb-4">🔥 Важные новости:</h4>
                    <div class="space-y-3">
                        ${draft.hot_news.map(news => `
                            <div class="border border-gray-200 rounded-xl p-4">
                                <h5 class="font-medium text-gray-900 mb-2">${news.title}</h5>
                                <div class="flex items-center text-sm text-gray-500 mb-2">
                                    <span class="mr-4">📡 ${news.source}</span>
                                    <span class="mr-4">⭐ ${news.importance.toFixed(2)}</span>
                                    <span>${news.date}</span>
                                </div>
                                <p class="text-gray-600 text-sm">${news.summary}</p>
                            </div>
                        `).join('')}
                    </div>
                </div>
                
                ${draft.corporate_events && draft.corporate_events.length > 0 ? `
                    <div class="mb-6">
                        <h4 class="text-lg font-semibold text-gray-800 mb-4">🏢 Корпоративные события:</h4>
                        <div class="space-y-3">
                            ${draft.corporate_events.map(event => `
                                <div class="border border-gray-200 rounded-xl p-4">
                                    <h5 class="font-medium text-gray-900 mb-1">${event.company}</h5>
                                    <div class="text-sm text-blue-600 mb-2">${event.event_type}</div>
                                    <div class="text-sm text-gray-500 mb-2">${event.date}</div>
                                    <p class="text-gray-600 text-sm">${event.summary}</p>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}
                
                <div>
                    <h4 class="text-lg font-semibold text-gray-800 mb-3">💡 Рекомендации:</h4>
                    <ul class="space-y-2">
                        ${draft.recommendations.map(rec => `
                            <li class="flex items-start">
                                <span class="text-green-500 mr-2">✓</span>
                                <span class="text-gray-700">${rec}</span>
                            </li>
                        `).join('')}
                    </ul>
                </div>
            </div>
        `;
    }

    generateHotNewsHTML(hotNews) {
        return `
            <div class="bg-white rounded-2xl shadow-lg p-6">
                <h3 class="text-2xl font-bold text-gray-900 mb-4">${hotNews.title}</h3>
                <p class="text-gray-600 mb-6">Найдено ${hotNews.total_found} горячих новостей</p>
                
                <div class="space-y-4">
                    ${hotNews.news.map(news => `
                        <div class="border border-gray-200 rounded-xl p-4 hover:shadow-md transition-shadow">
                            <div class="flex items-start justify-between mb-3">
                                <h4 class="text-lg font-semibold text-gray-900 flex-1">${news.title}</h4>
                                <div class="ml-4 bg-gradient-to-r from-orange-400 to-red-500 text-white px-3 py-1 rounded-full text-sm font-medium">
                                    🔥 ${(news.hotness_score * 100).toFixed(0)}%
                                </div>
                            </div>
                            <p class="text-gray-600 mb-3">${news.content}</p>
                            <div class="flex items-center justify-between text-sm">
                                <div class="flex items-center space-x-4">
                                    <span class="text-gray-500">📡 ${news.source}</span>
                                    <span class="text-gray-500">${news.published_dt}</span>
                                </div>
                                <div class="flex space-x-2">
                                    ${news.tags.map(tag => `
                                        <span class="bg-gray-100 text-gray-800 px-2 py-1 rounded text-xs">${tag}</span>
                                    `).join('')}
                                </div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    generateAnalyticsHTML(analytics) {
        return `
            <div class="bg-white rounded-2xl shadow-lg p-6">
                <h3 class="text-2xl font-bold text-gray-900 mb-4">${analytics.title}</h3>
                <p class="text-gray-600 mb-6">${analytics.period}</p>
                
                <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                    <div class="text-center p-4 bg-blue-50 rounded-xl">
                        <div class="text-2xl font-bold text-blue-600">${analytics.metrics.total_news}</div>
                        <div class="text-sm text-gray-600">Всего новостей</div>
                    </div>
                    <div class="text-center p-4 bg-green-50 rounded-xl">
                        <div class="text-2xl font-bold text-green-600">${analytics.metrics.total_sources}</div>
                        <div class="text-sm text-gray-600">Источников</div>
                    </div>
                    <div class="text-center p-4 bg-purple-50 rounded-xl">
                        <div class="text-2xl font-bold text-purple-600">${analytics.metrics.avg_importance.toFixed(2)}</div>
                        <div class="text-sm text-gray-600">Средняя важность</div>
                    </div>
                    <div class="text-center p-4 bg-orange-50 rounded-xl">
                        <div class="text-2xl font-bold text-orange-600">${analytics.metrics.total_edisclosure}</div>
                        <div class="text-sm text-gray-600">E-disclosure</div>
                    </div>
                </div>
                
                <div class="mb-6">
                    <h4 class="text-lg font-semibold text-gray-800 mb-4">📊 Разбивка по источникам:</h4>
                    <div class="space-y-2">
                        ${analytics.sources_breakdown.map(item => `
                            <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                                <span class="font-medium text-gray-900">${item.source}</span>
                                <div class="flex items-center space-x-2">
                                    <span class="text-gray-600">${item.count}</span>
                                    <span class="text-blue-600 font-medium">${item.percentage}%</span>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
                
                <div>
                    <h4 class="text-lg font-semibold text-gray-800 mb-4">⭐ Топ новости по важности:</h4>
                    <div class="space-y-3">
                        ${analytics.top_news.map((news, index) => `
                            <div class="flex items-start space-x-3 p-3 border border-gray-200 rounded-lg">
                                <div class="flex-shrink-0 w-8 h-8 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-sm font-bold">
                                    ${index + 1}
                                </div>
                                <div class="flex-1">
                                    <h5 class="font-medium text-gray-900 mb-1">${news.title}</h5>
                                    <div class="text-sm text-gray-500">
                                        ${news.source} • ${news.date} • Важность: ${news.importance.toFixed(2)}
                                    </div>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            </div>
        `;
    }

    generateSearchHTML(searchResults) {
        return `
            <div class="bg-white rounded-2xl shadow-lg p-6">
                <h3 class="text-2xl font-bold text-gray-900 mb-4">${searchResults.title}</h3>
                <p class="text-gray-600 mb-6">Найдено ${searchResults.total_found} результатов</p>
                
                <div class="space-y-4">
                    ${searchResults.results.map(result => `
                        <div class="border border-gray-200 rounded-xl p-4 hover:shadow-md transition-shadow">
                            <h4 class="text-lg font-semibold text-gray-900 mb-2">${result.title}</h4>
                            <p class="text-gray-600 mb-3">${result.content}</p>
                            <div class="flex items-center justify-between text-sm">
                                <div class="flex items-center space-x-4">
                                    <span class="text-gray-500">📡 ${result.source}</span>
                                    <span class="text-gray-500">${result.published_dt}</span>
                                </div>
                                <div class="flex items-center space-x-2">
                                    <span class="bg-blue-100 text-blue-800 px-2 py-1 rounded text-xs">
                                        Релевантность: ${result.relevance}
                                    </span>
                                    <span class="bg-green-100 text-green-800 px-2 py-1 rounded text-xs">
                                        Важность: ${result.importance.toFixed(2)}
                                    </span>
                                </div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    showQueryInterface() {
        console.log('🔙 Возврат к интерфейсу запроса');
        
        // Показываем интерфейс запроса (используем более надёжный селектор)
        const heroSection = document.querySelector('.relative.overflow-hidden');
        if (heroSection) {
            heroSection.classList.remove('hidden');
        }
        
        // Скрываем результаты
        if (this.resultsSection) {
            this.resultsSection.classList.add('hidden');
        }

        // Настраиваем кнопки Telegram
        if (this.isInTelegram) {
            this.tg.BackButton.hide();
            this.updateSubmitButton();
        }
    }

    showLoading() {
        if (this.loadingOverlay) {
            this.loadingOverlay.classList.remove('hidden');
        }
    }

    hideLoading() {
        if (this.loadingOverlay) {
            this.loadingOverlay.classList.add('hidden');
        }
    }

    handleKeyDown(e) {
        // Ctrl+Enter для отправки
        if (e.ctrlKey && e.key === 'Enter') {
            if (this.submitBtn && !this.isProcessing) {
                this.submitBtn.click();
            }
        }
        
        // Escape для возврата
        if (e.key === 'Escape' && !this.resultsSection.classList.contains('hidden')) {
            this.showQueryInterface();
        }
    }

    hapticFeedback(type = 'light') {
        if (this.isInTelegram && this.tg.HapticFeedback) {
            this.tg.HapticFeedback.impactOccurred(type);
        }
    }

    showTelegramAlert(message) {
        if (this.isInTelegram) {
            this.tg.showAlert(message);
        } else {
            alert(message);
        }
    }

    generateRealRadarHTML(result) {
        /**
         * Генерирует HTML для реального ответа RADAR API
         * Формат: { query, answer, documents, metadata }
         */
        const { query, answer, documents, metadata } = result;
        
        return `
            <!-- Ответ RADAR -->
            <div class="bg-gradient-to-r from-green-50 to-emerald-50 rounded-2xl p-6 mb-6">
                <h3 class="text-xl font-bold text-gray-900 mb-4">🤖 Ответ RADAR</h3>
                <div class="bg-white rounded-xl p-4 border border-green-200">
                    <p class="text-gray-800 leading-relaxed">${answer}</p>
                </div>
            </div>

            <!-- Метаданные обработки -->
            <div class="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-2xl p-6 mb-6">
                <div class="flex items-center justify-between mb-4">
                    <h3 class="text-xl font-bold text-gray-900">📊 Статистика обработки</h3>
                    <span class="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm font-medium">
                        ${(metadata.total_time || 0).toFixed(2)}s
                    </span>
                </div>
                <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div class="text-center">
                        <div class="text-2xl font-bold text-blue-600">${metadata.num_documents || 0}</div>
                        <div class="text-sm text-gray-600">Документов</div>
                    </div>
                    <div class="text-center">
                        <div class="text-2xl font-bold text-green-600">${metadata.vectorizer ? '✓' : '✗'}</div>
                        <div class="text-sm text-gray-600">Векторизатор</div>
                    </div>
                    <div class="text-center">
                        <div class="text-2xl font-bold text-purple-600">${metadata.reranker ? '✓' : '✗'}</div>
                        <div class="text-sm text-gray-600">Reranker</div>
                    </div>
                    <div class="text-center">
                        <div class="text-2xl font-bold text-orange-600">${metadata.llm_model ? '✓' : '✗'}</div>
                        <div class="text-sm text-gray-600">LLM</div>
                    </div>
                </div>
            </div>

            <!-- Найденные документы -->
            <div class="bg-white rounded-2xl shadow-lg p-6">
                <h3 class="text-2xl font-bold text-gray-900 mb-6">📄 Найденные документы</h3>
                <div class="space-y-4">
                    ${documents.map((doc, index) => `
                        <div class="border border-gray-200 rounded-xl p-4 hover:shadow-md transition-shadow">
                            <div class="flex items-start justify-between mb-3">
                                <h4 class="text-lg font-semibold text-gray-900 flex-1">${doc.title}</h4>
                                <div class="flex items-center space-x-2 ml-4">
                                    <span class="bg-blue-100 text-blue-800 px-2 py-1 rounded-full text-xs font-medium">
                                        Позиция: ${doc.original_position || index + 1}
                                    </span>
                                    <span class="bg-green-100 text-green-800 px-2 py-1 rounded-full text-xs font-medium">
                                        Скор: ${(doc.rerank_score || 0).toFixed(3)}
                                    </span>
                                </div>
                            </div>
                            
                            <p class="text-gray-700 mb-3 leading-relaxed">${doc.text || doc.chunk_text}</p>
                            
                            <div class="flex items-center justify-between text-sm text-gray-500">
                                <div class="flex items-center space-x-4">
                                    <span>📰 ${doc.source}</span>
                                    <span>🕒 ${new Date(doc.timestamp * 1000).toLocaleDateString('ru-RU')}</span>
                                </div>
                                ${doc.url ? `<a href="${doc.url}" target="_blank" class="text-blue-600 hover:text-blue-800 underline">Открыть</a>` : ''}
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>

            <!-- Технические детали -->
            <div class="bg-gray-50 rounded-2xl p-6 mt-6">
                <h3 class="text-lg font-bold text-gray-900 mb-4">🔧 Технические детали</h3>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                    <div>
                        <span class="font-medium text-gray-700">Векторизатор:</span>
                        <span class="text-gray-600 ml-2">${metadata.vectorizer || 'Не указан'}</span>
                    </div>
                    <div>
                        <span class="font-medium text-gray-700">Reranker:</span>
                        <span class="text-gray-600 ml-2">${metadata.reranker || 'Не указан'}</span>
                    </div>
                    <div>
                        <span class="font-medium text-gray-700">LLM модель:</span>
                        <span class="text-gray-600 ml-2">${metadata.llm_model || 'Не указана'}</span>
                    </div>
                    <div>
                        <span class="font-medium text-gray-700">Время обработки:</span>
                        <span class="text-gray-600 ml-2">${(metadata.total_time || 0).toFixed(3)}с</span>
                    </div>
                </div>
            </div>

            <!-- Действия -->
            <div class="mt-8 flex flex-col sm:flex-row gap-4">
                <button class="flex-1 bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white font-semibold py-4 px-6 rounded-2xl transition-all duration-300 transform hover:scale-105">
                    📊 Экспорт результатов
                </button>
                <button class="flex-1 bg-gradient-to-r from-green-600 to-green-700 hover:from-green-700 hover:to-green-800 text-white font-semibold py-4 px-6 rounded-2xl transition-all duration-300 transform hover:scale-105">
                    🔄 Обновить данные
                </button>
            </div>
        `;
    }

    generateGenericHTML(result) {
        /**
         * Генерирует HTML для любого формата данных
         */
        return `
            <div class="bg-white rounded-2xl shadow-lg p-6">
                <h3 class="text-2xl font-bold text-gray-900 mb-4">📋 Результаты запроса</h3>
                <div class="bg-gray-50 rounded-xl p-4 overflow-auto">
                    <pre class="text-sm text-gray-700">${JSON.stringify(result, null, 2)}</pre>
                </div>
            </div>
        `;
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 Инициализация RADAR Query Interface...');
    window.queryInterface = new QueryInterface();
});