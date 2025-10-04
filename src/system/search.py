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
from weaviate.classes.query import HybridFusion, Rerank

def hybrid_search_with_rerank(collection, query, limit=10, rerank_limit=3, use_parent_docs=True):
    """
    Гибридный поиск с реренкингом используя BAAI/bge-reranker-v2-m3

    :param collection: Weaviate коллекция
    :param query: Поисковый запрос
    :param limit: Количество результатов для первичного поиска
    :param rerank_limit: Количество топ результатов после реренкинга
    :param use_parent_docs: Использовать полные родительские документы вместо чанков
    :return: Список результатов после реренкинга (с родительскими документами если use_parent_docs=True)
    """
    try:
        # STEP 1: Обычный гибридный поиск БЕЗ реренкинга
        print(f"\n{'='*80}")
        print(f"=== STEP 1: Hybrid Search (WITHOUT reranking) ===")
        print(f"{'='*80}")
        results_before = collection.query.hybrid(
            query=query,
            alpha=0.35,
            query_properties=["text_for_bm25", 'title'],
            fusion_type=HybridFusion.RELATIVE_SCORE,
            return_metadata=wvc.query.MetadataQuery(score=True),
            limit=limit
        )

        print(f"\nFound {len(results_before.objects)} results")

        # Сохраняем результаты ДО реренкинга
        before_ranking = []
        original_scores = {}
        for i, obj in enumerate(results_before.objects):
            doc_id = str(obj.uuid)
            score = obj.metadata.score
            title = obj.properties.get('title', 'N/A')

            original_scores[doc_id] = {
                'score': score,
                'position': i + 1,
                'title': title,
                'text': obj.properties.get('original_text', '')
            }
            before_ranking.append({
                'uuid': doc_id,
                'title': title,
                'score': score,
                'position': i + 1
            })

            print(f"{i+1:2d}. Score: {score:.6f} | {title[:70]}")

        # STEP 2: Гибридный поиск С реренкингом
        print(f"\n{'='*80}")
        print(f"=== STEP 2: Hybrid Search WITH Reranking ===")
        print(f"{'='*80}")
        results_after = collection.query.hybrid(
            query=query,
            alpha=0.35,
            query_properties=["text_for_bm25", 'title'],
            fusion_type=HybridFusion.RELATIVE_SCORE,
            return_metadata=wvc.query.MetadataQuery(score=True),
            limit=limit,
            rerank=Rerank(
                prop="original_text",
                query=query
            )
        )

        print(f"\nFound {len(results_after.objects)} results after reranking")

        # Анализируем результаты ПОСЛЕ реренкинга
        after_ranking = []
        for i, obj in enumerate(results_after.objects):
            doc_id = str(obj.uuid)
            rerank_score = obj.metadata.score
            title = obj.properties.get('title', 'N/A')

            original_data = original_scores.get(doc_id, {})
            original_score = original_data.get('score', 0.0)
            original_position = original_data.get('position', '?')

            position_change = original_position - (i + 1) if isinstance(original_position, int) else 0
            position_indicator = "🔺" if position_change > 0 else "🔻" if position_change < 0 else "➡️"

            after_ranking.append({
                'uuid': doc_id,
                'title': title,
                'original_score': original_score,
                'rerank_score': rerank_score,
                'original_position': original_position,
                'new_position': i + 1,
                'position_change': position_change
            })

            print(f"{i+1:2d}. {position_indicator} (was #{original_position}) | Hybrid: {original_score:.6f} → Rerank: {rerank_score:.6f} | {title[:50]}")

        # Формируем финальные результаты с дедупликацией родительских документов
        print(f"\n{'='*80}")
        if use_parent_docs:
            print(f"=== STEP 3: Parent Document Retrieval with Deduplication ===")
        else:
            print(f"=== DETAILED TOP {rerank_limit} RESULTS ===")
        print(f"{'='*80}")

        reranked_results = []
        seen_parent_docs = set()  # Для отслеживания уникальных родительских документов

        # Итерируемся по всем результатам после реренкинга
        for i, obj in enumerate(results_after.objects):
            # Прекращаем если набрали нужное количество уникальных документов
            if len(reranked_results) >= rerank_limit:
                break

            doc_id = str(obj.uuid)
            original_data = original_scores.get(doc_id, {})
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
                'chunk_text': obj.properties.get('original_text', ''),  # Сохраняем оригинальный чанк для справки
                'url': obj.properties.get('url', 'N/A'),
                'timestamp': obj.properties.get('timestamp', 0),
                'hybrid_score': original_data.get('score', 0.0),
                'rerank_score': obj.metadata.score,
                'original_position': original_data.get('position', '?'),
                'new_position': i + 1,
                'chunk_index': obj.properties.get('chunk_index', 0),
                'parent_doc_id': parent_doc_id,
                'text_type': text_type
            }
            reranked_results.append(result)

            position_change = result['original_position'] - result['new_position'] if isinstance(result['original_position'], int) else 0
            score_change = result['rerank_score'] - result['hybrid_score']

            print(f"\n📄 Result #{len(reranked_results)}")
            print(f"   Title: {result['title']}")
            print(f"   Type: {'🔹 Full Parent Document' if use_parent_docs else '📄 Chunk'}")
            if use_parent_docs:
                print(f"   Retrieved from chunk #{result['chunk_index']}")
            print(f"   Position: #{result['original_position']} → #{result['new_position']} (Δ {position_change:+d} places)")
            print(f"   Hybrid Score:  {result['hybrid_score']:.6f}")
            print(f"   Rerank Score:  {result['rerank_score']:.6f}")
            print(f"   Score Change:  {score_change:+.6f}")
            print(f"   Source: {result['source']}")
            if use_parent_docs:
                print(f"   Chunk preview: {result['chunk_text'][:120]}...")
                print(f"   Full doc length: {len(result['text'])} chars")
            else:
                print(f"   Text: {result['text'][:120]}...")

        print(f"\n✅ Final results: {len(reranked_results)} unique {'parent documents' if use_parent_docs else 'chunks'}")
        if use_parent_docs and len(seen_parent_docs) < len(results_after.objects[:rerank_limit]):
            print(f"   ℹ️  Skipped {len(results_after.objects[:rerank_limit]) - len(seen_parent_docs)} duplicate parent documents")

        return reranked_results

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
