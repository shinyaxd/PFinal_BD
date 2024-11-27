from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mysqldb import MySQL
from neo4j import GraphDatabase

# Configuración de la app
app = Flask(__name__)
app.secret_key = 'prueba123'

# Configuración de conexión a MySQL
app.config['MYSQL_HOST'] = 'autorack.proxy.rlwy.net'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'HbftwOUFIhcqzaaXcbvQMTFNRUZFHsEV'
app.config['MYSQL_DB'] = 'parcialD'
app.config['MYSQL_PORT'] = 55854

# Inicialización de MySQL
mysql = MySQL(app)

# Configuración de Neo4j
NEO4J_URI = "bolt://52.70.23.42:7687"  # Cambiar si estás usando un servidor remoto
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "pushups-railroad-war"

# Crear la conexión a Neo4j
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def crear_paciente_en_neo4j(paciente_id, nombre, apellido_paterno, apellido_materno):
    """Crear un nodo de Paciente en Neo4j."""
    with driver.session() as session:
        session.run(
            """
            CREATE (p:Paciente {
                id: $paciente_id,
                nombre: $nombre,
                apellido_paterno: $apellido_paterno,
                apellido_materno: $apellido_materno
            })
            """,
            paciente_id=paciente_id,
            nombre=nombre,
            apellido_paterno=apellido_paterno,
            apellido_materno=apellido_materno,
        )

# --- Rutas ---

# Pantalla inicial (opción para doctor o paciente)
@app.route('/')
def inicio():
    return render_template('inicio.html')

# Login para doctores
@app.route('/loginDoctor', methods=['GET', 'POST'])
def login_doctor():
    if request.method == 'POST':
        DocumentoIdentidad = request.form['DocumentoIdentidad']
        Contraseña = request.form['Contraseña']

        # Buscar el doctor en la base de datos
        cursor = mysql.connection.cursor()
        cursor.execute(
            "SELECT idLogin_Doctor, Contraseña FROM Login_Doctor WHERE DocumentoIdentidad = %s",
            (DocumentoIdentidad,)
        )
        user = cursor.fetchone()

        if user:  # Si encontramos al doctor
            id_doctor = user[0]
            stored_password = user[1]  # Contraseña almacenada en la base de datos

            # Verificar si la contraseña coincide
            if stored_password == Contraseña:
                session['loggedin'] = True
                session['idLogin_Doctor'] = id_doctor
                session['DocumentoIdentidad'] = DocumentoIdentidad
                flash('Inicio de sesión exitoso como doctor.', 'success')
                return redirect(url_for('dashboard_doctor'))
            else:
                flash('Contraseña incorrecta.', 'danger')
        else:
            flash('Usuario no encontrado.', 'danger')

    return render_template('login_doctor.html')

# Login para pacientes
@app.route('/loginPaciente', methods=['GET', 'POST'])
def login_paciente():
    if request.method == 'POST':
        documento = request.form['DocumentoIdentidad']
        contraseña = request.form['Contraseña']

        cursor = mysql.connection.cursor()
        cursor.execute("SELECT idLogin_Paciente, Contraseña FROM Login_Paciente WHERE DocumentoIdentidad = %s", (documento,))
        user = cursor.fetchone()

        if user and user[1] == contraseña:  # Comparar contraseñas directamente
            session['loggedin'] = True
            session['idLogin_Paciente'] = user[0]
            session['DocumentoIdentidad'] = documento
            flash('Inicio de sesión exitoso.', 'success')
            return redirect(url_for('dashboard_paciente'))
        else:
            flash('Credenciales incorrectas.', 'danger')

    return render_template('login_paciente.html')

# Dashboard para doctores
@app.route('/dashboardDoctor')
def dashboard_doctor():
    if 'loggedin' in session:  # Verifica si el doctor está logueado
        id_doctor = session['idLogin_Doctor']

        cursor = mysql.connection.cursor()

        # Obtener el nombre del doctor
        cursor.execute("SELECT Nombre FROM Informacion_Doctor WHERE idInformacion_Doctor = %s", (id_doctor,))
        doctor = cursor.fetchone()

        # Obtener los pacientes asignados al doctor
        cursor.execute("""
            SELECT p.idInformacion_Paciente, p.Nombre, p.ApellidoPaterno, p.ApellidoMaterno
            FROM DoctorPaciente dp
            INNER JOIN Informacion_Paciente p ON dp.idLogin_Paciente = p.idInformacion_Paciente
            WHERE dp.idLogin_Doctor = %s
        """, (id_doctor,))
        pacientes = cursor.fetchall()

        # Renderizar el dashboard con el nombre del doctor y los pacientes
        return render_template('dashboard_doctor.html', doctor=doctor, pacientes=pacientes)
    else:
        flash('Por favor, inicia sesión como doctor.', 'danger')
        return redirect(url_for('login_doctor'))

