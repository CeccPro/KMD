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
from tqdm import tqdm


GITHUB_INDEX_URL = f"https://ceccpro.github.io/kmd-db/index.json?cb={int(time.time())}"
INSTALL_PATH = r'C:\Program Files\KMD\packages'

def get_index():
    r = requests.get(GITHUB_INDEX_URL)
    if r.status_code != 200:
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
        raise Exception(f"ID de paquete inválido: {package_id} (se esperaba 'Autor@Paquete')")
    author, name = parts

    index = get_index()

    # Buscar el paquete con ese autor y nombre
    entry = next((p for p in index if p['author'] == author and p['name'] == name), None)
    if not entry:
        raise Exception(f"Paquete {package_id} no encontrado en el índice")

    # Buscar la versión correcta
    version_entry = None
    if version:
        version_entry = next((v for v in entry['versions'] if v['versionName'] == version), None)
        if not version_entry:
            raise Exception(f"Versión '{version}' de {package_id} no encontrada")
    else:
        version_entry = next((v for v in entry['versions'] if v.get('latest')), None)
        if not version_entry:
            raise Exception(f"No se encontró una versión marcada como 'latest' para {package_id}")

    url = version_entry['downloadURL']
    print(f"⬇️ Descargando {package_id} ({version_entry['versionName']}) desde:\n{url}")

    response = requests.get(url, stream=True)
    if response.status_code != 200:
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
    print(f"Hash esperado:   {expected_hash}")
    print(f"Hash calculado:  {computed}")
    return computed == expected_hash

def extract_and_validate_manifest(zip_path):
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        with zip_ref.open('manifest.json') as manifest_file:
            manifest = json.load(manifest_file)

    index = get_index()
    # Buscar paquete por author y name
    index_entry = next((p for p in index if p['author'] == manifest['author'] and p['name'] == manifest['name']), None)
    if not index_entry:
        raise Exception("Paquete no encontrado en el índice al validar manifest")

    # Buscar la versión dentro de las versiones del índice que coincida con manifest['version']
    version_entry = next((v for v in index_entry['versions'] if v.get('versionName', v.get('vName')) == manifest['version']), None)
    if not version_entry:
        raise Exception("Versión no encontrada en el índice para este paquete")

    # Validaciones básicas
    if manifest['description'] != index_entry.get('description', ''):
        raise Exception("La descripción del manifest y el índice no coinciden")

    return manifest

def install_dependencies(manifest):
    for dep in manifest.get('dependencies', []):
        print(f"Instalando dependencia: {dep}")
        installCode = install_package(dep)
        if installCode == "OK":
            continue
        else:
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
            print(f"Ejecutando postInstall: {script}")
            try:
                subprocess.run([script_path], shell=True, check=True)
            except subprocess.CalledProcessError:
                print(f"Error al ejecutar el script {script}")
        else:
            print(f"Script {script} no encontrado en {package_path}")

