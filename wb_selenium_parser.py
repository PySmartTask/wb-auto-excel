from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import time
from datetime import datetime
import logging
import re

# --- Настройка логирования ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Запрос у пользователя ---
print("🛒 Парсер Wildberries.by")
search_query = input("Введите название товара для поиска: ").strip()

min_rating_input = input("Минимальный рейтинг (например, 4.5, пропустите, если не нужно): ").strip()
min_rating = float(min_rating_input.replace(',', '.')) if min_rating_input else 0.0

# --- Настройки ---
region = "by"
url = f"https://www.wildberries.{region}/catalog/0/search.aspx?search={search_query}"

# --- Настройки браузера ---
options = Options()
# options.add_argument("--headless")  # Раскомментируй, чтобы скрыть браузер
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")
options.add_argument("--disable-extensions")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

print(f"🌍 Регион: {region}")
print(f"🔍 Запрос: '{search_query}'")
print(f"⭐ Мин. рейтинг: {min_rating}" if min_rating > 0 else "⭐ Рейтинг: не фильтруем")
print("🚀 Запускаем браузер...")

# --- Запуск драйвера ---
try:
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => false});")
except Exception as e:
    print(f"❌ Ошибка запуска Chrome: {e}")
    exit()

try:
    driver.get(url)

    # Ждём загрузки карточек
    try:
        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "product-card")))
    except Exception as e:
        print("❌ Не удалось загрузить страницу.")
        driver.quit()
        exit()

    time.sleep(4)  # Дополнительная задержка

    products = driver.find_elements(By.CLASS_NAME, "product-card")
    print(f"📦 Найдено товаров: {len(products)}")

    result = []

    for i, product in enumerate(products[:30]):
        try:
            # --- Название ---
            try:
                # Пробуем получить через aria-label
                link = product.find_element(By.CSS_SELECTOR, "a[href*='/detail.aspx']")
                name = link.get_attribute("aria-label").strip()
            except:
                try:
                    # Резерв: по классу
                    name_elem = product.find_element(By.CLASS_NAME, "product-card__name")
                    name = name_elem.text.strip()
                except:
                    name = "Без названия"

            # --- Ссылка ---
            try:
                link_url = link.get_attribute("href") if 'link' in locals() else ""
            except:
                link_url = ""

            # --- Рейтинг ---
            rating = 0.0
            try:
                # Основной класс
                rating_elem = product.find_element(By.CLASS_NAME, "address-rate-mini")
                rating_text = rating_elem.text.strip().replace(',', '.')
                match = re.search(r'(\d+\.?\d*)', rating_text)
                if match:
                    rating = float(match.group(1))
            except:
                pass

            # --- Цена ---
            price = "Не указана"
            price_num = None
            try:
                # Основной селектор: <ins class="price__lower-price red-price">53,79&nbsp;р.</ins>
                price_elem = product.find_element(By.CSS_SELECTOR, "ins.price__lower-price")
                price_text = price_elem.text.strip()

                # Очистка: удаляем всё, кроме цифр и запятой
                clean_price = ''.join(c for c in price_text if c.isdigit() or c == ',')
                # Заменяем запятую на точку и превращаем в число
                if clean_price:
                    price_num = float(clean_price.replace(',', '.'))
            except:
                try:
                    # Резервный селектор
                    price_elem = product.find_element(By.CSS_SELECTOR, ".price__current")
                    price_text = price_elem.text.strip()
                    clean_price = ''.join(c for c in price_text if c.isdigit() or c == ',')
                    if clean_price:
                        price_num = float(clean_price.replace(',', '.'))
                except:
                    pass

            # --- Фильтр по рейтингу ---
            if rating < min_rating:
                continue

            # Добавляем в результат: цена как число
            result.append({
                "Название": name,
                "Цена": price_num,  # Число: 53.79
                "Рейтинг": rating,
                "Ссылка": link_url
            })

        except Exception as e:
            logger.warning(f"⚠️ Ошибка при обработке товара {i}: {e}")
            continue

    # --- Обработка ---
    if not result:
        print("❌ Нет товаров, соответствующих критериям.")
    else:
        df = pd.DataFrame(result)

        # Убеждаемся, что 'Цена' — числовой тип
        df["Цена"] = pd.to_numeric(df["Цена"], errors='coerce')

        # Сортировка по возрастанию цены
        df = df.sort_values(by="Цена", ascending=True, na_position='last')

        # --- Автоматическое имя файла ---
        today = datetime.now().strftime("%d.%m.%Y")
        safe_query = "".join(c for c in search_query if c.isalnum() or c in "._- ").replace(" ", "_")
        filename = f"wb_{safe_query}_{today}.xlsx"

        # Сохранение в Excel
        try:
            df.to_excel(filename, index=False, engine='openpyxl')
            print(f"✅ Готово! Сохранено {len(df)} товаров в:")
            print(f"💾 {filename}")
        except Exception as e:
            print(f"❌ Ошибка при сохранении: {e}")

except Exception as e:
    print(f"❌ Ошибка: {e}")
finally:
    driver.quit()