# Vista Doctor -> Paciente
@app.route('/paciente/<int:id_paciente>', methods=['GET', 'POST'])
def ver_paciente(id_paciente):
    if 'loggedin' not in session:
        flash('Por favor, inicia sesión como doctor.', 'danger')
        return redirect(url_for('login_doctor'))

    cursor = mysql.connection.cursor()

    # Obtener información del paciente, reserva y asistencia
    cursor.execute("""
    SELECT p.Nombre, p.ApellidoPaterno, p.ApellidoMaterno, p.FechaNacimiento,
           r.FechaReserva, ar.AsistioPaciente, e.NombreEspecialidad
    FROM Informacion_Paciente p
    LEFT JOIN Reserva r ON p.idInformacion_Paciente = r.Informacion_Paciente_idInformacion_Paciente
    LEFT JOIN AtencionRealizada ar ON r.idReserva = ar.Reserva_idReserva
    LEFT JOIN Especialidad e ON r.Especialidad_idEspecialidad = e.idEspecialidad
    WHERE p.idInformacion_Paciente = %s
    """, (id_paciente,))
    paciente = cursor.fetchone()

    if not paciente:
        flash('El paciente no existe o no está asignado a este doctor.', 'danger')
        return redirect(url_for('dashboard_doctor'))

    # Si el formulario para marcar asistencia fue enviado
    if request.method == 'POST':
        if 'marcar_asistencia' in request.form:
            asistio = request.form['asistio']
            cursor.execute("""
                UPDATE AtencionRealizada
                SET AsistioPaciente = %s
                WHERE Reserva_idReserva = (
                    SELECT idReserva
                    FROM Reserva
                    WHERE Informacion_Paciente_idInformacion_Paciente = %s
                )
            """, (asistio, id_paciente))
            mysql.connection.commit()
            flash('Estado de asistencia actualizado.', 'success')
            return redirect(url_for('ver_paciente', id_paciente=id_paciente))

        # Si se envió el historial médico
        elif 'guardar_historial' in request.form:
            observaciones = request.form['observaciones']
            atencion_realizada = request.form['atencion_realizada']

            # Insertar en Historial_Medico
            cursor.execute("""
                INSERT INTO Historial_Medico (Informacion_Paciente_idInformacion_Paciente, 
                                              AtencionRealizada_idAtencionRealizada, 
                                              FechaRegistro, Observaciones)
                VALUES (%s, %s, NOW(), %s)
            """, (id_paciente, atencion_realizada, observaciones))
            mysql.connection.commit()

            # Obtener el ID del historial médico recién creado
            cursor.execute("SELECT LAST_INSERT_ID()")
            id_historial = cursor.fetchone()[0]

            # Insertar medicamentos asociados al historial
            medicamento = request.form['medicamento']
            dosis = request.form['dosis']
            frecuencia = request.form['frecuencia']
            duracion = request.form['duracion']

            cursor.execute("""
                INSERT INTO Medicamentos (NombreMedicamento, Dosis, Frecuencia, Duración, HistorialMedico_idHistorialMedico)
                VALUES (%s, %s, %s, %s, %s)
            """, (medicamento, dosis, frecuencia, duracion, id_historial))
            mysql.connection.commit()

            flash('Historial médico y medicamentos guardados con éxito.', 'success')
            return redirect(url_for('ver_paciente', id_paciente=id_paciente))

    return render_template('ver_paciente.html', paciente=paciente)

# Dashboard para pacientes
@app.route('/dashboard_paciente')
def dashboard_paciente():
    if 'loggedin' in session:
        id_paciente = session['idLogin_Paciente']

        cursor = mysql.connection.cursor()
        # Query para obtener la información de los doctores asignados
        cursor.execute("""
            SELECT d.idInformacion_Doctor, d.Nombre, d.ApellidoPaterno, d.ApellidoMaterno, e.NombreEspecialidad, r.FechaReserva
            FROM Reserva r
            INNER JOIN Informacion_Doctor d ON r.Informacion_Doctor_idInformacion_Doctor = d.idInformacion_Doctor
            INNER JOIN Especialidad e ON r.Especialidad_idEspecialidad = e.idEspecialidad
            WHERE r.Informacion_Paciente_idInformacion_Paciente = %s
        """, (id_paciente,))
        doctores = cursor.fetchall()

        return render_template('dashboard_paciente.html', doctores=doctores)
    else:
        flash('Por favor, inicia sesión como paciente.', 'danger')
        return redirect(url_for('login_paciente'))

