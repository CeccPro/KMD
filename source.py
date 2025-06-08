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

username = os.getlogin()

# -- Configuración -- 
GITHUB_INDEX_URL = f"https://ceccpro.github.io/kmd-db/index.json?cb={int(time.time())}"
INSTALL_PATH = r'C:\Program Files\KMD\packages'
KMD_VERSION = "1.1.3"
LOG_PATH = rf'C:\users\{username}\appdata\local\kmd'

def compressLog():
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
    # Vuelve a ejecutar el script como 
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
    r = requests.get(GITHUB_INDEX_URL)
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
    index = get_index()
    query_lower = query.lower()

    # Buscar coincidencias en 'name' o en 'author@name'
    matches = [p for p in index if query_lower in p['name'].lower() or query_lower in f"{p['author']}@{p['name']}".lower()]
    if not matches:
        print(f"No se encontraron paquetes que coincidan con '{query}'")
        return []

    print(f"Coincidencias encontradas para '{query}':\n")
    for p in matches:
        desc = p.get('description', 'Sin descripción')
        pkg_id = f"{p['author']}@{p['name']}"
        print(f"{pkg_id}: {desc}")

    return matches

def verify_hash(file_path, expected_hash):
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            sha256.update(chunk)
    computed = sha256.hexdigest()
    writeLog("INFO", f"Hash del paquete en el index: {expected_hash}")
    writeLog("INFO", f"Hash calculado: {computed}")
    return computed == expected_hash

def extract_and_validate_manifest(zip_path):
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        with zip_ref.open('manifest.json') as manifest_file:
            manifest = json.load(manifest_file)

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

