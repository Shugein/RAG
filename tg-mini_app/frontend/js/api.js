/**
 * RADAR Finance Mini App - API Client
 * Клиент для работы с API сервером
 */


class APIClient {
    constructor(baseUrl = '/api') {
        this.baseUrl = baseUrl;
        this.cache = new Map();
        this.cacheTimeout = 5 * 60 * 1000; // 5 минут
    }


    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        
        try {
            console.log(` API запрос: ${url}`);
            
            const response = await fetch(url, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            console.log(`API ответ:`, data);
            
            return data;
            
        } catch (error) {
            console.error(`API ошибка для ${url}:`, error);
            throw error;
        }
    }


    async get(endpoint, useCache = true) {
        const cacheKey = `GET:${endpoint}`;
        
        if (useCache && this.cache.has(cacheKey)) {
            const cached = this.cache.get(cacheKey);
            const now = Date.now();
            
            if (now - cached.timestamp < this.cacheTimeout) {
                console.log(`Данные из кеша: ${endpoint}`);
                return cached.data;
            } else {
                this.cache.delete(cacheKey);
            }
        }
        
        const data = await this.request(endpoint);
        
        if (useCache) {
            this.cache.set(cacheKey, {
                data,
                timestamp: Date.now()
            });
        }
        
        return data;
    }

    async post(endpoint, body = {}) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(body)
        });
    }


    clearCache() {
        this.cache.clear();
        console.log('Кеш API очищен');
    }
}

const apiClient = new APIClient();


async function fetchDashboardData() {
    try {
        const data = await apiClient.get('/dashboard');
        return data;
    } catch (error) {
        console.error('Ошибка загрузки дашборда:', error);
        return getDashboardMockData();
    }
}


async function fetchHotNews(limit = 20) {
    try {
        const data = await apiClient.get(`/hot-news?limit=${limit}`);
        return data;
    } catch (error) {
        console.error('Ошибка загрузки горячих новостей:', error);
        return getHotNewsMockData();
    }
}

async function searchNews(query, filters = {}) {
    try {
        const params = new URLSearchParams({
            q: query,
            ...filters
        });
        
        const data = await apiClient.get(`/search?${params.toString()}`);
        return data;
    } catch (error) {
        console.error('Ошибка поиска:', error);
        return getSearchMockData(query);
    }
}


async function fetchStatistics() {
    try {
        const data = await apiClient.get('/statistics');
        return data;
    } catch (error) {
        console.error('Ошибка загрузки статистики:', error);
        return getStatisticsMockData();
    }
}

async function fetchEDisclosureData(type = 'news', limit = 20) {
    try {
        const data = await apiClient.get(`/e-disclosure/${type}?limit=${limit}`);
        return data;
    } catch (error) {
        console.error('❌ Ошибка загрузки E-disclosure:', error);
        return getEDisclosureMockData(type);
    }
}

function getDashboardMockData() {
    return {
        totalNews: 1507,
        hotNewsToday: 12,
        totalSources: 6,
        lastUpdate: new Date().toLocaleString('ru-RU'),
        topNews: [
            {
                id: '1',
                title: 'Сбербанк объявил о рекордной прибыли',
                source: 'RBC',
                hotness_score: 0.95,
                published_dt: '03.10.2025'
            },
            {
                id: '2',
                title: 'Газпром расширяет поставки в Азию',
                source: 'Ведомости',
                hotness_score: 0.87,
                published_dt: '03.10.2025'
            },
            {
                id: '3',
                title: 'ЦБ РФ изменил ключевую ставку',
                source: 'Коммерсант',
                hotness_score: 0.83,
                published_dt: '03.10.2025'
            }
        ]
    };
}

function getHotNewsMockData() {
    return {
        news: [
            {
                id: '1',
                title: 'Сбербанк объявил о рекордной прибыли за квартал',
                content: 'Крупнейший банк России сообщил о превышении ожидаемых показателей прибыли на 15%. Руководство банка отмечает стабильный рост во всех сегментах бизнеса...',
                source: 'RBC',
                published_dt: '03.10.2025 15:30',
                hotness_score: 0.95
            },
            {
                id: '2',
                title: 'Газпром расширяет поставки энергоносителей в страны Азии',
                content: 'Энергетический гигант подписал долгосрочные контракты на поставку газа с тремя крупными азиатскими компаниями...',
                source: 'Ведомости',
                published_dt: '03.10.2025 14:15',
                hotness_score: 0.87
            },
            {
                id: '3',
                title: 'ЦБ РФ изменил ключевую ставку до 21%',
                content: 'Центральный банк России принял решение о повышении ключевой ставки на 200 базисных пунктов...',
                source: 'Коммерсант',
                published_dt: '03.10.2025 12:00',
                hotness_score: 0.83
            }
        ]
    };
}

function getSearchMockData(query) {
    return {
        query,
        results: [
            {
                id: '1',
                title: `Результат поиска по "${query}"`,
                content: 'Найденный контент, содержащий поисковый запрос...',
                source: 'RBC',
                published_dt: '02.10.2025',
                relevance: 0.9
            }
        ],
        total: 1
    };
}

function getStatisticsMockData() {
    return {
        sources: {
            'RBC': 118,
            'Ведомости': 281,
            'Коммерсант': 69,
            'MOEX': 45,
            'Интерфакс': 94,
            'E-disclosure': 150
        },
        dates: {
            'today': 12,
            'week': 89,
            'month': 456
        },
        companies: {
            'Сбербанк': 23,
            'Газпром': 18,
            'Лукойл': 15
        }
    };
}

function getEDisclosureMockData(type) {
    if (type === 'news') {
        return {
            news: [
                {
                    id: '1',
                    title: 'Корпоративные новости',
                    company: 'ПАО Сбербанк',
                    date: '03.10.2025',
                    content: 'Содержание корпоративной новости...'
                }
            ]
        };
    } else {
        return {
            messages: [
                {
                    id: '1',
                    company: 'ПАО Сбербанк',
                    event_type: 'Выплата дивидендов',
                    date: '03.10.2025 15:30',
                    content: 'Полное содержание корпоративного события...'
                }
            ]
        };
    }
}


async function checkAPIHealth() {
    try {
        const response = await apiClient.get('/health');
        console.log('API сервер работает:', response);
        return true;
    } catch (error) {
        console.warn('API сервер недоступен, используем тестовые данные');
        return false;
    }
}

window.RadarApp = window.RadarApp || {};
window.RadarApp.api = {
    fetchDashboardData,
    fetchHotNews,
    searchNews,
    fetchStatistics,
    fetchEDisclosureData,
    checkAPIHealth,
    clearCache: () => apiClient.clearCache()
};

console.log('api.js загружен');