# Vista paciente -> doctor
@app.route('/doctor/<int:id_doctor>')
def ver_doctor(id_doctor):
    cursor = mysql.connection.cursor()

    # Obtener información del doctor
    cursor.execute("""
        SELECT Nombre, ApellidoPaterno, ApellidoMaterno, NumeroDocumento, FechaNacimiento
        FROM Informacion_Doctor
        WHERE idInformacion_Doctor = %s
    """, (id_doctor,))
    doctor = cursor.fetchone()

    if doctor:
        return render_template('ver_doctor.html', doctor=doctor)
    else:
        flash('Doctor no encontrado.', 'danger')
        return redirect(url_for('dashboard_paciente'))

# Historial Medico
@app.route('/historialMedico')
def historial_medico():
    if 'loggedin' in session and 'idLogin_Paciente' in session:
        id_paciente = session['idLogin_Paciente']

        cursor = mysql.connection.cursor()

        # Obtener el historial médico del paciente
        cursor.execute("""
            SELECT h.FechaRegistro, h.Observaciones, m.NombreMedicamento, m.Dosis, m.Frecuencia, m.Duración
            FROM Historial_Medico h
            LEFT JOIN Medicamentos m ON h.idHistorialMedico = m.HistorialMedico_idHistorialMedico
            WHERE h.Informacion_Paciente_idInformacion_Paciente = %s
        """, (id_paciente,))
        historial = cursor.fetchall()

        return render_template('historial_medico.html', historial=historial)
    else:
        flash('Por favor, inicia sesión como paciente.', 'danger')
        return redirect(url_for('login_paciente'))

# Crear nueva cita (paciente registrado anteriormente)
@app.route('/nueva_cita', methods=['GET', 'POST'])
def nueva_cita():
    if 'loggedin' not in session or 'idLogin_Paciente' not in session:
        flash('Por favor, inicia sesión como paciente.', 'danger')
        return redirect(url_for('login_paciente'))

    cursor = mysql.connection.cursor()

    # Obtener la lista de especialidades
    cursor.execute("SELECT idEspecialidad, NombreEspecialidad FROM Especialidad")
    especialidades = cursor.fetchall()

    if request.method == 'POST':
        especialidad_id = request.form['especialidad']
        fecha_reserva = request.form['fecha']
        id_paciente = session['idLogin_Paciente']

        # Asignar un doctor aleatorio para la especialidad
        cursor.execute("""
            SELECT d.idInformacion_Doctor
            FROM Informacion_Doctor d
            INNER JOIN DoctorEspecialidadAsociada dea
            ON d.idInformacion_Doctor = dea.Informacion_Doctor_idInformacion_Paciente
            WHERE dea.Especialidad_idEspecialidad = %s
            ORDER BY RAND()
            LIMIT 1
        """, (especialidad_id,))
        doctor = cursor.fetchone()

        if doctor:
            doctor_id = doctor[0]

            # Asignar un consultorio aleatorio
            cursor.execute("SELECT idConsultorio FROM Consultorio ORDER BY RAND() LIMIT 1")
            consultorio = cursor.fetchone()
            consultorio_id = consultorio[0] if consultorio else None

            if consultorio_id:
                # Crear la nueva reserva
                cursor.execute("""
                    INSERT INTO Reserva (Informacion_Paciente_idInformacion_Paciente, 
                                         Informacion_Doctor_idInformacion_Doctor, 
                                         Especialidad_idEspecialidad, 
                                         FechaReserva, 
                                         Consultorio_idConsultorio)
                    VALUES (%s, %s, %s, %s, %s)
                """, (id_paciente, doctor_id, especialidad_id, fecha_reserva, consultorio_id))
                mysql.connection.commit()
                flash('Cita generada con éxito.', 'success')
                # Redirigir al dashboard para actualizar automáticamente los doctores
                return redirect(url_for('dashboard_paciente'))
            else:
                flash('No hay consultorios disponibles.', 'danger')
        else:
            flash('No hay doctores disponibles para esta especialidad.', 'danger')

    return render_template('nueva_cita.html', especialidades=especialidades)

