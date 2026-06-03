from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

# ==================== MODELOS DE DATOS ====================

class Plan(db.Model):
    """Planes de suscripción para psicólogos"""
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), nullable=False)
    precio_mensual = db.Column(db.Float, nullable=False)
    max_empresas = db.Column(db.Integer, default=3)
    max_trabajadores_mes = db.Column(db.Integer, default=50)
    max_evaluaciones_mes = db.Column(db.Integer, default=100)
    tiene_soporte = db.Column(db.Boolean, default=False)
    tiene_excel = db.Column(db.Boolean, default=False)
    tiene_api = db.Column(db.Boolean, default=False)
    activo = db.Column(db.Boolean, default=True)

class Psicologo(UserMixin, db.Model):
    """Psicólogo suscriptor"""
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    registro_profesional = db.Column(db.String(50))
    especialidad = db.Column(db.String(100))
    telefono = db.Column(db.String(20))
    plan_id = db.Column(db.Integer, db.ForeignKey('plan.id'))
    fecha_suscripcion = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_vencimiento = db.Column(db.DateTime)
    estado_pago = db.Column(db.String(20), default='activo')
    max_empresas = db.Column(db.Integer, default=3)
    max_trabajadores_mes = db.Column(db.Integer, default=50)
    max_evaluaciones_mes = db.Column(db.Integer, default=100)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Empresa(db.Model):
    """Empresa cliente del psicólogo"""
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    rubro = db.Column(db.String(50))
    email_contacto = db.Column(db.String(100))
    telefono = db.Column(db.String(20))
    direccion = db.Column(db.String(200))
    logo = db.Column(db.String(200))
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)
    activa = db.Column(db.Boolean, default=True)
    
    # Relaciones
    trabajadores = db.relationship('Trabajador', backref='empresa', lazy=True)

class PsicologoEmpresa(db.Model):
    """Relación psicólogo-empresa"""
    id = db.Column(db.Integer, primary_key=True)
    psicologo_id = db.Column(db.Integer, db.ForeignKey('psicologo.id'))
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'))
    fecha_asignacion = db.Column(db.DateTime, default=datetime.utcnow)
    activo = db.Column(db.Boolean, default=True)

class Trabajador(db.Model):
    """Trabajador evaluado"""
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100))
    edad = db.Column(db.Integer)
    puesto = db.Column(db.String(100))
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'))
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)

class Test(db.Model):
    """Tests disponibles"""
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text)
    categoria = db.Column(db.String(50))
    duracion_estimada = db.Column(db.Integer)
    instrucciones = db.Column(db.Text)
    preguntas = db.Column(db.Text)  # JSON
    algoritmo = db.Column(db.String(50))
    activo = db.Column(db.Boolean, default=True)

class Evaluacion(db.Model):
    """Evaluación realizada"""
    id = db.Column(db.Integer, primary_key=True)
    test_id = db.Column(db.Integer, db.ForeignKey('test.id'))
    psicologo_id = db.Column(db.Integer, db.ForeignKey('psicologo.id'))
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'))
    trabajador_id = db.Column(db.Integer, db.ForeignKey('trabajador.id'))
    token_unico = db.Column(db.String(100), unique=True)
    fecha_envio = db.Column(db.DateTime)
    fecha_expiracion = db.Column(db.DateTime)
    fecha_respuesta = db.Column(db.DateTime)
    respuestas = db.Column(db.Text)
    puntaje_total = db.Column(db.Float)
    nivel_riesgo = db.Column(db.String(20))
    recomendaciones = db.Column(db.Text)
    estado = db.Column(db.String(20), default='pendiente')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def generar_token(self):
        import secrets
        self.token_unico = secrets.token_urlsafe(32)

class ResultadoTest(db.Model):
    """Resultados detallados"""
    id = db.Column(db.Integer, primary_key=True)
    evaluacion_id = db.Column(db.Integer, db.ForeignKey('evaluacion.id'))
    factor_nombre = db.Column(db.String(100))
    puntaje = db.Column(db.Float)
    nivel = db.Column(db.String(20))
    recomendacion = db.Column(db.Text)