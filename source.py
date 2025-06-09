import os
import hashlib
import zipfile
import json
import tempfile
import subprocess
import shutil
import argparse
import time
import requests
import ctypes
import sys
from datetime import datetime
from tqdm import tqdm
import random

# -- Configuración inicial --
username = os.getlogin() # Obtener el nombre de usuario actual
MY_GITHUB = "https://github.com/CeccPro" # Mi usuario de GitHub (Si ves esto, sigueme en GitHub! :D)

# -- Configuración de KMD -- 
GITHUB_INDEX_URL = f"https://ceccpro.github.io/kmd-db/index.json?cb={int(time.time())}" # URL del índice de paquetes en GitHub
INSTALL_PATH = r'C:\Program Files\KMD\packages' # Ruta de instalación de paquetes
KMD_VERSION = "1.1.5" # Versión de KMD
LOG_PATH = rf'C:\users\{username}\appdata\local\kmd' # Ruta del log

# -- Exclusiones --
EXCLUDED_PACKAGES = ["CeccPro@KMD-Win64"] # Paquetes que no deben mostrarse en búsquedas ni listados
EXCLUDED_REGISTER_PACKAGES = ["CeccPro@KMD-Win64"] # Paquetes que no deben registrarse para exitar que pueda desinstalarse de forma insegura

if not os.path.exists(INSTALL_PATH):
    os.makedirs(INSTALL_PATH)  # Crear la carpeta si no existe

def is_newer_version(latest: str, current: str) -> bool:
    latest_major, latest_minor, latest_patch = map(int, latest.split('.'))
    current_major, current_minor, current_patch = map(int, current.split('.'))
    return (
        (latest_major > current_major) or
        (latest_major == current_major and latest_minor > current_minor) or
        (latest_major == current_major and latest_minor == current_minor and latest_patch > current_patch)
    )

def check_for_updates(silent=True):
    """
    Busca si hay una versión más reciente de KMD en el índice.
    Si silent=False, muestra mensajes al usuario.
    Devuelve: (hay_update: bool, latest_version: str, download_url: str)
    """
    try:
        index = get_index()
        # Buscar el paquete especial de KMD
        kmd_pkg = next((p for p in index 
                       if f"{p['author']}@{p['name']}" in EXCLUDED_PACKAGES 
                       and p['name'].lower() == 'kmd-win64'), None)
        
        if not kmd_pkg:
            writeLog("WARNING", "No se encontró la información de actualización de KMD en el índice.")
            if not silent:
                print("No se encontró la información de actualización de KMD en el índice.")
            return False, None, None

        # Buscar la versión latest
        latest_version = next((v for v in kmd_pkg['versions'] if v.get('latest', False)), None)
        if not latest_version:
            writeLog("WARNING", "No se encontró versión marcada como 'latest' para KMD.")
            if not silent:
                print("No se encontró versión marcada como 'latest' para KMD.")
            return False, None, None

        latest_version_name = latest_version.get('versionName')
        download_url = latest_version.get('downloadURL')

        if not latest_version_name or not download_url:
            writeLog("ERROR", "Información de versión incompleta en el índice.")
            if not silent:
                print("Información de versión incompleta en el índice.")
            return False, None, None
        
        writeLog("INFO", f"Última versión de KMD encontrada en el index: {latest_version_name}")

        # Comparar versiones
        if is_newer_version(latest_version_name, KMD_VERSION) and KMD_VERSION != latest_version_name:
            writeLog("INFO", f"Nueva versión de KMD disponible: {latest_version_name} (actual: {KMD_VERSION})")
            if not silent:
                print(f"¡Nueva versión de KMD disponible ({latest_version_name})! (actual: {KMD_VERSION})")
            return True, latest_version_name, download_url
        else:
            writeLog("OK", "KMD está actualizado a la última versión.")
            return False, latest_version_name, download_url

    except Exception as e:
        writeLog("ERROR", f"Error al buscar actualizaciones: {e}")
        if not silent:
            print(f"Error al buscar actualizaciones: {e}")
        return False, None, None
    
def get_existential_message():
    """
    Retorna un mensaje existencial aleatorio como easter egg
    """
    messages = [
        "¿Si instalas un paquete y nadie lo usa, realmente está instalado? 🤔",
        "En el gran esquema del universo, ¿qué son realmente las dependencias?",
        "Cada paquete que instalas te hace un poco menos libre... y un poco más dependiente 😌",
        "¿Los paquetes sueñan con actualizaciones eléctricas? 🐑",
        "El verdadero legacy code son los amigos que hicimos en el camino 🌟",
        "rm -rf /* es temporal, pero doom es eterno 😈",
        "Detrás de cada gran programa hay un programador preguntándose qué está haciendo con su vida",
        "404: Significado de la vida no encontrado",
        "git commit -m 'Cambios existenciales' --no-verify",
        "Los bugs no son errores, son características no planificadas del universo 🪲",
        "¿Qué es un paquete sin su manifest? Una existencia vacía... como la mía 😢",
        "La vida es como un paquete: a veces viene con dependencias inesperadas",
        "¿Instalar un paquete es realmente una decisión consciente o solo una ilusión de control?",
        "En un mundo lleno de bugs, ¿quién necesita features?",
        "La única constante en la vida es el cambio... y los paquetes que no se actualizan",
        "¿Qué es la realidad sino un gran repositorio de código abierto?"
    ]
    return random.choice(messages)

