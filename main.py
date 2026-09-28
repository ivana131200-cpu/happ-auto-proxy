#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Автономная система генерации и обновления happ:// ссылок
Автоматически собирает актуальные proxy-серверы и создает зашифрованную подписку
"""

import os
import sys
import base64
import json
import re
import time
from typing import List, Set
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    print("❌ Модуль requests не установлен. Установите: pip install requests")
    sys.exit(1)


# ============================================================================
# КОНФИГУРАЦИЯ
# ============================================================================

# Проверенные публичные источники proxy-серверов
PROXY_SOURCES = [
    # 1. Pawdroid/Free-servers - популярный агрегатор с ежедневными обновлениями
    "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",
    
    # 2. mahdibland/ShadowsocksAggregator - большая коллекция SS/VMess/Trojan
    "https://raw.githubusercontent.com/mahdibland/ShadowsocksAggregator/master/sub/sub_merge_base64.txt",
    
    # 3. mfuu/v2ray - автообновляемая коллекция
    "https://raw.githubusercontent.com/mfuu/v2ray/master/v2ray",
    
    # 4. AzadNetCH/Clash - Shadowsocks и V2Ray конфиги
    "https://raw.githubusercontent.com/AzadNetCH/Clash/main/AzadNet_iOS.txt",
    
    # 5. Резервный источник - Barry-far
    "https://raw.githubusercontent.com/Barry-far/V2ray-Configs/main/Sub1.txt",
]

# Поддерживаемые протоколы
SUPPORTED_PROTOCOLS = ['vless://', 'vmess://', 'trojan://', 'ss://', 'trojan-go://']

# Настройки HTTP
REQUEST_TIMEOUT = 30
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}


# ============================================================================
# ФУНКЦИИ СБОРА И ОБРАБОТКИ
# ============================================================================

def fetch_proxies_from_source(url: str) -> List[str]:
    """
    Скачивает список прокси из указанного источника
    Автоматически декодирует Base64 если необходимо
    """
    try:
        print(f"📥 Загрузка из: {url}")
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        
        content = response.text.strip()
        
        # Попытка декодировать Base64 (многие источники хранят подписки в Base64)
        try:
            decoded = base64.b64decode(content).decode('utf-8', errors='ignore')
            # Если декодирование успешно и содержит протоколы - используем декодированное
            if any(proto in decoded for proto in SUPPORTED_PROTOCOLS):
                content = decoded
        except Exception:
            pass  # Не Base64 или уже plain text
        
        # Разбиваем на строки и фильтруем
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        proxies = [line for line in lines if any(line.startswith(proto) for proto in SUPPORTED_PROTOCOLS)]
        
        print(f"   ✅ Получено {len(proxies)} серверов")
        return proxies
        
    except requests.Timeout:
        print(f"   ⏱️  Таймаут при загрузке из {url}")
        return []
    except requests.RequestException as e:
        print(f"   ⚠️  Ошибка загрузки: {e}")
        return []
    except Exception as e:
        print(f"   ❌ Неожиданная ошибка: {e}")
        return []


def is_valid_proxy_url(proxy: str) -> bool:
    """
    Валидация формата proxy-строки
    Проверяет базовую корректность URL
    """
    try:
        # Проверка на минимальную длину
        if len(proxy) < 15:
            return False
        
        # Проверка протокола
        if not any(proxy.startswith(proto) for proto in SUPPORTED_PROTOCOLS):
            return False
        
        # Базовая проверка URL структуры
        if '://' not in proxy:
            return False
        
        # Проверка на наличие хоста (после ://)
        protocol_end = proxy.find('://') + 3
        if protocol_end >= len(proxy) or proxy[protocol_end:].startswith('/'):
            return False
        
        return True
        
    except Exception:
        return False


def clean_and_deduplicate(proxies: List[str]) -> List[str]:
    """
    Очистка и дедупликация списка прокси
    Удаляет дубликаты, невалидные и битые строки
    """
    print("\n🧹 Очистка и дедупликация...")
    
    unique_proxies: Set[str] = set()
    valid_count = 0
    
    for proxy in proxies:
        proxy = proxy.strip()
        
        # Пропускаем комментарии и пустые строки
        if not proxy or proxy.startswith('#') or proxy.startswith('//'):
            continue
        
        # Валидация
        if not is_valid_proxy_url(proxy):
            continue
        
        # Добавляем только уникальные
        if proxy not in unique_proxies:
            unique_proxies.add(proxy)
            valid_count += 1
    
    result = sorted(list(unique_proxies))
    print(f"   ✅ Валидных уникальных серверов: {len(result)}")
    
    return result


def encode_to_base64_subscription(proxies: List[str]) -> str:
    """
    Кодирует список прокси в Base64 формат подписки
    Стандартный формат для V2Ray/Sing-box/Clash
    """
    if not proxies:
        print("⚠️  Нет серверов для кодирования")
        return ""
    
    # Объединяем все прокси в одну строку (каждый с новой строки)
    subscription_content = '\n'.join(proxies)
    
    # Кодируем в Base64
    encoded = base64.b64encode(subscription_content.encode('utf-8')).decode('utf-8')
    
    print(f"📦 Закодировано {len(proxies)} серверов в Base64 подписку")
    return encoded


# ============================================================================
# РАБОТА С GITHUB GIST
# ============================================================================

def update_gist(gist_id: str, token: str, content: str, filename: str = "subscription.txt") -> str:
    """
    Обновляет существующий GitHub Gist
    Возвращает RAW URL файла (который никогда не меняется)
    """
    print(f"\n📝 Обновление Gist {gist_id}...")
    
    url = f"https://api.github.com/gists/{gist_id}"
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'Happ-Auto-Updater'
    }
    
    data = {
        "files": {
            filename: {
                "content": content
            }
        }
    }
    
    try:
        response = requests.patch(url, headers=headers, json=data, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        
        gist_data = response.json()
        raw_url = gist_data['files'][filename]['raw_url']
        
        # Формируем постоянный URL (без версии коммита)
        permanent_url = f"https://gist.githubusercontent.com/{gist_data['owner']['login']}/{gist_id}/raw/{filename}"
        
        print(f"   ✅ Gist успешно обновлен")
        print(f"   🔗 Постоянный URL: {permanent_url}")
        
        return permanent_url
        
    except requests.RequestException as e:
        print(f"   ❌ Ошибка обновления Gist: {e}")
        if hasattr(e.response, 'text'):
            print(f"   Ответ API: {e.response.text}")
        raise


def create_gist_if_not_exists(token: str, content: str, filename: str = "subscription.txt", 
                                description: str = "Happ Proxy Subscription") -> tuple:
    """
    Создает новый приватный Gist если GIST_ID не указан
    Возвращает (gist_id, raw_url)
    """
    print("\n🆕 Создание нового Gist...")
    
    url = "https://api.github.com/gists"
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'Happ-Auto-Updater'
    }
    
    data = {
        "description": description,
        "public": False,  # Приватный Gist
        "files": {
            filename: {
                "content": content
            }
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        
        gist_data = response.json()
        gist_id = gist_data['id']
        permanent_url = f"https://gist.githubusercontent.com/{gist_data['owner']['login']}/{gist_id}/raw/{filename}"
        
        print(f"   ✅ Gist создан успешно")
        print(f"   🆔 GIST_ID: {gist_id}")
        print(f"   🔗 URL: {permanent_url}")
        print(f"\n⚠️  ВАЖНО: Сохраните GIST_ID={gist_id} в GitHub Secrets!")
        
        return gist_id, permanent_url
        
    except requests.RequestException as e:
        print(f"   ❌ Ошибка создания Gist: {e}")
        if hasattr(e.response, 'text'):
            print(f"   Ответ API: {e.response.text}")
        raise


# ============================================================================
# РАБОТА С HAPP API
# ============================================================================

def generate_happ_link(subscription_url: str) -> str:
    """
    Отправляет URL подписки в Happ API и получает зашифрованную happ:// ссылку
    """
    print(f"\n🔐 Генерация happ:// ссылки...")
    print(f"   📎 URL подписки: {subscription_url}")
    
    api_url = "https://crypto.happ.su/api-v2.php"
    
    payload = {
        "url": subscription_url
    }
    
    try:
        response = requests.post(
            api_url, 
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        
        # API возвращает JSON с полем "link" или напрямую текст
        try:
            result = response.json()
            if isinstance(result, dict) and 'link' in result:
                happ_link = result['link']
            else:
                happ_link = str(result)
        except json.JSONDecodeError:
            # Если не JSON, берем как текст
            happ_link = response.text.strip()
        
        # Проверка что получили happ:// ссылку
        if not happ_link.startswith('happ://'):
            print(f"   ⚠️  Неожиданный формат ответа: {happ_link}")
            # Пытаемся найти happ:// в ответе
            match = re.search(r'happ://[^\s]+', happ_link)
            if match:
                happ_link = match.group(0)
            else:
                raise ValueError(f"API не вернул happ:// ссылку: {happ_link}")
        
        print(f"   ✅ Получена happ:// ссылка")
        return happ_link
        
    except requests.RequestException as e:
        print(f"   ❌ Ошибка вызова Happ API: {e}")
        if hasattr(e.response, 'text'):
            print(f"   Ответ API: {e.response.text}")
        raise
    except Exception as e:
        print(f"   ❌ Ошибка обработки ответа: {e}")
        raise


# ============================================================================
# СОХРАНЕНИЕ РЕЗУЛЬТАТА
# ============================================================================

def save_happ_link(happ_link: str, output_file: str = "HAPP_LINK.txt"):
    """
    Сохраняет happ:// ссылку в файл
    """
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(happ_link)
        print(f"\n💾 Ссылка сохранена в {output_file}")
    except Exception as e:
        print(f"⚠️  Не удалось сохранить в файл: {e}")


def update_readme_with_link(happ_link: str, readme_path: str = "README.md"):
    """
    Обновляет README.md с актуальной happ:// ссылкой
    """
    try:
        # Читаем существующий README или создаем новый
        try:
            with open(readme_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except FileNotFoundError:
            content = "# Happ Proxy Auto-Update\n\n"
        
        # Блок с ссылкой
        link_block = f"""## 🔗 Актуальная подписка

