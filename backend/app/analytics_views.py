import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Sum, Count, Avg, F
from django.db.models.functions import TruncDate
from .models import Order, OrderLine, DailySummary, Product, Category
from .auth import admin_required
from datetime import datetime, timedelta


@require_http_methods(["GET"])
@admin_required
def get_analytics(request):
    """Получить аналитику по заказам"""
    try:
        # Параметры запроса
        days = int(request.GET.get("days", 30))  # По умолчанию 30 дней

        # Вычисляем диапазон дат
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days - 1)

        # Форматируем даты для фильтрации
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")

        # Получаем дневные сводки за период
        daily_summaries = DailySummary.objects.filter(
            date__gte=start_date_str, date__lte=end_date_str
        ).order_by("date")

        # Выручка по дням
        revenue_by_day = [
            {
                "date": summary.date,
                "revenue": summary.total_revenue,
                "orders": summary.total_orders,
            }
            for summary in daily_summaries
        ]

        # Общая статистика
        total_revenue = sum(s.total_revenue for s in daily_summaries)
        total_orders = sum(s.total_orders for s in daily_summaries)
        avg_order_value = total_revenue / total_orders if total_orders > 0 else 0

        # Получаем все заказы за период
        all_orders = Order.objects.filter(
            daily_summary__date__gte=start_date_str,
            daily_summary__date__lte=end_date_str,
        )

        # Статистика по оплате
        paid_orders = all_orders.filter(is_paid=True).count()
        unpaid_orders = all_orders.filter(is_paid=False).count()
        paid_revenue = sum(o.total for o in all_orders.filter(is_paid=True))

        # Топ продуктов
        product_stats = (
            OrderLine.objects.filter(order__in=all_orders)
            .values("product_id", "name")
            .annotate(total_qty=Sum("qty"), total_revenue=Sum(F("price") * F("qty")))
            .order_by("-total_revenue")[:10]
        )

        top_products = [
            {
                "product_id": stat["product_id"],
                "name": stat["name"],
                "quantity": stat["total_qty"],
                "revenue": float(stat["total_revenue"]),
            }
            for stat in product_stats
        ]

        # Статистика по часам (для всех заказов)
        orders_by_hour = {}
        for order in all_orders:
            hour = order.created_at.hour
            if hour not in orders_by_hour:
                orders_by_hour[hour] = {"count": 0, "revenue": 0}
            orders_by_hour[hour]["count"] += 1
            if order.is_paid:
                orders_by_hour[hour]["revenue"] += order.total

        hourly_stats = [
            {
                "hour": hour,
                "orders": data["count"],
                "revenue": data["revenue"],
            }
            for hour, data in sorted(orders_by_hour.items())
        ]

        # Средний чек по дням недели
        orders_by_weekday = {}
        for order in all_orders:
            weekday = order.created_at.weekday()  # 0 = Monday, 6 = Sunday
            if weekday not in orders_by_weekday:
                orders_by_weekday[weekday] = {"count": 0, "revenue": 0}
            orders_by_weekday[weekday]["count"] += 1
            if order.is_paid:
                orders_by_weekday[weekday]["revenue"] += order.total

        weekday_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        weekday_stats = [
            {
                "weekday": weekday_names[day],
                "orders": data["count"],
                "revenue": data["revenue"],
                "avg_check": (
                    data["revenue"] / data["count"] if data["count"] > 0 else 0
                ),
            }
            for day, data in sorted(orders_by_weekday.items())
        ]

        # Статистика по времени обработки заказов
        processing_times = []
        for order in all_orders:
            if order.queued_at and order.handoff_at:
                # Вычисляем время в секундах
                processing_time = (order.handoff_at - order.queued_at).total_seconds()
                processing_times.append(processing_time)

        # Вычисляем статистику по времени
        queue_stats = {}
        if processing_times:
            queue_stats = {
                "avg_time": sum(processing_times) / len(processing_times),
                "min_time": min(processing_times),
                "max_time": max(processing_times),
                "total_orders_with_time": len(processing_times),
            }
        else:
            queue_stats = {
                "avg_time": 0,
                "min_time": 0,
                "max_time": 0,
                "total_orders_with_time": 0,
            }

        return JsonResponse(
            {
                "period": {
                    "start_date": start_date_str,
                    "end_date": end_date_str,
                    "days": days,
                },
                "summary": {
                    "total_revenue": total_revenue,
                    "total_orders": total_orders,
                    "avg_order_value": avg_order_value,
                    "paid_orders": paid_orders,
                    "unpaid_orders": unpaid_orders,
                    "paid_revenue": paid_revenue,
                },
                "revenue_by_day": revenue_by_day,
                "top_products": top_products,
                "hourly_stats": hourly_stats,
                "weekday_stats": weekday_stats,
                "queue_stats": queue_stats,
            }
        )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