def compressLog():
    """
    Comprime el archivo de log en un archivo ZIP con un timestamp.
    El archivo ZIP se guarda en la misma carpeta que el log.
    """
    writeLog("INFO", "Comprimiendo log...")
    logFile = os.path.join(LOG_PATH, "debug.log")
    if not os.path.exists(logFile):
        return

    # Timestamp para el nombre del zip (formato: YYYYMMDD-HHMMSS)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    # Nombre del zip
    zipName = fr"{LOG_PATH}\log-{timestamp}.zip"

    # Crear archivo zip y agregar el logFile dentro
    with zipfile.ZipFile(zipName, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(logFile, arcname=os.path.basename(logFile))

def check_log_size():
    """
    Verifica el tamaño del archivo de log y lo comprime si excede un tamaño máximo.
    Si el log no existe, no hace nada. El tamaño máximo es de 20 MB.
    """
    logFile = os.path.join(LOG_PATH, "debug.log")
    writeLog("INFO", "Verificando el tamaño del log...")
    maxLogSize = 20
    if os.path.exists(logFile):
        size_mb = int((os.path.getsize(logFile) / (1024*1024)) * 100) / 100  # Tamaño en MB
        size_kb = int((os.path.getsize(logFile) / (1024)) * 100) / 100  # Tamaño en KB
        
        if not size_mb == 0:
            writeLog("INFO", f"Tamaño del log: {size_mb} MB")
        else:
            writeLog("INFO", f"Tamaño del log: {size_kb} KB")
        if size_mb >= maxLogSize:
            writeLog("WARNING", f"El tamaño del log excede los {maxLogSize} MB")
            compressLog()
        else:
            writeLog("OK", "El log tiene un tamaño dentro de los límites")

def writeLog(status, text, newInstance=False):
    """
    Escribe un mensaje en el archivo de log.
    status: "OK", "ERROR", "WARNING", "INFO"
    text: El mensaje a registrar
    newInstance: Si es True, indica que es una nueva instancia de KMD
    """
    log_path = os.path.join(LOG_PATH, "debug.log")

    # Crear carpeta si no existe
    os.makedirs(LOG_PATH, exist_ok=True)

    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    if not newInstance:
        log_entry = f"[{timestamp}]: [{status}] {text}\n"
    else:
        if os.path.exists(log_path):
            log_entry = f"\n---- Nueva instancia iniciada -----\n[{timestamp}]: [{status}] {text}\n"
        else:
            log_entry = f"---- Nueva instancia iniciada -----\n[{timestamp}]: [{status}] {text}\n"

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(log_entry)

def run_as_admin():
    """
    Intenta relanzar el script actual con permisos de administrador.
    (No toques esto a menos que sepas lo que haces. Estuve horas intentando que funcionara)
    """
    # Vuelve a ejecutar el script como admin
    print("Se necesitan permisos de administrador. Relanzando KMD...")
    args = sys.argv[1:]
    if len(args) > 0 and os.path.basename(sys.argv[0]).split('.')[0].lower() == args[0].lower():
        args = args[1:]
    script = os.path.abspath(sys.argv[0])
    params = " ".join([f'"{arg}"' for arg in args])
    try:
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", "cmd.exe", f'/k ""{script}" {params}" & pause & exit', None, 1
        )
        sys.exit(0)
    except Exception as e:
        writeLog("ERROR", f"No se pudo ejecutar como admin: {e}")
        print(f"No se pudo ejecutar como admin: {e}")
        return False

def get_index():
    """
    Obtiene el índice de paquetes desde GitHub.
    Devuelve un objeto JSON con la lista de paquetes.
    Si no se puede obtener, lanza una excepción.
    """
    r = requests.get(GITHUB_INDEX_URL, timeout=30)
    if r.status_code != 200:
        writeLog("ERROR", "No se pudo obtener el índice de paquetes")
        raise Exception("No se pudo obtener el índice de paquetes")
    return r.json()

def download_package(package_id, version=None):
    """
    Descarga un paquete dado su ID (formato: Author@PackageName)
    y opcionalmente una versión específica.
    Muestra el progreso de descarga.
    """
    parts = package_id.split('@')
    if len(parts) != 2:
        writeLog("ERROR", f"ID de paquete inválido: {package_id} (se esperaba 'Autor@Paquete')")
        raise Exception(f"ID de paquete inválido: {package_id} (se esperaba 'Autor@Paquete')")
    author, name = parts

    index = get_index()

    # Buscar el paquete con ese autor y nombre
    entry = next((p for p in index if p['author'] == author and p['name'] == name), None)
    if not entry:
        writeLog("ERROR", f"Paquete {package_id} no encontrado en el índice")
        raise Exception(f"Paquete {package_id} no encontrado en el índice")

    # Buscar la versión correcta
    version_entry = None
    if version:
        version_entry = next((v for v in entry['versions'] if v['versionName'] == version), None)
        if not version_entry:
            writeLog("ERROR", "Versión '{version}' de {package_id} no encontrada")
            raise Exception(f"Versión '{version}' de {package_id} no encontrada")
    else:
        version_entry = next((v for v in entry['versions'] if v.get('latest')), None)
        if not version_entry:
            writeLog("ERROR", f"No se encontró una versión marcada como 'latest' para {package_id}")
            raise Exception(f"No se encontró una versión marcada como 'latest' para {package_id}")

    url = version_entry['downloadURL']
    writeLog("INFO", f"Descargando {package_id} ({version_entry['versionName']}) desde: {url}")
    print(f"Descargando {package_id} ({version_entry['versionName']}) desde:\n{url}")

    response = requests.get(url, stream=True)
    if response.status_code != 200:
        writeLog("ERROR", "Error al descargar el paquete")
        raise Exception("Error al descargar el paquete")

    total_size = int(response.headers.get('content-length', 0))
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')

    # Descargando con barra de progreso
    with tqdm(
        total=total_size, unit='B', unit_scale=True,
        desc=f"{name}-{version_entry['versionName']}",
        ncols=70
    ) as barra:
        for chunk in response.iter_content(chunk_size=1024):
            if chunk:
                temp_file.write(chunk)
                barra.update(len(chunk))

    temp_file.close()
    return temp_file.name, entry

def search_packages(query):
    """
    Busca paquetes en el índice por nombre o autor.
    Muestra los resultados encontrados.
    Devuelve una lista de paquetes que coinciden con la búsqueda.
    """
    index = get_index()
    query_lower = query.lower()
    matches = [
        p for p in index
        if (query_lower in p['name'].lower() or 
            query_lower in f"{p['author']}@{p['name']}".lower())
        and f"{p['author']}@{p['name']}" not in EXCLUDED_PACKAGES
    ]
    if not matches:
        print(f"No se encontraron paquetes que coincidan con '{query}'")
        return []

    print(f"Coincidencias encontradas para '{query}':\n")
    for p in matches:
        desc = p.get('description', 'Sin descripción')
        pkg_id = f"{p['author']}@{p['name']}"
        print(f"{pkg_id}: {desc}")

    return matches

def verify_hash(file_path, expected_hash) -> bool:
    """
    Verifica el hash SHA-256 de un archivo contra un hash esperado.
    Devuelve True si el hash coincide, False en caso contrario.
    """
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            sha256.update(chunk)
    computed = sha256.hexdigest()
    writeLog("INFO", f"Hash del paquete en el index: {expected_hash}")
    writeLog("INFO", f"Hash calculado: {computed}")
    return computed == expected_hash

