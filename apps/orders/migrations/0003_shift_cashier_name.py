from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0002_kassa_addons_and_shift"),
    ]

    operations = [
        migrations.AddField(
            model_name="shift",
            name="cashier_name",
            field=models.CharField(
                blank=True,
                help_text="Имя на кассе, как его вписали при открытии смены.",
                max_length=100,
                verbose_name="Кассир",
            ),
        ),
    ]
