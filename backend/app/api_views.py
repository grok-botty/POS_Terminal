import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .models import User, Category, Product, Order, OrderLine, DailySummary
from .auth import create_access_token, login_required, admin_required, get_current_user
from datetime import datetime


@csrf_exempt
@require_http_methods(["POST"])
def login(request):
    try:
        data = json.loads(request.body)
        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            return JsonResponse(
                {"error": "Требуется имя пользователя и пароль"}, status=400
            )

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return JsonResponse(
                {"error": "Неверное имя пользователя или пароль"}, status=401
            )

        if not user.check_password(password):
            return JsonResponse(
                {"error": "Неверное имя пользователя или пароль"}, status=401
            )

        token = create_access_token(user.id, user.username, user.role)

        return JsonResponse(
            {
                "token": token,
                "user": {"id": user.id, "username": user.username, "role": user.role},
            }
        )
    except Exception as e:
        import traceback

        print(f"❌ Ошибка при логине: {e}")
        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)


@require_http_methods(["GET"])
@login_required
def me(request):
    user = request.user
    return JsonResponse({"id": user.id, "username": user.username, "role": user.role})


@require_http_methods(["GET"])
@login_required
def get_categories(request):
    categories = Category.objects.all()
    return JsonResponse(
        {
            "categories": [
                {
                    "id": cat.id,
                    "name": cat.name,
                    "slug": cat.slug,
                    "order": cat.order,
                    "is_addon": cat.is_addon,
                }
                for cat in categories
            ]
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
@admin_required
def create_category(request):
    try:
        data = json.loads(request.body)
        name = data.get("name")
        slug = data.get("slug")

        if not name or not slug:
            return JsonResponse({"error": "Требуется название и slug"}, status=400)

        category = Category.objects.create(
            name=name,
            slug=slug,
            order=data.get("order", 0),
            is_addon=data.get("is_addon", False),
        )

        return JsonResponse(
            {
                "id": category.id,
                "name": category.name,
                "slug": category.slug,
                "order": category.order,
                "is_addon": category.is_addon,
            }
        )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["PUT"])
@admin_required
def update_category(request, category_id):
    try:
        category = Category.objects.get(id=category_id)
        data = json.loads(request.body)

        if "name" in data:
            category.name = data["name"]
        if "slug" in data:
            category.slug = data["slug"]
        if "order" in data:
            category.order = data["order"]
        if "is_addon" in data:
            category.is_addon = data["is_addon"]

        category.save()

        return JsonResponse(
            {
                "id": category.id,
                "name": category.name,
                "slug": category.slug,
                "order": category.order,
                "is_addon": category.is_addon,
            }
        )
    except Category.DoesNotExist:
        return JsonResponse({"error": "Категория не найдена"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["DELETE"])
@admin_required
def delete_category(request, category_id):
    try:
        category = Category.objects.get(id=category_id)
        category.delete()
        return JsonResponse({"success": True})
    except Category.DoesNotExist:
        return JsonResponse({"error": "Категория не найдена"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@require_http_methods(["GET"])
@login_required
def get_products(request):
    category_id = request.GET.get("category_id")

    if category_id:
        products = Product.objects.filter(category_id=category_id, is_active=True)
    else:
        products = Product.objects.filter(is_active=True)

    return JsonResponse(
        {
            "products": [
                {
                    "id": prod.id,
                    "name": prod.name,
                    "price": prod.price,
                    "category_id": prod.category_id,
                    "is_active": prod.is_active,
                }
                for prod in products
            ]
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
@admin_required
def create_product(request):
    try:
        data = json.loads(request.body)
        name = data.get("name")
        price = data.get("price")
        category_id = data.get("category_id")

        if not name or price is None or not category_id:
            return JsonResponse(
                {"error": "Требуется название, цена и категория"}, status=400
            )

        product = Product.objects.create(
            name=name,
            price=float(price),
            category_id=category_id,
            is_active=data.get("is_active", True),
        )

        return JsonResponse(
            {
                "id": product.id,
                "name": product.name,
                "price": product.price,
                "category_id": product.category_id,
                "is_active": product.is_active,
            }
        )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["PUT"])
@admin_required
def update_product(request, product_id):
    try:
        product = Product.objects.get(id=product_id)
        data = json.loads(request.body)

        if "name" in data:
            product.name = data["name"]
        if "price" in data:
            product.price = float(data["price"])
        if "category_id" in data:
            product.category_id = data["category_id"]
        if "is_active" in data:
            product.is_active = data["is_active"]

        product.save()

        return JsonResponse(
            {
                "id": product.id,
                "name": product.name,
                "price": product.price,
                "category_id": product.category_id,
                "is_active": product.is_active,
            }
        )
    except Product.DoesNotExist:
        return JsonResponse({"error": "Продукт не найден"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["DELETE"])
@admin_required
def delete_product(request, product_id):
    try:
        product = Product.objects.get(id=product_id)
        product.delete()
        return JsonResponse({"success": True})
    except Product.DoesNotExist:
        return JsonResponse({"error": "Продукт не найден"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@require_http_methods(["GET"])
@admin_required
def get_orders_by_date(request):
    """Получить все заказы за конкретную дату"""
    try:
        date = request.GET.get("date")
        if not date:
            return JsonResponse({"error": "Требуется параметр date"}, status=400)

        try:
            daily_summary = DailySummary.objects.get(date=date)
        except DailySummary.DoesNotExist:
            return JsonResponse(
                {
                    "date": date,
                    "total_revenue": 0,
                    "total_orders": 0,
                    "orders": [],
                }
            )

        orders = Order.objects.filter(daily_summary=daily_summary).order_by(
            "-created_at"
        )

        orders_data = []
        for order in orders:
            lines = OrderLine.objects.filter(order=order)
            lines_data = [
                {
                    "product_id": line.product_id,
                    "name": line.name,
                    "price": line.price,
                    "qty": line.qty,
                }
                for line in lines
            ]

            orders_data.append(
                {
                    "id": order.id,
                    "order_id": order.order_id,
                    "name": order.name,
                    "comment": order.comment,
                    "status": order.status,
                    "total": order.total,
                    "is_paid": order.is_paid,
                    "created_at": order.created_at.isoformat(),
                    "lines": lines_data,
                }
            )

        return JsonResponse(
            {
                "date": date,
                "total_revenue": daily_summary.total_revenue,
                "total_orders": daily_summary.total_orders,
                "orders": orders_data,
            }
        )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["PUT"])
@admin_required
def update_order(request, order_id):
    """Обновить заказ"""
    try:
        order = Order.objects.get(id=order_id)
        data = json.loads(request.body)

        if "name" in data:
            order.name = data["name"]
        if "comment" in data:
            order.comment = data["comment"]
        if "status" in data:
            order.status = data["status"]
        if "is_paid" in data:
            order.is_paid = data["is_paid"]

        # Если обновляются позиции заказа
        if "lines" in data:
            # Удаляем старые позиции
            OrderLine.objects.filter(order=order).delete()

            # Создаем новые позиции и пересчитываем total
            total = 0
            for line_data in data["lines"]:
                OrderLine.objects.create(
                    order=order,
                    product_id=line_data["product_id"],
                    name=line_data["name"],
                    price=line_data["price"],
                    qty=line_data["qty"],
                )
                total += line_data["price"] * line_data["qty"]

            order.total = total

        order.save()

        # Пересчитываем дневную сводку
        daily_summary = order.daily_summary
        orders = Order.objects.filter(daily_summary=daily_summary)
        daily_summary.total_revenue = sum(o.total for o in orders if o.is_paid)
        daily_summary.total_orders = orders.count()
        daily_summary.save()

        # Возвращаем обновленный заказ
        lines = OrderLine.objects.filter(order=order)
        lines_data = [
            {
                "product_id": line.product_id,
                "name": line.name,
                "price": line.price,
                "qty": line.qty,
            }
            for line in lines
        ]

        return JsonResponse(
            {
                "id": order.id,
                "order_id": order.order_id,
                "name": order.name,
                "comment": order.comment,
                "status": order.status,
                "total": order.total,
                "is_paid": order.is_paid,
                "created_at": order.created_at.isoformat(),
                "lines": lines_data,
            }
        )
    except Order.DoesNotExist:
        return JsonResponse({"error": "Заказ не найден"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["DELETE"])
@admin_required
def delete_order(request, order_id):
    """Удалить заказ"""
    try:
        order = Order.objects.get(id=order_id)
        daily_summary = order.daily_summary

        # Удаляем заказ (позиции удалятся автоматически через CASCADE)
        order.delete()

        # Пересчитываем дневную сводку
        orders = Order.objects.filter(daily_summary=daily_summary)
        daily_summary.total_revenue = sum(o.total for o in orders if o.is_paid)
        daily_summary.total_orders = orders.count()
        daily_summary.save()

        return JsonResponse({"success": True})
    except Order.DoesNotExist:
        return JsonResponse({"error": "Заказ не найден"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
