
window.RadarApp = {
    config: {
        apiBaseUrl: '/api',
        debug: true,
        version: '1.0.0'
    },
    
    state: {
        currentPage: 'dashboard',
        user: null,
        data: {
            dashboard: null,
            hotNews: null,
            searchResults: null
        },
        loading: false
    },
    
    cache: new Map(),
    
    eventHandlers: new Map()
};


async function initApp() {
    try {
        console.log('Инициализация RADAR Finance Mini App');
        
        if (window.Telegram && window.Telegram.WebApp) {
            initTelegram();
        } else {
            console.warn(' Telegram WebApp недоступен - режим разработки');
            initDevelopmentMode();
        }
        
        initNavigation();
        
        initEventHandlers();
        
        await loadInitialData();
        
        await showPage('dashboard');
        
        console.log('Приложение инициализировано успешно');
        
    } catch (error) {
        console.error('Ошибка инициализации приложения:', error);
        showError('Ошибка инициализации приложения');
    }
}


function initTelegram() {
    const tg = window.Telegram.WebApp;
    
    tg.ready();
    tg.expand();
    
    setupTheme();
    
    if (tg.initDataUnsafe && tg.initDataUnsafe.user) {
        window.RadarApp.state.user = tg.initDataUnsafe.user;
        updateUserInfo(tg.initDataUnsafe.user);
    }
    
    tg.MainButton.setText('Горячие новости');
    tg.MainButton.color = '#2AABEE';
    tg.MainButton.textColor = '#FFFFFF';
    tg.MainButton.show();
    
    tg.onEvent('mainButtonClicked', () => {
        showPage('hot-news');
    });
    
    window.RadarApp.telegram = tg;
    
    console.log('Telegram WebApp инициализирован');
}


function initDevelopmentMode() {
    window.RadarApp.state.user = {
        id: 123456789,
        first_name: 'Тестовый',
        last_name: 'Пользователь',
        language_code: 'ru'
    };
    
    updateUserInfo(window.RadarApp.state.user);
    
    console.log('Режим разработки активирован');
}


function setupTheme() {
    const tg = window.Telegram?.WebApp;
    
    if (tg) {
        if (tg.colorScheme === 'dark') {
            document.body.classList.add('dark-theme');
        } else {
            document.body.classList.add('light-theme');
        }
        
        tg.setHeaderColor('#17212B');
        tg.setBackgroundColor('#17212B');
    }
}


function updateUserInfo(user) {
    const userInfoElement = document.getElementById('userInfo');
    
    if (userInfoElement && user) {
        const avatar = user.first_name ? user.first_name[0].toUpperCase() : '👤';
        const fullName = `${user.first_name || ''} ${user.last_name || ''}`.trim() || 'Пользователь';
        
        userInfoElement.innerHTML = `
            <div class="user-card">
                <div class="user-avatar">${avatar}</div>
                <div class="user-details">
                    <h3>${fullName}</h3>
                    <p>ID: ${user.id} | Язык: ${user.language_code || 'ru'}</p>
                </div>
            </div>
        `;
    }
}


function initNavigation() {
    const navButtons = document.querySelectorAll('.nav-btn');
    
    navButtons.forEach(button => {
        button.addEventListener('click', (e) => {
            const page = e.target.dataset.page;
            if (page) {
                showPage(page);
                
                navButtons.forEach(btn => btn.classList.remove('active'));
                e.target.classList.add('active');
                
                hapticFeedback('light');
            }
        });
    });
}


function initEventHandlers() {
    const refreshBtn = document.getElementById('refreshBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', refreshData);
    }
    
    const helpBtn = document.getElementById('helpBtn');
    if (helpBtn) {
        helpBtn.addEventListener('click', showHelp);
    }
    
    window.addEventListener('error', (e) => {
        console.error('JavaScript ошибка:', e.error);
        showError('Произошла ошибка приложения');
    });
    
    window.addEventListener('unhandledrejection', (e) => {
        console.error('Неперехваченная ошибка промиса:', e.reason);
        showError('Ошибка загрузки данных');
    });
}

async function loadInitialData() {
    try {
        showLoading(true);
        
        const dashboardData = await fetchDashboardData();
        window.RadarApp.state.data.dashboard = dashboardData;
        
        console.log(' Начальные данные загружены');
        
    } catch (error) {
        console.error(' Ошибка загрузки начальных данных:', error);
        showError('Ошибка загрузки данных');
    } finally {
        showLoading(false);
    }
}

