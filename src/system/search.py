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
from weaviate.classes.query import HybridFusion, Rerank, Filter

def hybrid_search_with_rerank(
    collection,
    query,
    limit=10,
    rerank_limit=3,
    use_parent_docs=True,
    hotness_weight=0.3,
    alpha=0.6
):
    """
    Гибридный поиск с реренкингом используя BAAI/bge-reranker-v2-m3

    Hotness добавляется к финальному скору как взвешенная компонента.

    :param collection: Weaviate коллекция
    :param query: Поисковый запрос
    :param limit: Количество результатов для первичного поиска
    :param rerank_limit: Количество топ результатов после реренкинга
    :param use_parent_docs: Использовать полные родительские документы вместо чанков
    :param hotness_weight: Вес hotness в финальном скоре (0.0-1.0). Финальный скор = rerank_score * (1 - weight) + hotness * weight
    :param alpha: Баланс между векторным (alpha) и BM25 (1-alpha) поиском
                  0.0 = только BM25 (лексический)
                  0.5 = равный вес (по умолчанию)
                  1.0 = только векторный (семантический)
    :return: Список результатов после реренкинга (с родительскими документами если use_parent_docs=True)
    """
    try:
        # ЕДИНЫЙ гибридный поиск С реренкингом
        print(f"\n{'='*80}")
        print(f"=== HYBRID SEARCH WITH RERANKING ===")
        print(f"=== Alpha (vector/BM25 balance): {alpha} | Hotness weight: {hotness_weight} ===")
        print(f"{'='*80}")

        results = collection.query.hybrid(
            query=query,
            alpha=alpha,  # Баланс между векторным и BM25
            query_properties=["original_text", "text_for_bm25"],  # original_text для векторного, text_for_bm25 для BM25
            fusion_type=HybridFusion.RELATIVE_SCORE,
            return_metadata=wvc.query.MetadataQuery(score=True),
            limit=limit,
            rerank=Rerank(
                prop="original_text",  # Реранкер использует оригинальный текст
                query=query
            )
        )

        print(f"\nFound {len(results.objects)} results after hybrid search + reranking")

        # Анализируем результаты и добавляем hotness к скору
        ranking = []
        for i, obj in enumerate(results.objects):
            doc_id = str(obj.uuid)
            rerank_score = obj.metadata.score
            hotness = obj.properties.get('hotness', 0.5)
            title = obj.properties.get('title', 'N/A')

            # Вычисляем финальный скор с учетом hotness
            final_score = rerank_score * (1 - hotness_weight) + hotness * hotness_weight

            ranking.append({
                'uuid': doc_id,
                'title': title,
                'rerank_score': rerank_score,
                'hotness': hotness,
                'final_score': final_score,
                'rerank_position': i + 1
            })

        # ПЕРЕСОРТИРОВКА по финальному скору (rerank_score + hotness)
        ranking.sort(key=lambda x: x['final_score'], reverse=True)

        # Обновляем позиции после пересортировки
        for i, item in enumerate(ranking):
            item['final_position'] = i + 1

        print(f"\nAfter hotness adjustment:")
        for item in ranking:
            print(f"{item['final_position']:2d}. Rerank: {item['rerank_score']:.6f} + Hotness: {item['hotness']:.2f} = Final: {item['final_score']:.6f} | {item['title'][:50]}")

        # Формируем финальные результаты с дедупликацией родительских документов
        print(f"\n{'='*80}")
        if use_parent_docs:
            print(f"=== Final Documents (sorted by final score with hotness) ===")
        else:
            print(f"=== Final Chunks (TOP {rerank_limit}) ===")
        print(f"{'='*80}")

        final_results = []
        seen_parent_docs = set()  # Для отслеживания уникальных родительских документов

        # Создаем мапу для быстрого доступа к объектам по UUID
        objects_map = {str(obj.uuid): obj for obj in results.objects}

        # Итерируемся по отсортированному списку (по final_score)
        for rank_item in ranking:
            # Прекращаем если набрали нужное количество уникальных документов
            if len(final_results) >= rerank_limit:
                break

            doc_id = rank_item['uuid']
            obj = objects_map.get(doc_id)
            if not obj:
                continue

            parent_doc_id = obj.properties.get('parent_doc_id', doc_id)

            # Если используем родительские документы и этот parent уже был - пропускаем
            if use_parent_docs and parent_doc_id in seen_parent_docs:
                print(f"   ⏭️  Skipping duplicate parent doc (chunk from same document)")
                continue

            # Отмечаем parent документ как использованный
            if use_parent_docs:
                seen_parent_docs.add(parent_doc_id)

            # Определяем какой текст использовать
            if use_parent_docs:
                text_to_use = obj.properties.get('parent_doc_text', obj.properties.get('original_text', ''))
                text_type = "parent_document"
            else:
                text_to_use = obj.properties.get('original_text', '')
                text_type = "chunk"

            result = {
                'title': obj.properties.get('title', 'N/A'),
                'source': obj.properties.get('source', 'N/A'),
                'text': text_to_use,
                'chunk_text': obj.properties.get('original_text', ''),
                'url': obj.properties.get('url', 'N/A'),
                'timestamp': obj.properties.get('timestamp', 0),
                'rerank_score': rank_item['rerank_score'],
                'hotness': rank_item['hotness'],
                'final_score': rank_item['final_score'],
                'final_position': rank_item['final_position'],
                'chunk_index': obj.properties.get('chunk_index', 0),
                'parent_doc_id': parent_doc_id,
                'text_type': text_type,
                # Добавляем извлеченные сущности из метаданных
                'companies': obj.properties.get('companies', []),
                'company_tickers': obj.properties.get('company_tickers', []),
                'company_sectors': obj.properties.get('company_sectors', []),
                'people': obj.properties.get('people', []),
                'people_positions': obj.properties.get('people_positions', []),
                'markets': obj.properties.get('markets', []),
                'market_types': obj.properties.get('market_types', []),
                'financial_metric_types': obj.properties.get('financial_metric_types', []),
                'financial_metric_values': obj.properties.get('financial_metric_values', []),
                'entities_json': obj.properties.get('entities_json', ''),
            }
            final_results.append(result)

            print(f"\n📄 Result #{len(final_results)}")
            print(f"   Title: {result['title']}")
            print(f"   Type: {'🔹 Full Parent Document' if use_parent_docs else '📄 Chunk'}")
            if use_parent_docs:
                print(f"   Retrieved from chunk #{result['chunk_index']}")
            print(f"   Rerank Score:  {result['rerank_score']:.6f}")
            print(f"   Hotness:       {result['hotness']:.2f}")
            print(f"   Final Score:   {result['final_score']:.6f} = {result['rerank_score']:.4f} × {(1-hotness_weight):.2f} + {result['hotness']:.2f} × {hotness_weight:.2f}")
            print(f"   Source: {result['source']}")
            if use_parent_docs:
                print(f"   Chunk preview: {result['chunk_text'][:120]}...")
                print(f"   Full doc length: {len(result['text'])} chars")
            else:
                print(f"   Text: {result['text'][:120]}...")

        print(f"\n✅ Final results: {len(final_results)} unique {'parent documents' if use_parent_docs else 'chunks'}")

        return final_results

    except Exception as e:
        print(f"Search with rerank failed: {e}")
        import traceback
        traceback.print_exc()
        return []

# Пример поиска с GPU векторизацией (старая функция для совместимости)
def hybrid_search_test(collection, query):
    try:
        # Гибридный поиск (Weaviate автоматически векторизирует запрос с помощью GPU)
        results = collection.query.hybrid(
            query=query,
            alpha=0.35,  # 0.5 = равный вес векторному и BM25
            query_properties=["text_for_bm25", 'title'],
            fusion_type=HybridFusion.RELATIVE_SCORE,
            return_metadata=wvc.query.MetadataQuery(score=True),
            limit=10
        )

        print(f"Found {len(results.objects)} results for query: '{query}'")
        for i, obj in enumerate(results.objects):
            print(f"\n{i+1}. Title: {obj.properties.get('title', 'N/A')}")
            print(f"   Source: {obj.properties.get('source', 'N/A')}")
            print(f"   Text: {obj.properties.get('original_text', '')[:200]}...")
            print(f"   Score: {obj.metadata.score}")

    except Exception as e:
        print(f"Search test failed: {e}")
