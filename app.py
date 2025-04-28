import os
from flask import Flask, request, jsonify, render_template, abort
from pymongo import MongoClient
from bson import ObjectId # Para manejar los ObjectIds de MongoDB
from bson.errors import InvalidId # Para capturar errores de ID inválido
import math # Para calcular el total de páginas

# --- Configuración ---
app = Flask(__name__) # Crea la instancia de la aplicación Flask

# Configuración de MongoDB (mejor usar variables de entorno en producción)
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
DB_NAME = 'series-temporales'
COLLECTION_NAME = 'taxis'
DEFAULT_PAGE_LIMIT = 10 # Elementos por página por defecto

# --- Conexión a MongoDB ---
try:
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME] # Accede a la base de datos
    taxis_collection = db[COLLECTION_NAME] # Accede a la colección
    # Prueba la conexión
    client.admin.command('ping')
    print("¡Conexión a MongoDB exitosa!")
except Exception as e:
    print(f"Error al conectar a MongoDB: {e}")
    # Podrías querer salir o manejar esto de otra forma si la DB es esencial
    taxis_collection = None # Indica que la colección no está disponible


# --- Rutas de la API ---

# GET /api/taxis - Listar taxis con paginación
@app.route('/api/taxis', methods=['GET'])
def get_taxis():
    if taxis_collection is None:
        return jsonify({"message": "Error: Base de datos no inicializada"}), 500

    try:
        # Obtener parámetros de paginación de la query string
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', DEFAULT_PAGE_LIMIT))
        skip = (page - 1) * limit

        # Obtener el número total de documentos para calcular las páginas
        total_count = taxis_collection.count_documents({})
        total_pages = math.ceil(total_count / limit)

        # Realizar la consulta paginada
        # Proyectamos los campos que queremos, excluyendo _id si no se necesita explícitamente en la lista básica
        # Convertimos _id a string para que sea serializable en JSON
        taxis_cursor = taxis_collection.find({}, {'_id': 1, 'Matricula': 1, 'Clase': 1, 'Marca': 1, 'Categoria': 1}).skip(skip).limit(limit)

        taxis_list = []
        for taxi in taxis_cursor:
            taxi['_id'] = str(taxi['_id']) # Convertir ObjectId a string
            taxis_list.append(taxi)

        return jsonify({
            "data": taxis_list,
            "pagination": {
                "currentPage": page,
                "totalPages": total_pages,
                "limit": limit,
                "totalCount": total_count,
                "hasNextPage": page < total_pages,
                "hasPrevPage": page > 1
            }
        }), 200

    except Exception as e:
        print(f"Error al obtener taxis: {e}")
        return jsonify({"message": "Error interno al obtener la lista de taxis"}), 500


# POST /api/taxis - Crear un nuevo taxi
@app.route('/api/taxis', methods=['POST'])
def create_taxi():
    if taxis_collection is None:
        return jsonify({"message": "Error: Base de datos no inicializada"}), 500

    try:
        data = request.get_json()
        if not data or not data.get('Matricula') or not data.get('Marca'):
             # Añade validaciones más específicas según necesites
            return jsonify({"message": "Datos incompletos. Se requiere al menos Matrícula y Marca."}), 400

        # Asegúrate de que solo los campos esperados se inserten
        new_taxi_data = {
            "Matricula": data.get('Matricula'),
            "Clase": data.get('Clase'),
            "Marca": data.get('Marca'),
            "Categoria": data.get('Categoria')
            # Puedes añadir campos adicionales o timestamps aquí si es necesario
            # "createdAt": datetime.datetime.utcnow()
        }

        result = taxis_collection.insert_one(new_taxi_data)

        # Recuperar el documento insertado para devolverlo
        created_taxi = taxis_collection.find_one({"_id": result.inserted_id})
        if created_taxi:
             created_taxi['_id'] = str(created_taxi['_id']) # Convertir ObjectId a string
             return jsonify(created_taxi), 201
        else:
             return jsonify({"message": "Taxi creado pero no se pudo recuperar"}), 201 # O un error 500

    except Exception as e:
        print(f"Error al crear taxi: {e}")
        return jsonify({"message": "Error interno al crear el taxi"}), 500


# PUT /api/taxis/<id> - Actualizar un taxi existente
@app.route('/api/taxis/<string:id>', methods=['PUT'])
def update_taxi(id):
    if taxis_collection is None:
        return jsonify({"message": "Error: Base de datos no inicializada"}), 500

    try:
        # Validar el ObjectId
        try:
            obj_id = ObjectId(id)
        except InvalidId:
            return jsonify({"message": "ID de Taxi inválido"}), 400

        data = request.get_json()
        if not data:
            return jsonify({"message": "No se proporcionaron datos para actualizar"}), 400

        # Construir el objeto de actualización solo con los campos presentes en data
        update_data = {}
        allowed_fields = ['Matricula', 'Clase', 'Marca', 'Categoria']
        for field in allowed_fields:
            if field in data:
                update_data[field] = data[field]

        if not update_data:
             return jsonify({"message": "No se proporcionaron campos válidos para actualizar"}), 400

        result = taxis_collection.update_one(
            {"_id": obj_id},
            {"$set": update_data}
        )

        if result.matched_count == 0:
            return jsonify({"message": "Taxi no encontrado"}), 404

        # Recuperar y devolver el documento actualizado
        updated_taxi = taxis_collection.find_one({"_id": obj_id})
        if updated_taxi:
            updated_taxi['_id'] = str(updated_taxi['_id'])
            return jsonify(updated_taxi), 200
        else:
             # Esto sería raro si matched_count fue 1, pero por si acaso
             return jsonify({"message": "Taxi actualizado pero no se pudo recuperar"}), 200


    except Exception as e:
        print(f"Error al actualizar taxi {id}: {e}")
        return jsonify({"message": "Error interno al actualizar el taxi"}), 500


# DELETE /api/taxis/<id> - Eliminar un taxi
@app.route('/api/taxis/<string:id>', methods=['DELETE'])
def delete_taxi(id):
    if taxis_collection is None:
        return jsonify({"message": "Error: Base de datos no inicializada"}), 500

    try:
        # Validar el ObjectId
        try:
            obj_id = ObjectId(id)
        except InvalidId:
            return jsonify({"message": "ID de Taxi inválido"}), 400

        result = taxis_collection.delete_one({"_id": obj_id})

        if result.deleted_count == 0:
            return jsonify({"message": "Taxi no encontrado"}), 404

        return jsonify({"message": "Taxi eliminado correctamente", "id": id}), 200

    except Exception as e:
        print(f"Error al eliminar taxi {id}: {e}")
        return jsonify({"message": "Error interno al eliminar el taxi"}), 500


# --- Ruta para servir el frontend ---
@app.route('/')
def index():
    # Flask busca por defecto en la carpeta 'templates'
    return render_template('index.html')


# --- Iniciar la aplicación ---
if __name__ == '__main__':
    # debug=True es útil para desarrollo, ¡desactívalo en producción!
    # host='0.0.0.0' permite conexiones desde otras máquinas en la red
    app.run(debug=True, host='0.0.0.0', port=5000) # Puerto 5000 es común para Flask
