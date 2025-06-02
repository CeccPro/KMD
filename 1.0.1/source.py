import os
import hashlib
import requests
import zipfile
import json
import tempfile
import subprocess
import shutil
import argparse
import time

# === CONFIG ===
GITHUB_INDEX_URL = f"https://ceccpro.github.io/kmd-db/index.json?nocache={time.time()}"
INSTALL_PATH = r'C:\Program Files\KMD\packages'

def get_index():
    r = requests.get(GITHUB_INDEX_URL)
    if r.status_code != 200:
        raise Exception("No se pudo obtener el índice de paquetes")
    return r.json()

def download_package(package_id):
    index = get_index()
    entry = next((p for p in index if p['id'] == package_id), None)
    if not entry:
        raise Exception(f"Paquete {package_id} no encontrado en el índice")

    url = entry['downloadURL']
    print(f"Descargando {package_id} de {url}")
    r = requests.get(url)
    if r.status_code != 200:
        raise Exception("Error al descargar el paquete")

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
    temp_file.write(r.content)
    temp_file.close()
    return temp_file.name, entry

def search_packages(query):
    index = get_index()
    query_lower = query.lower()
    
    # Buscar coincidencias parciales en el nombre
    matches = [p for p in index if query_lower in p['name'].lower()]
    
    if not matches:
        print(f"No se encontraron paquetes que coincidan con '{query}'")
        return []
    
    print(f"Coincidencias encontradas para '{query}':\n")
    for p in matches:
        desc = p.get('description', 'Sin descripción')
        print(f"{p['id']}: {desc}")
    
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
    index_entry = next((p for p in index if p['id'] == manifest['id']), None)
    if not index_entry:
        raise Exception("Paquete no encontrado en el índice al validar manifest")

    # Validaciones básicas
    if (manifest['name'] != index_entry['name'] or
        manifest['version'] != index_entry['version'] or
        manifest['id'] != index_entry['id']):
        raise Exception("El manifest y el índice no coinciden")

    return manifest

def install_dependencies(manifest):
    for dep in manifest.get('dependencies', []):
        print(f"Instalando dependencia: {dep}")
        install_package(dep)

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

def register_package(manifest):
    os.makedirs(INSTALL_PATH, exist_ok=True)
    installed_file = os.path.join(INSTALL_PATH, 'installed.json')
    if os.path.exists(installed_file):
        with open(installed_file, 'r') as f:
            installed = json.load(f)
    else:
        installed = {"installed": []}

    # Reemplaza si ya estaba instalado
    installed['installed'] = [p for p in installed['installed'] if p['id'] != manifest['id']]
    installed['installed'].append(manifest)

    with open(installed_file, 'w') as f:
        json.dump(installed, f, indent=4)
    print(f"Paquete {manifest['id']} registrado correctamente")

def list_all_packages():
    index = get_index()
    print("Paquetes disponibles:\n")
    for p in index:
        desc = p.get('description', 'Sin descripción')
        print(f"{p['id']}: {desc}")