def run_uninstall(manifest, package_path):
    script = manifest.get('uninstallScript')
    if script:
        script_path = os.path.join(package_path, script)
        if os.path.exists(script_path):
            print(f"Ejecutando postInstall: {script}")
            try:
                subprocess.run([script_path], shell=True, check=True)
            except subprocess.CalledProcessError:
                print(f"Error al ejecutar el script {script}")
        else:
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
        with open(installed_file, 'r') as f:
            installed = json.load(f).get('installed', [])
            if any(f"{p['author']}@{p['name']}" == package_id for p in installed):
                print(f"El paquete {package_id} ya está instalado. Omitiendo instalación.")
                return "OK"

    zip_path = None
    try:
        author, pkg_name = package_id.split('@')
        index = get_index()

        # Buscar el paquete
        entry = next((p for p in index if p['author'] == author and p['name'] == pkg_name), None)
        if not entry:
            raise Exception(f"Paquete {package_id} no encontrado en el índice")

        # Elegir versión según el parámetro
        if version:
            selected_version = next((v for v in entry['versions'] if v['versionName'] == version), None)
            if not selected_version:
                raise Exception(f"La versión '{version}' de {package_id} no existe.")
        else:
            selected_version = next((v for v in entry['versions'] if v.get('latest', False)), None)
            if not selected_version:
                raise Exception(f"No se encontró versión 'latest' para {package_id}")

        # Descargar paquete (usa el parámetro version, aunque sea None)
        zip_path, _ = download_package(package_id, version)

        # Validar hash contra la versión correcta
        if not verify_hash(zip_path, selected_version['hash']):
            print("El hash no coincide con el esperado.")
            userInput = input("¿Deseas continuar con la instalación? (S/N) > ")
            if userInput.lower() not in ["s", "y"]:
                raise Exception("Hash del paquete no coincide, abortando instalación.")

        # Extraer y validar manifest
        manifest = extract_and_validate_manifest(zip_path)

        # Instalar dependencias
        if install_dependencies(manifest) != "OK":
            raise Exception("Error al instalar dependencias. Abortando instalación.")

        # Extraer paquete
        package_path = extract_package(zip_path, manifest['name'])

        # Ejecutar postinstall si existe
        run_postinstall(manifest, package_path)

        # Registrar el paquete como instalado
        register_package(manifest)

        print(f"Paquete {package_id}@{selected_version['versionName']} instalado con éxito")

    except Exception as e:
        print(f"Error durante la instalación de {package_id}: {e}")

    finally:
        if zip_path and os.path.exists(zip_path):
            os.remove(zip_path)

    return "OK"

def uninstall_package(package_id):
    installed_file = os.path.join(INSTALL_PATH, 'installed.json')
    if not os.path.exists(installed_file):
        print("No hay paquetes instalados.")
        return
    with open(installed_file, 'r') as f:
        installed_data = json.load(f)
    installed = installed_data['installed']
    # Buscar paquete por Author@Name (si cambiaste formato)
    package = next((p for p in installed if f"{p['author']}@{p['name']}" == package_id), None)
    if not package:
        print(f"No se encontró el paquete con ID '{package_id}' para desinstalar.")
        return
    package_folder = os.path.join(INSTALL_PATH, package['name'])
    # Leer manifest para verificar si tiene script de desinstalación
    manifest_path = os.path.join(package_folder, 'manifest.json')
    if os.path.exists(manifest_path):
        with open(manifest_path, 'r') as mf:
            manifest = json.load(mf)
        if 'uninstallScript' in manifest and manifest['uninstallScript'].strip():
            print(f"Ejecutando script de desinstalación: {manifest['uninstallScript']}")
            try:
                run_uninstall(manifest, package_folder)
            except Exception as e:
                print(f"Error al ejecutar script de desinstalación: {e}")
    # Borrar carpeta del paquete
    if os.path.exists(package_folder):
        shutil.rmtree(package_folder)
    # Actualizar installed.json
    installed_data['installed'] = [p for p in installed if f"{p['author']}@{p['name']}" != package_id]
    with open(installed_file, 'w') as f:
        json.dump(installed_data, f, indent=4)
    print(f"Paquete '{package['name']}' (ID: {package_id}) desinstalado.")

def update_package(package_id):
    index = get_index()

    # Validación del formato author@pkgName
    if '@' not in package_id:
        print(f"Formato inválido de package_id: {package_id}")
        return

    author, pkg_name = package_id.split('@', 1)

    # Buscar en el índice
    base_pkg = next((p for p in index if p['author'] == author and p['name'] == pkg_name), None)
    if not base_pkg:
        print(f"No se encontró el paquete {package_id} en el índice.")
        return

    # Buscar paquete instalado (usamos author y name)
    installed = get_installed_packages()
    installed_pkg = next((p for p in installed if p['author'] == author and p['name'] == pkg_name), None)

    # Obtener versión más reciente
    latest_version = next((v for v in base_pkg['versions'] if v.get('latest', False)), None)
    if not latest_version:
        print(f"No se encontró versión marcada como 'latest' para {package_id}")
        return

    latest_version_name = latest_version.get('versionName', latest_version.get('vName', ''))

    if installed_pkg:
        current_version = installed_pkg.get('version', '')
        if current_version == latest_version_name:
            print(f"{package_id} ya está actualizado a la versión {current_version}.")
            return
        else:
            print(f"Actualizando {package_id} de {current_version} a {latest_version_name}...")
            uninstall_package(package_id)
    else:
        print(f"{package_id} no está instalado, instalando versión {latest_version_name}...")

    install_package(package_id)
    print(f"Paquete {package_id} actualizado a {latest_version_name}.")

