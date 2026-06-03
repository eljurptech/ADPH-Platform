from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from flask_mail import Mail, Message
from database import db, Psicologo, Empresa, Trabajador, Test, Evaluacion, Plan, PsicologoEmpresa, ResultadoTest
from datetime import datetime, timedelta
import os
import json
import secrets
from dotenv import load_dotenv

load_dotenv()

# Crear la aplicación Flask
app = Flask(__name__)

# Configuraciones
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'clave-secreta-por-defecto-123456')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configuración de email (opcional)
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')

# Inicializar extensiones
db.init_app(app)
bcrypt = Bcrypt(app)
mail = Mail(app)

# Configurar login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Por favor inicia sesión para continuar'

@login_manager.user_loader
def load_user(user_id):
    return Psicologo.query.get(int(user_id))

# ==================== RUTAS PÚBLICAS ====================

@app.route('/')
def index():
    """Página de inicio pública"""
    planes = Plan.query.filter_by(activo=True).all()
    return render_template('index.html', planes=planes)

@app.route('/planes')
def planes():
    planes = Plan.query.filter_by(activo=True).all()
    return render_template('planes.html', planes=planes)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        psicologo = Psicologo.query.filter_by(email=email).first()
        
        if psicologo and bcrypt.check_password_hash(psicologo.password, password):
            login_user(psicologo)
            
            if email == os.environ.get('ADMIN_EMAIL', 'admin@adphgroup.com'):
                return redirect(url_for('admin_dashboard'))
            
            return redirect(url_for('dashboard'))
        else:
            flash('Email o contraseña incorrectos', 'danger')
    
    return render_template('auth/login.html')

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        registro_profesional = request.form.get('registro_profesional')
        especialidad = request.form.get('especialidad')
        plan_id = request.form.get('plan_id')
        
        if password != confirm_password:
            flash('Las contraseñas no coinciden', 'danger')
            return redirect(url_for('registro'))
        
        existe = Psicologo.query.filter_by(email=email).first()
        if existe:
            flash('Este email ya está registrado', 'danger')
            return redirect(url_for('registro'))
        
        plan = Plan.query.get(plan_id)
        if not plan:
            plan = Plan.query.filter_by(nombre='Básico').first()
        
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        
        nuevo_psicologo = Psicologo(
            nombre=nombre,
            email=email,
            password=hashed_password,
            registro_profesional=registro_profesional,
            especialidad=especialidad,
            plan_id=plan.id,
            max_empresas=plan.max_empresas,
            max_trabajadores_mes=plan.max_trabajadores_mes,
            fecha_vencimiento=datetime.utcnow() + timedelta(days=30),
            estado_pago='activo'
        )
        
        db.session.add(nuevo_psicologo)
        db.session.commit()
        
        flash('Registro exitoso. Ahora puedes iniciar sesión', 'success')
        return redirect(url_for('login'))
    
    planes = Plan.query.filter_by(activo=True).all()
    return render_template('auth/registro.html', planes=planes)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# ==================== RUTAS PARA PSICÓLOGOS ====================

@app.route('/dashboard')
@login_required
def dashboard():
    total_empresas = PsicologoEmpresa.query.filter_by(psicologo_id=current_user.id, activo=True).count()
    total_evaluaciones = Evaluacion.query.filter_by(psicologo_id=current_user.id).count()
    evaluaciones_pendientes = Evaluacion.query.filter_by(psicologo_id=current_user.id, estado='pendiente').count()
    evaluaciones_recientes = Evaluacion.query.filter_by(psicologo_id=current_user.id).order_by(Evaluacion.created_at.desc()).limit(5).all()
    
    dias_restantes = 0
    if current_user.fecha_vencimiento:
        dias_restantes = (current_user.fecha_vencimiento - datetime.utcnow()).days
    
    return render_template('psicologo/dashboard.html',
                         total_empresas=total_empresas,
                         total_evaluaciones=total_evaluaciones,
                         evaluaciones_pendientes=evaluaciones_pendientes,
                         evaluaciones_recientes=evaluaciones_recientes,
                         dias_restantes=dias_restantes)

