class QueryInterface {
    constructor() {
        this.selectedTypes = new Set();
        this.selectedSectors = new Set();
        this.isProcessing = false;
        
        this.initializeComponents();
        this.bindEvents();
        this.initializeTelegram();
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
        this.generatePdfToggle = document.getElementById('generatePdfToggle');
        
        // Кнопки выбора
        this.queryTypeButtons = document.querySelectorAll('.query-type-btn');
        this.sectorButtons = document.querySelectorAll('.sector-btn');
        this.quickActionButtons = document.querySelectorAll('.quick-action-btn');
        
        console.log('Query Interface инициализирован');
    }

    bindEvents() {
        if (this.queryForm) {
            this.queryForm.addEventListener('submit', (e) => this.handleSubmit(e));
        }

        if (this.queryInput) {
            this.queryInput.addEventListener('input', () => this.updateCharCount());
        }

        this.queryTypeButtons.forEach(btn => {
            btn.addEventListener('click', () => this.toggleQueryType(btn));
        });

        this.sectorButtons.forEach(btn => {
            btn.addEventListener('click', () => this.toggleSector(btn));
        });

        this.quickActionButtons.forEach(btn => {
            btn.addEventListener('click', () => this.handleQuickAction(btn));
        });

        if (this.backBtn) {
            this.backBtn.addEventListener('click', () => this.showQueryInterface());
        }

        document.addEventListener('keydown', (e) => this.handleKeyDown(e));
    }

    initializeTelegram() {
        if (window.Telegram && window.Telegram.WebApp) {
            this.tg = window.Telegram.WebApp;
            this.isInTelegram = true;
            
            this.tg.ready();
            this.tg.expand();
            this.tg.setHeaderColor('#1e40af');
            this.tg.setBackgroundColor('#ffffff');
            
            this.updateUserInfo();
            this.setupTelegramButtons();
            
            console.log('Telegram WebApp инициализирован');
            console.log('Пользователь:', this.tg.initDataUnsafe?.user);
        } else {
            this.isInTelegram = false;
            console.log('Запуск в обычном браузере');
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

        this.tg.MainButton.text = 'Получить данные RADAR';
        this.tg.MainButton.color = '#1e40af';
        this.tg.MainButton.textColor = '#ffffff';
        
        this.tg.MainButton.onClick(() => {
            if (this.submitBtn && !this.isProcessing) {
                this.submitBtn.click();
            }
        });

        this.tg.BackButton.onClick(() => {
            this.showQueryInterface();
        });
    }

    updateCharCount() {
        if (this.queryInput && this.charCount) {
            const length = this.queryInput.value.length;
            this.charCount.textContent = `${length}/500`;
            
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

        if (this.isInTelegram) {
            if (isValid) {
                this.tg.MainButton.show();
            } else {
                this.tg.MainButton.hide();
            }
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
            console.log(`🚀 Отправка запроса: "${query}"`);

            const generatePdf = this.generatePdfToggle?.checked || false;
            const result = await this.callRADARFunction(query, generatePdf);
            this.displayResults(result, generatePdf);

        } catch (error) {
            console.error('Ошибка обработки запроса:', error);
            this.showTelegramAlert(`Ошибка обработки запроса: ${error.message}`);
        } finally {
            this.isProcessing = false;
            this.hideLoading();
            this.updateSubmitButton();
        }
    }

    async callRADARFunction(queryText, generatePdf = false) {
        const response = await fetch('/api/process_query', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify({
                query: queryText,
                generate_pdf: generatePdf
            })
        });
        
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`HTTP ${response.status}: ${errorText}`);
        }
        
        const result = await response.json();
        console.log('Получен результат от RADAR:', result);
        
