from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0004_shift_start_time"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="auto_ready_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Момент, когда все позиции отмечены «отдали» и заказ оплачен. Через 5 секунд статус становится «Готово», если галочку сняли или оплату убрали раньше.",
                null=True,
                verbose_name="Автоготово с",
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="cancelled_at",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="Отменён в"
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="main_queue_until",
            field=models.DateTimeField(
                blank=True,
                help_text="Оплаченное «Готово» и «Отменено» остаются в основной очереди до этого момента (13 секунд), затем видны только в «Готовые» или «Отмена».",
                null=True,
                verbose_name="В основной очереди до",
            ),
        ),
        migrations.AddField(
            model_name="orderline",
            name="handed_out",
            field=models.BooleanField(
                default=False,
                help_text="Позицию уже отдали гостю. На карточке очереди это галочка.",
                verbose_name="Отдали",
            ),
        ),
    ]