def extract_and_validate_manifest(zip_path):
    """
    Extrae el manifest.json de un paquete ZIP y lo valida contra el índice.
    Devuelve el manifest como un diccionario si es válido, o "ERROR" en caso de fallo.
    """
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        try:
            with zip_ref.open('manifest.json') as manifest_file:
                manifest = json.load(manifest_file)
        except json.JSONDecodeError:
            writeLog("ERROR", "El archivo manifest.json está corrupto o malformado. Abortando instalación...")
            print(f"Error: Ha ocurrido un error mientras se abría manifest.json")
            return "ERROR"

    index = get_index()
    # Buscar paquete por author y name
    index_entry = next((p for p in index if p['author'] == manifest['author'] and p['name'] == manifest['name']), None)
    if not index_entry:
        writeLog("ERROR", "Paquete no encontrado en el índice al validar manifest")
        raise Exception("Paquete no encontrado en el índice al validar manifest")

    # Buscar la versión dentro de las versiones del índice que coincida con manifest['version']
    version_entry = next((v for v in index_entry['versions'] if v.get('versionName', v.get('vName')) == manifest['version']), None)
    if not version_entry:
        writeLog("ERROR", "Versión no encontrada en el índice para este paquete")
        raise Exception("Versión no encontrada en el índice para este paquete")

    # Validaciones básicas
    if manifest['description'] != index_entry.get('description', ''):
        writeLog("ERROR", "La descripción del manifest y el índice no coinciden")
        raise Exception("La descripción del manifest y el índice no coinciden")

    return manifest

def who_depends(package_id, silent=False):
    """
    Busca y muestra los paquetes que dependen de un paquete dado por su ID.
    package_id: ID del paquete en formato "autor@nombre"
    silent: Si es True, no muestra mensajes al usuario, solo registra en el log.
    Devuelve una lista de paquetes que dependen del paquete dado.
    """
    writeLog("INFO", f"Buscando paquetes que dependen de {package_id}")
    try:
        if not isinstance(package_id, str) or "@" not in package_id:
            writeLog("ERROR", f"ID de paquete inválido: {package_id}")
            print("Error: El ID del paquete debe ser una cadena válida en formato 'autor@nombre'.")
            return []

        installed_file = os.path.join(INSTALL_PATH, 'installed.json')
        if not os.path.exists(installed_file):
            writeLog("WARNING", "No se encontró el archivo del registro")
            if not silent:
                print("No hay paquetes instalados.")
            return []

        try:
            with open(installed_file, 'r') as f:
                installed_data = json.load(f)
        except json.JSONDecodeError:
            writeLog("ERROR", "El archivo installed.json está corrupto o malformado")
            if not silent:
                print("Error: El archivo de registro está corrupto. No se puede continuar.")
            return []

        installed = installed_data.get('installed', [])
        if not isinstance(installed, list):
            writeLog("ERROR", "El campo 'installed' no es una lista")
            if not silent:
                print("Error: Formato incorrecto en el archivo de registro.")
            return []

        dependents = []
        for p in installed:
            deps = p.get('dependencies', [])
            if not isinstance(deps, list):
                continue  # Ignora paquetes con dependencias mal formateadas

            for dep in deps:
                if not isinstance(dep, dict):
                    continue
                if dep.get('id') == package_id:
                    dependents.append(f"{p.get('author', 'desconocido')}@{p.get('name', 'desconocido')}")
                    break  # Si ya depende, no hace falta seguir revisando

        writeLog("INFO", f"Se encontró que {len(dependents)} paquetes dependen de {package_id}")

        if dependents:
            if not silent:
                print(f"Los siguientes paquetes dependen de '{package_id}':")
            for d in dependents:
                print(f"  - {d}")
        else:
            if not silent:
                print(f"Ningún paquete depende de '{package_id}'.")
        return dependents

    except Exception as e:
        writeLog("ERROR", f"Error inesperado en who_depends: {e}")
        print(f"Error inesperado: {e}")
        return []

def install_dependencies(manifest):
    """
    Instala las dependencias de un paquete dado su manifest.
    manifest: El manifest del paquete como un diccionario.
    Devuelve "OK" si todas las dependencias se instalaron correctamente, o "ERROR" en caso de fallo.
    """
    for dep in manifest.get('dependencies', []):
        pkg_id = dep.get("id")
        pkg_version = dep.get("version")

        if not pkg_id:
            writeLog("ERROR", "Dependencia inválida, falta el ID.")
            print("Dependencia inválida, falta el ID.")
            return "ERROR"
        
        writeLog("INFO", f"Instalando dependencia: {pkg_id} (versión: {pkg_version or 'latest'})")
        print(f"Instalando dependencia: {pkg_id} (versión: {pkg_version or 'latest'})")
        install_code = install_package(pkg_id, pkg_version)

        if install_code != "OK":
            writeLog("ERROR", f"Error al instalar dependencia: {pkg_id}")
            print(f"Error al instalar dependencia: {pkg_id}")
            return "ERROR"

    return "OK"