@app.route('/psicologo/empresas')
@login_required
def psicologo_empresas():
    relaciones = PsicologoEmpresa.query.filter_by(psicologo_id=current_user.id, activo=True).all()
    empresas = [rel.empresa for rel in relaciones]
    return render_template('psicologo/empresas.html', empresas=empresas)

@app.route('/psicologo/empresa/agregar', methods=['GET', 'POST'])
@login_required
def psicologo_agregar_empresa():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        rubro = request.form.get('rubro')
        email_contacto = request.form.get('email_contacto')
        telefono = request.form.get('telefono')
        
        empresas_actuales = PsicologoEmpresa.query.filter_by(psicologo_id=current_user.id, activo=True).count()
        if empresas_actuales >= current_user.max_empresas:
            flash(f'Haz alcanzado el límite de {current_user.max_empresas} empresas', 'warning')
            return redirect(url_for('psicologo_empresas'))
        
        nueva_empresa = Empresa(
            nombre=nombre,
            rubro=rubro,
            email_contacto=email_contacto,
            telefono=telefono
        )
        db.session.add(nueva_empresa)
        db.session.flush()
        
        relacion = PsicologoEmpresa(
            psicologo_id=current_user.id,
            empresa_id=nueva_empresa.id
        )
        db.session.add(relacion)
        db.session.commit()
        
        flash('Empresa agregada exitosamente', 'success')
        return redirect(url_for('psicologo_empresas'))
    
    return render_template('psicologo/agregar_empresa.html')

@app.route('/psicologo/tests')
@login_required
def psicologo_tests():
    tests = Test.query.filter_by(activo=True).all()
    return render_template('psicologo/tests.html', tests=tests)

@app.route('/psicologo/evaluacion/nueva', methods=['GET', 'POST'])
@login_required
def psicologo_nueva_evaluacion():
    if request.method == 'POST':
        empresa_id = request.form.get('empresa_id')
        test_id = request.form.get('test_id')
        emails = request.form.get('emails')
        fecha_expiracion = request.form.get('fecha_expiracion')
        
        empresa = Empresa.query.get(empresa_id)
        test = Test.query.get(test_id)
        
        lista_emails = [e.strip() for e in emails.replace('\r', '\n').replace('\n', ',').split(',') if e.strip()]
        
        for email in lista_emails:
            trabajador = Trabajador.query.filter_by(email=email, empresa_id=empresa_id).first()
            if not trabajador:
                nombre = email.split('@')[0].replace('.', ' ').title()
                trabajador = Trabajador(
                    nombre=nombre,
                    email=email,
                    empresa_id=empresa_id
                )
                db.session.add(trabajador)
                db.session.flush()
            
            evaluacion = Evaluacion(
                test_id=test_id,
                psicologo_id=current_user.id,
                empresa_id=empresa_id,
                trabajador_id=trabajador.id,
                fecha_envio=datetime.utcnow(),
                estado='pendiente'
            )
            evaluacion.generar_token()
            
            if fecha_expiracion:
                evaluacion.fecha_expiracion = datetime.strptime(fecha_expiracion, '%Y-%m-%d')
            else:
                evaluacion.fecha_expiracion = datetime.utcnow() + timedelta(days=7)
            
            db.session.add(evaluacion)
        
        db.session.commit()
        flash('Evaluaciones creadas exitosamente', 'success')
        return redirect(url_for('psicologo_evaluaciones'))
    
    empresas_rel = PsicologoEmpresa.query.filter_by(psicologo_id=current_user.id, activo=True).all()
    empresas = [rel.empresa for rel in empresas_rel]
    tests = Test.query.filter_by(activo=True).all()
    
    return render_template('psicologo/nueva_evaluacion.html', empresas=empresas, tests=tests)

