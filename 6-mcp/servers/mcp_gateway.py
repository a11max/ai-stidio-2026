"""
MCP Gateway — объединённый MCP-сервер с двумя режимами работы.

Автоматически сканирует текущую директорию на наличие .py файлов
с MCP-серверами.

Режимы:
    combined  — один сервер со всеми инструментами (с префиксами имён)
    multi     — каждый сервер запускается на отдельном порту (потоки)

Запуск:
    python mcp_gateway.py                    # combined (по умолчанию)
    python mcp_gateway.py --mode combined    # то же самое
    python mcp_gateway.py --mode multi       # каждый сервер на своём порту

Переменные окружения:
    GATEWAY_HOST — хост (по умолчанию 0.0.0.0)
    GATEWAY_PORT — базовый порт (по умолчанию 8000)
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import os
import re
import sys
import threading
from pathlib import Path
from types import ModuleType

from fastmcp import FastMCP

GATEWAY_FILENAME = Path(__file__).name
GATEWAY_HOST = os.getenv("GATEWAY_HOST", "158.160.175.155")
GATEWAY_PORT = int(os.getenv("GATEWAY_PORT", "8000"))


# ── Типы данных ──────────────────────────────────────────────────────────

class ServerInfo:
    """Результат обнаружения одного MCP-сервера."""

    def __init__(
        self,
        module_name: str,
        server_name: str,
        prefix: str,
        mcp_instance: FastMCP,
        tools: dict,
    ) -> None:
        self.module_name = module_name
        self.server_name = server_name
        self.prefix = prefix
        self.mcp_instance = mcp_instance
        self.tools = tools  # {tool_name: tool_object}


# ── Вспомогательные функции ──────────────────────────────────────────────


def _find_mcp_instance(module: ModuleType) -> FastMCP | None:
    """Найти экземпляр FastMCP внутри импортированного модуля.

    Проверяет все атрибуты модуля и возвращает первый найденный
    объект типа FastMCP.  Если экземпляр не найден, возвращает None.
    """
    for _name, obj in inspect.getmembers(module):
        if isinstance(obj, FastMCP):
            return obj
    return None


def _derive_prefix(server_name: str) -> str:
    """Получить из имени сервера корректный префикс для инструмента.

    Пример: ``"ArxivResearch"`` → ``"arxivresearch"``,
            ``"PersonalNotes"`` → ``"personalnotes"``.
    """
    prefix = server_name.strip().lower()
    prefix = re.sub(r"[\s\-]+", "_", prefix)
    # Оставляем буквы, цифры, подчёркивания (включая кириллицу)
    prefix = re.sub(r"[^\w]", "", prefix, flags=re.UNICODE)
    return prefix


def _get_tools(mcp_instance: FastMCP) -> dict:
    """Извлечь зарегистрированные инструменты из FastMCP-экземпляра.

    Пробует несколько вариантов внутреннего API, чтобы быть
    совместимым с разными версиями библиотеки.

    Returns:
        Словарь ``{tool_name: tool_object}``, или пустой словарь.
    """
    # mcp (>=1.x)  — _tool_manager._tools
    mgr = getattr(mcp_instance, "_tool_manager", None)
    if mgr is not None:
        tools = getattr(mgr, "_tools", None)
        if tools:
            return dict(tools)

    # Альтернативный вариант — _tools напрямую
    tools = getattr(mcp_instance, "_tools", None)
    if tools:
        return dict(tools)

    return {}


# ── Обнаружение серверов (общее для обоих режимов) ───────────────────────


def discover_servers() -> list[ServerInfo]:
    """Просканировать директорию и вернуть список обнаруженных MCP-серверов.

    Для каждого найденного сервера возвращает ``ServerInfo`` с
    экземпляром FastMCP и его инструментами.  Эта функция **не**
    регистрирует инструменты ни на каком сервере — вызывающий код
    решает, как их использовать.
    """
    servers_dir = Path(__file__).parent.resolve()

    # Добавляем директорию в sys.path для корректного импорта
    if str(servers_dir) not in sys.path:
        sys.path.insert(0, str(servers_dir))

    py_files = sorted(servers_dir.glob("*.py"))
    servers: list[ServerInfo] = []

    for py_file in py_files:
        if py_file.name in (GATEWAY_FILENAME, "__init__.py"):
            continue

        module_name = py_file.stem

        try:
            module = importlib.import_module(module_name)
        except Exception as exc:
            print(f"⚠️  Не удалось импортировать {py_file.name}: {exc}")
            continue

        mcp_instance = _find_mcp_instance(module)
        if mcp_instance is None:
            print(f"ℹ️  {py_file.name}: FastMCP-экземпляр не найден, пропуск")
            continue

        server_name: str = getattr(mcp_instance, "name", module_name)
        prefix = _derive_prefix(server_name)
        tools = _get_tools(mcp_instance)

        if not tools:
            print(f"ℹ️  {py_file.name} ({server_name}): инструменты не найдены")
            continue

        servers.append(
            ServerInfo(
                module_name=module_name,
                server_name=server_name,
                prefix=prefix,
                mcp_instance=mcp_instance,
                tools=tools,
            )
        )

    return servers


# ── Режим combined ───────────────────────────────────────────────────────


def run_combined(servers: list[ServerInfo]) -> None:
    """Запустить один объединённый сервер со всеми инструментами.

    Каждый инструмент получает префикс ``<server>__<tool>`` и
    указание источника в описании.
    """
    combined = FastMCP("MCP Gateway", host=GATEWAY_HOST, port=GATEWAY_PORT)
    registered: list[tuple[str, str]] = []

    for srv in servers:
        for tool_name, tool_obj in srv.tools.items():
            prefixed_name = f"{srv.prefix}__{tool_name}"

            fn = getattr(tool_obj, "fn", tool_obj)
            description = getattr(tool_obj, "description", "") or ""
            full_description = (
                f"[{srv.server_name}] {description}"
                if description
                else f"[{srv.server_name}]"
            )

            combined.tool(name=prefixed_name, description=full_description)(fn)
            registered.append((prefixed_name, srv.server_name))

    print("🚀 Запуск MCP Gateway (режим: combined)...")
    print(f"📦 Зарегистрировано инструментов: {len(registered)}\n")
    for tool_name, server in registered:
        print(f"  • {tool_name}  (из {server})")
    print(f"\n🌐 http://{GATEWAY_HOST}:{GATEWAY_PORT}\n")

    combined.run(transport="streamable-http")


# ── Режим multi ──────────────────────────────────────────────────────────


def _run_server(
    mcp_instance: FastMCP, host: str, port: int, server_name: str
) -> None:
    """Запустить один MCP-сервер (вызывается в отдельном потоке)."""
    try:
        mcp_instance.settings.host = host
        mcp_instance.settings.port = port
        mcp_instance.run(transport="sse")
    except Exception as exc:
        print(f"❌ Ошибка в сервере {server_name} (порт {port}): {exc}")


def run_multi(servers: list[ServerInfo]) -> None:
    """Запустить каждый обнаруженный сервер на отдельном порту.

    Порты назначаются последовательно, начиная с ``GATEWAY_PORT``.
    """
    print("🚀 Запуск MCP Gateway (режим: multi)...\n")

    threads: list[threading.Thread] = []

    for idx, srv in enumerate(servers):
        port = GATEWAY_PORT + idx
        tool_names = list(srv.tools.keys())
        print(
            f"  • {srv.server_name} → http://{GATEWAY_HOST}:{port}  "
            f"({len(tool_names)} инструмент(ов))"
        )

        t = threading.Thread(
            target=_run_server,
            args=(srv.mcp_instance, GATEWAY_HOST, port, srv.server_name),
            daemon=True,
        )
        threads.append(t)

    print()
    for t in threads:
        t.start()

    # Ожидаем завершения всех потоков
    for t in threads:
        t.join()


# ── Точка входа ──────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="MCP Gateway — объединённый MCP-сервер",
    )
    parser.add_argument(
        "--mode",
        choices=["combined", "multi"],
        default="combined",
        help=(
            "Режим работы: "
            "combined — один сервер со всеми инструментами (по умолчанию), "
            "multi — каждый сервер на отдельном порту"
        ),
    )
    args = parser.parse_args()

    servers = discover_servers()

    if not servers:
        print("❌ Ни одного MCP-сервера не найдено.")
        sys.exit(1)

    if args.mode == "combined":
        run_combined(servers)
    else:
        run_multi(servers)


if __name__ == "__main__":
    main()
