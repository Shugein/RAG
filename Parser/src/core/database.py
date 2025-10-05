#Parser.src/core/database.py
"""
Модуль управления подключениями к базе данных.
Использует SQLAlchemy 2.0 с async/await поддержкой.
"""

import logging
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    async_sessionmaker,
    create_async_engine
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool, QueuePool
from sqlalchemy import event, pool, text

from Parser.src.core.config import settings

logger = logging.getLogger(__name__)

# ============================================================================
# БАЗОВЫЕ ОБЪЕКТЫ SQLALCHEMY
# ============================================================================

# Base - это базовый класс для всех моделей (таблиц)
# Все модели в models.py наследуются от этого класса
Base = declarative_base()

# Глобальные переменные для engine и session factory
# Они инициализируются один раз при старте приложения
engine: Optional[AsyncEngine] = None
async_session_factory: Optional[async_sessionmaker] = None


# ============================================================================
# СОЗДАНИЕ И НАСТРОЙКА ENGINE
# ============================================================================

async def create_engine_with_settings() -> AsyncEngine:
    """
    Создает и настраивает асинхронный engine для PostgreSQL.
    
    Engine - это основной интерфейс SQLAlchemy к базе данных.
    Он управляет пулом подключений и выполняет SQL-запросы.
    
    Returns:
        AsyncEngine: Настроенный engine для работы с БД
    """
    
    # Определяем класс пула в зависимости от режима работы
    if settings.TESTING:
        # В тестах используем NullPool - без пулинга
        # Каждый запрос создает новое подключение
        poolclass = NullPool
    else:
        # В продакшене используем QueuePool - эффективный пул подключений
        poolclass = QueuePool
    
    # Создаем асинхронный engine
    engine = create_async_engine(
        # URL подключения из настроек
        # Формат: postgresql+asyncpg://user:pass@host:port/dbname
        settings.DATABASE_URL,
        
        # Эхо SQL-запросов в логи (только в DEBUG режиме)
        echo=settings.DEBUG,
        
        # Настройки пула подключений
        poolclass=poolclass,
        
        # Размер пула - количество постоянных подключений
        # Эти подключения держатся открытыми и переиспользуются
        pool_size=settings.DB_POOL_SIZE,  # default: 20
        
        # Максимальный overflow - дополнительные подключения при нагрузке
        # Создаются при необходимости и закрываются после использования
        max_overflow=settings.DB_MAX_OVERFLOW,  # default: 40
        
        # Таймаут получения подключения из пула (в секундах)
        # Если все подключения заняты, ждем указанное время
        pool_timeout=settings.DB_POOL_TIMEOUT,  # default: 30
        
        # Проверка подключения перед использованием
        # Отправляет SELECT 1 перед каждым использованием подключения
        pool_pre_ping=True,
        
        # Время жизни подключения в секундах (2 часа)
        # После этого времени подключение пересоздается
        pool_recycle=7200,
        
        # Дополнительные параметры для asyncpg драйвера
        connect_args={
            # Таймаут на установку подключения
            "server_settings": {
                "application_name": "news_aggregator",
                "client_encoding": "UTF8"
            },
            "command_timeout": 60,
            
            # Подготовленные statements для ускорения запросов
            "prepared_statement_cache_size": 0,  # Отключаем для избежания проблем
            
            # SSL настройки (если нужно)
            # "ssl": "require",
        }
    )
    
    return engine


# ============================================================================
# ИНИЦИАЛИЗАЦИЯ И ЗАКРЫТИЕ
# ============================================================================

async def init_db():
    """
    Инициализирует подключение к БД и создает session factory.
    
    Вызывается один раз при старте приложения.
    Создает глобальные объекты engine и session_factory.
    """
    global engine, async_session_factory
    
    try:
        # Создаем engine если его еще нет
        if engine is None:
            logger.info("Initializing database engine...")
            engine = await create_engine_with_settings()
            
            # Проверяем подключение
            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            
            logger.info(f"Database connected: {settings.DATABASE_URL.split('@')[1]}")
        
        # Создаем фабрику сессий
        if async_session_factory is None:
            async_session_factory = async_sessionmaker(
                bind=engine,
                class_=AsyncSession,
                
                # expire_on_commit=False означает, что объекты остаются доступными
                # после коммита транзакции (не требуют перезагрузки)
                expire_on_commit=False,
                
                # autoflush=False - не сбрасывать изменения автоматически
                # Мы сами контролируем когда делать flush
                autoflush=False,
                
                # autocommit=False - используем явные транзакции
                autocommit=False
            )
            logger.info("Session factory created")
            
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


async def close_db():
    """
    Закрывает все подключения к БД.
    
    Вызывается при остановке приложения.
    Gracefully закрывает все активные подключения.
    """
    global engine, async_session_factory
    
    if engine:
        logger.info("Closing database connections...")
        await engine.dispose()
        engine = None
        async_session_factory = None
        logger.info("Database connections closed")


