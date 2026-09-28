#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Локальный тестовый скрипт для проверки работы системы
Запустите перед коммитом в GitHub, чтобы убедиться что все работает
"""

import os
import sys

# Установка тестовых переменных окружения
os.environ['GIST_TOKEN'] = 'your_test_token_here'  # Замените на реальный токен для теста
os.environ['GIST_ID'] = ''  # Оставьте пустым для создания нового Gist

def test_imports():
    """Проверка импорта всех необходимых модулей"""
    print("🧪 Тест 1: Проверка импортов...")
    try:
        import requests
        import base64
        import json
        import re
        print("   ✅ Все модули импортированы успешно")
        return True
    except ImportError as e:
        print(f"   ❌ Ошибка импорта: {e}")
        print("   💡 Установите зависимости: pip install -r requirements.txt")
        return False


def test_proxy_sources():
    """Проверка доступности источников прокси"""
    print("\n🧪 Тест 2: Проверка источников прокси...")
    import requests
    from main import PROXY_SOURCES, REQUEST_HEADERS, REQUEST_TIMEOUT
    
    available = 0
    for url in PROXY_SOURCES:
        try:
            response = requests.head(url, headers=REQUEST_HEADERS, timeout=10)
            if response.status_code == 200:
                print(f"   ✅ {url[:50]}...")
                available += 1
            else:
                print(f"   ⚠️  {url[:50]}... (HTTP {response.status_code})")
        except Exception as e:
            print(f"   ❌ {url[:50]}... (Ошибка)")
    
    print(f"\n   Доступно источников: {available}/{len(PROXY_SOURCES)}")
    return available > 0


def test_fetch_proxies():
    """Проверка сбора прокси из источников"""
    print("\n🧪 Тест 3: Сбор прокси из источников...")
    from main import fetch_proxies_from_source, PROXY_SOURCES
    
    all_proxies = []
    for url in PROXY_SOURCES[:2]:  # Тестируем только первые 2 источника
        proxies = fetch_proxies_from_source(url)
        all_proxies.extend(proxies)
    
    print(f"   Собрано записей: {len(all_proxies)}")
    return len(all_proxies) > 0


def test_validation():
    """Проверка валидации прокси"""
    print("\n🧪 Тест 4: Валидация прокси...")
    from main import is_valid_proxy_url
    
    test_cases = [
        ("vless://valid@example.com:443", True),
        ("vmess://base64encodedconfig", True),
        ("trojan://password@server.com:443", True),
        ("ss://base64@server.com:8388", True),
        ("invalid://test", False),
        ("", False),
        ("not a url", False),
    ]
    
    passed = 0
    for proxy, expected in test_cases:
        result = is_valid_proxy_url(proxy)
        status = "✅" if result == expected else "❌"
        print(f"   {status} {proxy[:40]}: {result} (ожидалось {expected})")
        if result == expected:
            passed += 1
    
    print(f"\n   Пройдено тестов: {passed}/{len(test_cases)}")
    return passed == len(test_cases)


def test_deduplication():
    """Проверка дедупликации"""
    print("\n🧪 Тест 5: Дедупликация...")
    from main import clean_and_deduplicate
    
    test_proxies = [
        "vless://test1@server1.com:443",
        "vless://test1@server1.com:443",  # Дубликат
        "vmess://test2@server2.com:443",
        "invalid",  # Невалидный
        "",  # Пустой
        "vless://test3@server3.com:443",
    ]
    
    cleaned = clean_and_deduplicate(test_proxies)
    print(f"   Исходных: {len(test_proxies)}")
    print(f"   После очистки: {len(cleaned)}")
    print(f"   Ожидалось: 3")
    
    return len(cleaned) == 3


def test_base64_encoding():
    """Проверка Base64 кодирования"""
    print("\n🧪 Тест 6: Base64 кодирование...")
    from main import encode_to_base64_subscription
    import base64
    
    test_proxies = [
        "vless://test1@server1.com:443",
        "vmess://test2@server2.com:443",
    ]
    
    encoded = encode_to_base64_subscription(test_proxies)
    
    # Проверка что закодировано в Base64
    try:
        decoded = base64.b64decode(encoded).decode('utf-8')
        lines = decoded.strip().split('\n')
        print(f"   ✅ Закодировано {len(lines)} строк")
        return len(lines) == len(test_proxies)
    except Exception as e:
        print(f"   ❌ Ошибка декодирования: {e}")
        return False


def test_environment_variables():
    """Проверка переменных окружения"""
    print("\n🧪 Тест 7: Переменные окружения...")
    
    gist_token = os.environ.get('GIST_TOKEN')
    gist_id = os.environ.get('GIST_ID')
    
    if not gist_token or gist_token == 'your_test_token_here':
        print("   ⚠️  GIST_TOKEN не установлен или использует значение по умолчанию")
        print("   💡 Для полного теста установите реальный токен в test_local.py")
        return False
    else:
        print(f"   ✅ GIST_TOKEN установлен: {gist_token[:10]}...")
    
    if gist_id:
        print(f"   ✅ GIST_ID установлен: {gist_id}")
    else:
        print("   ℹ️  GIST_ID не установлен (будет создан новый Gist)")
    
    return True


def main():
    """Запуск всех тестов"""
    print("=" * 70)
    print("🧪 ЛОКАЛЬНОЕ ТЕСТИРОВАНИЕ HAPP AUTO-UPDATE SYSTEM")
    print("=" * 70)
    
    tests = [
        ("Импорты", test_imports),
        ("Источники прокси", test_proxy_sources),
        ("Сбор прокси", test_fetch_proxies),
        ("Валидация", test_validation),
        ("Дедупликация", test_deduplication),
        ("Base64 кодирование", test_base64_encoding),
        ("Переменные окружения", test_environment_variables),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n   ❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
            results.append((name, False))
    
    # Итоги
    print("\n" + "=" * 70)
    print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print("=" * 70)
    print(f"Пройдено тестов: {passed}/{total}")
    
    if passed == total:
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print("\n💡 Система готова к деплою на GitHub Actions")
        return 0
    else:
        print("⚠️  НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОШЛИ")
        print("\n💡 Исправьте ошибки перед деплоем")
        return 1


if __name__ == "__main__":
    sys.exit(main())
