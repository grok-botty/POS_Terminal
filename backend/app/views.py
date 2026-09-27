from datetime import datetime
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json

from .models import DailySummary, Order, OrderLine


@require_http_methods(["GET"])
def health(request):
    return JsonResponse({"ok": True})


@csrf_exempt
@require_http_methods(["POST"])
def end_day(request):
    try:
        # Парсим JSON из тела запроса
        data = json.loads(request.body)
        orders_data = data.get("orders", [])

        today = datetime.now().strftime("%Y-%m-%d")

        # Проверяем, не закрыт ли уже день
        if DailySummary.objects.filter(date=today).exists():
            return JsonResponse(
                {
                    "success": False,
                    "message": f"День {today} уже закрыт. Удалите запись из БД если хотите закрыть заново.",
                },
                status=400,
            )

        # Подсчитываем статистику
        total_revenue = 0.0
        paid_orders = 0
        unpaid_orders = 0

        for order_data in orders_data:
            lines = order_data.get("lines", {})
            order_total = sum(line["price"] * line["qty"] for line in lines.values())
            total_revenue += order_total

            if order_data.get("isPaid", False):
                paid_orders += 1
            else:
                unpaid_orders += 1

        total_orders = len(orders_data)

        # Создаём запись дневной сводки
        daily_summary = DailySummary.objects.create(
            date=today, total_revenue=total_revenue, total_orders=total_orders
        )

        # Сохраняем заказы
        for order_data in orders_data:
            lines = order_data.get("lines", {})
            order_total = sum(line["price"] * line["qty"] for line in lines.values())

            # Преобразуем timestamps в datetime
            queued_at = None
            if order_data.get("queuedAt"):
                queued_at = datetime.fromtimestamp(order_data["queuedAt"] / 1000)

            handoff_at = None
            if order_data.get("handoffAt"):
                handoff_at = datetime.fromtimestamp(order_data["handoffAt"] / 1000)

            order = Order.objects.create(
                order_id=order_data["id"],
                name=order_data["name"],
                comment=order_data.get("comment", ""),
                status=order_data["status"],
                total=order_total,
                is_paid=order_data.get("isPaid", False),
                created_at=datetime.fromtimestamp(order_data["createdAt"] / 1000),
                queued_at=queued_at,
                handoff_at=handoff_at,
                daily_summary=daily_summary,
            )

            # Сохраняем позиции заказа
            for line_data in lines.values():
                OrderLine.objects.create(
                    order=order,
                    product_id=line_data["productId"],
                    name=line_data["name"],
                    price=line_data["price"],
                    qty=line_data["qty"],
                )

        return JsonResponse(
            {
                "success": True,
                "date": today,
                "total_revenue": total_revenue,
                "total_orders": total_orders,
                "paid_orders": paid_orders,
                "unpaid_orders": unpaid_orders,
                "message": f"День {today} успешно закрыт. Выручка: {total_revenue:.2f} ₽",
            }
        )

    except Exception as e:
        return JsonResponse(
            {"success": False, "message": f"Ошибка при закрытии дня: {str(e)}"},
            status=500,
        )