@app.route('/psicologo/evaluaciones')
@login_required
def psicologo_evaluaciones():
    evaluaciones = Evaluacion.query.filter_by(psicologo_id=current_user.id).order_by(Evaluacion.created_at.desc()).all()
    return render_template('psicologo/evaluaciones.html', evaluaciones=evaluaciones)

@app.route('/psicologo/evaluacion/<int:evaluacion_id>')
@login_required
def psicologo_ver_evaluacion(evaluacion_id):
    evaluacion = Evaluacion.query.get_or_404(evaluacion_id)
    if evaluacion.psicologo_id != current_user.id:
        flash('No tienes permiso', 'danger')
        return redirect(url_for('psicologo_evaluaciones'))
    
    test = Test.query.get(evaluacion.test_id)
    respuestas = json.loads(evaluacion.respuestas) if evaluacion.respuestas else {}
    
    return render_template('psicologo/ver_evaluacion.html', 
                         evaluacion=evaluacion, 
                         test=test, 
                         respuestas=respuestas)

@app.route('/psicologo/mi-plan')
@login_required
def psicologo_mi_plan():
    plan = Plan.query.get(current_user.plan_id)
    dias_restantes = 0
    if current_user.fecha_vencimiento:
        dias_restantes = (current_user.fecha_vencimiento - datetime.utcnow()).days
    
    evaluaciones_este_mes = Evaluacion.query.filter(
        Evaluacion.psicologo_id == current_user.id,
        Evaluacion.created_at >= datetime.utcnow().replace(day=1)
    ).count()
    
    empresas_actuales = PsicologoEmpresa.query.filter_by(psicologo_id=current_user.id, activo=True).count()
    
    return render_template('psicologo/mi_plan.html',
                         plan=plan,
                         dias_restantes=dias_restantes,
                         evaluaciones_este_mes=evaluaciones_este_mes,
                         empresas_actuales=empresas_actuales,
                         limite_empresas=current_user.max_empresas,
                         limite_evaluaciones=current_user.max_evaluaciones_mes)

# ==================== RUTAS PARA EVALUAR (TRABAJADOR) ====================

@app.route('/evaluar/<token>')
def evaluar_trabajador(token):
    evaluacion = Evaluacion.query.filter_by(token_unico=token).first()
    
    if not evaluacion:
        return render_template('error.html', mensaje='Link inválido o expirado')
    
    if evaluacion.estado == 'completada':
        return render_template('error.html', mensaje='Esta evaluación ya fue completada')
    
    if evaluacion.fecha_expiracion and evaluacion.fecha_expiracion < datetime.utcnow():
        return render_template('error.html', mensaje='Este link ha expirado')
    
    test = Test.query.get(evaluacion.test_id)
    preguntas = json.loads(test.preguntas) if test.preguntas else []
    
    return render_template('evaluar/test.html', 
                         evaluacion=evaluacion, 
                         test=test, 
                         preguntas=preguntas)

@app.route('/guardar_respuestas/<token>', methods=['POST'])
def guardar_respuestas(token):
    evaluacion = Evaluacion.query.filter_by(token_unico=token).first()
    
    if not evaluacion:
        return jsonify({'error': 'Evaluación no encontrada'}), 404
    
    if evaluacion.estado == 'completada':
        return jsonify({'error': 'Ya fue completada'}), 400
    
    respuestas = request.json.get('respuestas', {})
    evaluacion.respuestas = json.dumps(respuestas)
    evaluacion.fecha_respuesta = datetime.utcnow()
    evaluacion.estado = 'completada'
    
    # Calcular puntaje
    puntajes = [int(v) for v in respuestas.values() if v]
    if puntajes:
        evaluacion.puntaje_total = sum(puntajes) / len(puntajes)
        
        if evaluacion.puntaje_total <= 2:
            evaluacion.nivel_riesgo = 'Bajo'
            evaluacion.recomendaciones = 'El trabajador presenta bajo riesgo. Mantener buenas prácticas.'
        elif evaluacion.puntaje_total <= 3.5:
            evaluacion.nivel_riesgo = 'Medio'
            evaluacion.recomendaciones = 'Se recomienda implementar mejoras específicas y monitorear.'
        else:
            evaluacion.nivel_riesgo = 'Alto'
            evaluacion.recomendaciones = 'Requiere intervención prioritaria. Diseñar programa de acción.'
    
    db.session.commit()
    return jsonify({'success': True})

