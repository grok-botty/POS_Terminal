from .models import User, Category, Product


def init_database():
    if User.objects.count() == 0:
        admin = User(username="admin", role="admin")
        admin.set_password("admin")
        admin.save()
        print("✅ Создан администратор: admin/admin")

        user = User(username="user", role="user")
        user.set_password("user")
        user.save()
        print("✅ Создан пользователь: user/user")

    if Category.objects.count() == 0:
        drinks = Category.objects.create(name="Напитки", slug="drinks", order=1)
        syrups = Category.objects.create(name="Сиропы", slug="syrups", order=2)
        addons = Category.objects.create(name="Добавки", slug="addons", order=3)
        season = Category.objects.create(name="Сезон", slug="season", order=4)
        print("✅ Созданы категории")

        Product.objects.create(name="Латте", price=250, category=drinks)
        Product.objects.create(name="Капучино", price=230, category=drinks)
        Product.objects.create(name="Американо", price=180, category=drinks)
        Product.objects.create(name="Чай", price=150, category=drinks)
        Product.objects.create(name="Матча", price=280, category=drinks)
        Product.objects.create(name="Какао", price=200, category=drinks)
        print("✅ Созданы продукты")