def extract_package(zip_path, package_name):
    """
    Extrae un paquete ZIP a una carpeta específica dentro de INSTALL_PATH.
    zip_path: Ruta al archivo ZIP del paquete.
    package_name: Nombre del paquete (usado para crear la carpeta de destino).
    Devuelve la ruta de la carpeta donde se extrajo el paquete.
    """
    dest_path = os.path.join(INSTALL_PATH, package_name)
    os.makedirs(dest_path, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(dest_path)
    return dest_path

def run_postinstall(manifest, package_path):
    """
    Ejecuta un script de post-instalación si está definido en el manifest.
    manifest: El manifest del paquete como un diccionario.
    package_path: Ruta donde se extrajo el paquete.
    """
    script = manifest.get('postInstallScript')
    if script:
        script_path = os.path.join(package_path, script)
        if os.path.exists(script_path):
            writeLog("INFO", f"Ejecutando script de instalación: {script}")
            print(f"Ejecutando script de instalación: '{script}'")
            try:
                subprocess.run([script_path], shell=True, check=True)
            except subprocess.CalledProcessError:
                writeLog("ERROR", f"Error al ejecutar el script de instalación '{script}'")
                print(f"Error al ejecutar el script {script}")
        else:
            writeLog("ERROR", f"Script {script} no encontrado en {package_path}")
            print(f"Script {script} no encontrado en {package_path}")

def run_uninstall(manifest, package_path):
    """
    Ejecuta un script de desinstalación si está definido en el manifest.
    manifest: El manifest del paquete como un diccionario.
    package_path: Ruta donde se extrajo el paquete.
    """
    script = manifest.get('uninstallScript')
    if script:
        script_path = os.path.join(package_path, script)
        if os.path.exists(script_path):
            writeLog("INFO", f"Ejecutando script de desinstalación: '{script}'")
            print(f"Ejecutando script de desinstalación: '{script}'")
            try:
                subprocess.run([script_path], shell=True, check=True)
            except subprocess.CalledProcessError:
                writeLog("ERROR", f"Error al ejecutar el script de instalación '{script}'")
                print(f"Error al ejecutar el script {script}")
        else:
            writeLog("ERROR", f"Script {script} no encontrado en {package_path}")
            print(f"Script {script} no encontrado en {package_path}")

def autoremove_unused_packages():
    """
    Elimina paquetes huérfanos que no tienen dependientes.
    Un paquete se considera huérfano si tiene dependencias, pero ninguna de ellas está instalada.
    Revisa el archivo installed.json y elimina los paquetes que no son utilizados por otros.
    """
    installed_file = os.path.join(INSTALL_PATH, 'installed.json')

    if not os.path.exists(installed_file):
        writeLog("INFO", "No se encuentra el archivo del registro.")
        print("No hay paquetes instalados.")
        return

    try:
        with open(installed_file, 'r') as f:
            installed = json.load(f)
    except json.JSONDecodeError:
            writeLog("ERROR", "El archivo installed.json está corrupto o malformado.")
            raise Exception(f"Error: Ha ocurrido un error mientras se leía el registro.")

    all_ids = [f"{p['author']}@{p['name']}" for p in installed['installed']]
    removed_any = False
    changes = True  # Para seguir limpiando en cascada

    while changes:
        changes = False
        to_remove = []

        for pkg in installed['installed']:
            pkg_id = f"{pkg['author']}@{pkg['name']}"
            dependents = pkg.get('dependents', [])

            # Si tiene dependents pero ninguno de ellos existe, marcar para borrar
            if dependents and all(dep not in all_ids for dep in dependents):
                to_remove.append(pkg_id)

        if to_remove:
            for pkg_id in to_remove:
                uninstall_package(pkg_id)  # Aquí llamas a tu función de desinstalación
                writeLog("INFO", f"Se eliminó el paquete huérfano: {pkg_id}")
                print(f"Se eliminó el paquete huérfano: {pkg_id}")
                removed_any = True
            # Recargar lista después de cada tanda de desinstalaciones
            try:
                with open(installed_file, 'r') as f:
                    installed = json.load(f)
            except json.JSONDecodeError:
                writeLog("ERROR", "El archivo installed.json está corrupto o malformado. Abortando instalación...")
                raise Exception(f"Error: Ha ocurrido un error mientras se leía el registro.")
            all_ids = [f"{p['author']}@{p['name']}" for p in installed['installed']]
            changes = True  # Repetir para limpiar en cascada

    if not removed_any:
        print("No hay paquetes huérfanos para eliminar.")
        writeLog("INFO", "No hay paquetes huérfanos para eliminar.")

def register_package(manifest):
    """
    Registra un paquete en el archivo installed.json.
    manifest: El manifest del paquete como un diccionario.
    Devuelve "OK" si se registró correctamente, o "ERROR" en caso de fallo.
    """
    os.makedirs(INSTALL_PATH, exist_ok=True)
    installed_file = os.path.join(INSTALL_PATH, 'installed.json')

    if os.path.exists(installed_file):
        try:
            with open(installed_file, 'r') as f:
                installed = json.load(f)
        except json.JSONDecodeError:
            writeLog("ERROR", "El archivo installed.json está corrupto o malformado")
            print(f"Error: Ha ocurrido un error mientras se instalaba {manifest['author']}@{manifest['name']}.")
            return "ERROR"
    else:
        installed = {"installed": []}

    # Construir el ID del paquete
    package_id = f"{manifest['author']}@{manifest['name']}"

    # Actualizar dependents en cada dependencia (si existen)
    if 'dependencies' in manifest:
        for dep in manifest['dependencies']:
            dep_id = dep['id']  # El ID de la dependencia, tipo "CeccPro@testLib"
            for pkg in installed['installed']:
                pkg_id = f"{pkg['author']}@{pkg['name']}"
                if pkg_id == dep_id:
                    if 'dependents' not in pkg:
                        pkg['dependents'] = []
                    if package_id not in pkg['dependents']:
                        pkg['dependents'].append(package_id)

    # Asegurar que el paquete tenga al menos el campo dependents vacío
    if 'dependents' not in manifest:
        manifest['dependents'] = []

    # Reemplazar si ya estaba
    installed['installed'] = [p for p in installed['installed'] if f"{p['author']}@{p['name']}" != package_id]
    installed['installed'].append(manifest)

    # Guardar cambios
    with open(installed_file, 'w') as f:
        json.dump(installed, f, indent=4)

    writeLog("OK", f"El paquete {package_id} se registró correctamente")
    print(f"Paquete {package_id} registrado correctamente")
    return "OK"

def list_all_packages():
    """
    Lista todos los paquetes disponibles en el índice, excluyendo los paquetes definidos en EXCLUDED_PACKAGES.
    Muestra el ID del paquete y su descripción.
    """
    index = get_index()
    print("Paquetes disponibles:")
    for p in index:
        package_id = f"{p['author']}@{p['name']}"
        if package_id in EXCLUDED_PACKAGES:
            continue
        desc = p.get('description', 'Sin descripción')
        print(f"{package_id}: {desc}")
    print("\n")

def install_package(package_id, version=None, installExcludedPackages=False, KMDautoupdate=False):
    """
    Instala un paquete dado su ID (formato: Author@PackageName) y una versión opcional.
    package_id: ID del paquete en formato "Autor@Nombre".
    version: Versión específica a instalar, si se desea. Si es None, instala la última versión.
    Devuelve "OK" si la instalación fue exitosa, o "ERROR" en caso de fallo.
    """
    installed_file = os.path.join(INSTALL_PATH, 'installed.json')
    if os.path.exists(installed_file):
        writeLog("OK", "La lista de paquetes instalados existe.")
        try:
            with open(installed_file, 'r') as f:
                installed = json.load(f).get('installed', [])
        except json.JSONDecodeError:
            writeLog("ERROR", "El archivo installed.json está corrupto o malformado. Abortando instalación...")
            print(f"Error: Ha ocurrido un error mientras se instalaba {package_id}.")
            return "ERROR"
        if any(f"{p['author']}@{p['name']}" == package_id for p in installed):
            writeLog("OK", f"El paquete {package_id} ya está instalado. Omitiendo instalación")
            print(f"El paquete {package_id} ya está instalado. Omitiendo instalación.")
            return "OK"

    zip_path = None
    try:
        writeLog("INFO", "Creando carpeta de paquetes (Si no existe ya)")
        os.makedirs(INSTALL_PATH, exist_ok=True)
        author, pkg_name = package_id.split('@')
        index = get_index()

        # Verificar si KMD tiene permisos de admin
        if ctypes.windll.shell32.IsUserAnAdmin() == 1:
            writeLog("OK", "KMD tiene permisos de admin")
        else:
            writeLog("WARNING", "KMD no tiene permisos de admin. Esto podría ocasionar errores.")

        # Archivo temporal para verificar si se necesitan permisos de admin
        writeLog("INFO", "Creando archivo temporal para verificar permisos de admin...")
        test_path = os.path.join(INSTALL_PATH, "__perm_check.tmp")
        with open(test_path, 'w') as f:
            f.write("test")
        if os.path.exists(test_path):
            writeLog("OK", "Archivo temporal creado exitosamente!")
        os.remove(test_path)

        # Buscar el paquete
        writeLog("INFO", "Buscando paquete en el index...")
        entry = next((p for p in index if p['author'] == author and p['name'] == pkg_name), None)
        if not entry or (not installExcludedPackages and f"{entry['author']}@{entry['name']}" in EXCLUDED_PACKAGES):
            writeLog("ERROR", f"Paquete {package_id} no encontrado en el índice")
            raise Exception(f"Paquete {package_id} no encontrado en el índice")

        # Elegir versión según el parámetro
        if version:
            writeLog("INFO", f"Instalando versión {version}...")
            selected_version = next((v for v in entry['versions'] if v['versionName'] == version), None)
            if not selected_version:
                writeLog("ERROR", f"La versión '{version}' de {package_id} no existe.")
                raise Exception(f"La versión '{version}' de {package_id} no existe.")
        else:
            writeLog("INFO", "No se especificó una versión. Instalando latest...")
            selected_version = next((v for v in entry['versions'] if v.get('latest', False)), None)
            if not selected_version:
                writeLog("ERROR", f"No se encontró una versión latest para {package_id}")
                raise Exception(f"No se encontró una versión latest para {package_id}")

        # Descargar paquete (usa el parámetro version, aunque sea None)
        zip_path, _ = download_package(package_id, version)

        # Validar hash contra la versión correcta
        writeLog("INFO", "Comparando el hash del paquete...")
        if not verify_hash(zip_path, selected_version['hash']):
            print("El hash no coincide con el esperado.")
            writeLog("WARNING", "El hash del paquete no coincide con el esperado")
            userInput = input("¿Deseas continuar con la instalación? (S/N) > ")
            if userInput.lower() not in ["s", "y"]:
                writeLog("ERROR", "El usuario ha decidido abortar la instalación")
                raise Exception("Abortando instalación.")

        # Extraer y validar manifest
        manifest = extract_and_validate_manifest(zip_path)
        if manifest == "ERROR":
            writeLog("ERROR", f"Ha ocurrido un error mientras se instalaba {package_id}. Abortando...")
            raise Exception(f"Ha ocurrido un error mientras se instalaba {package_id}. Abortando...")

        # Instalar dependencias
        writeLog("INFO", "Instalando dependencias...")
        returnCode = install_dependencies(manifest)
        if returnCode != "OK":
            writeLog("ERROR", "Error al instalar dependencias. Abortando instalación.")
            raise Exception("Error al instalar dependencias. Abortando instalación.")

        # Extraer paquete
        writeLog("INFO", "Extrayendo paquete...")
        package_path = extract_package(zip_path, manifest['name'])

        # Ejecutar postinstall si existe
        run_postinstall(manifest, package_path)

        # Registrar el paquete como instalado
        if not package_id in EXCLUDED_REGISTER_PACKAGES:
            regCode = register_package(manifest)
            if regCode != "OK":
                writeLog("ERROR", "Ha ocurrido un error mientras se registraba el paquete")
                print(f"Ha ocurrido un error mientras se instalaba {package_id}")
        else:
            # Si el paquete está en la lista de paquetes excluidos de registro, no lo registramos
            writeLog("INFO", f"El paquete {package_id} está en la lista de paquetes excluidos de registro. No se registrará.")

        writeLog("OK", f"El paquete {package_id} se ha instalado correctamente!")
        print(f"Paquete {package_id} v{selected_version['versionName']} instalado con éxito")

    except PermissionError as e:
        writeLog("WARNING", f"KMD no tiene permisos de admin. Error obtenido: {e}. (Relanzando...)")
        # Verificar y ejecutar como admin
        isadmin = run_as_admin()
        if not isadmin:
            writeLog("ERROR", "No se pudo ejecutar KMD con permisos de administrador")
            raise Exception("No se pudo ejecutar KMD con permisos de administrador")
        
    except KeyboardInterrupt:
        writeLog("ERROR", f"El usuario interrumpió la instalación con KeyboardInterrupt")
        print("Abortando instalalción...")

    except Exception as e:
        writeLog("ERROR", f"Error durante la instalación de {package_id}: {e}")
        print(f"Error durante la instalación de {package_id}: {e}")

    finally:
        if zip_path and os.path.exists(zip_path):
            writeLog("INFO", "Eliminando archivos temporales...")
            os.remove(zip_path)
    return "OK"

def uninstall_package(package_id):
    """
    Desinstala un paquete dado su ID (formato: Author@PackageName).
    package_id: ID del paquete en formato "Autor@Nombre".
    Muestra mensajes de progreso y advertencias si hay dependencias.
    """
    writeLog("INFO", f"Desinstalando {package_id}")

    if ctypes.windll.shell32.IsUserAnAdmin() == 1:
        writeLog("OK", "KMD tiene permisos de admin")
    else:
        writeLog("WARNING", "KMD no tiene permisos de admin. Esto podría ocasionar errores.")

    installed_file = os.path.join(INSTALL_PATH, 'installed.json')
    if not os.path.exists(installed_file):
        writeLog("WARNING", "No se encontró el archivo del registro")
        print("No hay paquetes instalados.")
        return
    try:
        with open(installed_file, 'r') as f:
            installed_data = json.load(f)
    except json.JSONDecodeError:
            writeLog("ERROR", "El archivo installed.json está corrupto o malformado. Abortando instalación...")
            print(f"Error: Ha ocurrido un error mientras se leía el registro")
            return
    installed = installed_data['installed']

    writeLog("INFO", "Buscando paquete en el registro...")
    package = next((p for p in installed if f"{p['author']}@{p['name']}" == package_id), None)
    if not package:
        writeLog("ERROR", f"No se encontró el paquete '{package_id}' en el registro.")
        print(f"No se encontró el paquete con ID '{package_id}' para desinstalar.")
        return

    # Verificar si alguien más depende de este paquete
    for p in installed:
        deps = p.get('dependencies', [])
        for dep in deps:
            if dep.get('id') == package_id:
                depender_id = f"{p['author']}@{p['name']}"
                writeLog("WARNING", f"{depender_id} depende de {package_id}. Mostrando advertencia...")
                print(f"Advertencia: '{depender_id}' depende de '{package_id}'. Desinstalarlo puede causar errores.")
                print("¿Aún quieres desinstalarlo? (S/N)")
                userInput = input(">")
                if not userInput.lower() in ['s', 'y']:
                    writeLog("INFO", "Se canceló la desinstalación.")
                    print("Se canceló la desinstalación.")
                    return
                else:
                    writeLog("WARNING", "Se continuó con la desinstalación. Esto puede ocasionar errores.")
                break

    package_folder = os.path.join(INSTALL_PATH, package['name'])

    try:
        test_path = os.path.join(package_folder, "__perm_check.tmp")
        with open(test_path, 'w') as f:
            f.write("test")
        os.remove(test_path)

    except PermissionError:
        writeLog("WARNING", "KMD no tiene permisos de admin. Relanzando...")
        isadmin = run_as_admin()
        if not isadmin:
            writeLog("ERROR", "No se pudo ejecutar KMD con permisos de administrador")
            raise Exception("No se pudo ejecutar KMD con permisos de administrador")

    writeLog("INFO", "Verificando si hay script de desinstalación")
    manifest_path = os.path.join(package_folder, 'manifest.json')
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, 'r') as mf:
                manifest = json.load(mf)
        except json.JSONDecodeError:
            writeLog("ERROR", "El archivo manifest.json está corrupto o malformado. Abortando instalación...")
            print(f"Error: Ha ocurrido un error mientras se instalaba {package_id}.")
        if 'uninstallScript' in manifest and manifest['uninstallScript'].strip():
            writeLog("INFO", f"Ejecutando script de desinstalación: {manifest['uninstallScript']}")
            print(f"Ejecutando script de desinstalación: {manifest['uninstallScript']}")
            try:
                run_uninstall(manifest, package_folder)
            except Exception as e:
                writeLog("ERROR", f"Error al ejecutar script de desinstalación: {e}")
                print(f"Error al ejecutar script de desinstalación: {e}")
        else:
            writeLog("INFO", "No se especificó un script de desinstalación en el manifiesto")
    else:
        writeLog("WARNING", "No se encontró el manifiesto del paquete a desinstalar")

    writeLog("INFO", "Eliminando carpeta del paquete")
    if os.path.exists(package_folder):
        try:
            shutil.rmtree(package_folder)
        except Exception as e:
            print(f"Ha ocurrido un error durante la desinstalación: {e}")

    installed_data['installed'] = [p for p in installed if f"{p['author']}@{p['name']}" != package_id]
    with open(installed_file, 'w') as f:
        json.dump(installed_data, f, indent=4)
    writeLog("OK", f"Paquete '{package_id}' desinstalado.")
    print(f"Paquete '{package['name']}' (ID: {package_id}) desinstalado")