# ============================================================================
# ПОЛУЧЕНИЕ СЕССИЙ
# ============================================================================

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency для FastAPI endpoints.
    
    Создает новую сессию для каждого запроса.
    Автоматически закрывает сессию после использования.
    
    Использование в FastAPI:
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Item))
            return result.scalars().all()
    
    Yields:
        AsyncSession: Сессия для работы с БД
    """
    if async_session_factory is None:
        await init_db()
    
    # Создаем новую сессию
    async with async_session_factory() as session:
        try:
            # Отдаем сессию для использования
            yield session
            # После выполнения endpoint'а коммитим изменения
            await session.commit()
        except Exception as e:
            # При ошибке откатываем транзакцию
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            # Закрываем сессию
            await session.close()


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager для получения сессии вне FastAPI.
    
    Используется в скриптах, background задачах и т.д.
    
    Использование:
        async with get_db_session() as session:
            user = await session.get(User, user_id)
            user.name = "New Name"
            await session.commit()
    
    Yields:
        AsyncSession: Сессия для работы с БД
    """
    if async_session_factory is None:
        await init_db()
    
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ============================================================================
# СПЕЦИАЛЬНЫЕ ФУНКЦИИ
# ============================================================================

async def create_tables():
    """
    Создает все таблицы в БД на основе моделей.
    
    Используется для initial setup или в тестах.
    В продакшене лучше использовать Alembic миграции.
    """
    if engine is None:
        await init_db()
    
    async with engine.begin() as conn:
        # Импортируем все модели, чтобы они зарегистрировались
        from Parser.src.core.models import (
            Source, News, Image, Entity, LinkedCompany,
            Topic, SectorConstituent, CompanyAlias, 
            OutboxEvent, ParserState
        )
        
        # Создаем все таблицы
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created")


async def drop_tables():
    """
    Удаляет все таблицы из БД.
    
    ВНИМАНИЕ: Удаляет все данные!
    Используется только в тестах или для полного сброса.
    """
    if engine is None:
        await init_db()
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        logger.info("Database tables dropped")


async def check_connection() -> bool:
    """
    Проверяет доступность БД.
    
    Returns:
        bool: True если БД доступна, False если нет
    """
    try:
        if engine is None:
            await init_db()
        
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False


# ============================================================================
# ТРАНЗАКЦИИ И БАТЧЕВАЯ ОБРАБОТКА
# ============================================================================

@asynccontextmanager
async def transaction():
    """
    Context manager для явного управления транзакциями.
    
    Все операции внутри блока выполняются в одной транзакции.
    При ошибке вся транзакция откатывается.
    
    Использование:
        async with transaction() as session:
            user = User(name="John")
            session.add(user)
            
            order = Order(user_id=user.id, amount=100)
            session.add(order)
            # Коммит произойдет автоматически при выходе из блока
    """
    async with get_db_session() as session:
        async with session.begin():
            yield session
            # При выходе из блока автоматически будет commit или rollback


async def bulk_insert(model_class, records: list):
    """
    Массовая вставка записей для оптимизации.
    
    Args:
        model_class: Класс модели (например, News)
        records: Список словарей с данными
    
    Использование:
        await bulk_insert(News, [
            {"title": "News 1", "text": "..."},
            {"title": "News 2", "text": "..."},
        ])
    """
    async with get_db_session() as session:
        # Используем bulk_insert_mappings для эффективной вставки
        await session.run_sync(
            lambda sync_session: sync_session.bulk_insert_mappings(
                model_class, records
            )
        )
        await session.commit()


# ============================================================================
# МОНИТОРИНГ И МЕТРИКИ
# ============================================================================

def setup_pool_monitoring():
    """
    Настраивает мониторинг пула подключений.
    
    Логирует события пула для отладки проблем с подключениями.
    """
    if not engine:
        return
    
    @event.listens_for(engine.sync_engine.pool, "connect")
    def receive_connect(dbapi_conn, connection_record):
        """Вызывается при создании нового подключения"""
        logger.debug(f"Pool: New connection created. Total: {engine.pool.size()}")
    
    @event.listens_for(engine.sync_engine.pool, "checkout")
    def receive_checkout(dbapi_conn, connection_record, connection_proxy):
        """Вызывается при получении подключения из пула"""
        logger.debug(f"Pool: Connection checked out. In use: {engine.pool.checked_out()}")
    
    @event.listens_for(engine.sync_engine.pool, "checkin")
    def receive_checkin(dbapi_conn, connection_record):
        """Вызывается при возврате подключения в пул"""
        logger.debug(f"Pool: Connection returned. Available: {engine.pool.size() - engine.pool.checked_out()}")


async def get_pool_stats() -> dict:
    """
    Получает статистику пула подключений.
    
    Returns:
        dict: Статистика пула
    """
    if not engine:
        return {}
    
    pool = engine.pool
    return {
        "size": pool.size(),
        "checked_out": pool.checked_out(),
        "overflow": pool.overflow(),
        "available": pool.size() - pool.checked_out(),
        "total": pool.size() + pool.overflow()
    }