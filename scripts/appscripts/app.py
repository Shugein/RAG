"""
Streamlit интерфейс для RAG системы
"""
import streamlit as st
import pandas as pd
import time
from Parser.src.system.engine import RAGPipeline

# Настройка страницы
st.set_page_config(
    page_title="RAG System Demo",
    page_icon="🔍",
    layout="wide"
)

# Инициализация сессии
if 'rag' not in st.session_state:
    st.session_state.rag = RAGPipeline()
    with st.spinner('Подключение к Weaviate...'):
        st.session_state.rag.connect()
    st.success('Подключено к Weaviate!')

if 'history' not in st.session_state:
    st.session_state.history = []

# Заголовок
st.title("🔍 RAG System - Поиск и генерация ответов")
st.markdown("---")

# Sidebar с настройками
with st.sidebar:
    st.header("⚙️ Настройки")

    search_limit = st.slider(
        "Количество результатов поиска",
        min_value=5,
        max_value=20,
        value=10,
        help="Сколько документов искать в первом проходе"
    )

    rerank_limit = st.slider(
        "Результатов после реренкинга",
        min_value=1,
        max_value=10,
        value=3,
        help="Топ-N документов после реренкинга для генерации ответа"
    )

    reasoning_level = st.selectbox(
        "Уровень рассуждений LLM",
        options=["low", "medium", "high"],
        index=0,
        help="Уровень детализации ответа"
    )

    use_parent_docs = st.checkbox(
        "Использовать полные документы",
        value=True,
        help="Если включено, retriever вернет полный родительский документ вместо чанка. Дубликаты автоматически удаляются."
    )

    st.markdown("---")
    st.markdown("### 📊 Модели")
    st.markdown("""
    - **Векторизация**: sergeyzh/BERTA
    - **Реренкинг**: BAAI/bge-reranker-v2-m3
    - **LLM**: openai/gpt-oss-20b:free
    """)

    if st.button("🗑️ Очистить историю"):
        st.session_state.history = []
        st.rerun()

# Основная область
col1, col2 = st.columns([2, 1])

with col1:
    st.header("💬 Задайте вопрос")

    # Примеры вопросов
    example_queries = [
        "Стоимость акций Газпрома",
        "Новости о спорте",
        "Экономические события"
    ]

    st.markdown("**Примеры вопросов:**")
    example_cols = st.columns(len(example_queries))
    for i, example in enumerate(example_queries):
        if example_cols[i].button(f"📝 {example}", key=f"example_{i}"):
            st.session_state.current_query = example

    # Поле ввода
    user_query = st.text_area(
        "Ваш вопрос:",
        value=st.session_state.get('current_query', ''),
        height=100,
        placeholder="Введите вопрос..."
    )

    # Кнопка поиска
    if st.button("🔍 Найти ответ", type="primary", use_container_width=True):
        if user_query.strip():
            with st.spinner('Обработка запроса...'):
                # Выполнение RAG пайплайна
                result = st.session_state.rag.query(
                    user_query=user_query,
                    search_limit=search_limit,
                    rerank_limit=rerank_limit,
                    reasoning_level=reasoning_level,
                    use_parent_docs=use_parent_docs
                )

                # Сохранение в историю
                st.session_state.history.insert(0, {
                    'timestamp': time.strftime('%H:%M:%S'),
                    'query': user_query,
                    'result': result
                })

                # Очистка поля ввода
                st.session_state.current_query = ''
                st.rerun()
        else:
            st.warning("Пожалуйста, введите вопрос")

with col2:
    st.header("📈 Статистика")
    if st.session_state.history:
        last_result = st.session_state.history[0]['result']
        metadata = last_result['metadata']

        st.metric("⏱️ Время обработки", f"{metadata['total_time']:.2f}s")
        st.metric("📄 Документов найдено", metadata['num_documents'])
    else:
        st.info("Статистика появится после первого запроса")

# Отображение результатов
st.markdown("---")

