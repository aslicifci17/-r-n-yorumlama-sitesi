import os
import uuid
from PIL import Image
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# --- UYGULAMA KURULUMU ---
app = Flask(__name__)
db = SQLAlchemy()

project_dir = os.path.dirname(os.path.abspath(__file__))
database_file = f"sqlite:///{os.path.join(project_dir, 'instance/site.db')}"

app.config['SECRET_KEY'] = 'bu-cok-gizli-bir-anahtar'
app.config['SQLALCHEMY_DATABASE_URI'] = database_file
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(project_dir, 'static', 'uploads')

db.init_app(app)

# --- VERİTABANI MODELLERİ ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    image_file = db.Column(db.String(40), nullable=False, default='default.jpg')
    products = db.relationship('Product', backref='author', lazy=True)
    comments = db.relationship('Comment', backref='author', lazy=True)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    def __repr__(self):
        return f"Category('{self.name}')"

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    image_path = db.Column(db.String(200), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    category = db.relationship('Category', backref=db.backref('products', lazy=True))
    comments = db.relationship('Comment', backref='product', lazy=True, cascade="all, delete-orphan")
    @property
    def avg_rating(self):
        if not self.comments:
            return 0
        total_rating = sum(comment.rating for comment in self.comments)
        return round(total_rating / len(self.comments), 1)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    date_posted = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)

# --- OTOMATİK İŞLEMLER ---
@app.context_processor
def inject_categories():
    try:
        categories = Category.query.order_by(Category.name).all()
        return dict(all_categories=categories)
    except Exception:
        return dict(all_categories=[])

# --- YARDIMCI FONKSİYONLAR ---
def save_picture(form_picture):
    random_hex = str(uuid.uuid4().hex)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(app.root_path, 'static/profile_pics', picture_fn)
    output_size = (150, 150)
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path)
    return picture_fn

# --- ROTALAR (SAYFALAR) ---
@app.route("/")
def index():
    page = request.args.get('page', 1, type=int)
    query = request.args.get('q')
    category_id = request.args.get('category_id', type=int)
    product_query = Product.query
    if category_id:
        product_query = product_query.filter_by(category_id=category_id)
    if query:
        search = f"%{query}%"
        product_query = product_query.filter(db.or_(Product.name.ilike(search), Product.description.ilike(search)))
    products_pagination = product_query.order_by(Product.id.desc()).paginate(page=page, per_page=9)
    return render_template('index.html', products_pagination=products_pagination)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        user_exists = User.query.filter_by(username=username).first()
        if user_exists:
            flash('Bu kullanıcı adı zaten alınmış. Lütfen başka bir tane seçin.', 'danger')
            return redirect(url_for('register'))
        email_exists = User.query.filter_by(email=email).first()
        if email_exists:
            flash('Bu e-posta adresi zaten kayıtlı.', 'danger')
            return redirect(url_for('register'))
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, email=email, password_hash=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('Hesabınız başarıyla oluşturuldu! Şimdi giriş yapabilirsiniz.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Kullanıcıyı kullanıcı adına göre veritabanından bul
        user = User.query.filter_by(username=username).first()
        
        # Kullanıcı varsa ve girilen şifre veritabanındaki hash ile eşleşiyorsa
        if user and check_password_hash(user.password_hash, password):
            # Kullanıcı bilgilerini session'a kaydet
            session['user_id'] = user.id
            session['username'] = user.username
            session['user_image'] = user.image_file  # Profil fotoğrafını session'a ekle
            
            flash('Başarıyla giriş yaptınız!', 'success')
            return redirect(url_for('index'))
        else:
            # Kullanıcı yoksa veya şifre yanlışsa
            flash('Giriş başarısız. Lütfen kullanıcı adınızı ve şifrenizi kontrol edin.', 'danger')
            return redirect(url_for('login'))
            
    # Eğer GET isteği ise, sadece giriş formunu göster
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    session.pop('user_image', None)
    flash('Başarıyla çıkış yaptınız.', 'info')
    return redirect(url_for('login'))

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'user_id' not in session:
        flash('Ürün yüklemek için lütfen giriş yapın.', 'danger')
        return redirect(url_for('login'))
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        category_id = request.form.get('category_id')
        if 'image' not in request.files:
            flash('Formda resim dosyası bölümü bulunamadı!', 'danger')
            return redirect(request.url)
        image_file = request.files['image']
        if image_file.filename == '':
            flash('Lütfen bir resim dosyası seçin!', 'danger')
            return redirect(request.url)
        if image_file:
            file_extension = os.path.splitext(image_file.filename)[1]
            unique_filename = str(uuid.uuid4()) + file_extension
            image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
            new_product = Product(name=name, description=description, image_path=os.path.join('uploads', unique_filename).replace('\\', '/'), user_id=session['user_id'], category_id=category_id)
            db.session.add(new_product)
            db.session.commit()
            flash('Ürün başarıyla eklendi!', 'success')
            return redirect(url_for('index'))
    return render_template('upload.html')

@app.route('/product/<int:product_id>', methods=['GET', 'POST'])
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    if request.method == 'POST':
        if 'user_id' not in session:
            flash('Yorum yapmak için lütfen giriş yapın.', 'danger')
            return redirect(url_for('login'))
        comment_text = request.form.get('comment_text')
        rating = request.form.get('rating')
        if comment_text and rating:
            new_comment = Comment(text=comment_text, rating=int(rating), user_id=session['user_id'], product_id=product.id)
            db.session.add(new_comment)
            db.session.commit()
            flash('Yorumunuz ve puanınız başarıyla eklendi.', 'success')
            return redirect(url_for('product_detail', product_id=product.id))
        else:
            flash('Lütfen hem puan verin hem de yorum yazın.', 'danger')
            return redirect(url_for('product_detail', product_id=product.id))
    comments = Comment.query.filter_by(product_id=product.id).order_by(Comment.date_posted.desc()).all()
    return render_template('product_detail.html', product=product, comments=comments)

@app.route('/product/<int:product_id>/delete', methods=['POST'])
def delete_product(product_id):
    if 'user_id' not in session:
        flash('Bu işlemi yapmak için giriş yapmalısınız.', 'danger')
        return redirect(url_for('login'))
    product = Product.query.get_or_404(product_id)
    if product.author.id != session['user_id']:
        flash('Bu ürünü silme yetkiniz yok.', 'danger')
        return redirect(url_for('product_detail', product_id=product.id))
    try:
        image_path_full = os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(product.image_path))
        if os.path.exists(image_path_full):
            os.remove(image_path_full)
    except Exception as e:
        print(f"Dosya silinirken hata oluştu: {e}")
    db.session.delete(product)
    db.session.commit()
    flash('Ürün başarıyla silindi.', 'success')
    return redirect(url_for('index'))