# Citas
@app.route('/registro_cita', methods=['GET', 'POST'])
def registro_cita():
    if request.method == 'POST':
        # Datos del formulario
        tipo_documento = request.form.get('tipo_documento')
        numero_documento = request.form.get('numero_documento')
        nombre = request.form.get('nombre')
        apellido_paterno = request.form.get('apellido_paterno')
        apellido_materno = request.form.get('apellido_materno')
        fecha_nacimiento = request.form.get('fecha_nacimiento')
        fecha_reserva = request.form.get('fecha_reserva')
        especialidad_id = request.form.get('especialidad')
        numero_celular = request.form.get('numero_celular')
        contraseña = request.form.get('contraseña')

        try:
            cursor = mysql.connection.cursor()

            # Verificar si el paciente ya existe
            cursor.execute("""
                SELECT idInformacion_Paciente FROM Informacion_Paciente WHERE NumeroDocumento = %s
            """, (numero_documento,))
            paciente_existente = cursor.fetchone()

            if paciente_existente:
                flash('El paciente ya está registrado. Por favor, inicia sesión para continuar.', 'danger')
                return redirect(url_for('login_paciente'))

            # Insertar un nuevo paciente en `Informacion_Paciente`
            cursor.execute("""
                INSERT INTO Informacion_Paciente (TipoDeDocumento, NumeroDocumento, Nombre, ApellidoPaterno, ApellidoMaterno, FechaNacimiento, FechaAfiliacion, EsAfiliado)
                VALUES (%s, %s, %s, %s, %s, %s, CURDATE(), 1)
            """, (tipo_documento, numero_documento, nombre, apellido_paterno, apellido_materno, fecha_nacimiento))
            mysql.connection.commit()

            # Obtener el ID del paciente recién registrado
            cursor.execute("SELECT LAST_INSERT_ID()")
            id_paciente = cursor.fetchone()[0]

            # Insertar el número de celular en `contacto_Paciente`
            cursor.execute("""
                INSERT INTO contacto_Paciente (celular, Informacion_Paciente_idInformacion_Paciente)
                VALUES (%s, %s)
            """, (numero_celular, id_paciente))
            mysql.connection.commit()

            # Insertar el login del paciente
            cursor.execute("""
                INSERT INTO Login_Paciente (DocumentoIdentidad, Contraseña)
                VALUES (%s, %s)
            """, (numero_documento, contraseña))
            mysql.connection.commit()

            # Crear el nodo en Neo4j
            crear_paciente_en_neo4j(id_paciente, nombre, apellido_paterno, apellido_materno)

            # Asignar un doctor aleatorio para la especialidad seleccionada
            cursor.execute("""
                SELECT d.idInformacion_Doctor
                FROM Informacion_Doctor d
                INNER JOIN DoctorEspecialidadAsociada dea
                ON d.idInformacion_Doctor = dea.Informacion_Doctor_idInformacion_Doctor
                WHERE dea.Especialidad_idEspecialidad = %s
                ORDER BY RAND()
                LIMIT 1
            """, (especialidad_id,))
            doctor = cursor.fetchone()

            if doctor:
                doctor_id = doctor[0]

                # Asignar un consultorio aleatorio
                cursor.execute("SELECT idConsultorio FROM Consultorio ORDER BY RAND() LIMIT 1")
                consultorio = cursor.fetchone()
                consultorio_id = consultorio[0] if consultorio else None

                if consultorio_id:
                    # Crear la nueva reserva
                    # Crear una reserva de cita
                    cursor.execute("""
                        INSERT INTO Reserva (Informacion_Paciente_idInformacion_Paciente, 
                                            Informacion_Doctor_idInformacion_Doctor, 
                                            Especialidad_idEspecialidad, 
                                            FechaReserva, 
                                            Consultorio_idConsultorio)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (id_paciente, doctor_id, especialidad_id, fecha_reserva, consultorio_id))
                    mysql.connection.commit()

                    flash('Paciente registrado y cita programada con éxito.', 'success')
                    # Redirigir al dashboard para actualizar automáticamente los doctores
                    return redirect(url_for('dashboard_paciente'))
                else:
                    flash('No hay consultorios disponibles.', 'danger')
            else:
                flash('No hay doctores disponibles para esta especialidad.', 'danger')

        except Exception as e:
            mysql.connection.rollback()
            print("Error:", e)
            flash(f'Ocurrió un error: {e}', 'danger')
            return redirect(url_for('registro_cita'))

    # Obtener especialidades para mostrar en el formulario
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT idEspecialidad, NombreEspecialidad FROM Especialidad")
    especialidades = cursor.fetchall()

    return render_template('registro_cita.html', especialidades=especialidades)

# Logout
@app.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión exitosamente.', 'info')
    return redirect(url_for('inicio'))

# Neo4j
@app.teardown_appcontext
def close_connections(exception=None):
    """Cerrar conexiones al apagar la aplicación."""
    driver.close()

# Ejecutar la app
if __name__ == '__main__':
    app.run(debug=True)