if st.session_state.history:
    latest = st.session_state.history[0]
    result = latest['result']

    st.header("✅ Ответ")
    st.markdown(f"**Вопрос:** {result['query']}")

    # Ответ модели
    with st.container():
        st.markdown("### 🤖 Ответ модели:")
        st.info(result['answer'])

    # Документы
    st.markdown("---")
    st.header("📚 Использованные документы")

    # Таблица с результатами поиска
    st.markdown("### 🔍 Этап 1: Гибридный поиск (до реренкинга)")
    if 'documents' in result and result['documents']:
        # Показываем информацию о том, что было до реренкинга
        st.caption("Первичные результаты гибридного поиска (BM25 + векторный)")

    st.markdown("### 🎯 Этап 2: После реренкинга")

    for i, doc in enumerate(result['documents'], 1):
        # Определяем тип документа
        doc_type_icon = "🔹" if doc.get('text_type') == 'parent_document' else "📄"
        doc_type_label = "Полный документ" if doc.get('text_type') == 'parent_document' else "Чанк"

        with st.expander(f"{doc_type_icon} Документ #{i}: {doc['title']}", expanded=(i == 1)):
            # Индикатор типа документа
            if doc.get('text_type') == 'parent_document':
                st.info(f"📖 {doc_type_label} (получен из чанка #{doc.get('chunk_index', '?')})")
            else:
                st.info(f"📄 {doc_type_label} #{doc.get('chunk_index', '?')}")

            col_a, col_b, col_c = st.columns([2, 1, 1])

            with col_a:
                st.markdown(f"**Источник:** {doc['source']}")
                st.markdown(f"**URL:** {doc.get('url', 'N/A')}")
                if doc.get('text_type') == 'parent_document':
                    st.markdown(f"**Размер документа:** {len(doc['text']):,} символов")

            with col_b:
                st.metric(
                    "Hybrid Score",
                    f"{doc.get('hybrid_score', 0):.4f}",
                    help="Оценка гибридного поиска"
                )

            with col_c:
                st.metric(
                    "Rerank Score",
                    f"{doc['rerank_score']:.4f}",
                    delta=f"{doc['rerank_score'] - doc.get('hybrid_score', 0):.4f}",
                    help="Оценка после реренкинга"
                )

            # Позиция в ранжировании
            if 'original_position' in doc and 'new_position' in doc:
                position_change = doc['original_position'] - doc['new_position']
                if position_change > 0:
                    st.success(f"🔺 Поднялся с #{doc['original_position']} на #{doc['new_position']} (+{position_change} мест)")
                elif position_change < 0:
                    st.error(f"🔻 Опустился с #{doc['original_position']} на #{doc['new_position']} ({position_change} мест)")
                else:
                    st.info(f"➡️ Позиция #{doc['new_position']} (без изменений)")

            # Показываем чанк, который привел к этому документу
            if doc.get('text_type') == 'parent_document' and 'chunk_text' in doc:
                st.markdown("**🎯 Релевантный фрагмент (chunk):**")
                st.markdown(f"```\n{doc['chunk_text'][:300]}...\n```")

                with st.expander("📄 Показать весь документ"):
                    st.text_area(
                        "Полный текст документа",
                        value=doc['text'],
                        height=400,
                        disabled=True,
                        key=f"full_doc_{i}"
                    )
            else:
                # Текст чанка
                st.markdown("**Текст:**")
                st.markdown(f"```\n{doc['text'][:500]}...\n```")

    # График сравнения scores
    st.markdown("---")
    st.header("📊 Визуализация реренкинга")

    # Создаем DataFrame для графика
    chart_data = []
    for i, doc in enumerate(result['documents'], 1):
        chart_data.append({
            'Документ': f"Doc #{i}",
            'Hybrid Score': doc.get('hybrid_score', 0),
            'Rerank Score': doc['rerank_score']
        })

    df = pd.DataFrame(chart_data)
    df_melted = df.melt(id_vars=['Документ'], var_name='Тип Score', value_name='Значение')

    st.bar_chart(df_melted.pivot(index='Документ', columns='Тип Score', values='Значение'))

# История запросов
if len(st.session_state.history) > 1:
    st.markdown("---")
    st.header("📜 История запросов")

    for i, item in enumerate(st.session_state.history[1:6], 1):  # Показываем последние 5
        with st.expander(f"⏰ {item['timestamp']} - {item['query'][:50]}..."):
            st.markdown(f"**Ответ:** {item['result']['answer'][:200]}...")
            st.markdown(f"**Документов:** {len(item['result']['documents'])}")

# Футер
st.markdown("---")
st.markdown("""
<div style='text-align: center'>
    <p>RAG System powered by Weaviate, BERTA, BGE-Reranker, and OpenRouter</p>
</div>
""", unsafe_allow_html=True)