@app.route('/product/<int:product_id>/edit', methods=['GET', 'POST'])
def edit_product(product_id):
    if 'user_id' not in session:
        flash('Bu işlemi yapmak için giriş yapmalısınız.', 'danger')
        return redirect(url_for('login'))
    product = Product.query.get_or_404(product_id)
    if product.author.id != session['user_id']:
        flash('Bu ürünü düzenleme yetkiniz yok.', 'danger')
        return redirect(url_for('product_detail', product_id=product.id))
    if request.method == 'POST':
        product.name = request.form.get('name')
        product.description = request.form.get('description')
        product.category_id = request.form.get('category_id')
        db.session.commit()
        flash('Ürün başarıyla güncellendi.', 'success')
        return redirect(url_for('product_detail', product_id=product.id))
    return render_template('edit_product.html', product=product)

@app.route('/profile/<string:username>')
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    page = request.args.get('page', 1, type=int)
    products_pagination = Product.query.filter_by(author=user).order_by(Product.id.desc()).paginate(page=page, per_page=6)
    return render_template('profile.html', user=user, products_pagination=products_pagination)
    
@app.route('/comment/<int:comment_id>/delete', methods=['POST'])
def delete_comment(comment_id):
    if 'user_id' not in session:
        flash('Bu işlemi yapmak için giriş yapmalısınız.', 'danger')
        return redirect(url_for('login'))
    comment = Comment.query.get_or_404(comment_id)
    product_id = comment.product.id
    if comment.author.id != session['user_id']:
        flash('Bu yorumu silme yetkiniz yok.', 'danger')
        return redirect(url_for('product_detail', product_id=product_id))
    db.session.delete(comment)
    db.session.commit()
    flash('Yorumunuz başarıyla silindi.', 'success')
    return redirect(url_for('product_detail', product_id=product_id))

@app.route('/comment/<int:comment_id>/edit', methods=['GET', 'POST'])
def edit_comment(comment_id):
    if 'user_id' not in session:
        flash('Bu işlemi yapmak için giriş yapmalısınız.', 'danger')
        return redirect(url_for('login'))
    comment = Comment.query.get_or_404(comment_id)
    product_id = comment.product.id
    if comment.author.id != session['user_id']:
        flash('Bu yorumu düzenleme yetkiniz yok.', 'danger')
        return redirect(url_for('product_detail', product_id=product_id))
    if request.method == 'POST':
        comment.text = request.form.get('comment_text')
        db.session.commit()
        flash('Yorumunuz başarıyla güncellendi.', 'success')
        return redirect(url_for('product_detail', product_id=product_id))
    return render_template('edit_comment.html', comment=comment)

@app.route('/account', methods=['GET', 'POST'])
def account():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])

    if request.method == 'POST':
        if 'picture' in request.files:
            picture_file = request.files['picture']
            if picture_file.filename != '':
                if user.image_file != 'default.jpg':
                    old_picture_path = os.path.join(app.root_path, 'static/profile_pics', user.image_file)
                    if os.path.exists(old_picture_path):
                        os.remove(old_picture_path)
                
                picture_filename = save_picture(picture_file)
                user.image_file = picture_filename
                db.session.commit()
                flash('Profil fotoğrafınız güncellendi!', 'success')
                return redirect(url_for('account'))

    return render_template('account.html', current_user=user)

@app.cli.command("init-db")
def init_db_command():
    """Veritabanını temizler ve yeniden oluşturur."""
    db.create_all()
    print("Veritabanı tabloları oluşturuldu.")
    if Category.query.count() == 0:
        print("Varsayılan kategoriler ekleniyor...")
        default_categories = ['Elektronik', 'Kitap', 'Giyim', 'Ev & Yaşam', 'Kozmetik']
        for cat_name in default_categories:
            db.session.add(Category(name=cat_name))
        db.session.commit()
        print("Kategoriler eklendi.")
    else:
        print("Kategoriler zaten mevcut.")


# --- UYGULAMAYI ÇALIŞTIRMA BLOĞU ---

@app.cli.command("init-db")
def init_db_command():
    """Veritabanını temizler ve yeniden oluşturur."""
    db.create_all()
    print("Veritabanı tabloları oluşturuldu.")
    if Category.query.count() == 0:
        print("Varsayılan kategoriler ekleniyor...")
        default_categories = ['Elektronik', 'Kitap', 'Giyim', 'Ev & Yaşam', 'Kozmetik']
        for cat_name in default_categories:
            db.session.add(Category(name=cat_name))
        db.session.commit()
        print("Kategoriler eklendi.")
    else:
        print("Kategoriler zaten mevcut.")

if __name__ == '__main__':
    app.run(debug=True)