@app.route('/gracias')
def gracias():
    return render_template('evaluar/gracias.html')

# ==================== RUTAS PARA ADMIN ====================

@app.route('/admin')
@login_required
def admin_dashboard():
    if current_user.email != os.environ.get('ADMIN_EMAIL', 'admin@adphgroup.com'):
        return redirect(url_for('dashboard'))
    
    total_psicologos = Psicologo.query.count()
    total_empresas = Empresa.query.count()
    total_evaluaciones = Evaluacion.query.count()
    total_tests = Test.query.count()
    
    return render_template('admin/dashboard.html',
                         total_psicologos=total_psicologos,
                         total_empresas=total_empresas,
                         total_evaluaciones=total_evaluaciones,
                         total_tests=total_tests)

# ==================== INICIALIZAR BASE DE DATOS ====================

def init_default_data():
    """Crear datos iniciales si no existen"""
    
    # Crear planes
    if Plan.query.count() == 0:
        planes_data = [
            {'nombre': 'Básico', 'precio_mensual': 99, 'max_empresas': 3, 'max_trabajadores_mes': 50, 'max_evaluaciones_mes': 100},
            {'nombre': 'Profesional', 'precio_mensual': 199, 'max_empresas': 10, 'max_trabajadores_mes': 200, 'max_evaluaciones_mes': 500, 'tiene_soporte': True, 'tiene_excel': True},
            {'nombre': 'Empresarial', 'precio_mensual': 399, 'max_empresas': 999, 'max_trabajadores_mes': 9999, 'max_evaluaciones_mes': 9999, 'tiene_soporte': True, 'tiene_excel': True, 'tiene_api': True}
        ]
        for p in planes_data:
            plan = Plan(**p)
            db.session.add(plan)
        db.session.commit()
        print("✅ Planes creados")
    
    # Crear tests
    if Test.query.count() == 0:
        tests_data = [
            {
                'nombre': 'Riesgos Psicosociales NOM-035',
                'descripcion': 'Evaluación de factores de riesgo psicosocial',
                'categoria': 'psicosocial',
                'duracion_estimada': 15,
                'instrucciones': 'Responde con honestidad. No hay respuestas correctas.',
                'preguntas': json.dumps([
                    "¿Trabajas bajo presión de tiempo?",
                    "¿Tu trabajo requiere mucho esfuerzo mental?",
                    "¿Tienes tiempo suficiente para tus tareas?",
                    "¿Recibes apoyo de tus compañeros?",
                    "¿Tu trabajo es valorado?"
                ]),
                'algoritmo': 'promedio'
            }
        ]
        for t in tests_data:
            test = Test(**t)
            db.session.add(test)
        db.session.commit()
        print("✅ Tests creados")
    
    # Crear admin
    admin_email = os.environ.get('ADMIN_EMAIL', 'admin@adphgroup.com')
    admin = Psicologo.query.filter_by(email=admin_email).first()
    if not admin:
        plan = Plan.query.filter_by(nombre='Empresarial').first()
        hashed = bcrypt.generate_password_hash(os.environ.get('ADMIN_PASSWORD', 'Admin123!')).decode('utf-8')
        admin = Psicologo(
            nombre='ADPH Group Admin',
            email=admin_email,
            password=hashed,
            especialidad='Administrador',
            plan_id=plan.id if plan else None,
            max_empresas=9999,
            max_trabajadores_mes=9999,
            fecha_vencimiento=datetime.utcnow() + timedelta(days=3650),
            estado_pago='activo'
        )
        db.session.add(admin)
        db.session.commit()
        print("✅ Usuario admin creado")

# ==================== EJECUTAR ====================

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        init_default_data()
    app.run(debug=True, host='0.0.0.0', port=5000)