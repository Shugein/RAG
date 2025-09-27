import time
import torch

# Начало отсчета времени выполнения
start_total = time.time()

# Загрузка модулей
print("Loading modules...")
start_modules = time.time()

from src.system import search
import weaviate
import weaviate.classes.config as wc


end_modules = time.time()
print(f"Modules loaded in: {end_modules - start_modules:.2f} seconds")

# Определение устройства
start_device = time.time()
if torch.cuda.is_available():
    device = torch.device("cuda")
elif torch.backends.mps.is_available():
    # Apple Silicon
    device = torch.device("mps")
else:
    device = torch.device("cpu")
end_device = time.time()
print(f"Device detection completed in: {end_device - start_device:.4f} seconds")
print(f"Using device: {device}")

# Подключение к Weaviate
print("Connecting to Weaviate...")
start_connection = time.time()
client = weaviate.connect_to_local()
assert client.is_ready(), "Weaviate is not ready"
end_connection = time.time()
print(f"Weaviate connection established in: {end_connection - start_connection:.2f} seconds")

# Получение коллекции
start_collection = time.time()
COLL_NAME = "NewsChunks"
collection = client.collections.use(COLL_NAME)
end_collection = time.time()
print(f"Collection access in: {end_collection - start_collection:.4f} seconds")

# Выполнение поиска
text = 'Погодные аномалии'
print(f"\nExecuting search for: '{text}'...")
start_search = time.time()

search_results = search.hybrid_search_test(collection, query=text)

end_search = time.time()
print(f"Search completed in: {end_search - start_search:.2f} seconds")

print("\nSearch results:")
print(search_results)

# Закрытие соединения
start_close = time.time()
client.close()
end_close = time.time()
print(f"Connection closed in: {end_close - start_close:.4f} seconds")

# Общее время выполнения
end_total = time.time()
print(f"\n=== TIMING SUMMARY ===")
print(f"Total execution time: {end_total - start_total:.2f} seconds")
print(f"  - Module loading: {end_modules - start_modules:.2f}s ({((end_modules - start_modules)/(end_total - start_total)*100):.1f}%)")
print(f"  - Device detection: {end_device - start_device:.4f}s")
print(f"  - Weaviate connection: {end_connection - start_connection:.2f}s ({((end_connection - start_connection)/(end_total - start_total)*100):.1f}%)")
print(f"  - Collection access: {end_collection - start_collection:.4f}s")
print(f"  - Search execution: {end_search - start_search:.2f}s ({((end_search - start_search)/(end_total - start_total)*100):.1f}%)")
print(f"  - Connection closing: {end_close - start_close:.4f}s")