def repair_package(package_id):
    """
    Reinstala un paquete dado su ID (formato: Author@PackageName).
    package_id: ID del paquete en formato "Autor@Nombre".
    Muestra mensajes de progreso y verifica si el paquete está instalado.
    Si el paquete no está instalado, muestra un mensaje de error.
    """
    index = get_index()

    # Validación del formato author@pkgName
    if '@' not in package_id:
        writeLog("ERROR", f"Formato inválido de package_id: {package_id}")
        print(f"Formato inválido de package_id: {package_id}")
        return

    author, pkg_name = package_id.split('@', 1)

    # Buscar en el índice
    base_pkg = next((p for p in index if p['author'] == author and p['name'] == pkg_name), None)
    if not base_pkg:
        writeLog("ERROR", f"No se encontró el paquete {package_id} en el índice")
        print(f"No se encontró el paquete {package_id} en el índice.")
        return

    # Buscar paquete instalado
    installed = get_installed_packages()
    if installed == "ERROR":
        writeLog("ERROR", "get_installed_packages devolvió un flag de error.")
        print("Error: Ha ocurrido un error. Abortando...")
        return
    installed_pkg = next((p for p in installed if p['author'] == author and p['name'] == pkg_name), None)

    if installed_pkg:
        current_version = installed_pkg.get('version', '')
        writeLog("INFO", f"Reinstalando {package_id} en su versión actual: {current_version}...")
        print(f"Reinstalando {package_id} en su versión actual: {current_version}...")
        uninstall_package(package_id)
        install_package(package_id, current_version)
        writeLog("OK", f"Paquete {package_id} reparado (versión {current_version}).")
        print(f"Paquete {package_id} reparado (versión {current_version}).")
    else:
        writeLog("ERROR", f"El paquete {package_id} no está instalado.")
        print(f"El paquete {package_id} no está instalado.")
        return