async function showPage(pageName) {
    try {
        console.log(` Переход на страницу: ${pageName}`);
        
        showLoading(true);
        window.RadarApp.state.currentPage = pageName;
        
        const mainContent = document.getElementById('mainContent');
        if (!mainContent) return;
        
        let content = '';
        
        switch (pageName) {
            case 'dashboard':
                content = await generateDashboardContent();
                break;
            case 'hot-news':
                content = await generateHotNewsContent();
                break;
            case 'search':
                content = await generateSearchContent();
                break;
            case 'settings':
                content = await generateSettingsContent();
                break;
            default:
                content = '<div class="alert alert-warning">Страница не найдена</div>';
        }
        
        mainContent.style.opacity = '0';
        setTimeout(() => {
            mainContent.innerHTML = content;
            mainContent.style.opacity = '1';
            
            initPageHandlers(pageName);
        }, 150);
        
    } catch (error) {
        console.error(` Ошибка показа страницы ${pageName}:`, error);
        showError('Ошибка загрузки страницы');
    } finally {
        showLoading(false);
    }
}

function initPageHandlers(pageName) {
    document.querySelectorAll('[data-action]').forEach(element => {
        element.addEventListener('click', handleAction);
    });
    
    switch (pageName) {
        case 'search':
            initSearchHandlers();
            break;
        case 'hot-news':
            initHotNewsHandlers();
            break;
    }
}

function handleAction(e) {
    const action = e.target.dataset.action;
    const data = e.target.dataset;
    
    console.log(` Действие: ${action}`, data);
    
    switch (action) {
        case 'refresh':
            refreshData();
            break;
        case 'load-more':
            loadMoreData(data.type);
            break;
        case 'show-details':
            showDetails(data.id, data.type);
            break;
    }
    
    hapticFeedback('light');
}

async function refreshData() {
    try {
        hapticFeedback('medium');
        showLoading(true);
        
        window.RadarApp.cache.clear();
        
        await showPage(window.RadarApp.state.currentPage);
        
        showNotification('Данные обновлены!', 'success');
        
    } catch (error) {
        console.error(' Ошибка обновления данных:', error);
        showError('Ошибка обновления данных');
    } finally {
        showLoading(false);
    }
}

function showHelp() {
    const helpContent = `
        <div class="modal-content">
            <div class="modal-header">
                <h3 class="modal-title">Справка</h3>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body">
                <h4>О приложении</h4>
                <p>RADAR Finance - система анализа финансовых новостей и корпоративных событий.</p>
                
                <h4>Горячие новости</h4>
                <p>Самые важные события дня на основе алгоритма RADAR.</p>
                
                <h4> Поиск</h4>
                <p>Поиск новостей по компаниям, событиям и ключевым словам.</p>
                
                <h4>Статистика</h4>
                <p>Аналитика по источникам и категориям новостей.</p>
            </div>
        </div>
    `;
    
    showModal(helpContent);
}

function hapticFeedback(type = 'light') {
    const tg = window.RadarApp.telegram;
    if (tg && tg.HapticFeedback) {
        tg.HapticFeedback.impactOccurred(type);
    }
}

function showNotification(message, type = 'info') {
    const tg = window.RadarApp.telegram;
    if (tg) {
        tg.showAlert(message);
    } else {
        alert(message);
    }
}


function showError(message) {
    console.error(' Ошибка:', message);
    showNotification(message, 'error');
}

function showLoading(show) {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) {
        if (show) {
            overlay.classList.remove('hidden');
        } else {
            overlay.classList.add('hidden');
        }
    }
    
    window.RadarApp.state.loading = show;
}


function showModal(content) {
    console.log('Модальное окно:', content);
}

function closeModal() {
    console.log('Закрытие модального окна');
}

document.addEventListener('DOMContentLoaded', () => {
    console.log('RADAR Finance Mini App - Запуск');
    initApp();
});

window.RadarApp.showPage = showPage;
window.RadarApp.refreshData = refreshData;
window.RadarApp.showHelp = showHelp;
window.RadarApp.hapticFeedback = hapticFeedback;

console.log('main.js загружен');