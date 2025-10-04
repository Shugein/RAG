
class CleanRadarApp {
    constructor() {
        this.initializeElements();
        this.bindEvents();
        console.log('✅ Clean RADAR App инициализирован');
    }

    initializeElements() {
        this.queryForm = document.getElementById('queryForm');
        this.queryInput = document.getElementById('queryInput');
        this.submitBtn = document.getElementById('submitBtn');
        this.charCount = document.getElementById('charCount');
        this.loadingOverlay = document.getElementById('loadingOverlay');
        this.resultsSection = document.getElementById('resultsSection');
        this.queryInterface = document.getElementById('queryInterface');
        this.backBtn = document.getElementById('backBtn');
        this.queryDescription = document.getElementById('queryDescription');
        this.resultsContent = document.getElementById('resultsContent');
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

        // Кнопка "Назад"
        if (this.backBtn) {
            this.backBtn.addEventListener('click', () => this.showQueryInterface());
        }
    }

    updateCharCount() {
        if (this.queryInput && this.charCount) {
            const length = this.queryInput.value.length;
            this.charCount.textContent = `${length}/500`;
        }
    }

    async handleSubmit(e) {
        e.preventDefault();
        
        const query = this.queryInput?.value?.trim();
        if (!query) {
            alert('Пожалуйста, введите ваш запрос');
            return;
        }

        this.showLoading();

        try {
            console.log('📤 Отправка запроса:', query);

            const response = await fetch('/api/process_query', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify({
                    query: query
                })
            });
            
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`HTTP ${response.status}: ${errorText}`);
            }
            
            const result = await response.json();
            console.log('📥 Получен ответ:', result);
            
            this.displayResults(result);

        } catch (error) {
            console.error('❌ Ошибка:', error);
            alert(`Ошибка: ${error.message}`);
        } finally {
            this.hideLoading();
        }
    }

    displayResults(result) {
        console.log('🎨 Отображение результатов');
        
        // Переключаемся на страницу результатов
        if (this.queryInterface) {
            this.queryInterface.classList.add('hidden');
        }
        
        if (this.resultsSection) {
            this.resultsSection.classList.remove('hidden');
        }
        
        // Обновляем описание
        if (this.queryDescription) {
            this.queryDescription.textContent = `По запросу: "${result.query}"`;
        }

        // Рендерим результаты
        this.renderResults(result);
    }

    renderResults(result) {
        if (!this.resultsContent) return;

        const { query, answer, documents, metadata } = result;
        
        const html = `
            <!-- Ответ RADAR -->
            <div class="bg-gradient-to-r from-green-50 to-emerald-50 rounded-2xl p-6 mb-6">
                <h3 class="text-xl font-bold text-gray-900 mb-4">Ответ RADAR</h3>
                <div class="bg-white rounded-xl p-4 border border-green-200">
                    <p class="text-gray-800 leading-relaxed">${answer}</p>
                </div>
            </div>

            <!-- Метаданные -->
            <div class="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-2xl p-6 mb-6">
                <div class="flex items-center justify-between mb-4">
                    <h3 class="text-xl font-bold text-gray-900">Статистика обработки</h3>
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
                        <div class="text-sm font-medium text-green-600">${metadata.vectorizer ? metadata.vectorizer.split('/')[1] || metadata.vectorizer : 'N/A'}</div>
                        <div class="text-sm text-gray-600">Векторизатор</div>
                    </div>
                    <div class="text-center">
                        <div class="text-sm font-medium text-purple-600">${metadata.reranker ? metadata.reranker.split('/')[1] || metadata.reranker : 'N/A'}</div>
                        <div class="text-sm text-gray-600">Reranker</div>
                    </div>
                    <div class="text-center">
                        <div class="text-sm font-medium text-orange-600">${metadata.llm_model ? metadata.llm_model.split('/')[1] || metadata.llm_model : 'N/A'}</div>
                        <div class="text-sm text-gray-600">LLM</div>
                    </div>
                </div>
            </div>

            <!-- Найденные документы -->
            <div class="bg-white rounded-2xl shadow-lg p-6">
                <h3 class="text-2xl font-bold text-gray-900 mb-6">Найденные документы</h3>
                <div class="space-y-4">
                    ${documents.map((doc, index) => `
                        <div class="border border-gray-200 rounded-xl p-4 hover:shadow-md transition-shadow">
                            <div class="flex items-start justify-between mb-3">
                                <h4 class="text-lg font-semibold text-gray-900 flex-1">${doc.title}</h4>
                                <div class="flex items-center space-x-2 ml-4">
                                    <span class="bg-blue-100 text-blue-800 px-2 py-1 rounded-full text-xs font-medium">
                                        #${doc.original_position || index + 1}
                                    </span>
                                    <span class="bg-green-100 text-green-800 px-2 py-1 rounded-full text-xs font-medium">
                                        ${(doc.rerank_score || 0).toFixed(3)}
                                    </span>
                                </div>
                            </div>
                            
                            <p class="text-gray-700 mb-3 leading-relaxed">${doc.text || doc.chunk_text}</p>
                            
                            <div class="flex items-center justify-between text-sm text-gray-500">
                                <div class="flex items-center space-x-4">
                                    <span><strong>${doc.source}</strong></span>
                                    <span>${new Date(doc.timestamp * 1000).toLocaleDateString('ru-RU')}</span>
                                </div>
                                ${doc.url ? `<a href="${doc.url}" target="_blank" class="text-blue-600 hover:text-blue-800 underline">Открыть</a>` : ''}
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>

            <!-- Действия -->
            <div class="mt-8 flex flex-col gap-4 text-center">
                <p class="text-gray-600 italic">
                    Это тестовая заглушка. В реальной версии здесь будут данные от вашей RADAR системы.
                </p>
            </div>
        `;
        
        this.resultsContent.innerHTML = html;
    }

    showQueryInterface() {
        console.log('🔙 Возврат к форме запроса');
        
        if (this.queryInterface) {
            this.queryInterface.classList.remove('hidden');
        }
        
        if (this.resultsSection) {
            this.resultsSection.classList.add('hidden');
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
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 Инициализация чистого RADAR App...');
    window.cleanRadarApp = new CleanRadarApp();
});