def update_package(package_id):
    """
    Actualiza un paquete a su última versión disponible.
    package_id: ID del paquete en formato "Autor@Nombre".
    Muestra mensajes de progreso y verifica si el paquete está instalado.
    Si el paquete no está instalado, lo instala en su última versión.
    Si ya está actualizado, muestra un mensaje informativo.
    """
    index = get_index()

    # Validación del formato author@pkgName
    if '@' not in package_id:
        writeLog("ERROR", f"Formato inválido de package_id: {package_id}")
        print(f"Formato inválido de package_id: {package_id}")
        return

    author, pkg_name = package_id.split('@', 1)

    # Buscar en el índice
    base_pkg = next((p for p in index if p['author'] == author and p['name'] == pkg_name), None)
    if not base_pkg:
        writeLog("ERROR", f"No se encontró el paquete {package_id} en el índice")
        print(f"No se encontró el paquete {package_id} en el índice.")
        return

    # Buscar paquete instalado (usamos author y name)
    installed = get_installed_packages()
    if installed == "ERROR":
        writeLog("ERROR", "get_installed_packages devolvió un flag de error.")
        print("Error: Ha ocurrido un error. Abortando...")
        return
    installed_pkg = next((p for p in installed if p['author'] == author and p['name'] == pkg_name), None)

    # Obtener versión más reciente
    latest_version = next((v for v in base_pkg['versions'] if v.get('latest', False)), None)
    if not latest_version:
        writeLog("ERROR", f"No se encontró versión marcada como 'latest' para {package_id}")
        print(f"No se encontró versión marcada como 'latest' para {package_id}")
        return

    latest_version_name = latest_version.get('versionName', latest_version.get('vName', ''))

    if installed_pkg:
        current_version = installed_pkg.get('version', '')
        if current_version == latest_version_name:
            writeLog("OK", f"{package_id} ya está actualizado a la versión {current_version}.")
            print(f"{package_id} ya está actualizado a la versión {current_version}.")
            return
        else:
            writeLog("INFO", f"Actualizando {package_id} de {current_version} a {latest_version_name}...")
            print(f"Actualizando {package_id} de {current_version} a {latest_version_name}...")
            uninstall_package(package_id)
    else:
        writeLog("INFO", f"{package_id} no está instalado, instalando versión {latest_version_name}...")
        print(f"{package_id} no está instalado, instalando versión {latest_version_name}...")

    install_package(package_id)
    writeLog("OK", f"Paquete {package_id} actualizado a {latest_version_name}.")
    print(f"Paquete {package_id} actualizado a {latest_version_name}.")

