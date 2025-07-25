from app import app, db, Category

with app.app_context():
    print("Veritabanı tabloları oluşturuluyor...")
    db.create_all()
    print("Tablolar başarıyla oluşturuldu.")

    # Kategoriler boşsa, varsayılanları ekle
    if Category.query.count() == 0:
        print("Varsayılan kategoriler ekleniyor...")
        default_categories = ['Elektronik', 'Kitap', 'Giyim', 'Ev & Yaşam', 'Kozmetik']
        for cat_name in default_categories:
            db.session.add(Category(name=cat_name))
        db.session.commit()
        print("Kategoriler eklendi.")
    else:
        print("Kategoriler zaten mevcut.")