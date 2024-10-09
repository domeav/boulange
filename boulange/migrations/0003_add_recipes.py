# Generated by Django 5.1 on 2024-08-18 07:12

from django.db import migrations


def populate_products(apps, schema_editor):
    Ingredient = apps.get_model("boulange", "Ingredient")
    Product = apps.get_model("boulange", "Product")
    ProductLine = apps.get_model("boulange", "ProductLine")

    # Nature
    ref_GN = Product(name="Semi-complet nature (1 kg)", ref="GN", price=5)
    ref_GN.save()
    GN_ingredients = [
        (Ingredient.objects.get(name="Farine blé"), 637),
        (Ingredient.objects.get(name="Eau"), 414),
        (Ingredient.objects.get(name="Levain"), 178),
        (Ingredient.objects.get(name="Sel"), 11),
    ]
    for ing in GN_ingredients:
        ProductLine(product=ref_GN, ingredient=ing[0], quantity=ing[1]).save()
    ref_TGN = Product(
        name="Semi-complet nature (2 kg)",
        ref="TGN",
        price=10,
        orig_product=ref_GN,
        coef=2,
    )
    ref_TGN.save()
    ref_PN = Product(
        name="Semi-complet nature (500 g)",
        ref="PN",
        price=2.7,
        orig_product=ref_GN,
        coef=0.5,
    )
    ref_PN.save()
    # Lin
    ref_GL = Product(name="Semi-complet Lin (1 kg)", ref="GL", price=6.5)
    ref_GL.save()
    GL_ingredients = [
        (Ingredient.objects.get(name="Farine blé"), 585),
        (Ingredient.objects.get(name="Eau"), 409),
        (Ingredient.objects.get(name="Levain"), 164),
        (Ingredient.objects.get(name="Sel"), 11),
        (Ingredient.objects.get(name="Graines lin"), 76),
    ]
    for ing in GL_ingredients:
        ProductLine(product=ref_GL, ingredient=ing[0], quantity=ing[1]).save()
    ref_TGL = Product(
        name="Semi-complet lin (2 kg)", ref="TGL", price=13, orig_product=ref_GL, coef=2
    )
    ref_TGL.save()
    ref_PL = Product(
        name="Semi-complet lin (500 g)",
        ref="PL",
        price=3.5,
        orig_product=ref_GL,
        coef=0.5,
    )
    ref_PL.save()
    # Kasha
    ref_GK = Product(name="Semi-complet Kasha (1 kg)", ref="GK", price=6.5)
    ref_GK.save()
    GK_ingredients = [
        (Ingredient.objects.get(name="Farine blé"), 599),
        (Ingredient.objects.get(name="Eau"), 389),
        (Ingredient.objects.get(name="Levain"), 168),
        (Ingredient.objects.get(name="Sel"), 11),
        (Ingredient.objects.get(name="Graines kasha"), 78),
    ]
    for ing in GK_ingredients:
        ProductLine(product=ref_GK, ingredient=ing[0], quantity=ing[1]).save()
    ref_TGK = Product(
        name="Semi-complet kasha (2 kg)",
        ref="TGK",
        price=13,
        orig_product=ref_GK,
        coef=2,
    )
    ref_TGK.save()
    ref_PK = Product(
        name="Semi-complet kasha (500 g)",
        ref="PK",
        price=3.5,
        orig_product=ref_GK,
        coef=0.5,
    )
    ref_PK.save()
    # sarrasin
    ref_GSa = Product(name="Sarrasin 100% (800 g)", ref="GSa", price=6.5)
    ref_GSa.save()
    GSa_ingredients = [
        (Ingredient.objects.get(name="Farine sarrasin"), 549 * 0.8),
        (Ingredient.objects.get(name="Eau"), 549 * 0.8),
        (Ingredient.objects.get(name="Levain"), 165 * 0.8),
        (Ingredient.objects.get(name="Sel"), 11 * 0.8),
    ]
    for ing in GSa_ingredients:
        ProductLine(product=ref_GSa, ingredient=ing[0], quantity=ing[1]).save()
    ref_PSa = Product(
        name="Sarrasin 100% (400 g)",
        ref="PSa",
        price=3.5,
        orig_product=ref_GSa,
        coef=0.5,
    )
    ref_PSa.save()
    # seigle
    ref_GSe = Product(name="Seigle 100% (800 g)", ref="GSe", price=5)
    ref_GSe.save()
    GSe_ingredients = [
        (Ingredient.objects.get(name="Farine blé"), 197 * 0.8),
        (Ingredient.objects.get(name="Farine seigle"), 461 * 0.8),
        (Ingredient.objects.get(name="Eau"), 428 * 0.8),
        (Ingredient.objects.get(name="Levain"), 184 * 0.8),
        (Ingredient.objects.get(name="Sel"), 12 * 0.8),
    ]
    for ing in GSe_ingredients:
        ProductLine(product=ref_GSe, ingredient=ing[0], quantity=ing[1]).save()
    ref_PSe = Product(
        name="Seigle 100% (400 g)", ref="PSe", price=2.7, orig_product=ref_GSe, coef=0.5
    )
    ref_PSe.save()

    # brioches
    BR = Product(name="Brioche raisin", ref="BR", price=4.7)
    BR.save()
    BR_ingredients = [
        (Ingredient.objects.get(name="Farine blé"), 493),
        (Ingredient.objects.get(name="Lait"), 296),
        (Ingredient.objects.get(name="Huile"), 49),
        (Ingredient.objects.get(name="Levain"), 256),
        (Ingredient.objects.get(name="Sel"), 6),
        (Ingredient.objects.get(name="Sucre"), 69),
        (Ingredient.objects.get(name="Raisins secs"), 94),
    ]
    for ing in BR_ingredients:
        ProductLine(product=BR, ingredient=ing[0], quantity=ing[1]).save()
    BC = Product(name="Brioche chocolat", ref="BC", price=5.7)
    BC.save()
    BC_ingredients = [
        (Ingredient.objects.get(name="Farine blé"), 493),
        (Ingredient.objects.get(name="Lait"), 296),
        (Ingredient.objects.get(name="Huile"), 49),
        (Ingredient.objects.get(name="Levain"), 256),
        (Ingredient.objects.get(name="Sel"), 6),
        (Ingredient.objects.get(name="Sucre"), 69),
        (Ingredient.objects.get(name="Pépites de chocolat"), 94),
    ]
    for ing in BC_ingredients:
        ProductLine(product=BC, ingredient=ing[0], quantity=ing[1]).save()
    # gâteaux/biscuits
    cookie = Product(name="Cookie", ref="COOKIE", price=2, nb_units=12)
    cookie.save()
    cookie_ingredients = [
        (Ingredient.objects.get(name="Farine blé"), 400),
        (Ingredient.objects.get(name="Eau"), 120),
        (Ingredient.objects.get(name="Beurre"), 200),
        (Ingredient.objects.get(name="Oeufs"), 3),
        (Ingredient.objects.get(name="Levain"), 150),
        (Ingredient.objects.get(name="Sucre"), 100),
        (Ingredient.objects.get(name="Pépites de chocolat"), 200),
        (Ingredient.objects.get(name="Noisettes"), 120),
    ]
    for ing in cookie_ingredients:
        ProductLine(product=cookie, ingredient=ing[0], quantity=ing[1]).save()
    gateau_breton = Product(name="Gâteau breton", ref="BRETON", price=12)
    gateau_breton.save()
    gateau_breton_ingredients = [
        (Ingredient.objects.get(name="Farine blé"), 500),
        (Ingredient.objects.get(name="Eau"), 90),
        (Ingredient.objects.get(name="Beurre"), 400),
        (Ingredient.objects.get(name="Oeufs"), 6),
        (Ingredient.objects.get(name="Sucre"), 300),
    ]
    for ing in gateau_breton_ingredients:
        ProductLine(product=gateau_breton, ingredient=ing[0], quantity=ing[1]).save()
    gateau_argent = Product(name="Gâteau d'argent", ref="ARGENT", price=2, nb_units=15)
    gateau_argent.save()
    gateau_argent_ingredients = [
        (Ingredient.objects.get(name="Farine blé"), 450),
        (Ingredient.objects.get(name="Eau"), 90),
        (Ingredient.objects.get(name="Oeufs"), 15),
        (Ingredient.objects.get(name="Huile"), 200),
        (Ingredient.objects.get(name="Sucre"), 250),
    ]
    for ing in gateau_argent_ingredients:
        ProductLine(product=gateau_argent, ingredient=ing[0], quantity=ing[1]).save()
    far = Product(name="Far", ref="FAR", price=15)
    far.save()
    far_ingredients = [
        (Ingredient.objects.get(name="Farine blé"), 375),
        (Ingredient.objects.get(name="Lait"), 1500),
        (Ingredient.objects.get(name="Oeufs"), 6),
        (Ingredient.objects.get(name="Beurre"), 30),
        (Ingredient.objects.get(name="Sucre"), 250),
        (Ingredient.objects.get(name="Pruneaux"), 375),
    ]
    for ing in far_ingredients:
        ProductLine(product=far, ingredient=ing[0], quantity=ing[1]).save()

    ref_PATON = Product(name="Pâton pizza (x1)", ref="PATON", price=1.8)
    ref_PATON.save()
    PATON_ingredients = [
        (Ingredient.objects.get(name="Farine blé"), 125),
        (Ingredient.objects.get(name="Eau"), 75),
        (Ingredient.objects.get(name="Huile olive"), 75),
        (Ingredient.objects.get(name="Levain"), 25),
        (Ingredient.objects.get(name="Sel"), 3.5),
        (Ingredient.objects.get(name="Herbes de provence"), 2.5),
    ]
    for ing in PATON_ingredients:
        ProductLine(product=ref_PATON, ingredient=ing[0], quantity=ing[1]).save()
    ref_PATON5 = Product(
        name="Pâton pizza (x5)", ref="PATON5", price=8, orig_product=ref_PATON, coef=5
    )
    ref_PATON5.save()


class Migration(migrations.Migration):

    dependencies = [
        ("boulange", "0002_ingredients"),
    ]

    operations = [migrations.RunPython(populate_products)]
