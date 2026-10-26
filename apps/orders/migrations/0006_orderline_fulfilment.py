from django.db import migrations, models


def copy_order_fulfilment_onto_lines(apps, schema_editor):
    """Старые строки наследуют формат заказа. Новое значение по умолчанию — «здесь»."""
    OrderLine = apps.get_model("orders", "OrderLine")
    OrderLine.objects.filter(order__fulfilment="to_go").update(fulfilment="to_go")


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0005_handout_and_queue_hold"),
    ]

    operations = [
        migrations.AlterField(
            model_name="order",
            name="fulfilment",
            field=models.CharField(
                choices=[
                    ("here", "В зале"),
                    ("to_go", "С собой"),
                    ("own_cup", "В свою"),
                ],
                default="here",
                help_text=(
                    "Формат пустого заказа. У позиций формат свой: общая пилюля "
                    "на карточке есть только когда он совпадает у всех строк."
                ),
                max_length=8,
                verbose_name="Формат",
            ),
        ),
        migrations.AddField(
            model_name="orderline",
            name="fulfilment",
            field=models.CharField(
                choices=[
                    ("here", "В зале"),
                    ("to_go", "С собой"),
                    ("own_cup", "В свою"),
                ],
                default="here",
                help_text="здесь, с собой или своя тара. У каждой позиции своё значение.",
                max_length=8,
                verbose_name="Формат",
            ),
        ),
        migrations.RunPython(
            copy_order_fulfilment_onto_lines, migrations.RunPython.noop
        ),
    ]