def install_package(package_id):
    # Verificar si ya está instalado
    installed_file = os.path.join(INSTALL_PATH, 'installed.json')
    if os.path.exists(installed_file):
        with open(installed_file, 'r') as f:
            installed = json.load(f).get('installed', [])
            if any(p['id'] == package_id for p in installed):
                print(f"El paquete {package_id} ya está instalado. Omitiendo instalación.")
                return

    try:
        # Descargar y validar
        zip_path, index_entry = download_package(package_id)
        if not verify_hash(zip_path, index_entry['hash']):
            raise Exception("Hash del paquete no coincide, abortando instalación")

        manifest = extract_and_validate_manifest(zip_path)

        # 1. Instalar dependencias primero
        install_dependencies(manifest)

        # 2. Extraer el paquete
        package_path = extract_package(zip_path, manifest['name'])

        # 3. Ejecutar script post instalación si hay
        run_postinstall(manifest, package_path)

        # 4. Registrar en installed.json
        register_package(manifest)

        print(f"Paquete {package_id} instalado con éxito")

    except Exception as e:
        print(f"Error durante la instalación de {package_id}: {e}")

    finally:
        if zip_path and os.path.exists(zip_path):
            os.remove(zip_path)

    # Verificar si ya está instalado
    installed_file = os.path.join(INSTALL_PATH, 'installed.json')
    if os.path.exists(installed_file):
        with open(installed_file, 'r') as f:
            installed = json.load(f).get('installed', [])
            if any(p['id'] == package_id for p in installed):
                print(f"El paquete {package_id} ya está instalado. Omitiendo instalación.")
                return

    # Descargar y validar
    zip_path, index_entry = download_package(package_id)
    if not verify_hash(zip_path, index_entry['hash']):
        raise Exception("Hash del paquete no coincide, abortando instalación")

    manifest = extract_and_validate_manifest(zip_path)
    install_dependencies(manifest)

    # Extraer y ejecutar postinstall
    dest_path = os.path.join(INSTALL_PATH, manifest['name'])
    os.makedirs(dest_path, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(dest_path)

    run_postinstall(manifest, dest_path)
    register_package(manifest)
    os.remove(zip_path)

    print(f"Paquete {package_id} instalado con éxito")
    print(f"\n===== Instalando {package_id} =====")
    zip_path = None
    try:
        zip_path, index_entry = download_package(package_id)
        if not verify_hash(zip_path, index_entry['hash']):
            raise Exception("Hash del paquete no coincide, abortando instalación")

        manifest = extract_and_validate_manifest(zip_path)

        # 1. Instalar dependencias primero
        install_dependencies(manifest)

        # 2. Extraer el paquete
        package_path = extract_package(zip_path, manifest['name'])

        # 3. Ejecutar script post instalación si hay
        run_postinstall(manifest, package_path)

        # 4. Registrar en installed.json
        register_package(manifest)

        print(f"Paquete {package_id} instalado con éxito")

    except Exception as e:
        print(f"Error durante la instalación de {package_id}: {e}")

    finally:
        if zip_path and os.path.exists(zip_path):
            os.remove(zip_path)

def uninstall_package(package_id):
    installed_file = os.path.join(INSTALL_PATH, 'installed.json')
    if not os.path.exists(installed_file):
        print("No hay paquetes instalados.")
        return

    with open(installed_file, 'r') as f:
        installed_data = json.load(f)

    installed = installed_data['installed']
    package = next((p for p in installed if p['id'] == package_id), None)

    if not package:
        print(f"No se encontró el paquete con ID '{package_id}' para desinstalar.")
        return

    # Borrar carpeta del paquete
    package_folder = os.path.join(INSTALL_PATH, package['name'])
    if os.path.exists(package_folder):
        import shutil
        shutil.rmtree(package_folder)

    # Borrar del JSON
    installed_data['installed'] = [p for p in installed if p['id'] != package_id]
    with open(installed_file, 'w') as f:
        json.dump(installed_data, f, indent=4)

    print(f"Paquete '{package['name']}' (ID: {package_id}) desinstalado.")


def update_package(package_id):
    index = get_index()
    # Sacar la parte base del paquete (autor.paquete)
    base_name = package_id.split('@')[0]  # Ejemplo: 'CeccPro.testApp'
    
    # Buscar todas las versiones del paquete base en el índice
    versions = [p for p in index if p['id'].startswith(base_name + '@')]
    if not versions:
        print(f"No se encontraron versiones para {base_name}")
        return
    
    # Ordenar versiones (asumiendo que la última es la más reciente)
    # Aquí puedes mejorar el ordenamiento si usas semver, pero asumo orden lexicográfico simple
    versions.sort(key=lambda p: p['version'])
    latest = versions[-1]
    latest_id = latest['id']
    
    if latest_id == package_id:
        print(f"Ya tienes la última versión instalada: {latest_id}")
        return
    
    # Revisar si el paquete está instalado (por ID)
    installed = get_installed_packages()
    if package_id not in [p['id'] for p in installed]:
        print(f"El paquete {package_id} no está instalado, instalando la última versión {latest_id} directamente.")
        install_package(latest_id)
        return
    
    # Desinstalar la versión actual
    uninstall_package(package_id)
    
    # Instalar la versión más reciente
    install_package(latest_id)

    installed_file = os.path.join(INSTALL_PATH, 'installed.json')
    if not os.path.exists(installed_file):
        print("No hay paquetes instalados para actualizar.")
        return
    
    with open(installed_file, 'r') as f:
        installed = json.load(f).get('installed', [])
    
    pkg = next((p for p in installed if p['id'] == package_id), None)
    if not pkg:
        print(f"El paquete {package_id} no está instalado.")
        return
    
    print(f"Actualizando paquete {package_id}...")
    try:
        install_package(package_id)
    except Exception as e:
        print(f"Error actualizando {package_id}: {e}")

def update_all_packages():
    installed_file = os.path.join(INSTALL_PATH, 'installed.json')
    if not os.path.exists(installed_file):
        print("No hay paquetes instalados para actualizar.")
        return

    with open(installed_file, 'r') as f:
        installed = json.load(f)

    index = get_index()
    updated_any = False

    for pkg in installed.get('installed', []):
        pkg_base_id = pkg['id'].split('@')[0]  # 'Autor.Paquete'
        # Buscar todas las versiones del paquete en el índice
        versions = [p for p in index if p['id'].startswith(pkg_base_id + '@')]
        if not versions:
            print(f"No se encontró el paquete {pkg_base_id} en el índice, saltando...")
            continue

        # Ordenar por versión (asumiendo que la versión es tipo semver o similar)
        versions.sort(key=lambda p: p['version'])
        latest = versions[-1]['id']

        if pkg['id'] != latest:
            print(f"Actualizando {pkg['id']} a {latest}...")
            uninstall_package(pkg['id'])
            install_package(latest)
            updated_any = True
        else:
            print(f"{pkg['id']} ya está en la última versión.")

    if not updated_any:
        print("Todos los paquetes ya están actualizados.")

    installed = get_installed_packages()
    if not installed:
        print("No hay paquetes instalados para actualizar.")
        return
    
    for pkg in installed:
        current_id = pkg['id']
        print(f"Actualizando {current_id}...")
        try:
            update_package(current_id)
        except Exception as e:
            print(f"Error al actualizar {current_id}: {e}")

    installed_file = os.path.join(INSTALL_PATH, 'installed.json')
    if not os.path.exists(installed_file):
        print("No hay paquetes instalados para actualizar.")
        return
    
    with open(installed_file, 'r') as f:
        installed = json.load(f).get('installed', [])
    
    if not installed:
        print("No hay paquetes instalados para actualizar.")
        return
    
    for pkg in installed:
        print(f"Actualizando {pkg['id']}...")
        try:
            install_package(pkg['id'])
        except Exception as e:
            print(f"Error actualizando {pkg['id']}: {e}")
    index = get_index()
    installed_file = os.path.join(INSTALL_PATH, 'installed.json')
    
    if not os.path.exists(installed_file):
        print("No hay paquetes instalados.")
        return

    with open(installed_file, 'r') as f:
        installed = json.load(f)['installed']
    
    for pkg in installed:
        name = pkg['name']
        # Buscar la versión más reciente del mismo paquete
        available = [p for p in index if p['name'] == name]
        if not available:
            print(f"No se encontró el paquete '{name}' en el índice.")
            continue
        
        latest = sorted(available, key=lambda x: x['version'], reverse=True)[0]
        if latest['version'] != pkg['version']:
            print(f"Actualizando {name} de v{pkg['version']} a v{latest['version']}")
            install_package(latest['id'])
        else:
            print(f"{name} ya está en la última versión ({pkg['version']})")    

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
        installed = json.load(f)
    
    if not installed.get('installed'):
        print("No hay paquetes instalados aún.")
        return
    
    print("Paquetes instalados:")
    for pkg in installed['installed']:
        print(f"- {pkg['id']}: {pkg.get('description', 'Sin descripción')}")

def get_usage():
    return '''Comandos disponibles:
    install [ID]       - Instala un paquete
    search [nombre]    - Busca paquetes
    list-all           - Lista todos los paquetes
    uninstall [nombre] - Desinstala un paquete
    remove [nombre]    - Alias para uninstall
    update-all         - Actualiza todos los paquetes
    update [ID]        - Actualiza un paquete
    list-installed     - Lista todos los paquetes instalados
    help               - Muestra este dialogo de ayuda
    '''


# === Ejemplo de uso ===
if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='KMD - Gestor de paquetes')
    parser.add_argument('command', help='Comando: install, search, list-all, uninstall, remove, update')
    parser.add_argument('value', nargs='?', help='Valor para el comando (ID o nombre del paquete)')
    args = parser.parse_args()

    try:
        if args.command == 'install' and args.value:
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
        elif args.command in ['help', '-h', '--help']:
            print(get_usage())
        else:
            print("Uso inválido.", get_usage())
    except Exception as e:
        print(f"Error: {e}")
