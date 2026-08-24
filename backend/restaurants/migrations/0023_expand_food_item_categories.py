from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('restaurants', '0022_restaurant_delivery_mode'),
    ]

    operations = [
        migrations.AlterField(
            model_name='fooditem',
            name='food_categ',
            field=models.CharField(
                choices=[
                    ('Vegetarian', 'Vegetarian'),
                    ('Non-Vegetarian', 'Non-Vegetarian'),
                    ('Beverages', 'Beverages'),
                    ('Desserts', 'Desserts'),
                    ('Staples', 'Staples'),
                    ('Fresh Produce', 'Fresh Produce'),
                    ('Dairy & Eggs', 'Dairy & Eggs'),
                    ('Household', 'Household'),
                    ('Medicines', 'Medicines'),
                    ('Wellness', 'Wellness'),
                    ('Personal Care', 'Personal Care'),
                    ('Baby Care', 'Baby Care'),
                    ('First Aid', 'First Aid'),
                    ('Clothing', 'Clothing'),
                    ('Electronics', 'Electronics'),
                    ('Home Goods', 'Home Goods'),
                    ('Beauty', 'Beauty'),
                    ('Accessories', 'Accessories'),
                    ('Parcel Delivery', 'Parcel Delivery'),
                    ('Document Delivery', 'Document Delivery'),
                    ('Same-day Delivery', 'Same-day Delivery'),
                    ('Bulk Delivery', 'Bulk Delivery'),
                    ('Handmade Goods', 'Handmade Goods'),
                    ('Local Services', 'Local Services'),
                    ('Repairs', 'Repairs'),
                    ('Beauty Services', 'Beauty Services'),
                    ('Tailoring', 'Tailoring'),
                    ('Electronics Repair', 'Electronics Repair'),
                    ('Home Services', 'Home Services'),
                    ('Mobile Money Services', 'Mobile Money Services'),
                    ('Printing & Documents', 'Printing & Documents'),
                    ('Other Local Items', 'Other Local Items'),
                ],
                max_length=40,
            ),
        ),
    ]