        return result;
    }

    displayResults(result, hasPdf = false) {
        console.log('Отображение результатов:', result);
        
        const heroSection = document.querySelector('.relative.overflow-hidden');
        if (heroSection) {
            heroSection.classList.add('hidden');
        }
        
        if (this.resultsSection) {
            this.resultsSection.classList.remove('hidden');
        }
        
        const queryDescription = document.getElementById('queryDescription');
        if (queryDescription) {
            const queryText = result.query || 'ваш запрос';
            queryDescription.textContent = `По запросу: "${queryText}"`;
        }

        this.renderResults(result, hasPdf);

        if (this.isInTelegram) {
            this.tg.MainButton.hide();
            this.tg.BackButton.show();
        }
        
        this.hapticFeedback('success');
    }

    renderResults(result, hasPdf = false) {
        console.log('Рендер результатов:', result);
        
        const resultsContent = document.getElementById('resultsContent');
        if (!resultsContent) {
            console.error('Элемент resultsContent не найден');
            return;
        }

        // Используем новую структуру от Сергея
        const { query, draft, documents, metadata, pdf_path } = result;
        
        const html = `
            <!-- Draft Response - Готовая статья -->
            <div class="bg-gradient-to-r from-indigo-50 to-purple-50 rounded-2xl p-6 mb-6">
                <h3 class="text-2xl font-bold text-gray-900 mb-4">${draft?.headline || 'Результат анализа'}</h3>
                <p class="text-lg text-gray-700 mb-4 font-medium">${draft?.dek || 'Анализ финансовых данных'}</p>
                
                ${draft?.key_points ? `
                <div class="bg-white rounded-xl p-4 mb-4">
                    <h4 class="font-bold text-gray-900 mb-3">Ключевые тезисы:</h4>
                    <ul class="space-y-2">
                        ${draft.key_points.map(point => `
                            <li class="flex items-start">
                                <span class="text-indigo-500 mr-2">•</span>
                                <span class="text-gray-700">${point}</span>
                            </li>
                        `).join('')}
                    </ul>
                </div>
                ` : ''}

                ${draft?.hashtags ? `
                <div class="flex flex-wrap gap-2 mb-4">
                    ${draft.hashtags.map(tag => `
                        <span class="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm">${tag}</span>
                    `).join('')}
                </div>
                ` : ''}

                ${hasPdf && pdf_path ? `
                <div class="bg-white rounded-xl p-4 mt-4">
                    <div class="flex items-center justify-between">
                        <div class="flex items-center space-x-3">
                            <div class="text-2xl">📄</div>
                            <div>
                                <div class="font-semibold text-gray-900">PDF отчет готов</div>
                                <div class="text-sm text-gray-600">Скачайте полный отчет в формате PDF</div>
                            </div>
                        </div>
                        <button 
                            onclick="window.queryInterface.downloadPdf('${pdf_path}')"
                            class="bg-gradient-to-r from-blue-500 to-indigo-600 hover:from-blue-600 hover:to-indigo-700 text-white font-medium px-6 py-3 rounded-xl transition-all duration-200 transform hover:scale-105 shadow-md hover:shadow-lg flex items-center space-x-2"
                        >
                            <img src="static/assets/images/ui-elements/pdf-download.svg" alt="Download" class="w-5 h-5" />
                            <span>Скачать PDF</span>
                        </button>
                    </div>
                </div>
                ` : ''}
            </div>

            <!-- Метаданные -->
            <div class="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-2xl p-6 mb-6">
                <div class="flex items-center justify-between mb-4">
                    <h3 class="text-xl font-bold text-gray-900"> Статистика обработки</h3>
                    <span class="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm font-medium">
                        ${(metadata?.total_time || 0).toFixed(2)}s
                    </span>
                </div>
                <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div class="text-center">
                        <div class="text-2xl font-bold text-blue-600">${metadata?.num_documents || 0}</div>
                        <div class="text-sm text-gray-600">Документов</div>
                    </div>
                    <div class="text-center">
                        <div class="text-sm font-medium text-green-600">${metadata?.vectorizer || 'N/A'}</div>
                        <div class="text-sm text-gray-600">Векторизатор</div>
                    </div>
                    <div class="text-center">
                        <div class="text-sm font-medium text-purple-600">${metadata?.reranker || 'N/A'}</div>
                        <div class="text-sm text-gray-600">Reranker</div>
                    </div>
                    <div class="text-center">
                        <div class="text-sm font-medium text-orange-600">${metadata?.llm_model || 'N/A'}</div>
                        <div class="text-sm text-gray-600">LLM</div>
                    </div>
                </div>
            </div>

            <!-- Найденные документы -->
            <div class="bg-white rounded-2xl shadow-lg p-6">
                <h3 class="text-2xl font-bold text-gray-900 mb-6">📄 Найденные документы</h3>
                <div class="space-y-4">
                    ${(documents || []).map((doc, index) => `
                        <div class="border border-gray-200 rounded-xl p-4 hover:shadow-md transition-shadow">
                            <div class="flex items-start justify-between mb-3">
                                <h4 class="text-lg font-semibold text-gray-900 flex-1">${doc.title}</h4>
                                <div class="flex items-center space-x-2 ml-4">
                                    <span class="bg-blue-100 text-blue-800 px-2 py-1 rounded-full text-xs font-medium">
                                        #${doc.final_position || index + 1}
                                    </span>
                                    <span class="bg-green-100 text-green-800 px-2 py-1 rounded-full text-xs font-medium">
                                        ${(doc.final_score || doc.rerank_score || 0).toFixed(3)}
                                    </span>
                                    ${doc.hotness ? `
                                        <span class="bg-red-100 text-red-800 px-2 py-1 rounded-full text-xs font-medium">
                                            🔥${(doc.hotness).toFixed(2)}
                                        </span>
                                    ` : ''}
                                </div>
                            </div>
                            
                            <p class="text-gray-700 mb-3 leading-relaxed">${doc.chunk_text || doc.text}</p>
                            
                            ${(doc.companies && doc.companies.length > 0) ? `
                                <div class="mb-2">
                                    <strong class="text-sm text-gray-600">Компании:</strong>
                                    ${doc.companies.map(company => `<span class="bg-gray-100 text-gray-800 px-2 py-1 rounded text-xs ml-1">${company}</span>`).join('')}
                                </div>
                            ` : ''}
                            
                            <div class="flex items-center justify-between text-sm text-gray-500 mt-3">
                                <div class="flex items-center space-x-4">
                                    <span><strong>${doc.source}</strong></span>
                                    <span>${new Date(doc.timestamp * 1000).toLocaleDateString('ru-RU')}</span>
                                    ${doc.text_type ? `<span class="text-xs bg-gray-100 px-2 py-1 rounded">${doc.text_type}</span>` : ''}
                                </div>
                                ${doc.url ? `<a href="${doc.url}" target="_blank" class="text-blue-600 hover:text-blue-800 underline">Открыть</a>` : ''}
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>

            ${draft?.disclaimer ? `
                <div class="mt-6 p-4 bg-gray-50 rounded-xl">
                    <p class="text-sm text-gray-600 italic">${draft.disclaimer}</p>
                </div>
            ` : ''}
        `;
        
        resultsContent.innerHTML = html;
    }

    showQueryInterface() {
        console.log('🔙 Возврат к интерфейсу запроса');
        
        const heroSection = document.querySelector('.relative.overflow-hidden');
        if (heroSection) {
            heroSection.classList.remove('hidden');
        }
        
        if (this.resultsSection) {
            this.resultsSection.classList.add('hidden');
        }

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
        if (e.ctrlKey && e.key === 'Enter') {
            if (this.submitBtn && !this.isProcessing) {
                this.submitBtn.click();
            }
        }
        
        if (e.key === 'Escape' && !this.resultsSection?.classList.contains('hidden')) {
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

    handleQuickAction(btn) {
        const query = btn.getAttribute('data-query');
        if (query && this.queryInput) {
            this.queryInput.value = query;
            this.updateCharCount();
            
            // Автоматически отправляем запрос
            if (this.submitBtn && !this.isProcessing) {
                this.submitBtn.click();
            }
            
            this.hapticFeedback('light');
        }
    }

    downloadPdf(pdfPath) {
        console.log('Скачивание PDF:', pdfPath);
        
        try {
            // Извлекаем имя файла из пути
            const filename = pdfPath.split('/').pop();
            const downloadUrl = `/api/download/pdf/${filename}`;
            
            if (this.isInTelegram) {
                // В Telegram Mini App открываем PDF в новом окне
                const fullUrl = `${window.location.origin}${downloadUrl}`;
                this.tg.openLink(fullUrl);
                this.hapticFeedback('success');
            } else {
                // В обычном браузере скачиваем файл
                const link = document.createElement('a');
                link.href = downloadUrl;
                link.download = `radar_report_${Date.now()}.pdf`;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            }
            
            console.log('PDF скачивание инициировано:', downloadUrl);
            
        } catch (error) {
            console.error('Ошибка при скачивании PDF:', error);
            this.showTelegramAlert('Ошибка при скачивании PDF файла');
        }
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    console.log('Инициализация RADAR Query Interface...');
    window.queryInterface = new QueryInterface();
});