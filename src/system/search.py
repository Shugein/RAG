# def semantic_search_with_score(db, query, limit=3):
#     """
#     Выполняет семантический поиск и возвращает уникальные документы с их оценками.

#     :param db: Объект базы данных, поддерживающий similarity_search_with_score.
#     :param query: Строка запроса.
#     :param limit: Максимальное количество уникальных документов для возврата.
#     :return: Кортеж из двух списков: документов и их оценок.
#     """
#     # Запрашиваем больше результатов, чтобы компенсировать возможные дубликаты
#     over_fetch_limit = limit * 2
#     results = db._collection.similarity_search_with_score(query, k=limit)

#     seen = set()
#     unique_docs = []
#     unique_scores = []

#     for doc, score in results:
#         content = doc.page_content.strip()
#         if content not in seen:
#             seen.add(content)
#             unique_docs.append(content)
#             unique_scores.append(score)
#             if len(unique_docs) >= limit:
#                 break

#     return unique_docs, unique_scores


# #===== Reranker =====#
# # Инициализация модели для ранжирования
# from transformers import BertTokenizer, BertForSequenceClassification, AutoModelForSequenceClassification

# # Инициализация токенизатора и модели для ранжирования
# tokenizer_reranker = BertTokenizer.from_pretrained("nlpaueb/legal-bert-base-uncased")
# model_reranker = BertForSequenceClassification.from_pretrained("nlpaueb/legal-bert-base-uncased").to(device)

# model_reranker.eval()

# def rerank_and_filter(query, documents, top_n=3, threshold=0.3):
#     # Реранкинг документов
#     inputs = tokenizer_reranker([query]*len(documents), documents, return_tensors='pt', truncation=True, padding=True)
#     with torch.no_grad():
#         outputs = model_reranker(**inputs)
#     scores = torch.softmax(outputs.logits, dim=1)[:,1].tolist()

#     ranked_docs = sorted(zip(documents, scores), key=lambda x: x[1])

#     # Выбор документов ниже порога
#     filtered_docs = [doc for doc, score in ranked_docs if score <= threshold]

#     # Если отфильтрованных документов меньше top_n, дополняем их топ-N
#     if len(filtered_docs) < top_n:
#         filtered_docs = [doc for doc, score in ranked_docs[:top_n]]

#     rearranged_docs_topn = filtered_docs[:top_n]
#     rearranged_docs = [rearranged_docs_topn[1]] + rearranged_docs_topn[2:2+(top_n-2)] + [rearranged_docs_topn[0]]
#     return rearranged_docs, rearranged_docs_topn

import weaviate.classes as wvc

# Пример поиска с GPU векторизацией
def hybrid_search_test(collection, query):
    try:
        # Гибридный поиск (Weaviate автоматически векторизирует запрос с помощью GPU)
        results = collection.query.hybrid(
            query=query,
            alpha=0.5,  # 0.5 = равный вес векторному и BM25
            query_properties=["text_for_bm25", 'title'],  # только поле "question" участвует в BM25
            return_metadata=wvc.query.MetadataQuery(score=True),
            limit=3
        )

        print(f"Found {len(results.objects)} results for query: '{query}'")
        for i, obj in enumerate(results.objects):
            print(f"\n{i+1}. Title: {obj.properties.get('title', 'N/A')}")
            print(f"   Source: {obj.properties.get('source', 'N/A')}")
            print(f"   Text: {obj.properties.get('original_text', '')[:200]}...")
            print(f"   Score: {obj.metadata.score}")

    except Exception as e:
        print(f"Search test failed: {e}")
