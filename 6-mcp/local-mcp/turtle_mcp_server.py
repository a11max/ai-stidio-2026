"""
MCP Server для рисования черепашьей графикой.

Этот сервер предоставляет инструменты для управления черепашкой
через Model Context Protocol (MCP).

Запуск: python turtle_mcp_server.py
"""

import turtle
import threading
from fastmcp import FastMCP

# Создаём MCP сервер
mcp = FastMCP("TurtleGraphics")

# Глобальные переменные для управления черепашкой
_turtle = None
_screen = None
_turtle_lock = threading.Lock()

def ensure_turtle():
    """Инициализирует черепашку, если она ещё не создана."""
    global _turtle, _screen
    with _turtle_lock:
        if _turtle is None:
            _screen = turtle.Screen()
            _screen.title("MCP Turtle Graphics")
            _turtle = turtle.Turtle()
            _turtle.speed(3)  # Средняя скорость для наглядности
        return _turtle


@mcp.tool()
def forward(distance: float) -> str:
    """
    Переместить черепашку вперёд на указанное расстояние в пикселях.
    При опущенном пере оставляет линию.
    
    Args:
        distance: Расстояние в пикселях (обычно от 10 до 200)
    """
    t = ensure_turtle()
    t.forward(distance)
    return f"Черепашка продвинулась вперёд на {distance} пикселей"


@mcp.tool()
def left(degrees: float) -> str:
    """
    Повернуть черепашку налево на указанный угол в градусах.
    
    Args:
        degrees: Угол поворота в градусах (например, 90 для прямого угла)
    """
    t = ensure_turtle()
    t.left(degrees)
    return f"Черепашка повернулась налево на {degrees} градусов"


@mcp.tool()
def right(degrees: float) -> str:
    """
    Повернуть черепашку направо на указанный угол в градусах.
    
    Args:
        degrees: Угол поворота в градусах (например, 90 для прямого угла)
    """
    t = ensure_turtle()
    t.right(degrees)
    return f"Черепашка повернулась направо на {degrees} градусов"


@mcp.tool()
def penup() -> str:
    """
    Поднять перо. После этого черепашка будет двигаться без рисования линий.
    Используйте для перемещения в другую точку без рисования.
    """
    t = ensure_turtle()
    t.penup()
    return "Перо поднято — черепашка не будет рисовать"


@mcp.tool()
def pendown() -> str:
    """
    Опустить перо. После этого черепашка будет рисовать линии при движении.
    """
    t = ensure_turtle()
    t.pendown()
    return "Перо опущено — черепашка будет рисовать"


@mcp.tool()
def reset_canvas() -> str:
    """
    Очистить холст и вернуть черепашку в начальную позицию.
    Используйте перед началом нового рисунка.
    """
    t = ensure_turtle()
    t.reset()
    return "Холст очищен, черепашка в начальной позиции"


@mcp.tool()
def get_position() -> str:
    """
    Получить текущую позицию и направление черепашки.
    """
    t = ensure_turtle()
    x, y = t.position()
    heading = t.heading()
    return f"Позиция: ({x:.1f}, {y:.1f}), направление: {heading:.1f}°"


if __name__ == "__main__":
    print("🐢 Запуск MCP Turtle Server...")
    print("📡 Сервер доступен по адресу: http://localhost:8000/mcp")
    print("⚠️  Для остановки нажмите Ctrl+C")
    
    # Запускаем сервер с Streamable HTTP транспортом
    mcp.run(
        transport="streamable-http",
        host="127.0.0.1",
        port=8000
    )