def update_all_packages():
    """
    Actualiza todos los paquetes instalados a su última versión disponible.
    Revisa el archivo installed.json para obtener la lista de paquetes instalados.
    Si un paquete no tiene una versión 'latest' en el índice, se omite.
    Si un paquete ya está actualizado, se muestra un mensaje informativo.
    Si no hay paquetes instalados, muestra un mensaje informativo.
    """
    installed_file = os.path.join(INSTALL_PATH, 'installed.json')
    if not os.path.exists(installed_file):
        writeLog("ERROR", "No se encotrnó el archivo de registro.")
        print("No hay paquetes instalados para actualizar.")
        return

    try:
        with open(installed_file, 'r') as f:
            installed_data = json.load(f)
    except json.JSONDecodeError:
        writeLog("ERROR", "El archivo installed.json está corrupto o malformado. Abortando instalación...")
        print(f"Error: Ha ocurrido un error mientras se instalaba {package_id}.")
        return

    installed_list = installed_data.get('installed', [])
    if not installed_list:
        writeLog("ERROR", "No hay paquetes instalados para actualizar.")
        print("No hay paquetes instalados para actualizar.")
        return

    index = get_index()
    updated_any = False

    for pkg in installed_list:
        package_id = pkg['author'] + '@' + pkg['name']
        current_version = pkg.get('version', '')

        # Buscar paquete en el índice
        base_pkg = next((p for p in index if p['author'] == pkg['author'] and p['name'] == pkg['name']), None)
        if not base_pkg:
            writeLog("WARNING", f"No se encontró el paquete {package_id} en el índice, saltando...")
            print(f"No se encontró el paquete {package_id} en el índice, saltando...")
            continue

        # Buscar la versión latest
        latest_version_entry = next((v for v in base_pkg['versions'] if v.get('latest')), None)
        if not latest_version_entry:
            writeLog("WARNING", f"No hay versión 'latest' para {package_id}, saltando...")
            print(f"No hay versión 'latest' para {package_id}, saltando...")
            continue

        latest_version_name = latest_version_entry.get('versionName')
        if current_version != latest_version_name:
            writeLog("INFO", f"Actualizando {package_id} de {current_version} a {latest_version_name}...")
            print(f"Actualizando {package_id} de {current_version} a {latest_version_name}...")
            uninstall_package(package_id)
            install_package(package_id)
            updated_any = True
        else:
            writeLog("OK", f"{package_id} ya está en la última versión ({current_version}).")
            print(f"{package_id} ya está en la última versión ({current_version}).")

    if not updated_any:
        writeLog("OK", "Todos los paquetes ya están actualizados.")
        print("Todos los paquetes ya están actualizados.")

def get_installed_packages():
    """
    Obtiene la lista de paquetes instalados desde el archivo installed.json.
    Devuelve una lista de diccionarios con la información de cada paquete instalado.
    Si el archivo no existe, devuelve una lista vacía.
    Si el archivo está corrupto o malformado, devuelve "ERROR".
    """
    installed_file = os.path.join(INSTALL_PATH, 'installed.json')
    if os.path.exists(installed_file):
        try:
            with open(installed_file, 'r') as f:
                data = json.load(f)
        except json.JSONDecodeError:
            writeLog("ERROR", "El archivo installed.json está corrupto o malformado. Abortando instalación...")
            print(f"Error: Ha ocurrido un error mientras se leía el registro.")
            return "ERROR"
        return data.get('installed', [])
    return []

def success_kmdupdate_message(version):
    """
    Muestra un mensaje de éxito después de actualizar KMD.
    version: La versión a la que se actualizó KMD.
    """
    writeLog("OK", f"KMD actualizado a la versión {version} con éxito.")
    print(f"KMD actualizado a la versión {version} con éxito.")
    print("¡Gracias por usar KMD! Si te gusta, considera seguirme en GitHub:")
    print(MY_GITHUB)

def list_installed_packages():
    """
    Lista todos los paquetes instalados desde el archivo installed.json.
    Muestra el ID del paquete, su versión, descripción y autor.
    Si el archivo no existe o está vacío, muestra un mensaje informativo.
    Si el archivo está corrupto o malformado, muestra un mensaje de error.
    """
    installed_file = os.path.join(INSTALL_PATH, 'installed.json')
    if not os.path.exists(installed_file):
        writeLog("WARNING", "No se encontró el  del registro")
        print("No hay< paquetes instalados aún.")
        return

    try:
        with open(installed_file, 'r') as f:
            installed_data = json.load(f)
    except json.JSONDecodeError:
            writeLog("ERROR", "El archivo installed.json está corrupto o malformado. Abortando instalación...")
            print(f"Error: Ha ocurrido un error mientras se leía el registro.")
            return "ERROR"

    installed = installed_data.get('installed', [])
    if not installed:
        writeLog("WARNING", "El archivo del registro está vacío")
        print("No hay paquetes instalados aún.")
        return

    print("Paquetes instalados:\n")
    for pkg in installed:
        author = pkg.get('author', 'Desconocido')
        pkg_name = pkg.get('name', 'SinNombre')
        version = pkg.get('version', '¿versión?')
        description = pkg.get('description', 'Sin descripción')
        package_id = f"{author}@{pkg_name}"

        print(f"- {package_id} ({version})")
        print(f"Descripción: {description}\n")

def list_package_versions(package_id):
    """
    Lista todas las versiones disponibles de un paquete dado su ID (formato: Author@PackageName).
    package_id: ID del paquete en formato "Autor@Nombre".
    Muestra las versiones disponibles y cuál es la última.
    Si el paquete no se encuentra en el índice, muestra un mensaje de error.
    """
    try:
        author, name = package_id.split('@')
    except ValueError:
        writeLog("ERROR", "El ID del paquete debe tener el formato 'Autor@Nombre'")
        print("El ID del paquete debe tener el formato 'Autor@Nombre'")
        return

    index = get_index()
    entry = next((p for p in index if p['author'] == author and p['name'] == name), None)

    if not entry:
        print(f"No se encontró el paquete {package_id} en el índice.")
        writeLog("ERROR", f"No se encontró el paquete {package_id} en el índice.")
        return

    print(f"Versiones disponibles para {package_id}:")
    for v in entry['versions']:
        tag = " (latest)" if v.get('latest') else ""
        print(f"- {v['versionName']}{tag}")