def update_all_packages():
    installed_file = os.path.join(INSTALL_PATH, 'installed.json')
    if not os.path.exists(installed_file):
        print("No hay paquetes instalados para actualizar.")
        return

    with open(installed_file, 'r') as f:
        installed_data = json.load(f)

    installed_list = installed_data.get('installed', [])
    if not installed_list:
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
            print(f"No se encontró el paquete {package_id} en el índice, saltando...")
            continue

        # Buscar la versión latest
        latest_version_entry = next((v for v in base_pkg['versions'] if v.get('latest')), None)
        if not latest_version_entry:
            print(f"No hay versión 'latest' para {package_id}, saltando...")
            continue

        latest_version_name = latest_version_entry.get('versionName')
        if current_version != latest_version_name:
            print(f"Actualizando {package_id} de {current_version} a {latest_version_name}...")
            uninstall_package(package_id)  # Asume que uninstall_package ahora solo usa author@name
            install_package(package_id)
            updated_any = True
        else:
            print(f"{package_id} ya está en la última versión ({current_version}).")

    if not updated_any:
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
        print("No hay paquetes instalados aún.")
        return

    with open(installed_file, 'r') as f:
        installed_data = json.load(f)

    installed = installed_data.get('installed', [])
    if not installed:
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
        print("El ID del paquete debe tener el formato 'Autor@Nombre'")
        return

    index = get_index()
    entry = next((p for p in index if p['author'] == author and p['name'] == name), None)

    if not entry:
        print(f"No se encontró el paquete {package_id} en el índice.")
        return

    print(f"Versiones disponibles para {package_id}:")
    for v in entry['versions']:
        tag = " (latest)" if v.get('latest') else ""
        print(f"- {v['versionName']}{tag}")

def get_usage():
    return '''Comandos disponibles:
    install [ID] [Versión]  - Instala un paquete
    search [nombre]         - Busca paquetes
    list-versions [ID]      - Lista las versiones disponibles de un paquete
    list-all                - Lista todos los paquetes
    uninstall [nombre]      - Desinstala un paquete
    remove [nombre]         - Alias para uninstall
    update-all              - Actualiza todos los paquetes
    update [ID]             - Actualiza un paquete
    list-installed          - Lista todos los paquetes instalados
    help                    - Muestra este dialogo de ayuda
    '''

def main():
    parser = argparse.ArgumentParser(description='KMD - Gestor de paquetes')
    parser.add_argument('command', help='Comando: install, search, list-all, uninstall, remove, update')
    parser.add_argument('value', nargs='?', help='Valor para el comando (ID o nombre del paquete)')
    parser.add_argument('extraArgs', nargs='?', help='Argumentos secundarios')
    args = parser.parse_args()
    try:
        if args.command == 'install' and args.value and args.extraArgs:
            install_package(args.value, args.extraArgs)
        elif args.command == 'install' and args.value:
            install_package(args.value)
        elif args.command == 'search' and args.value:
            search_packages(args.value)
        elif args.command == 'list-all':
            list_all_packages()
        elif args.command == 'list-installed':
            list_installed_packages()
        elif args.command in ['uninstall', 'remove'] and args.value:
            uninstall_package(args.value)
        elif args.command == 'update' and args.value:
            update_package(args.value)
        elif args.command == 'update-all':
            update_all_packages()
        elif args.command == 'list-versions' and args.value:
            list_package_versions(args.value)
        elif args.command in ['help', '-h', '--help']:
            print(get_usage())
        else:
            print("Uso inválido.", get_usage())
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    main()