def extract_main_content(html_content):
    """
    Извлекает основной текст из HTML-контента с помощью BeautifulSoup.

    Параметры:
    - html_content (str): HTML-код страницы.

    Возвращает:
    - text (str): Извлеченный и очищенный текст.
    """
    soup = BeautifulSoup(html_content, 'html.parser')

    # Удаляем все скрипты и стили
    for script_or_style in soup(['script', 'style', 'noscript']):
        script_or_style.decompose()

    # Пытаемся найти тег <article>, если он есть
    article = soup.find('article')
    if article:
        text = article.get_text(separator='\n')
    else:
        # Если <article> нет, выбираем наиболее содержательный <div>
        divs = soup.find_all('div')
        max_text = ''
        max_length = 0
        for div in divs:
            div_text = div.get_text(separator='\n').strip()
            div_length = len(div_text)
            if div_length > max_length:
                max_length = div_length
                max_text = div_text
        text = max_text

    # Дополнительная очистка текста
    clean_main_text = clean_text(text)

    return clean_main_text

def internet_search(query, k):
    """
    Выполняет поиск в интернете с помощью Google,
    загружает контент первых k ссылок и обрабатывает его с использованием Text Splitters из langchain.

    Параметры:
    - query (str): Поисковой запрос.
    - k (int): Количество ссылок для обработки.

    Возвращает:
    - result_array (list): Список, содержащий по 2 чанка с каждой ссылки.
    """
    # Выполнение поискового запроса
    links = search(query, lang='ru', num_results=k)
    result_array = []

    for idx, link in enumerate(links):
        try:
            print(f"Обрабатывается ссылка {idx+1}/{k}: {link}")
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/58.0.3029.110 Safari/537.3"
            }
            response = requests.get(link, headers=headers, timeout=10)
            response.raise_for_status()
            html_content = response.text

            # Извлечение основного текста
            clean_main_text = extract_main_content(html_content)

            if not clean_main_text:
                print(f"На странице {link} не найден основной текст.")
                continue

            # Разбиение текста на чанки
            text_splitter = RecursiveCharacterTextSplitter(
                separator='\n',
                chunk_size=1000,
                chunk_overlap=100
            )
            chunks = text_splitter.split_text(clean_main_text)

            # Берем только первые 2 чанка
            first_two_chunks = chunks[:2]

            result_array.append(clean_main_text)

        except requests.exceptions.RequestException as e:
            print(f"Ошибка при загрузке {link}: {e}")
        except Exception as e:
            print(f"Ошибка при обработке контента с {link}: {e}")

    return result_array