def update_kmd():
    """
    Actualiza KMD a la última versión disponible.
    Descarga el último release de KMD desde GitHub y lo instala.
    Si no hay una nueva versión, muestra un mensaje informativo.
    """
    writeLog("INFO", "Comenzando actualización de KMD...")
    updateAvaliable, latest_version, _ = check_for_updates(True)

    writeLog("INFO", f"Versión actual de KMD: {KMD_VERSION}")
    writeLog("INFO", f"Última versión disponible: {latest_version}")

    if not updateAvaliable:
        writeLog("OK", "KMD ya está actualizado a la última versión.")
        print("KMD ya está actualizado a la última versión.")
        return

    writeLog("INFO", f"Actualizando KMD de {KMD_VERSION} a {latest_version}...")
    install_package("CeccPro@KMD-Win64", None, installExcludedPackages=True, KMDautoupdate=True)

def get_kmdVersion():
    """
    Devuelve la versión actual de KMD.
    """
    return f'''KMD Package Manager {KMD_VERSION}
By CeccPro. My GitHub:
{MY_GITHUB}
Pls, follow me on GitHub! It's free and helps a lot!'''

def get_usage():
    """
    Devuelve un string con la lista de comandos disponibles y su descripción.
    """
    return '''Comandos disponibles:
    install [ID] [Versión]  - Instala un paquete
    search [Nombre]         - Busca paquetes
    list-versions [ID]      - Lista las versiones disponibles de un paquete
    list-all                - Lista todos los paquetes
    uninstall [ID]          - Desinstala un paquete
    remove [ID]             - Alias para uninstall
    update-all              - Actualiza todos los paquetes
    update [ID]             - Actualiza un paquete
    repair [ID]             - Repara reinstalando un paquete
    list-installed          - Lista todos los paquetes instalados
    help                    - Muestra este dialogo de ayuda
    version                 - Muestra la versión instalada de KMD
    autoremove              - Elimina las dependencias huerfanas
    who-depends [ID]        - Muestra cuantos paquetes dependen de otro paquete
    update-kmd              - Actualiza KMD a la última versión
    whoami                  - Muestra información del autor de KMD (A nadie le importa, pero bueno...)
    '''

def main():
    """
    Función principal que maneja los comandos de KMD.
    Analiza los argumentos de la línea de comandos y ejecuta la acción correspondiente.
    """
    writeLog("INFO", f"KMD {KMD_VERSION} running.", True)
    parser = argparse.ArgumentParser(description='KMD - Gestor de paquetes')
    parser.add_argument('command', help='Comando: install, search, list-all, uninstall, remove, update, etc (Ejecuta "kmd help" para verlos completos)')
    parser.add_argument('value', nargs='?', help='ID del paquete')
    parser.add_argument('extraArgs', nargs='?', help='Argumentos extra (Si son necesarios)')
    args = parser.parse_args()

    # Añadir 1% de probabilidad de mostrar mensaje existencial
    if random.random() < 0.01:
        print("\n" + get_existential_message() + "\n")

    try:
        # Instalar paquete (Con versión)
        if args.command == 'install' and args.value and args.extraArgs:
            writeLog("INFO", f"Iniciando instalación de {args.value} versión {args.extraArgs}")
            install_package(args.value, args.extraArgs)

        # Instalar paquete
        elif args.command == 'install' and args.value:
            writeLog("INFO", f"Iniciando instalación de {args.value}...")
            install_package(args.value)

        # Buscar paquete
        elif args.command == 'search' and args.value:
            writeLog("INFO", f"Buscando paquete '{args.value}'...")
            search_packages(args.value)

        elif args.command == 'list-all':
            writeLog("INFO", f"Listando todos los paquetes...")
            list_all_packages()

        elif args.command == 'repair' and args.value:
            writeLog("INFO", f"Reparando instalación de {args.value}")
            repair_package(args.value)

        elif args.command == 'who-depends' and args.value:
            writeLog("INFO", f"Verificando paquetes que dependen de {args.value}")
            who_depends(args.value)

        elif args.command == 'autoremove':
            writeLog("INFO", f"Eliminando dependencias huerfanas...")
            autoremove_unused_packages()

        elif args.command == 'list-installed':
            writeLog("INFO", f"Listando paquetes instalados...")
            list_installed_packages()

        elif args.command in ['uninstall', 'remove'] and args.value:
            writeLog("INFO", f"Desinstalando paquete '{args.value}'...")
            uninstall_package(args.value)

        elif args.command == 'update' and args.value:
            writeLog("INFO", f"Actualizando paquete '{args.value}'...")
            update_package(args.value)

        elif args.command == 'update-all':
            writeLog("INFO", f"Actualizando todos los paquetes...")
            update_all_packages()

        elif args.command == 'list-versions' and args.value:
            writeLog("INFO", f"Listando versiones del paquete '{args.value}'...")
            list_package_versions(args.value)

        elif args.command in ['help', 'usage']:
            writeLog("INFO", f"Imprimiendo ayuda...")
            print(get_usage())

        elif args.command in ['version', '-v', '--version']:
            writeLog("INFO", f"Mostrando versión de KMD...")
            print(get_kmdVersion())

        elif args.command == 'update-kmd':
            writeLog("INFO", f"Actualizando KMD a la última versión...")
            update_kmd()

        elif args.command == 'whoami':
            writeLog("INFO", f"Mostrando información del autor...")
            print(f"Autor: CeccPro\nGitHub: {MY_GITHUB}\nVersión de KMD: {KMD_VERSION}")

        elif args.command == 'meaning-of-life':
            writeLog("INFO", "Usuario buscando el significado de la vida...")
            print("42... pero la verdadera pregunta es: ¿por qué sigues buscando respuestas en un gestor de paquetes? 🤔")

        else:
            writeLog("ERROR", f"Comando '{args.command} {args.value} {args.extraArgs}' no reconocido. Imprimiendo ayuda")
            print("Uso inválido.", get_usage())

    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    main() # Ejecutar la función principal
    check_log_size() # Verificar el tamaño del log al finalizar
    check_for_updates(False) # Comprobar si hay actualizaciones al finalizar