def install_dependencies(manifest):
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
    dest_path = os.path.join(INSTALL_PATH, package_name)
    os.makedirs(dest_path, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(dest_path)
    return dest_path

def run_postinstall(manifest, package_path):
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

def register_package(manifest):
    os.makedirs(INSTALL_PATH, exist_ok=True)
    installed_file = os.path.join(INSTALL_PATH, 'installed.json')
    
    if os.path.exists(installed_file):
        with open(installed_file, 'r') as f:
            installed = json.load(f)
    else:
        installed = {"installed": []}

    # Construir el ID del paquete
    package_id = f"{manifest['author']}@{manifest['name']}"

    # Reemplaza si ya estaba instalado
    installed['installed'] = [p for p in installed['installed'] if f"{p['author']}@{p['name']}" != package_id]
    installed['installed'].append(manifest)

    with open(installed_file, 'w') as f:
        json.dump(installed, f, indent=4)

    writeLog("OK", f"El paquete {package_id} se registró correctamente")
    print(f"Paquete {package_id} registrado correctamente")

def list_all_packages():
    index = get_index()
    print("Paquetes disponibles:")
    for p in index:
        desc = p.get('description', 'Sin descripción')
        package_id = f"{p['author']}@{p['name']}"
        print(f"{package_id}: {desc}")
    print("\n")

def install_package(package_id, version=None):
    installed_file = os.path.join(INSTALL_PATH, 'installed.json')
    if os.path.exists(installed_file):
        writeLog("OK", "La lista de paquetes instalados existe.")
        with open(installed_file, 'r') as f:
            installed = json.load(f).get('installed', [])
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
            writeLog("OK", "Creado exitosamente!")
        os.remove(test_path)

        # Buscar el paquete
        writeLog("INFO", "Buscando paquete en el index...")
        entry = next((p for p in index if p['author'] == author and p['name'] == pkg_name), None)
        if not entry:
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

        # Instalar dependencias
        writeLog("INFO", "Instalando dependencias...")
        if install_dependencies(manifest) != "OK":
            writeLog("ERROR", "Error al instalar dependencias. Abortando instalación.")
            raise Exception("Error al instalar dependencias. Abortando instalación.")

        # Extraer paquete
        writeLog("INFO", "Extrayendo paquete...")
        package_path = extract_package(zip_path, manifest['name'])

        # Ejecutar postinstall si existe
        run_postinstall(manifest, package_path)

        # Registrar el paquete como instalado
        register_package(manifest)

        writeLog("OK", f"El paquete {package_id} se ha instalado correctamente!")
        print(f"Paquete {package_id}@{selected_version['versionName']} instalado con éxito")

    except PermissionError as e:
        writeLog("WARNING", f"KMD no tiene permisos de admin. Error obtenido: {e}. (Relanzando...)")
        # Verificar y ejecutar como admin
        isadmin = run_as_admin()
        if not isadmin:
            writeLog("ERROR", "No se pudo ejecutar KMD con permisos de administrador")
            raise Exception("No se pudo ejecutar KMD con permisos de administrador")

    except Exception as e:
        writeLog("ERROR", f"Error durante la instalación de {package_id}: {e}")
        print(f"Error durante la instalación de {package_id}: {e}")

    finally:
        if zip_path and os.path.exists(zip_path):
            writeLog("INFO", "Eliminando archivos temporales...")
            os.remove(zip_path)

    return "OK"

def uninstall_package(package_id):
    writeLog("INFO", f"Desinstalando {package_id}")

    # Verificar si KMD tiene permisos de admin
    if ctypes.windll.shell32.IsUserAnAdmin() == 1:
        writeLog("OK", "KMD tiene permisos de admin")
    else:
        writeLog("WARNING", "KMD no tiene permisos de admin. Esto podría ocasionar errores.")

    installed_file = os.path.join(INSTALL_PATH, 'installed.json')
    if not os.path.exists(installed_file):
        writeLog("WARNING", "No se encontró el archivo del registro")
        print("No hay paquetes instalados.")
        return
    with open(installed_file, 'r') as f:
        installed_data = json.load(f)
    installed = installed_data['installed']

    writeLog("INFO", "Buscando paquete en el registro...")
    # Buscar paquete por ID
    package = next((p for p in installed if f"{p['author']}@{p['name']}" == package_id), None)
    if not package:
        writeLog("ERROR", f"No se encontró el paquete '{package_id}' en el registro.")
        print(f"No se encontró el paquete con ID '{package_id}' para desinstalar.")
        return

    package_folder = os.path.join(INSTALL_PATH, package['name'])

    # Comprobar si se necesitan permisos de admin para la acción
    try:
        # Archivo temporal
        test_path = os.path.join(package_folder, "__perm_check.tmp")
        with open(test_path, 'w') as f:
            f.write("test")
        os.remove(test_path)

    except PermissionError:
        writeLog("WARNING", "KMD no tiene permisos de admin. Relanzando...")
        # Verificar y ejecutar como admin
        isadmin = run_as_admin()
        if not isadmin:
            writeLog("ERROR", "No se pudo ejecutar KMD con permisos de administrador")
            raise Exception("No se pudo ejecutar KMD con permisos de administrador")

    # Leer manifest para verificar si tiene script de desinstalación
    writeLog("INFO", "Verificando si hay script de desinstalación")
    manifest_path = os.path.join(package_folder, 'manifest.json')
    if os.path.exists(manifest_path):
        with open(manifest_path, 'r') as mf:
            manifest = json.load(mf)
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
    # Borrar carpeta del paquete
    if os.path.exists(package_folder):
        try:
            shutil.rmtree(package_folder)
        except Exception as e:
            print(f"Ha ocurrido un error durante la desisntalación: {e}")

    # Actualizar installed.json
    installed_data['installed'] = [p for p in installed if f"{p['author']}@{p['name']}" != package_id]
    with open(installed_file, 'w') as f:
        json.dump(installed_data, f, indent=4)
    writeLog("OK", f"Paquete '{package_id}' desinstalado.")
    print(f"Paquete '{package['name']}' (ID: {package_id}) desinstalado")

def repair_package(package_id):
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
    installed_file = os.path.join(INSTALL_PATH, 'installed.json')
    if not os.path.exists(installed_file):
        writeLog("ERROR", "No se encotrnó el archivo de registro.")
        print("No hay paquetes instalados para actualizar.")
        return

    with open(installed_file, 'r') as f:
        installed_data = json.load(f)

    installed_list = installed_data.get('installed', [])
    if not installed_list:
        writeLog("ERROR", "No hay paquetes instalados para actualizar.")
        print("ERROR", "No hay paquetes instalados para actualizar.")
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
    installed_file = os.path.join(INSTALL_PATH, 'installed.json')
    if os.path.exists(installed_file):
        with open(installed_file, 'r') as f:
            data = json.load(f)
        return data.get('installed', [])
    return []

def list_installed_packages():
    installed_file = os.path.join(INSTALL_PATH, 'installed.json')
    if not os.path.exists(installed_file):
        writeLog("WARNING", "No se encontró el  del registro")
        print("No hay< paquetes instalados aún.")
        return

    with open(installed_file, 'r') as f:
        installed_data = json.load(f)

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

def get_kmdVersion():
    return f'''KMD Package Manager {KMD_VERSION}
By CeccPro. My GitHub:
https://github.com/ceccpro
Pls follow me. It can help me a lot :)
'''

def get_usage():
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
    '''

def main():
    writeLog("INFO", f"KMD {KMD_VERSION} running.", True)
    parser = argparse.ArgumentParser(description='KMD - Gestor de paquetes')
    parser.add_argument('command', help='Comando: install, search, list-all, uninstall, remove, update, etc (Ejecuta "kmd help" para verlos completos)')
    parser.add_argument('value', nargs='?', help='ID del paquete')
    parser.add_argument('extraArgs', nargs='?', help='Argumentos extra (Si son necesarios)')
    args = parser.parse_args()
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

        else:
            writeLog("ERROR", f"Comando '{args.command} {args.value} {args.extraArgs}' no reconocido. Imprimiendo ayuda")
            print("Uso inválido.", get_usage())
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    main()
    check_log_size()