```
{happ_link}
```

**Последнее обновление:** {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}

### Как использовать:
1. Скопируйте ссылку выше
2. Откройте приложение Happ
3. Добавьте подписку через эту ссылку
4. Серверы будут обновляться автоматически!

---
"""
        
        # Если уже есть блок с ссылкой - заменяем
        if '## 🔗 Актуальная подписка' in content:
            # Находим начало блока
            start = content.find('## 🔗 Актуальная подписка')
            # Находим конец блока (следующий ## или конец файла)
            end = content.find('\n## ', start + 1)
            if end == -1:
                end = content.find('\n---', start + 1)
                if end != -1:
                    end = content.find('\n', end + 4)
            
            if end == -1:
                content = content[:start] + link_block
            else:
                content = content[:start] + link_block + content[end+1:]
        else:
            # Добавляем в начало (после заголовка)
            if content.startswith('# '):
                first_newline = content.find('\n')
                content = content[:first_newline+1] + '\n' + link_block + content[first_newline+1:]
            else:
                content = link_block + content
        
        # Записываем обновленный README
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"📄 README.md обновлен с актуальной ссылкой")
        
    except Exception as e:
        print(f"⚠️  Не удалось обновить README: {e}")


# ============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================================================

def main():
    """
    Основной workflow системы
    """
    print("=" * 70)
    print("🚀 HAPP PROXY AUTO-UPDATE SYSTEM")
    print("=" * 70)
    
    # 1. Получение переменных окружения
    gist_token = os.environ.get('GIST_TOKEN')
    gist_id = os.environ.get('GIST_ID', '')
    
    if not gist_token:
        print("❌ ОШИБКА: Не установлена переменная окружения GIST_TOKEN")
        print("   Создайте GitHub Personal Access Token и добавьте в Secrets")
        sys.exit(1)
    
    print(f"✅ GitHub Token: {'*' * 20}{gist_token[-4:]}")
    if gist_id:
        print(f"✅ Gist ID: {gist_id}")
    else:
        print("ℹ️  Gist ID не указан - будет создан новый Gist")
    
    # 2. Сбор прокси из всех источников
    print(f"\n{'=' * 70}")
    print("📡 ШАГ 1: Сбор прокси из источников")
    print('=' * 70)
    
    all_proxies = []
    for source_url in PROXY_SOURCES:
        proxies = fetch_proxies_from_source(source_url)
        all_proxies.extend(proxies)
        time.sleep(1)  # Небольшая задержка между запросами
    
    print(f"\n📊 Всего собрано: {len(all_proxies)} записей")
    
    # 3. Очистка и дедупликация
    print(f"\n{'=' * 70}")
    print("🧹 ШАГ 2: Очистка и дедупликация")
    print('=' * 70)
    
    clean_proxies = clean_and_deduplicate(all_proxies)
    
    if not clean_proxies:
        print("❌ ОШИБКА: Не удалось получить ни одного валидного сервера")
        sys.exit(1)
    
    # 4. Кодирование в Base64
    print(f"\n{'=' * 70}")
    print("📦 ШАГ 3: Кодирование подписки")
    print('=' * 70)
    
    subscription_base64 = encode_to_base64_subscription(clean_proxies)
    
    # 5. Обновление/создание Gist
    print(f"\n{'=' * 70}")
    print("📝 ШАГ 4: Обновление GitHub Gist")
    print('=' * 70)
    
    try:
        if gist_id:
            subscription_url = update_gist(gist_id, gist_token, subscription_base64)
        else:
            gist_id, subscription_url = create_gist_if_not_exists(gist_token, subscription_base64)
            # Сохраняем GIST_ID для будущих запусков
            print(f"\n💡 Добавьте в GitHub Secrets: GIST_ID={gist_id}")
    except Exception as e:
        print(f"❌ Критическая ошибка при работе с Gist: {e}")
        sys.exit(1)
    
    # 6. Генерация happ:// ссылки
    print(f"\n{'=' * 70}")
    print("🔐 ШАГ 5: Генерация happ:// ссылки")
    print('=' * 70)
    
    try:
        happ_link = generate_happ_link(subscription_url)
    except Exception as e:
        print(f"❌ Критическая ошибка при генерации happ:// ссылки: {e}")
        sys.exit(1)
    
    # 7. Сохранение результатов
    print(f"\n{'=' * 70}")
    print("💾 ШАГ 6: Сохранение результатов")
    print('=' * 70)
    
    save_happ_link(happ_link)
    update_readme_with_link(happ_link)
    
    # 8. Итоговый вывод
    print(f"\n{'=' * 70}")
    print("✅ УСПЕШНО ЗАВЕРШЕНО")
    print('=' * 70)
    print(f"\n🎉 Ваша постоянная happ:// ссылка:")
    print(f"\n   {happ_link}\n")
    print("📱 Добавьте эту ссылку в приложение Happ один раз -")
    print("   серверы будут обновляться автоматически!\n")
    print(f"📊 Статистика:")
    print(f"   • Собрано серверов: {len(all_proxies)}")
    print(f"   • Уникальных валидных: {len(clean_proxies)}")
    print(f"   • Источников: {len(PROXY_SOURCES)}")
    print(f"   • Время обновления: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    print('=' * 70)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Прервано пользователем")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
